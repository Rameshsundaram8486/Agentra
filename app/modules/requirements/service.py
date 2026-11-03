"""Business rules for requirement items; the only entry point for other modules.

A draft (from the Business Analyst agent) becomes a new version of the project's requirements baseline
document plus an immutable set of items linked to that version, so approving the document version approves
exactly those items. Rules enforced here, not by the agent:
- Item IDs are assigned by the server, per project and kind, and never reused. A draft keeps an item's ID by
  referring to it; an unknown or mismatched ID is refused.
- Status is derived: confirmed only for a fact with no unanswered decision behind it; assumptions and
  suggestions are proposed; open questions are open. A model cannot mark anything confirmed.
- An approved baseline cannot be redrafted; changes to it need a change request (Increment 3b).
"""

import re
import uuid

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.artifacts.service import ArtifactCreate, ArtifactsService, VersionCreate, VersionRecord
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.errors import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.requirements import repository
from app.modules.requirements.models import RequirementId, RequirementItem, RequirementVersion
from app.modules.requirements.quality_checks import CheckedItem, check_items
from app.modules.requirements.rendering import render_brd
from app.modules.requirements.schemas import (
    PREFIXES,
    DraftItem,
    DraftResult,
    QualityFlag,
    RequirementItemView,
    RequirementsDraft,
    RequirementsView,
    SourceRef,
    Status,
)

__all__ = ["BASELINE_TITLE", "BASELINE_TYPE", "DraftItem", "RequirementsDraft", "RequirementsService", "RequirementsView", "SourceRef"]

BASELINE_TYPE = "requirements_baseline"
BASELINE_TITLE = "Business requirements"
_ID = re.compile(r"^(?P<prefix>[A-Z]+(?:-[A-Z]+)?)-(?P<number>\d{3,})$")


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
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._decisions = decisions
        self._projects = projects

    # For agent tasks --------------------------------------------------------------------------

    def baseline_problem(self, project_id: uuid.UUID) -> str | None:
        """Why a new draft cannot be recorded now, or None."""
        record = self._baseline_record(project_id)
        if record is not None and self._decisions.approval_statuses([record.id])[record.id] == "approved":
            return (
                f"The requirements baseline v{record.version_no} is approved; changing it needs a change request, "
                "which arrives in Increment 3b"
            )
        return None

    def current_items(self, project_id: uuid.UUID) -> list[RequirementItemView]:
        """Items of the latest drafted version, for an agent revising them. Callers authorise first."""
        record = self._baseline_record(project_id)
        return [self._item_view(row) for row in repository.items_for(self._session, record.id)] if record else []

    def record_draft(self, actor: Actor, project_id: uuid.UUID, draft: RequirementsDraft) -> DraftResult:
        self._identity.require_project(actor, project_id, "artifact.author")
        draft = RequirementsDraft.model_validate(draft)
        if problem := self.baseline_problem(project_id):
            raise InvalidTransitionError(problem)

        ids = self._assign_ids(project_id, draft.items)
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
            },
        )
        return DraftResult(view=result_view, ids={item.ref: ids[item.ref] for item in draft.items})

    # Reads ----------------------------------------------------------------------------------

    def view(self, actor: Actor, project_id: uuid.UUID) -> RequirementsView | None:
        """The latest drafted requirements of a project, or None if nothing has been drafted."""
        self._identity.require_project(actor, project_id, "artifact.view")
        record = self._baseline_record(project_id)
        return self._view(record.artifact_id, record.id) if record else None

    # Helpers --------------------------------------------------------------------------------

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
            items=items,
            created_at=version_row.created_at,
        )
