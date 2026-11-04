"""Business rules for the solution design; the only entry point for other modules.

A draft (from the Solution Architect agent) becomes a new version of the project's design baseline document plus
an immutable set of design items, tied to the approved requirements version it was designed against. Rules
enforced here, not by the agent:
- Design item IDs are assigned by the server and never reused; a draft keeps an ID only by referring to it.
- Every requirement ID a design item claims to satisfy, and every exception, must exist in that requirements
  version; a draft against anything but the current approved requirements is refused.
- Status is derived as for requirements: confirmed only for a fact with no unanswered decision behind it.
- Coverage: every confirmed requirement must be covered by a design item or have a documented exception.
  Phase 8 cannot complete otherwise (exit check design_coverage).
- A design becomes stale when the approved requirements it was designed against are no longer the current
  approved requirements (for example after a change request). A stale design cannot be approved.
- An approved design is under change control; changing it arrives with Increment 4b.
"""

import re
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.artifacts.service import ArtifactCreate, ArtifactsService, VersionCreate, VersionRecord
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.design import repository
from app.modules.design.models import DesignId, DesignItem, DesignVersion
from app.modules.design.quality_checks import CheckedItem, check_items
from app.modules.design.rendering import render_design
from app.modules.design.schemas import (
    PREFIXES,
    Coverage,
    CoverageRow,
    DesignDraft,
    DesignDraftItem,
    DesignItemView,
    DesignSource,
    DesignView,
    DraftResult,
    QualityFlag,
    RequirementException,
    ReviewResponse,
    Status,
)
from app.modules.errors import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.requirements.service import RequirementsService

__all__ = [
    "DESIGN_TITLE",
    "DESIGN_TYPE",
    "DesignDraft",
    "DesignDraftItem",
    "DesignService",
    "DesignSource",
    "DesignView",
    "RequirementException",
    "ReviewResponse",
]

DESIGN_TYPE = "design_baseline"
DESIGN_TITLE = "Solution design"
COVERED_KINDS = ("functional", "non_functional", "business_rule")
_ID = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<number>\d{3,})$")
_NEW_REF_TEXT = re.compile(r"\bnew-\d+\b")


def status_for(item: DesignDraftItem) -> Status:
    if item.kind == "open_question" or item.label == "open_question":
        return "open"
    if item.label in ("assumption", "suggestion"):
        return "proposed"
    if any(source.type == "decision" and not source.answer for source in item.sources):
        return "proposed"
    return "confirmed"


def parse_item_id(value: str) -> tuple[str, int] | None:
    match = _ID.match(value)
    return (match["prefix"], int(match["number"])) if match and match["prefix"] in PREFIXES.values() else None


class DesignService:
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
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._decisions = decisions
        self._projects = projects
        self._requirements = requirements

    # For agent tasks and other modules ------------------------------------------------------------

    def approved_requirements(self, project_id: uuid.UUID) -> VersionRecord | None:
        """The current requirements version if it is approved; designs are built only on that."""
        current = self._requirements.current_baseline(project_id)
        return current[0] if current and current[1] == "approved" else None

    def baseline_problem(self, project_id: uuid.UUID) -> str | None:
        """Why a new design draft cannot be recorded now, or None."""
        if self.approved_requirements(project_id) is None:
            return "The requirements are not approved at their current version; design builds on an approved requirements baseline"
        record = self._design_record(project_id)
        if record is not None and self._artifacts.is_locked_baseline(record.artifact_id) and not self._stale_reason(record.id):
            return f"The solution design v{record.version_no} is approved and under change control; design change requests arrive in Increment 4b"
        return None

    def current_items(self, project_id: uuid.UUID) -> list[DesignItemView]:
        record = self._design_record(project_id)
        return [self._item_view(row) for row in repository.items_for(self._session, record.id)] if record else []

    def coverage_failures(self, project_id: uuid.UUID) -> list[str]:
        """Phase exit check design_coverage: a current, non-stale design covering every confirmed requirement."""
        record = self._design_record(project_id)
        if record is None:
            return ["No solution design has been drafted yet"]
        if reason := self._stale_reason(record.id):
            return [reason]
        coverage = self._coverage(repository.version_for(self._session, record.id))  # type: ignore[arg-type]
        if coverage.gaps:
            return [f"Confirmed requirements not covered by the design and without a documented exception: {', '.join(coverage.gaps)}"]
        return []

    def approval_problems(self, version_id: uuid.UUID) -> list[str]:
        """Checked before a design version is approved: a stale design cannot be."""
        if repository.version_for(self._session, version_id) is None:
            return []  # a design document written by hand; only agent-drafted designs are tied to requirements
        reason = self._stale_reason(version_id)
        return [reason] if reason else []

    def coverage_by_requirement(self, project_id: uuid.UUID) -> dict[str, list[str]] | None:
        """Requirement ID -> design item IDs (or the exception) for the current design; None before there is one."""
        record = self._design_record(project_id)
        if record is None:
            return None
        coverage = self._coverage(repository.version_for(self._session, record.id))  # type: ignore[arg-type]
        return {row.requirement_id: (row.design_items or ([f"Exception: {row.exception}"] if row.exception else [])) for row in coverage.rows}

    def record_draft(self, actor: Actor, project_id: uuid.UUID, draft: DesignDraft) -> DraftResult:
        self._identity.require_project(actor, project_id, "artifact.author")
        draft = DesignDraft.model_validate(draft)
        if problem := self.baseline_problem(project_id):
            raise InvalidTransitionError(problem)
        requirements = self.approved_requirements(project_id)
        assert requirements is not None
        if requirements.id != draft.requirements_version_id:
            raise InvalidTransitionError("The approved requirements changed while the design was being drafted; ask again")
        requirement_ids = {item.item_id for item in self._requirements.items_of_version(requirements.id)}
        unknown = sorted({rid for item in draft.items for rid in item.satisfies if rid not in requirement_ids})
        unknown += sorted({e.requirement_id for e in draft.exceptions if e.requirement_id not in requirement_ids})
        if unknown:
            raise ValidationFailedError(f"Not in requirements v{requirements.version_no}: {', '.join(unknown)}")

        ids = self._assign_ids(project_id, draft.items)
        missing = sorted({ref for item in draft.items for ref in item.related if ref not in ids})
        if missing:
            raise ValidationFailedError(f"Design items refer to unknown items: {', '.join(missing)}")
        responses = [
            r.model_copy(update={"response": _NEW_REF_TEXT.sub(lambda m: ids.get(m.group(0), m.group(0)), r.response)})
            for r in draft.review_responses
        ]
        views = [
            DesignItemView(
                item_id=ids[item.ref],
                kind=item.kind,
                title=item.title.strip(),
                description=item.description.strip(),
                rationale=item.rationale.strip(),
                label=item.label,
                status=status_for(item),
                satisfies=list(dict.fromkeys(item.satisfies)),
                related=[ids[ref] for ref in dict.fromkeys(item.related) if ids[ref] != ids[item.ref]],
                unverified_capabilities=[c.strip() for c in item.unverified_capabilities if c.strip()],
                sources=item.sources,
                quality_flags=[],
            )
            for item in draft.items
        ]
        exceptions = list({e.requirement_id: e for e in draft.exceptions}.values())
        coverage = self._coverage_of(requirements.id, views, exceptions)
        item_flags, set_flags = check_items(
            [CheckedItem(v.item_id, v.kind, v.label, v.rationale, v.satisfies, v.related, v.unverified_capabilities) for v in views],
            coverage.gaps,
        )
        views = [view.model_copy(update={"quality_flags": item_flags[view.item_id]}) for view in views]
        project = self._projects.get_project(actor, project_id)
        content = render_design(
            project_name=project.name,
            requirements_label=f"{requirements.artifact_title} v{requirements.version_no} (sha256 {requirements.content_sha256[:12]})",
            summary=draft.summary,
            component_diagram=draft.component_diagram,
            data_flow_diagram=draft.data_flow_diagram,
            items=views,
            exceptions=exceptions,
            coverage=coverage,
            set_flags=set_flags,
            input_refs=draft.input_refs,
            review_responses=responses,
        )

        previous = self._design_record(project_id)
        if previous is None:
            detail = self._artifacts.create_artifact(
                actor,
                project_id,
                ArtifactCreate(artifact_type=DESIGN_TYPE, title=DESIGN_TITLE, content=content, change_summary=draft.change_summary, source_refs=draft.input_refs[:50]),
            )
        else:
            detail = self._artifacts.add_version(
                actor,
                previous.artifact_id,
                VersionCreate(content=content, change_summary=draft.change_summary, source_refs=draft.input_refs[:50], expected_current_version=previous.version_no),
                # A stale approved design is replaced by a redraft against the new requirements; that is the change.
                authorised_change=self._artifacts.is_locked_baseline(previous.artifact_id),
            )
        version = detail.current_version
        now = self._clock.now()
        repository.add(
            self._session,
            DesignVersion(
                project_id=project_id,
                artifact_id=detail.id,
                artifact_version_id=version.id,
                previous_artifact_version_id=previous.id if previous else None,
                requirements_version_id=requirements.id,
                summary=draft.summary.strip(),
                component_diagram=draft.component_diagram.strip(),
                data_flow_diagram=draft.data_flow_diagram.strip(),
                exceptions=[e.model_dump() for e in exceptions],
                set_flags=[flag.model_dump() for flag in set_flags],
                input_refs=draft.input_refs,
                review_responses=[r.model_dump(mode="json") for r in responses],
                created_at=now,
            ),
        )
        known = {row.item_id for row in repository.registered_ids(self._session, project_id)}
        for position, view in enumerate(views):
            if view.item_id not in known:
                _, number = parse_item_id(view.item_id)  # type: ignore[misc]
                repository.add(
                    self._session,
                    DesignId(project_id=project_id, item_id=view.item_id, kind=view.kind, number=number, first_artifact_version_id=version.id, created_at=now),
                )
            self._session.add(
                DesignItem(
                    project_id=project_id,
                    artifact_version_id=version.id,
                    item_id=view.item_id,
                    position=position,
                    kind=view.kind,
                    title=view.title,
                    description=view.description,
                    rationale=view.rationale,
                    label=view.label,
                    status=view.status,
                    satisfies=view.satisfies,
                    related=view.related,
                    unverified_capabilities=view.unverified_capabilities,
                    sources=[source.model_dump(mode="json") for source in view.sources],
                    quality_flags=[flag.model_dump() for flag in view.quality_flags],
                    created_at=now,
                )
            )
        self._session.flush()
        result = self._view(detail.id, version.id)
        self._audit.record(
            actor_id=actor.id,
            action="design.draft",
            entity_type="artifact_version",
            entity_id=version.id,
            project_id=project_id,
            after={
                "version_no": version.version_no,
                "requirements_version_no": requirements.version_no,
                "items": len(views),
                "coverage": {"confirmed": coverage.confirmed, "covered": coverage.covered, "excepted": coverage.excepted, "gaps": coverage.gaps},
            },
        )
        return DraftResult(view=result, ids={item.ref: ids[item.ref] for item in draft.items})

    # Reads -------------------------------------------------------------------------------------------

    def view(self, actor: Actor, project_id: uuid.UUID) -> DesignView | None:
        self._identity.require_project(actor, project_id, "artifact.view")
        record = self._design_record(project_id)
        return self._view(record.artifact_id, record.id) if record else None

    # Helpers -----------------------------------------------------------------------------------------

    def _design_record(self, project_id: uuid.UUID) -> VersionRecord | None:
        records = [r for r in self._artifacts.current_records_of_type(project_id, DESIGN_TYPE) if r.artifact_title == DESIGN_TITLE]
        if not records or repository.version_for(self._session, records[0].id) is None:
            return None
        return records[0]

    def _stale_reason(self, design_version_id: uuid.UUID) -> str | None:
        row = repository.version_for(self._session, design_version_id)
        if row is None:
            return None
        designed_against = self._artifacts.version_record(row.requirements_version_id)
        current = self._requirements.current_baseline(row.project_id)
        if current is None or current[0].id != row.requirements_version_id:
            now = f"v{current[0].version_no}" if current else "missing"
            return f"The design is stale: it was drafted against requirements v{designed_against.version_no}, and the requirements are now {now}"
        if current[1] != "approved":
            return f"The design is stale: requirements v{designed_against.version_no} are no longer approved"
        return None

    def _coverage(self, version: DesignVersion) -> Coverage:
        views = [self._item_view(row) for row in repository.items_for(self._session, version.artifact_version_id)]
        return self._coverage_of(version.requirements_version_id, views, [RequirementException.model_validate(e) for e in version.exceptions])

    def _coverage_of(self, requirements_version_id: uuid.UUID, items: Sequence[DesignItemView], exceptions: Sequence[RequirementException]) -> Coverage:
        by_requirement: dict[str, list[str]] = {}
        for item in items:
            for rid in item.satisfies:
                by_requirement.setdefault(rid, []).append(item.item_id)
        reasons = {e.requirement_id: e.reason for e in exceptions}
        rows = [
            CoverageRow(
                requirement_id=r.item_id,
                kind=r.kind,
                title=r.title,
                status=r.status,
                design_items=by_requirement.get(r.item_id, []),
                exception=reasons.get(r.item_id),
            )
            for r in self._requirements.items_of_version(requirements_version_id)
            if r.kind in COVERED_KINDS
        ]
        confirmed = [row for row in rows if row.status == "confirmed"]
        return Coverage(
            confirmed=len(confirmed),
            covered=sum(1 for row in confirmed if row.design_items),
            excepted=sum(1 for row in confirmed if not row.design_items and row.exception),
            gaps=[row.requirement_id for row in confirmed if not row.design_items and not row.exception],
            rows=rows,
        )

    def _assign_ids(self, project_id: uuid.UUID, items: list[DesignDraftItem]) -> dict[str, str]:
        registered = {row.item_id: row for row in repository.registered_ids(self._session, project_id)}
        next_number: dict[str, int] = {}
        for row in registered.values():
            prefix = PREFIXES[row.kind]
            next_number[prefix] = max(next_number.get(prefix, 1), row.number + 1)
        refs = [item.ref.strip() for item in items]
        if len(set(refs)) != len(refs):
            raise ValidationFailedError("Each design item in a draft needs its own ref")
        ids: dict[str, str] = {}
        for item in items:
            ref = item.ref.strip()
            if ref in registered:
                if registered[ref].kind != item.kind:
                    raise ValidationFailedError(f"{ref} is a {registered[ref].kind.replace('_', ' ')} item; it cannot become {item.kind}")
                ids[item.ref] = ref
            elif parse_item_id(ref):
                raise ValidationFailedError(f"{ref} is not a design item ID on this project; new items need a new ref, not an ID")
        for item in items:
            if item.ref in ids:
                continue
            prefix = PREFIXES[item.kind]
            number = next_number.get(prefix, 1)
            next_number[prefix] = number + 1
            ids[item.ref] = f"{prefix}-{number:03d}"
        return ids

    def _item_view(self, row: DesignItem) -> DesignItemView:
        return DesignItemView(
            item_id=row.item_id,
            kind=row.kind,  # type: ignore[arg-type]
            title=row.title,
            description=row.description,
            rationale=row.rationale,
            label=row.label,  # type: ignore[arg-type]
            status=row.status,  # type: ignore[arg-type]
            satisfies=row.satisfies,
            related=row.related,
            unverified_capabilities=row.unverified_capabilities,
            sources=[DesignSource.model_validate(s) for s in row.sources],
            quality_flags=[QualityFlag.model_validate(f) for f in row.quality_flags],
        )

    def _view(self, artifact_id: uuid.UUID, version_id: uuid.UUID) -> DesignView:
        row = repository.version_for(self._session, version_id)
        if row is None:
            raise NotFoundError("No drafted design for this version")
        record = self._artifacts.version_record(version_id)
        items = [self._item_view(item) for item in repository.items_for(self._session, version_id)]
        ids = [item.item_id for item in items]
        previous = {i.item_id for i in repository.items_for(self._session, row.previous_artifact_version_id)} if row.previous_artifact_version_id else set()
        counts: dict[str, int] = {"confirmed": 0, "proposed": 0, "open": 0}
        for item in items:
            counts[item.status] += 1
        stale = self._stale_reason(version_id)
        return DesignView(
            artifact_id=artifact_id,
            artifact_title=record.artifact_title,
            version_id=version_id,
            version_no=record.version_no,
            approval_status=self._decisions.approval_statuses([version_id])[version_id],
            locked=self._artifacts.is_locked_baseline(artifact_id) and record.is_current,
            stale=stale is not None,
            stale_reason=stale,
            requirements_version_no=self._artifacts.version_record(row.requirements_version_id).version_no,
            summary=row.summary,
            component_diagram=row.component_diagram,
            data_flow_diagram=row.data_flow_diagram,
            set_flags=[QualityFlag.model_validate(f) for f in row.set_flags],
            counts=counts,
            added=[i for i in ids if i not in previous] if previous else ids,
            removed=sorted(previous - set(ids)),
            review_responses=[ReviewResponse.model_validate(r) for r in row.review_responses],
            exceptions=[RequirementException.model_validate(e) for e in row.exceptions],
            coverage=self._coverage(row),
            items=items,
            created_at=row.created_at,
        )
