"""Business rules for requirement items; the only entry point for other modules.

A draft (from the Business Analyst agent) becomes a new version of the project's requirements baseline
document plus an immutable set of items linked to that version, so approving the document version approves
exactly those items. Rules enforced here, not by the agent:
- Item IDs are assigned by the server, per project and kind, and never reused. A draft keeps an item's ID by
  referring to it; an unknown or mismatched ID is refused.
- Status is derived: confirmed only for a fact with no unanswered decision behind it; assumptions and
  suggestions are proposed; open questions are open. A model cannot mark anything confirmed.
- An approved baseline is under change control: only an approved change request can change it, and only
  the items the change request lists (app/modules/requirements/change_control.py).
- A change request needs one approval per configured role, from different people, never from the person
  who raised it, and never from an agent. Any rejection rejects it. Requests and their events are never edited.
"""

import re
import uuid
from collections.abc import Callable, Mapping, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.artifacts.service import ArtifactCreate, ArtifactsService, VersionCreate, VersionRecord
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.decisions.authority import require_human
from app.modules.errors import ConflictError, InvalidTransitionError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.requirements import repository
from app.modules.requirements.change_control import ComparableItem, change_violations
from app.modules.requirements.models import ChangeRequest, ChangeRequestEvent, RequirementId, RequirementItem, RequirementVersion
from app.modules.requirements.quality_checks import CheckedItem, check_items
from app.modules.requirements.rendering import render_brd
from app.modules.requirements.schemas import (
    PREFIXES,
    ChangeRequestCreate,
    ChangeRequestDecisionCreate,
    ChangeRequestEventView,
    ChangeRequestView,
    DraftItem,
    DraftResult,
    QualityFlag,
    RequirementItemView,
    RequirementsDraft,
    RequirementsView,
    ReviewResponse,
    SourceRef,
    Status,
    TraceabilityView,
)
from app.modules.requirements.traceability import build_rows, to_csv

__all__ = [
    "BASELINE_TITLE",
    "BASELINE_TYPE",
    "ChangeRequestCreate",
    "ChangeRequestDecisionCreate",
    "ChangeRequestView",
    "DraftItem",
    "RequirementsDraft",
    "RequirementsService",
    "RequirementsView",
    "ReviewResponse",
    "SourceRef",
    "TraceabilityView",
]

BASELINE_TYPE = "requirements_baseline"
BASELINE_TITLE = "Business requirements"
_ID = re.compile(r"^(?P<prefix>[A-Z]+(?:-[A-Z]+)?)-(?P<number>\d{3,})$")
_NEW_REF_TEXT = re.compile(r"\bnew-\d+\b")


def status_for(item: DraftItem) -> Status:
    if item.kind == "open_question" or item.label == "open_question":
        return "open"
    if item.kind == "assumption" or item.label in ("assumption", "suggestion"):
        return "proposed"
    if any(source.type == "decision" and not source.answer for source in item.sources):
        return "proposed"
    return "confirmed"


def parse_item_id(value: str) -> tuple[str, int] | None:
    match = _ID.match(value)
    return (match["prefix"], int(match["number"])) if match else None


class RequirementsService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        artifacts: ArtifactsService,
        decisions: DecisionsService,
        projects: ProjectsService,
        change_request_roles: Sequence[str] = ("owner", "customer_approver"),
        design_lookup: Callable[[uuid.UUID], Mapping[str, list[str]] | None] | None = None,
    ) -> None:
        """design_lookup(project_id) maps requirement IDs to the design items covering them (design module)."""
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._decisions = decisions
        self._projects = projects
        self._change_request_roles = tuple(change_request_roles)
        self._design_lookup = design_lookup

    # For agent tasks --------------------------------------------------------------------------

    def baseline_problem(self, project_id: uuid.UUID, change_request_id: uuid.UUID | None = None) -> str | None:
        """Why a draft cannot be recorded now, or None. With a change request: why it cannot be applied."""
        record = self._baseline_record(project_id)
        locked = record is not None and self._artifacts.is_locked_baseline(record.artifact_id)
        if change_request_id is None:
            if locked:
                return f"The requirements baseline v{record.version_no} is approved and under change control; raise a change request"  # type: ignore[union-attr]
            return None
        request = repository.get_change_request(self._session, change_request_id)
        if request is None or request.project_id != project_id:
            return "Change request not found"
        status = self._cr_status(request)
        if status != "approved":
            return f"{self._cr_label(request)} is {status}; only an approved change request can be applied"
        if not locked or record is None or record.id != request.baseline_version_id:
            return f"{self._cr_label(request)} was raised against a baseline version that is no longer the approved current version"
        return None

    def current_baseline(self, project_id: uuid.UUID) -> tuple[VersionRecord, str] | None:
        """The current requirements version and its approval status. Callers authorise first."""
        record = self._baseline_record(project_id)
        return (record, self._decisions.approval_statuses([record.id])[record.id]) if record else None

    def items_of_version(self, version_id: uuid.UUID) -> list[RequirementItemView]:
        """Items of one drafted requirements version. Callers authorise first."""
        return [self._item_view(row) for row in repository.items_for(self._session, version_id)]

    def current_items(self, project_id: uuid.UUID) -> list[RequirementItemView]:
        """Items of the latest drafted version, for an agent revising them. Callers authorise first."""
        record = self._baseline_record(project_id)
        return [self._item_view(row) for row in repository.items_for(self._session, record.id)] if record else []

    def record_draft(self, actor: Actor, project_id: uuid.UUID, draft: RequirementsDraft) -> DraftResult:
        self._identity.require_project(actor, project_id, "artifact.author")
        draft = RequirementsDraft.model_validate(draft)
        if problem := self.baseline_problem(project_id, draft.change_request_id):
            raise InvalidTransitionError(problem)
        change_request = repository.get_change_request(self._session, draft.change_request_id) if draft.change_request_id else None
        if change_request is not None:
            violations = change_violations(
                [self._comparable(item) for item in self.current_items(project_id)],
                [self._comparable(item) for item in draft.items],
                affected=set(change_request.affected_item_ids),
                allows_new_items=change_request.allows_new_items,
            )
            if violations:
                raise ValidationFailedError(f"{self._cr_label(change_request)} does not allow this: " + "; ".join(p for _, p in violations))

        ids = self._assign_ids(project_id, draft.items)
        unknown = sorted({ref for item in draft.items for ref in item.related if ref not in ids})
        if unknown:
            raise ValidationFailedError(f"Items refer to unknown items: {', '.join(unknown)}")
        # The agent names new items by their draft refs (new-1); readers need the IDs they were given.
        responses = [
            response.model_copy(update={"response": _NEW_REF_TEXT.sub(lambda m: ids.get(m.group(0), m.group(0)), response.response)})
            for response in draft.review_responses
        ]
        views = [
            RequirementItemView(
                item_id=ids[item.ref],
                kind=item.kind,
                title=item.title.strip(),
                statement=item.statement.strip(),
                label=item.label,
                status=status_for(item),
                priority=item.priority,
                acceptance_criteria=[c.strip() for c in item.acceptance_criteria if c.strip()],
                sources=item.sources,
                quality_flags=[],
                related=[ids[ref] for ref in item.related if ids[ref] != ids[item.ref]],
            )
            for item in draft.items
        ]
        item_flags, set_flags = check_items(
            [
                CheckedItem(
                    item_id=view.item_id,
                    kind=view.kind,
                    title=view.title,
                    statement=view.statement,
                    acceptance_criteria=view.acceptance_criteria,
                    cites_open_decision=any(s.type == "decision" and not s.answer for s in view.sources),
                )
                for view in views
            ]
        )
        views = [view.model_copy(update={"quality_flags": item_flags[view.item_id]}) for view in views]
        project = self._projects.get_project(actor, project_id)
        content = render_brd(
            project_name=project.name,
            summary=draft.summary,
            items=views,
            set_flags=set_flags,
            process_flow_mermaid=draft.process_flow_mermaid,
            input_refs=draft.input_refs,
            review_responses=responses,
            change_request=f"{self._cr_label(change_request)}: {change_request.title}" if change_request else None,
        )

        previous = self._baseline_record(project_id)
        if previous is None:
            detail = self._artifacts.create_artifact(
                actor,
                project_id,
                ArtifactCreate(
                    artifact_type=BASELINE_TYPE,
                    title=BASELINE_TITLE,
                    content=content,
                    change_summary=draft.change_summary,
                    source_refs=draft.input_refs[:50],
                ),
            )
        else:
            detail = self._artifacts.add_version(
                actor,
                previous.artifact_id,
                VersionCreate(
                    content=content,
                    change_summary=draft.change_summary,
                    source_refs=draft.input_refs[:50],
                    expected_current_version=previous.version_no,
                ),
                authorised_change=change_request is not None,
            )
        version = detail.current_version
        now = self._clock.now()
        repository.add(
            self._session,
            RequirementVersion(
                project_id=project_id,
                artifact_id=detail.id,
                artifact_version_id=version.id,
                previous_artifact_version_id=previous.id if previous else None,
                summary=draft.summary.strip(),
                process_flow=draft.process_flow_mermaid.strip(),
                set_flags=[flag.model_dump() for flag in set_flags],
                input_refs=draft.input_refs,
                review_responses=[response.model_dump(mode="json") for response in responses],
                change_request_id=change_request.id if change_request else None,
                created_at=now,
            ),
        )
        if change_request is not None:
            repository.add(
                self._session,
                ChangeRequestEvent(
                    change_request_id=change_request.id,
                    project_id=project_id,
                    event="applied",
                    role=None,
                    actor_id=actor.id,
                    comment=None,
                    artifact_version_id=version.id,
                    created_at=now,
                ),
            )
        known = {row.item_id for row in repository.registered_ids(self._session, project_id)}
        for position, view in enumerate(views):
            if view.item_id not in known:
                prefix, number = parse_item_id(view.item_id)  # type: ignore[misc]
                repository.add(
                    self._session,
                    RequirementId(
                        project_id=project_id,
                        item_id=view.item_id,
                        kind=view.kind,
                        number=number,
                        first_artifact_version_id=version.id,
                        created_at=now,
                    ),
                )
            self._session.add(
                RequirementItem(
                    project_id=project_id,
                    artifact_version_id=version.id,
                    item_id=view.item_id,
                    position=position,
                    kind=view.kind,
                    title=view.title,
                    statement=view.statement,
                    label=view.label,
                    status=view.status,
                    priority=view.priority,
                    acceptance_criteria=view.acceptance_criteria,
                    sources=[source.model_dump(mode="json") for source in view.sources],
                    quality_flags=[flag.model_dump() for flag in view.quality_flags],
                    related=view.related,
                    created_at=now,
                )
            )
        self._session.flush()
        result_view = self._view(detail.id, version.id)
        self._audit.record(
            actor_id=actor.id,
            action="requirements.draft",
            entity_type="artifact_version",
            entity_id=version.id,
            project_id=project_id,
            after={
                "version_no": version.version_no,
                "items": len(views),
                "counts": result_view.counts,
                "added": result_view.added,
                "removed": result_view.removed,
                "flagged": sum(1 for view in views if view.quality_flags),
                "change_request": self._cr_label(change_request) if change_request else None,
                "review_comments_answered": len(draft.review_responses),
            },
        )
        return DraftResult(view=result_view, ids={item.ref: ids[item.ref] for item in draft.items})

    # Reads ----------------------------------------------------------------------------------

    def view(self, actor: Actor, project_id: uuid.UUID) -> RequirementsView | None:
        """The latest drafted requirements of a project, or None if nothing has been drafted."""
        self._identity.require_project(actor, project_id, "artifact.view")
        record = self._baseline_record(project_id)
        return self._view(record.artifact_id, record.id) if record else None

    def traceability(self, actor: Actor, project_id: uuid.UUID) -> TraceabilityView | None:
        self._identity.require_project(actor, project_id, "artifact.view")
        record = self._baseline_record(project_id)
        if record is None:
            return None
        design = self._design_lookup(project_id) if self._design_lookup else None
        rows, gaps = build_rows([self._item_view(row) for row in repository.items_for(self._session, record.id)], design)
        return TraceabilityView(
            version_id=record.id,
            version_no=record.version_no,
            approval_status=self._decisions.approval_statuses([record.id])[record.id],
            rows=rows,
            gaps=gaps,
        )

    def traceability_csv(self, actor: Actor, project_id: uuid.UUID) -> str | None:
        view = self.traceability(actor, project_id)
        return to_csv(view) if view else None

    # Change requests --------------------------------------------------------------------------

    def raise_change_request(self, actor: Actor, project_id: uuid.UUID, data: ChangeRequestCreate) -> ChangeRequestView:
        self._identity.require_project(actor, project_id, "change.raise")
        require_human(actor, "raise a change request")
        data = ChangeRequestCreate.model_validate(data)
        record = self._baseline_record(project_id)
        if record is None or not self._artifacts.is_locked_baseline(record.artifact_id):
            raise InvalidTransitionError("There is no approved requirements baseline yet; until there is, ask for a new draft instead")
        known = {row.item_id for row in repository.items_for(self._session, record.id)}
        affected = list(dict.fromkeys(item.strip().upper() for item in data.affected_item_ids if item.strip()))
        unknown = [item for item in affected if item not in known]
        if unknown:
            raise ValidationFailedError(f"Not in the baseline v{record.version_no}: {', '.join(unknown)}")
        if not affected and not data.allows_new_items:
            raise ValidationFailedError("List the requirements to change, or allow new items, or both")
        request = ChangeRequest(
            project_id=project_id,
            number=repository.next_change_request_number(self._session, project_id),
            baseline_artifact_id=record.artifact_id,
            baseline_version_id=record.id,
            title=data.title.strip(),
            reason=data.reason.strip(),
            change=data.change.strip(),
            impact=data.impact.strip(),
            affected_item_ids=affected,
            allows_new_items=data.allows_new_items,
            raised_by=actor.id,
            created_at=self._clock.now(),
        )
        try:
            with self._session.begin_nested():
                repository.add(self._session, request)
        except IntegrityError as exc:
            raise ConflictError("Another change request was raised at the same moment; try again") from exc
        self._audit.record(
            actor_id=actor.id,
            action="change_request.raise",
            entity_type="change_request",
            entity_id=request.id,
            project_id=project_id,
            reason=request.reason,
            after={"cr": self._cr_label(request), "baseline_version_no": record.version_no, "affected": affected, "allows_new_items": data.allows_new_items},
        )
        return self._cr_views([request])[0]

    def decide_change_request(self, actor: Actor, change_request_id: uuid.UUID, data: ChangeRequestDecisionCreate) -> ChangeRequestView:
        request = self._load_cr(change_request_id)
        self._identity.require_project(actor, request.project_id, "artifact.view")
        require_human(actor, "decide a change request")
        data = ChangeRequestDecisionCreate.model_validate(data)
        if actor.id == request.raised_by:
            raise PermissionDeniedError("You raised this change request, so other people must decide it")
        status = self._cr_status(request)
        if status != "open":
            raise InvalidTransitionError(f"{self._cr_label(request)} is already {status}")
        events = repository.change_request_events(self._session, [request.id])[request.id]
        if any(event.actor_id == actor.id for event in events if event.role):
            raise PermissionDeniedError("You have already decided this change request; another person must give the other approval")
        decided_roles = {event.role for event in events if event.role}
        roles = self._identity.roles_for(actor, request.project_id)
        role = next((r for r in self._change_request_roles if r in roles and r not in decided_roles), None)
        if role is None:
            needed = [r for r in self._change_request_roles if r not in decided_roles]
            raise PermissionDeniedError(f"Deciding this change request needs one of these roles: {', '.join(needed)}")
        comment = (data.comment or "").strip() or None
        if data.decision == "rejected" and comment is None:
            raise ValidationFailedError("Explain why the change request is rejected")
        try:
            with self._session.begin_nested():
                repository.add(
                    self._session,
                    ChangeRequestEvent(
                        change_request_id=request.id,
                        project_id=request.project_id,
                        event=data.decision,
                        role=role,
                        actor_id=actor.id,
                        comment=comment,
                        artifact_version_id=None,
                        created_at=self._clock.now(),
                    ),
                )
        except IntegrityError as exc:
            raise ConflictError("Someone decided in this role just now; reload the change request") from exc
        self._audit.record(
            actor_id=actor.id,
            action=f"change_request.{data.decision}",
            entity_type="change_request",
            entity_id=request.id,
            project_id=request.project_id,
            reason=comment,
            after={"cr": self._cr_label(request), "role": role, "status": self._cr_status(request)},
        )
        return self._cr_views([request])[0]

    def list_change_requests(self, actor: Actor, project_id: uuid.UUID) -> list[ChangeRequestView]:
        self._identity.require_project(actor, project_id, "artifact.view")
        return self._cr_views(repository.change_requests_for_project(self._session, project_id))

    def get_change_request(self, actor: Actor, change_request_id: uuid.UUID) -> ChangeRequestView:
        request = self._load_cr(change_request_id)
        self._identity.require_project(actor, request.project_id, "artifact.view")
        return self._cr_views([request])[0]

    # Helpers --------------------------------------------------------------------------------

    @staticmethod
    def _comparable(item: DraftItem | RequirementItemView) -> ComparableItem:
        ref = item.ref if isinstance(item, DraftItem) else item.item_id
        return ComparableItem(ref, item.kind, item.title, item.statement, item.label, item.priority, item.acceptance_criteria)

    @staticmethod
    def _cr_label(request: ChangeRequest) -> str:
        return f"CR-{request.number:03d}"

    def _load_cr(self, change_request_id: uuid.UUID) -> ChangeRequest:
        request = repository.get_change_request(self._session, change_request_id)
        if request is None:
            raise NotFoundError("Change request not found")
        return request

    def _cr_status(self, request: ChangeRequest, events: list[ChangeRequestEvent] | None = None) -> str:
        if events is None:
            events = repository.change_request_events(self._session, [request.id])[request.id]
        if any(event.event == "applied" for event in events):
            return "applied"
        if any(event.event == "rejected" for event in events):
            return "rejected"
        approved = {event.role for event in events if event.event == "approved"}
        return "approved" if set(self._change_request_roles) <= approved else "open"

    def _cr_views(self, requests: list[ChangeRequest]) -> list[ChangeRequestView]:
        events = repository.change_request_events(self._session, [request.id for request in requests])
        people = {request.raised_by for request in requests} | {e.actor_id for rows in events.values() for e in rows}
        names = self._identity.display_names(people)
        views = []
        for request in requests:
            rows = events[request.id]
            applied = next((e for e in rows if e.event == "applied"), None)
            views.append(
                ChangeRequestView(
                    id=request.id,
                    project_id=request.project_id,
                    cr_id=self._cr_label(request),
                    baseline_artifact_id=request.baseline_artifact_id,
                    baseline_version_id=request.baseline_version_id,
                    baseline_version_no=self._artifacts.version_record(request.baseline_version_id).version_no,
                    title=request.title,
                    reason=request.reason,
                    change=request.change,
                    impact=request.impact,
                    affected_item_ids=request.affected_item_ids,
                    allows_new_items=request.allows_new_items,
                    raised_by=request.raised_by,
                    raised_by_name=names.get(request.raised_by),
                    status=self._cr_status(request, rows),  # type: ignore[arg-type]
                    required_roles=list(self._change_request_roles),
                    approved_roles=[e.role for e in rows if e.event == "approved" and e.role],
                    applied_version_no=self._artifacts.version_record(applied.artifact_version_id).version_no if applied and applied.artifact_version_id else None,
                    events=[
                        ChangeRequestEventView(
                            event=e.event,  # type: ignore[arg-type]
                            role=e.role,
                            actor_id=e.actor_id,
                            actor_name=names.get(e.actor_id),
                            comment=e.comment,
                            artifact_version_id=e.artifact_version_id,
                            created_at=e.created_at,
                        )
                        for e in rows
                    ],
                    created_at=request.created_at,
                )
            )
        return views

    def _baseline_record(self, project_id: uuid.UUID) -> VersionRecord | None:
        """The current version of the agent-drafted baseline document, if it has drafted items."""
        records = [
            r for r in self._artifacts.current_records_of_type(project_id, BASELINE_TYPE) if r.artifact_title == BASELINE_TITLE
        ]
        if not records or repository.version_for(self._session, records[0].id) is None:
            return None
        return records[0]

    def _assign_ids(self, project_id: uuid.UUID, items: list[DraftItem]) -> dict[str, str]:
        registered = {row.item_id: row for row in repository.registered_ids(self._session, project_id)}
        next_number: dict[str, int] = {}
        for row in registered.values():
            prefix = PREFIXES[row.kind]
            next_number[prefix] = max(next_number.get(prefix, 1), row.number + 1)
        ids: dict[str, str] = {}
        refs = [item.ref.strip() for item in items]
        if len(set(refs)) != len(refs):
            raise ValidationFailedError("Each item in a draft needs its own ref")
        for item in items:  # keep existing IDs first, so new numbering never collides
            ref = item.ref.strip()
            if ref in registered:
                if registered[ref].kind != item.kind:
                    raise ValidationFailedError(f"{ref} is a {registered[ref].kind.replace('_', ' ')} item; it cannot become {item.kind}")
                ids[item.ref] = ref
            elif parse_item_id(ref):
                raise ValidationFailedError(f"{ref} is not an item ID on this project; new items need a new ref, not an ID")
        for item in items:
            if item.ref in ids:
                continue
            prefix = PREFIXES[item.kind]
            number = next_number.get(prefix, 1)
            next_number[prefix] = number + 1
            ids[item.ref] = f"{prefix}-{number:03d}"
        return ids

    def _item_view(self, row: RequirementItem) -> RequirementItemView:
        return RequirementItemView(
            item_id=row.item_id,
            kind=row.kind,  # type: ignore[arg-type]
            title=row.title,
            statement=row.statement,
            label=row.label,  # type: ignore[arg-type]
            status=row.status,  # type: ignore[arg-type]
            priority=row.priority,  # type: ignore[arg-type]
            acceptance_criteria=row.acceptance_criteria,
            sources=[SourceRef.model_validate(source) for source in row.sources],
            quality_flags=[QualityFlag.model_validate(flag) for flag in row.quality_flags],
            related=list(row.related or []),
        )

    def _view(self, artifact_id: uuid.UUID, version_id: uuid.UUID) -> RequirementsView:
        version_row = repository.version_for(self._session, version_id)
        if version_row is None:
            raise NotFoundError("No drafted requirements for this version")
        record = self._artifacts.version_record(version_id)
        items = [self._item_view(row) for row in repository.items_for(self._session, version_id)]
        current_ids = [item.item_id for item in items]
        previous_ids = (
            {row.item_id for row in repository.items_for(self._session, version_row.previous_artifact_version_id)}
            if version_row.previous_artifact_version_id
            else set()
        )
        counts: dict[str, int] = {"confirmed": 0, "proposed": 0, "open": 0}
        for item in items:
            counts[item.status] += 1
        return RequirementsView(
            artifact_id=artifact_id,
            artifact_title=record.artifact_title,
            version_id=version_id,
            version_no=record.version_no,
            approval_status=self._decisions.approval_statuses([version_id])[version_id],
            summary=version_row.summary,
            process_flow_mermaid=version_row.process_flow,
            set_flags=[QualityFlag.model_validate(flag) for flag in version_row.set_flags],
            counts=counts,
            added=[item_id for item_id in current_ids if item_id not in previous_ids] if previous_ids else current_ids,
            removed=sorted(previous_ids - set(current_ids)),
            review_responses=[ReviewResponse.model_validate(r) for r in version_row.review_responses or []],
            change_request=(
                self._cr_label(cr) if version_row.change_request_id and (cr := repository.get_change_request(self._session, version_row.change_request_id)) else None
            ),
            locked=self._artifacts.is_locked_baseline(artifact_id) and record.is_current,
            items=items,
            created_at=version_row.created_at,
        )
