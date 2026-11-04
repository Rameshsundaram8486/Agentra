"""Business rules for design reviews; the only entry point for other modules.

A review (from the Security Reviewer or Developer agent) becomes a new version of the project's Security review or
Feasibility review document plus an immutable set of findings, tied to the exact design version it reviews.
Rules enforced here, not by the agents:
- Only the current, non-stale version of an agent-drafted design can be reviewed.
- A security review answers every check in config/policies/security_checklist.yaml exactly once; a feasibility
  review rates every design item except open questions exactly once (app/modules/design_reviews/rules.py).
- A security review with a high-severity gap cannot be approved, nor one of a design version that is no longer
  current. Its approval by a reviewer is the security sign-off and accepts its medium and low gaps.
- A design version can be approved only with an approved security review of that exact version and a feasibility
  review of that version with nothing rated not feasible (design_problems, wired as an approval check and as the
  Phase 8 exit check design_reviews).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.artifacts.service import ArtifactCreate, ArtifactsService, VersionCreate, VersionRecord
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.design.service import DesignService, DesignView
from app.modules.design_reviews import repository
from app.modules.design_reviews.checklist import SecurityChecklist
from app.modules.design_reviews.models import DesignReview, DesignReviewFinding
from app.modules.design_reviews.rendering import render_review
from app.modules.design_reviews.rules import feasibility_problems, security_problems
from app.modules.design_reviews.schemas import (
    OPEN_VERDICTS,
    REVIEW_TYPES,
    DesignReviewsView,
    FindingDraft,
    FindingView,
    OpenFinding,
    ReviewDraft,
    ReviewKind,
    ReviewReply,
    ReviewView,
)
from app.modules.errors import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.requirements.service import RequirementsService

__all__ = ["REVIEW_TYPES", "DesignReviewsService", "DesignReviewsView", "FindingDraft", "OpenFinding", "ReviewDraft", "ReviewReply", "ReviewView"]


class DesignReviewsService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        artifacts: ArtifactsService,
        decisions: DecisionsService,
        projects: ProjectsService,
        requirements: RequirementsService,
        design: DesignService,
        checklist: SecurityChecklist,
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._decisions = decisions
        self._projects = projects
        self._requirements = requirements
        self._design = design
        self._checklist = checklist

    # For agent tasks and other modules ------------------------------------------------------------

    def review_target(self, project_id: uuid.UUID, design_version_id: uuid.UUID) -> DesignView:
        """The design version a review would be of, if it may be reviewed now."""
        design = self._design.version_view(design_version_id)
        if design is None or self._artifacts.version_record(design_version_id).project_id != project_id:
            raise ValidationFailedError("Only a design drafted by the Solution Architect agent can be reviewed")
        current = self._design.current_version_id(project_id)
        if design_version_id != current:
            raise InvalidTransitionError(f"Design v{design.version_no} is no longer the current version; review the current one")
        if design.stale_reason:
            raise InvalidTransitionError(design.stale_reason)
        return design

    def content_problems(self, kind: ReviewKind, findings: list[FindingDraft], design: DesignView) -> list[tuple[str, str]]:
        """What is wrong with a set of findings for this design version (shared with the agent tasks' checks)."""
        requirement_ids = {item.item_id for item in self._requirements.items_of_version(self._requirements_version_id(design))}
        if kind == "security":
            checks = {key: check.title for key, check in self._checklist.checks.items()}
            return security_problems(findings, checks, {item.item_id for item in design.items}, requirement_ids)
        return feasibility_problems(findings, {item.item_id: item.kind for item in design.items}, requirement_ids)

    def design_problems(self, design_version_id: uuid.UUID) -> list[str]:
        """What stops this design version from being approved, as far as reviews go. A design document written
        by hand is not reviewed here (it cannot pass the Phase 8 coverage check either)."""
        design = self._design.version_view(design_version_id)
        if design is None:
            return []
        problems = []
        security = repository.latest_for_design(self._session, design_version_id, "security")
        if security is None:
            problems.append(f"Design v{design.version_no} has no security review yet; ask the Security Reviewer agent")
        else:
            record = self._artifacts.version_record(security.artifact_version_id)
            if high := self._high_gaps(security.artifact_version_id):
                problems.append(f"Security review v{record.version_no} of design v{design.version_no} has high-severity gaps: {', '.join(high)}")
            elif self._decisions.approval_statuses([record.id])[record.id] != "approved":
                problems.append(f"Security review v{record.version_no} of design v{design.version_no} is not signed off (approved) yet")
        feasibility = repository.latest_for_design(self._session, design_version_id, "feasibility")
        if feasibility is None:
            problems.append(f"Design v{design.version_no} has no feasibility review yet; ask the Developer agent")
        elif blocked := [f.ref for f in repository.findings_for(self._session, feasibility.artifact_version_id) if f.verdict == "not_feasible"]:
            version_no = self._artifacts.version_record(feasibility.artifact_version_id).version_no
            problems.append(f"Feasibility review v{version_no} of design v{design.version_no} rates items not feasible: {', '.join(blocked)}")
        return problems

    def findings_for_design(self, design_version_id: uuid.UUID, kind: ReviewKind) -> list[FindingView]:
        """The findings of the latest review of this kind of one design version (none if it was not reviewed)."""
        review = repository.latest_for_design(self._session, design_version_id, kind)
        return self._view(review.artifact_version_id).findings if review else []

    def gate_failures(self, project_id: uuid.UUID) -> list[str]:
        """Phase exit check design_reviews: the current design passes the review gate."""
        current = self._design.current_version_id(project_id)
        return self.design_problems(current) if current else []

    def security_approval_problems(self, review_version_id: uuid.UUID) -> list[str]:
        """Checked before a security review version is approved (signed off)."""
        review = repository.review_for(self._session, review_version_id)
        if review is None:
            return []  # a review document written by hand; it does not count towards the gate
        problems = []
        design = self._design.version_view(review.design_version_id)
        current = self._design.current_version_id(review.project_id)
        if design is None or review.design_version_id != current:
            problems.append(f"This review is of design v{design.version_no if design else '?'}, which is no longer the current design")
        elif design.stale_reason:
            problems.append(design.stale_reason)
        if high := self._high_gaps(review_version_id):
            problems.append(f"It has high-severity gaps ({', '.join(high)}); have the Solution Architect redraft the design and review it again")
        return problems

    def open_findings(self, project_id: uuid.UUID, review_version_ids: Iterable[uuid.UUID]) -> list[OpenFinding]:
        """Gaps and concerns in these review versions that the next design draft must answer. Only reviews of the
        current design version count; findings on older versions were answered by the draft that replaced them."""
        current = self._design.current_version_id(project_id)
        found = []
        for version_id in review_version_ids:
            review = repository.review_for(self._session, version_id)
            if review is None or review.project_id != project_id or review.design_version_id != current:
                continue
            review_no = self._artifacts.version_record(version_id).version_no
            design_no = self._artifacts.version_record(review.design_version_id).version_no
            found += [
                OpenFinding(
                    kind=review.kind,  # type: ignore[arg-type]
                    review_version_no=review_no,
                    design_version_no=design_no,
                    ref=f.ref,
                    title=f.title,
                    verdict=f.verdict,
                    severity=f.severity,  # type: ignore[arg-type]
                    assessment=f.assessment,
                    recommendation=f.recommendation,
                )
                for f in repository.findings_for(self._session, version_id)
                if f.verdict in OPEN_VERDICTS[review.kind]
            ]
        return found

    # Commands ----------------------------------------------------------------------------------------

    def record_review(self, actor: Actor, project_id: uuid.UUID, draft: ReviewDraft) -> ReviewView:
        self._identity.require_project(actor, project_id, "artifact.author")
        draft = ReviewDraft.model_validate(draft)
        design = self.review_target(project_id, draft.design_version_id)
        if problems := self.content_problems(draft.kind, draft.findings, design):
            raise ValidationFailedError("; ".join(f"{path}: {message}" for path, message in problems[:20]))

        titles = {key: check.title for key, check in self._checklist.checks.items()} if draft.kind == "security" else {i.item_id: i.title for i in design.items}
        findings = [
            FindingView(
                ref=f.ref,
                title=titles[f.ref],
                verdict=f.verdict,
                severity=f.severity,
                complexity=f.complexity,
                assessment=f.assessment.strip(),
                recommendation=f.recommendation.strip(),
                design_items=list(dict.fromkeys(f.design_items)),
                requirements=list(dict.fromkeys(f.requirements)),
                unverified=[u.strip() for u in f.unverified if u.strip()],
            )
            for f in draft.findings
        ]
        checklist = self._checklist.label if draft.kind == "security" else None
        project = self._projects.get_project(actor, project_id)
        design_record = self._artifacts.version_record(design.version_id)
        content = render_review(
            kind=draft.kind,
            project_name=project.name,
            design_label=f"{design_record.artifact_title} v{design.version_no} (sha256 {design_record.content_sha256[:12]})",
            checklist=checklist,
            summary=draft.summary,
            findings=findings,
            review_responses=draft.review_responses,
        )
        artifact_type, title = REVIEW_TYPES[draft.kind]
        source_refs = [f"{design_record.artifact_title} v{design.version_no}"] + ([checklist] if checklist else [])
        previous = self._record(project_id, draft.kind)
        if previous is None:
            detail = self._artifacts.create_artifact(
                actor, project_id, ArtifactCreate(artifact_type=artifact_type, title=title, content=content, change_summary=draft.change_summary, source_refs=source_refs)
            )
        else:
            detail = self._artifacts.add_version(
                actor,
                previous.artifact_id,
                VersionCreate(content=content, change_summary=draft.change_summary, source_refs=source_refs, expected_current_version=previous.version_no),
            )
        version = detail.current_version
        now = self._clock.now()
        repository.add(
            self._session,
            DesignReview(
                project_id=project_id,
                kind=draft.kind,
                artifact_id=detail.id,
                artifact_version_id=version.id,
                design_version_id=design.version_id,
                checklist=checklist,
                summary=draft.summary.strip(),
                review_responses=[r.model_dump(mode="json") for r in draft.review_responses],
                created_at=now,
            ),
        )
        for position, f in enumerate(findings):
            self._session.add(DesignReviewFinding(review_version_id=version.id, position=position, created_at=now, **f.model_dump()))
        self._session.flush()
        view = self._view(version.id)
        self._audit.record(
            actor_id=actor.id,
            action="design_review.record",
            entity_type="artifact_version",
            entity_id=version.id,
            project_id=project_id,
            after={"kind": draft.kind, "version_no": view.version_no, "design_version_no": design.version_no, "counts": view.counts, "checklist": checklist},
        )
        return view

    # Reads -------------------------------------------------------------------------------------------

    def view(self, actor: Actor, project_id: uuid.UUID) -> DesignReviewsView:
        self._identity.require_project(actor, project_id, "artifact.view")
        current = self._design.current_version_id(project_id)
        reviews = {}
        for kind in REVIEW_TYPES:
            record = self._record(project_id, kind)
            reviews[kind] = self._view(record.id) if record and repository.review_for(self._session, record.id) else None
        return DesignReviewsView(
            design_version_id=current,
            design_version_no=self._artifacts.version_record(current).version_no if current else None,
            security=reviews["security"],
            feasibility=reviews["feasibility"],
            gate=self.design_problems(current) if current else [],
        )

    # Helpers -----------------------------------------------------------------------------------------

    def _record(self, project_id: uuid.UUID, kind: str) -> VersionRecord | None:
        artifact_type, title = REVIEW_TYPES[kind]
        records = [r for r in self._artifacts.current_records_of_type(project_id, artifact_type) if r.artifact_title == title]
        return records[0] if records else None

    def _requirements_version_id(self, design: DesignView) -> uuid.UUID:
        version = self._design.requirements_version_of(design.version_id)
        if version is None:
            raise NotFoundError("No drafted design for this version")
        return version

    def _high_gaps(self, review_version_id: uuid.UUID) -> list[str]:
        return [f.ref for f in repository.findings_for(self._session, review_version_id) if f.verdict == "gap" and f.severity == "high"]

    def _view(self, review_version_id: uuid.UUID) -> ReviewView:
        review = repository.review_for(self._session, review_version_id)
        if review is None:
            raise NotFoundError("No review for this version")
        record = self._artifacts.version_record(review_version_id)
        findings = [
            FindingView(
                ref=f.ref,
                title=f.title,
                verdict=f.verdict,
                severity=f.severity,  # type: ignore[arg-type]
                complexity=f.complexity,  # type: ignore[arg-type]
                assessment=f.assessment,
                recommendation=f.recommendation,
                design_items=f.design_items,
                requirements=f.requirements,
                unverified=f.unverified,
            )
            for f in repository.findings_for(self._session, review_version_id)
        ]
        counts: dict[str, int] = {}
        for finding in findings:
            counts[finding.verdict] = counts.get(finding.verdict, 0) + 1
        current = self._design.current_version_id(review.project_id)
        design = self._design.version_view(review.design_version_id)
        is_current = review.design_version_id == current and design is not None and not design.stale
        blocking = []
        if review.kind == "security" and (high := [f.ref for f in findings if f.verdict == "gap" and f.severity == "high"]):
            blocking.append(f"High-severity gaps: {', '.join(high)}")
        if review.kind == "feasibility" and (blocked := [f.ref for f in findings if f.verdict == "not_feasible"]):
            blocking.append(f"Rated not feasible: {', '.join(blocked)}")
        return ReviewView(
            kind=review.kind,  # type: ignore[arg-type]
            artifact_id=review.artifact_id,
            artifact_title=record.artifact_title,
            version_id=review_version_id,
            version_no=record.version_no,
            approval_status=self._decisions.approval_statuses([review_version_id])[review_version_id],
            design_version_id=review.design_version_id,
            design_version_no=design.version_no if design else self._artifacts.version_record(review.design_version_id).version_no,
            current=is_current,
            checklist=review.checklist,
            summary=review.summary,
            counts=counts,
            blocking=blocking,
            findings=findings,
            review_responses=[ReviewReply.model_validate(r) for r in review.review_responses],
            created_at=review.created_at,
        )
