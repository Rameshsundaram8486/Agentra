"""Business rules for the implementation backlog; the only entry point for other modules.

A draft (from the Developer agent) becomes a new version of the project's Implementation backlog document plus an
immutable set of epics and work items, tied to the approved design version it plans. Rules enforced here, not by
the agent (app/modules/backlog/rules.py):
- Only the current, approved, non-stale design can be planned.
- Epic and work item IDs are assigned by the server and never reused; a draft keeps an ID only by referring to it.
- Every buildable design item is implemented by at least one work item; references to design items, requirements
  and acceptance criteria must exist; dependencies stay inside the backlog, never point to a later wave and
  never form a cycle.
- Each work item traces to the requirements it states plus those its design items satisfy.
- A backlog is stale once the design it plans is no longer the current approved design. A stale backlog cannot
  be approved, and Phase 8 completes only with an approved backlog of the current design (exit check
  backlog_current).
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.artifacts.service import ArtifactCreate, ArtifactsService, VersionCreate, VersionRecord
from app.modules.audit.service import AuditService
from app.modules.backlog import repository
from app.modules.backlog.models import BacklogId, BacklogItem, BacklogVersion
from app.modules.backlog.rendering import render_backlog
from app.modules.backlog.rules import backlog_problems, parse_id
from app.modules.backlog.schemas import (
    EPIC_PREFIX,
    ITEM_PREFIX,
    BacklogDraft,
    BacklogReply,
    BacklogResult,
    BacklogView,
    EpicDraft,
    EpicView,
    WorkItemDraft,
    WorkItemView,
)
from app.modules.decisions.service import DecisionsService
from app.modules.design.service import DesignService, DesignView
from app.modules.errors import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.requirements.service import RequirementsService

__all__ = ["BACKLOG_TITLE", "BACKLOG_TYPE", "BacklogDraft", "BacklogReply", "BacklogService", "BacklogView", "EpicDraft", "WorkItemDraft"]

BACKLOG_TYPE = "implementation_backlog"
BACKLOG_TITLE = "Implementation backlog"


class BacklogService:
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

    # For agent tasks and other modules ------------------------------------------------------------

    def plan_target(self, project_id: uuid.UUID, design_version_id: uuid.UUID) -> DesignView:
        """The design version a backlog would plan, if it may be planned now: current, approved and not stale."""
        design = self._design.version_view(design_version_id)
        if design is None or self._artifacts.version_record(design_version_id).project_id != project_id:
            raise ValidationFailedError("Only a design drafted by the Solution Architect agent can be planned")
        if design_version_id != self._design.current_version_id(project_id):
            raise InvalidTransitionError(f"Design v{design.version_no} is no longer the current version; plan the current one")
        if design.stale_reason:
            raise InvalidTransitionError(design.stale_reason)
        if design.approval_status != "approved":
            raise InvalidTransitionError(f"Design v{design.version_no} is not approved; the backlog plans an approved design")
        return design

    def planning_context(self, design: DesignView) -> tuple[dict[str, str], dict[str, int]]:
        """(design item ID -> kind, requirement ID -> number of acceptance criteria) for checking a draft."""
        requirements_version = self._design.requirements_version_of(design.version_id)
        assert requirements_version is not None
        criteria = {r.item_id: len(r.acceptance_criteria) for r in self._requirements.items_of_version(requirements_version)}
        return {i.item_id: i.kind for i in design.items}, criteria

    def known_ids(self, project_id: uuid.UUID) -> tuple[set[str], set[str]]:
        rows = repository.registered_ids(self._session, project_id)
        return {r.item_id for r in rows if r.kind == "epic"}, {r.item_id for r in rows if r.kind == "work_item"}

    def current_items(self, project_id: uuid.UUID) -> tuple[list[EpicView], list[WorkItemView]]:
        record = self._record(project_id)
        if record is None:
            return [], []
        row = repository.version_for(self._session, record.id)
        assert row is not None
        return [EpicView.model_validate(e) for e in row.epics], [self._item_view(i) for i in repository.items_for(self._session, record.id)]

    def current_version_id(self, project_id: uuid.UUID) -> uuid.UUID | None:
        record = self._record(project_id)
        return record.id if record else None

    def planned_design(self, version_id: uuid.UUID) -> uuid.UUID | None:
        """The design version a backlog version plans."""
        row = repository.version_for(self._session, version_id)
        return row.design_version_id if row else None

    def stale_reason(self, version_id: uuid.UUID) -> str | None:
        row = repository.version_for(self._session, version_id)
        if row is None:
            return None
        planned = self._artifacts.version_record(row.design_version_id)
        current = self._design.current_version_id(row.project_id)
        if current != row.design_version_id:
            now = f"v{self._artifacts.version_record(current).version_no}" if current else "missing"
            return f"The backlog is stale: it plans design v{planned.version_no}, and the design is now {now}"
        design = self._design.version_view(current)
        if design is None or design.stale or design.approval_status != "approved":
            return f"The backlog is stale: design v{planned.version_no} is no longer approved"
        return None

    def approval_problems(self, version_id: uuid.UUID) -> list[str]:
        """Checked before a backlog version is approved: a stale backlog cannot be."""
        reason = self.stale_reason(version_id)
        return [reason] if reason else []

    def gate_failures(self, project_id: uuid.UUID) -> list[str]:
        """Phase exit check backlog_current: an approved backlog of the current approved design."""
        record = self._record(project_id)
        if record is None:
            return ["No implementation backlog yet; ask the Developer agent to plan the approved design"]
        if reason := self.stale_reason(record.id):
            return [reason]
        if self._decisions.approval_statuses([record.id])[record.id] != "approved":
            return [f"Implementation backlog v{record.version_no} is not approved"]
        return []

    def requirement_lookup(self, project_id: uuid.UUID) -> dict[str, list[str]] | None:
        """Requirement ID -> work item IDs of the current backlog; None before there is one."""
        record = self._record(project_id)
        if record is None:
            return None
        found: dict[str, list[str]] = {}
        for item in repository.items_for(self._session, record.id):
            for rid in item.requirements:
                found.setdefault(rid, []).append(item.item_id)
        return found

    def design_item_lookup(self, project_id: uuid.UUID) -> dict[str, list[str]] | None:
        """Design item ID -> work item IDs of the current backlog; None before there is one."""
        record = self._record(project_id)
        if record is None:
            return None
        found: dict[str, list[str]] = {}
        for item in repository.items_for(self._session, record.id):
            for design_item in item.design_items:
                found.setdefault(design_item, []).append(item.item_id)
        return found

    # Commands ----------------------------------------------------------------------------------------

    def record_draft(self, actor: Actor, project_id: uuid.UUID, draft: BacklogDraft) -> BacklogResult:
        self._identity.require_project(actor, project_id, "artifact.author")
        draft = BacklogDraft.model_validate(draft)
        design = self.plan_target(project_id, draft.design_version_id)
        design_items, criteria = self.planning_context(design)
        known_epics, known_items = self.known_ids(project_id)
        problems = backlog_problems(draft.epics, draft.items, design_items=design_items, criteria=criteria, known_epics=known_epics, known_items=known_items)
        if problems:
            raise ValidationFailedError("; ".join(f"{path}: {message}" for path, message in problems[:20]))

        ids = self._assign_ids(project_id, draft)
        satisfies = {i.item_id: i.satisfies for i in design.items}
        epics = [EpicView(epic_id=ids[e.ref], title=e.title.strip(), description=e.description.strip()) for e in draft.epics]
        items = [
            WorkItemView(
                item_id=ids[i.ref],
                epic_id=ids[i.epic],
                title=i.title.strip(),
                description=i.description.strip(),
                work_type=i.work_type,
                design_items=list(dict.fromkeys(i.design_items)),
                requirements=sorted(set(i.requirements) | {r for d in i.design_items for r in satisfies.get(d, [])}),
                acceptance=list(dict.fromkeys(i.acceptance)),
                estimate=i.estimate,
                depends_on=[ids[d] for d in dict.fromkeys(i.depends_on)],
                wave=i.wave,
            )
            for i in draft.items
        ]
        project = self._projects.get_project(actor, project_id)
        design_record = self._artifacts.version_record(design.version_id)
        content = render_backlog(
            project_name=project.name,
            design_label=f"{design_record.artifact_title} v{design.version_no} (sha256 {design_record.content_sha256[:12]})",
            summary=draft.summary,
            epics=epics,
            items=items,
            review_responses=draft.review_responses,
        )
        source_refs = [f"{design_record.artifact_title} v{design.version_no}"]
        previous = self._record(project_id)
        if previous is None:
            detail = self._artifacts.create_artifact(
                actor, project_id, ArtifactCreate(artifact_type=BACKLOG_TYPE, title=BACKLOG_TITLE, content=content, change_summary=draft.change_summary, source_refs=source_refs)
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
            BacklogVersion(
                project_id=project_id,
                artifact_id=detail.id,
                artifact_version_id=version.id,
                design_version_id=design.version_id,
                summary=draft.summary.strip(),
                epics=[e.model_dump() for e in epics],
                review_responses=[r.model_dump(mode="json") for r in draft.review_responses],
                created_at=now,
            ),
        )
        registered = {row.item_id for row in repository.registered_ids(self._session, project_id)}
        for kind, new_ids in (("epic", [e.epic_id for e in epics]), ("work_item", [i.item_id for i in items])):
            for item_id in new_ids:
                if item_id not in registered:
                    _, number = parse_id(item_id)  # type: ignore[misc]
                    self._session.add(BacklogId(project_id=project_id, item_id=item_id, kind=kind, number=number, first_artifact_version_id=version.id, created_at=now))
        for position, item in enumerate(items):
            self._session.add(BacklogItem(project_id=project_id, artifact_version_id=version.id, position=position, created_at=now, **item.model_dump()))
        self._session.flush()
        view = self._view(version.id)
        self._audit.record(
            actor_id=actor.id,
            action="backlog.draft",
            entity_type="artifact_version",
            entity_id=version.id,
            project_id=project_id,
            after={"version_no": view.version_no, "design_version_no": design.version_no, "epics": len(epics), "items": len(items), "estimates": view.estimates},
        )
        return BacklogResult(view=view, ids={ref: ids[ref] for ref in [*(e.ref for e in draft.epics), *(i.ref for i in draft.items)]})

    # Reads -------------------------------------------------------------------------------------------

    def view(self, actor: Actor, project_id: uuid.UUID) -> BacklogView | None:
        self._identity.require_project(actor, project_id, "artifact.view")
        record = self._record(project_id)
        return self._view(record.id) if record else None

    # Helpers -----------------------------------------------------------------------------------------

    def _record(self, project_id: uuid.UUID) -> VersionRecord | None:
        records = [r for r in self._artifacts.current_records_of_type(project_id, BACKLOG_TYPE) if r.artifact_title == BACKLOG_TITLE]
        if not records or repository.version_for(self._session, records[0].id) is None:
            return None
        return records[0]

    def _assign_ids(self, project_id: uuid.UUID, draft: BacklogDraft) -> dict[str, str]:
        registered = {row.item_id: row for row in repository.registered_ids(self._session, project_id)}
        next_number = {EPIC_PREFIX: 1, ITEM_PREFIX: 1}
        for row in registered.values():
            prefix = EPIC_PREFIX if row.kind == "epic" else ITEM_PREFIX
            next_number[prefix] = max(next_number[prefix], row.number + 1)
        ids: dict[str, str] = {}
        for prefix, refs in ((EPIC_PREFIX, [e.ref for e in draft.epics]), (ITEM_PREFIX, [i.ref for i in draft.items])):
            for ref in refs:
                if ref in registered:
                    ids[ref] = ref
            for ref in refs:
                if ref not in ids:
                    ids[ref] = f"{prefix}-{next_number[prefix]:03d}"
                    next_number[prefix] += 1
        return ids

    @staticmethod
    def _item_view(row: BacklogItem) -> WorkItemView:
        return WorkItemView(
            item_id=row.item_id,
            epic_id=row.epic_id,
            title=row.title,
            description=row.description,
            work_type=row.work_type,  # type: ignore[arg-type]
            design_items=row.design_items,
            requirements=row.requirements,
            acceptance=row.acceptance,
            estimate=row.estimate,  # type: ignore[arg-type]
            depends_on=row.depends_on,
            wave=row.wave,
        )

    def _view(self, version_id: uuid.UUID) -> BacklogView:
        row = repository.version_for(self._session, version_id)
        if row is None:
            raise NotFoundError("No drafted backlog for this version")
        record = self._artifacts.version_record(version_id)
        items = [self._item_view(i) for i in repository.items_for(self._session, version_id)]
        stale = self.stale_reason(version_id)
        waves: dict[int, int] = {}
        for item in items:
            waves[item.wave] = waves.get(item.wave, 0) + 1
        return BacklogView(
            artifact_id=row.artifact_id,
            artifact_title=record.artifact_title,
            version_id=version_id,
            version_no=record.version_no,
            approval_status=self._decisions.approval_statuses([version_id])[version_id],
            design_version_id=row.design_version_id,
            design_version_no=self._artifacts.version_record(row.design_version_id).version_no,
            stale=stale is not None,
            stale_reason=stale,
            summary=row.summary,
            epics=[EpicView.model_validate(e) for e in row.epics],
            items=items,
            estimates={size: sum(1 for i in items if i.estimate == size) for size in ("S", "M", "L")},
            waves=dict(sorted(waves.items())),
            review_responses=[BacklogReply.model_validate(r) for r in row.review_responses],
            created_at=row.created_at,
        )
