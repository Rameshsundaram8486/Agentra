"""Business rules for approvals and decision records; the only entry point for other modules.

Approvals: human only, role from the approval matrix, independent of the authors, bound to the exact version
id and content hash, and only for the current version. Decisions: the original request and recommendation are
never changed; each human response is a separate, numbered outcome.
"""

import uuid
from collections.abc import Callable, Iterable, Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.artifacts.service import ArtifactsService
from app.modules.audit.service import AuditService
from app.modules.decisions import repository
from app.modules.decisions.authority import ApprovalMatrix, check_can_approve, check_can_decide
from app.modules.decisions.models import Approval, DecisionOutcome, DecisionRequest
from app.modules.decisions.schemas import (
    ApprovalCreate,
    ApprovalView,
    ArtifactApprovals,
    DecisionOption,
    DecisionOutcomeCreate,
    DecisionOutcomeView,
    DecisionRequestCreate,
    DecisionStatus,
    DecisionView,
    VersionApprovalState,
)
from app.modules.decisions.version_binding import check_binding
from app.modules.errors import ConflictError, InvalidTransitionError, NotFoundError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService

__all__ = [
    "ApprovalCreate",
    "ApprovalView",
    "ArtifactApprovals",
    "DecisionOutcomeCreate",
    "DecisionRequestCreate",
    "DecisionView",
    "DecisionsService",
]


def _status(outcomes: list[DecisionOutcome]) -> DecisionStatus:
    if not outcomes:
        return "open"
    return "deferred" if outcomes[-1].action == "defer" else "decided"


class DecisionsService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        artifacts: ArtifactsService,
        matrix: ApprovalMatrix,
        approval_checks: Mapping[str, Callable[[uuid.UUID], list[str]]] | None = None,
    ) -> None:
        """approval_checks: artifact type -> problems with approving a given version (from other modules)."""
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._matrix = matrix
        self._approval_checks = approval_checks or {}

    # Approvals ------------------------------------------------------------------------------

    def record_approval(self, actor: Actor, version_id: uuid.UUID, data: ApprovalCreate) -> ApprovalView:
        data = ApprovalCreate.model_validate(data)
        version = self._artifacts.version_record(version_id)
        self._identity.require_project(actor, version.project_id, "artifact.view")
        policy = self._matrix.artifact_type(version.artifact_type)
        if policy is None:
            raise ValidationFailedError(f"No approval rule exists for artifact type '{version.artifact_type}'")
        check_can_approve(
            actor,
            self._identity.roles_for(actor, version.project_id),
            policy,
            self._artifacts.author_ids(version.artifact_id),
        )
        if data.decision == "approved" and (check := self._approval_checks.get(version.artifact_type)):
            if problems := check(version.id):
                raise InvalidTransitionError("Cannot approve this version: " + "; ".join(problems))
        content_sha256 = check_binding(version, data.content_sha256)
        self._artifacts.verify_content(version.id)
        comment = (data.comment or "").strip() or None
        if data.decision != "approved" and comment is None:
            raise ValidationFailedError("Explain what is wrong or what needs to change")

        approval = Approval(
            project_id=version.project_id,
            artifact_id=version.artifact_id,
            artifact_version_id=version.id,
            content_sha256=content_sha256,
            decision=data.decision,
            approver_id=actor.id,
            comment=comment,
            created_at=self._clock.now(),
        )
        repository.add(self._session, approval)
        self._audit.record(
            actor_id=actor.id,
            action="approval.record",
            entity_type="artifact_version",
            entity_id=version.id,
            project_id=version.project_id,
            reason=comment,
            after={
                "decision": data.decision,
                "artifact_id": str(version.artifact_id),
                "version_no": version.version_no,
                "content_sha256": content_sha256,
            },
        )
        return self._approval_views([approval], {version.id: version.version_no})[0]

    def artifact_approvals(self, actor: Actor, artifact_id: uuid.UUID) -> ArtifactApprovals:
        """Approval history of an artifact and the state of its current version."""
        detail = self._artifacts.get_artifact(actor, artifact_id)  # authorises artifact.view
        numbers = {version.id: version.version_no for version in detail.versions}
        history = self._approval_views(repository.approvals_for_artifact(self._session, artifact_id), numbers)
        current_id = detail.current_version.id
        latest = next((view for view in history if view.artifact_version_id == current_id), None)
        return ArtifactApprovals(
            current=VersionApprovalState(
                version_id=current_id,
                version_no=detail.current_version_no,
                status=latest.decision if latest else "pending",
                latest=latest,
            ),
            history=history,
        )

    def approval_statuses(self, version_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Latest approval decision per version ('pending' if none). Callers authorise first."""
        return {
            version_id: (latest.decision if (latest := repository.latest_approval(self._session, version_id)) else "pending")
            for version_id in version_ids
        }

    def approval_gate_failures(self, project_id: uuid.UUID, required_types: Iterable[str]) -> list[str]:
        """Each required type needs at least one artifact, and every such artifact's current version approved."""
        failures = []
        for artifact_type in required_types:
            policy = self._matrix.artifact_type(artifact_type)
            title = policy.title if policy else artifact_type
            records = self._artifacts.current_records_of_type(project_id, artifact_type)
            if not records:
                failures.append(f"No {title.lower()} exists yet")
            for record in records:
                latest = repository.latest_approval(self._session, record.id)
                if latest is None or latest.decision != "approved" or latest.content_sha256 != record.content_sha256:
                    failures.append(f"{title} '{record.artifact_title}' v{record.version_no} is not approved")
                else:
                    self._artifacts.verify_content(record.id)
        return failures

    # Decisions ------------------------------------------------------------------------------

    def raise_decision(self, actor: Actor, project_id: uuid.UUID, data: DecisionRequestCreate) -> DecisionView:
        self._identity.require_project(actor, project_id, "decision.raise")
        data = DecisionRequestCreate.model_validate(data)
        if data.artifact_version_id is not None:
            if self._artifacts.version_record(data.artifact_version_id).project_id != project_id:
                raise ValidationFailedError("The linked artifact version belongs to another project")
        request = DecisionRequest(
            project_id=project_id,
            title=data.title.strip(),
            question=data.question.strip(),
            context=(data.context or "").strip() or None,
            options=[option.model_dump() for option in data.options],
            recommended_option=data.recommended_option,
            recommendation_rationale=data.recommendation_rationale.strip(),
            assumptions=[item.strip() for item in data.assumptions if item.strip()],
            risks=[item.strip() for item in data.risks if item.strip()],
            artifact_version_id=data.artifact_version_id,
            raised_by=actor.id,
            created_at=self._clock.now(),
        )
        repository.add(self._session, request)
        self._audit.record(
            actor_id=actor.id,
            action="decision.raise",
            entity_type="decision_request",
            entity_id=request.id,
            project_id=project_id,
            after={
                "title": request.title,
                "options": [option.key for option in data.options],
                "recommended_option": data.recommended_option,
            },
        )
        return self._views([request])[0]

    def list_decisions(self, actor: Actor, project_id: uuid.UUID) -> list[DecisionView]:
        self._identity.require_project(actor, project_id, "decision.view")
        return self._views(repository.requests_for_project(self._session, project_id))

    def get_decision(self, actor: Actor, decision_id: uuid.UUID) -> DecisionView:
        request = self._load(decision_id)
        self._identity.require_project(actor, request.project_id, "decision.view")
        return self._views([request])[0]

    def record_outcome(self, actor: Actor, decision_id: uuid.UUID, data: DecisionOutcomeCreate) -> DecisionView:
        request = self._load(decision_id)
        self._identity.require_project(actor, request.project_id, "decision.view")
        check_can_decide(actor, self._identity.roles_for(actor, request.project_id), self._matrix.decisions)
        data = DecisionOutcomeCreate.model_validate(data)
        outcomes = repository.outcomes_for(self._session, [request.id])[request.id]
        if _status(outcomes) == "decided":
            raise InvalidTransitionError("This decision has already been made; raise a new decision request to revisit it")

        keys = {option["key"] for option in request.options}
        if data.action in ("accept", "modify") and request.recommended_option is None:
            raise ValidationFailedError("There is no recommendation to accept or modify; select an option instead")
        if data.action == "select_option":
            if data.selected_option not in keys:
                raise ValidationFailedError(f"Unknown option '{data.selected_option}'")
            if data.selected_option == request.recommended_option:
                raise ValidationFailedError("That is the recommended option; use accept instead")

        outcome = DecisionOutcome(
            decision_request_id=request.id,
            project_id=request.project_id,
            outcome_no=len(outcomes) + 1,
            action=data.action,
            selected_option=data.selected_option,
            custom_choice=(data.custom_choice or "").strip() or None,
            comment=(data.comment or "").strip() or None,
            decided_by=actor.id,
            created_at=self._clock.now(),
        )
        try:
            with self._session.begin_nested():
                repository.add(self._session, outcome)
        except IntegrityError as exc:
            raise ConflictError("Someone else answered this decision just now; reload it") from exc
        self._audit.record(
            actor_id=actor.id,
            action="decision.outcome",
            entity_type="decision_request",
            entity_id=request.id,
            project_id=request.project_id,
            reason=outcome.comment,
            after={
                "action": outcome.action,
                "selected_option": outcome.selected_option,
                "custom_choice": outcome.custom_choice,
                "outcome_no": outcome.outcome_no,
            },
        )
        return self._views([request])[0]

    def approvals_by_id(self, approval_ids: Iterable[uuid.UUID]) -> list[ApprovalView]:
        """Approval records in the given order. Callers authorise first."""
        ids = list(approval_ids)
        rows = {row.id: row for row in repository.approvals_by_id(self._session, ids)}
        found = [rows[approval_id] for approval_id in ids if approval_id in rows]
        numbers = {row.artifact_version_id: self._artifacts.version_record(row.artifact_version_id).version_no for row in found}
        return self._approval_views(found, numbers)

    def decision_statuses(self, decision_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, DecisionStatus]:
        """open, deferred or decided per decision request. Callers authorise first."""
        ids = list(decision_ids)
        outcomes = repository.outcomes_for(self._session, ids)
        return {decision_id: _status(outcomes[decision_id]) for decision_id in ids}

    # Helpers --------------------------------------------------------------------------------

    def _load(self, decision_id: uuid.UUID) -> DecisionRequest:
        request = repository.get_request(self._session, decision_id)
        if request is None:
            raise NotFoundError("Decision not found")
        return request

    def _approval_views(self, approvals: list[Approval], version_numbers: dict[uuid.UUID, int]) -> list[ApprovalView]:
        names = self._identity.display_names({approval.approver_id for approval in approvals})
        return [
            ApprovalView(
                id=approval.id,
                artifact_id=approval.artifact_id,
                artifact_version_id=approval.artifact_version_id,
                version_no=version_numbers.get(approval.artifact_version_id, 0),
                content_sha256=approval.content_sha256,
                decision=approval.decision,  # type: ignore[arg-type]
                approver_id=approval.approver_id,
                approver_name=names.get(approval.approver_id),
                comment=approval.comment,
                created_at=approval.created_at,
            )
            for approval in approvals
        ]

    def _views(self, requests: list[DecisionRequest]) -> list[DecisionView]:
        outcomes = repository.outcomes_for(self._session, [request.id for request in requests])
        people = {request.raised_by for request in requests} | {
            outcome.decided_by for rows in outcomes.values() for outcome in rows
        }
        names = self._identity.display_names(people)
        views = []
        for request in requests:
            rows = outcomes[request.id]
            options = [DecisionOption.model_validate(option) for option in request.options]
            titles = {option.key: option.title for option in options}
            final = rows[-1] if rows and rows[-1].action != "defer" else None
            final_choice = None
            if final is not None:
                final_choice = {
                    "accept": titles.get(request.recommended_option or ""),
                    "modify": f"{titles.get(request.recommended_option or '', '')} (modified)",
                    "select_option": titles.get(final.selected_option or ""),
                    "other": final.custom_choice,
                    "reject": None,
                }[final.action]
            views.append(
                DecisionView(
                    id=request.id,
                    project_id=request.project_id,
                    title=request.title,
                    question=request.question,
                    context=request.context,
                    options=options,
                    recommended_option=request.recommended_option,
                    recommendation_rationale=request.recommendation_rationale,
                    assumptions=request.assumptions,
                    risks=request.risks,
                    artifact_version_id=request.artifact_version_id,
                    raised_by=request.raised_by,
                    raised_by_name=names.get(request.raised_by),
                    created_at=request.created_at,
                    status=_status(rows),
                    final_choice=final_choice,
                    outcomes=[
                        DecisionOutcomeView(
                            outcome_no=row.outcome_no,
                            action=row.action,  # type: ignore[arg-type]
                            selected_option=row.selected_option,
                            custom_choice=row.custom_choice,
                            comment=row.comment,
                            decided_by=row.decided_by,
                            decided_by_name=names.get(row.decided_by),
                            created_at=row.created_at,
                        )
                        for row in rows
                    ],
                )
            )
        return views
