"""Business rules for workflow state; the only entry point for other modules.

Every state change goes through `_apply`: access check, optimistic version check, lifecycle and role check,
gates, compare-and-set update, a StateTransition row and an audit event, all in the caller's transaction.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.errors import (
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.modules.identity.service import Actor, IdentityService
from app.modules.workflow import repository
from app.modules.workflow.definitions import Lifecycle, PhaseDefinition, WorkflowCatalog
from app.modules.workflow.gates import (
    CANCELLED,
    COMPLETED,
    IN_PROGRESS,
    phase_entry_failures,
    phase_exit_failures,
    task_start_failures,
)
from app.modules.workflow.models import PhaseRun, StateTransition, Task
from app.modules.workflow.schemas import PhaseRunView, StateTransitionView, TaskView, TransitionRequest
from app.modules.workflow.state_machine import allowed_targets, check_transition

__all__ = ["PhaseRunView", "StateTransitionView", "TaskView", "TransitionRequest", "WorkflowService"]


class WorkflowService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        catalog: WorkflowCatalog,
        audit: AuditService,
        identity: IdentityService,
        decisions: DecisionsService,
    ) -> None:
        self._session = session
        self._clock = clock
        self._catalog = catalog
        self._audit = audit
        self._identity = identity
        self._decisions = decisions

    def open_project(self, actor: Actor, project_id: uuid.UUID) -> None:
        """Creates a phase run (and its tasks) for every defined phase. Called by the projects service."""
        now = self._clock.now()
        opened = {}
        for number in sorted(self._catalog.phases):
            definition = self._catalog.phase(number)
            run = PhaseRun(
                project_id=project_id,
                phase=number,
                definition_key=definition.key,
                definition_version=definition.version,
                state=self._catalog.lifecycle(definition.lifecycle).initial_state,
                version=1,
                created_at=now,
                updated_at=now,
            )
            repository.add(self._session, run)
            task_state = self._catalog.lifecycle(definition.task_lifecycle).initial_state
            for position, task in enumerate(definition.tasks):
                repository.add(
                    self._session,
                    Task(
                        phase_run_id=run.id,
                        project_id=project_id,
                        key=task.key,
                        position=position,
                        title=task.title,
                        agent=task.agent,
                        depends_on=list(task.depends_on),
                        state=task_state,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    ),
                )
            opened[str(number)] = f"{definition.key}@v{definition.version}"
        self._audit.record(
            actor_id=actor.id,
            action="workflow.open_project",
            entity_type="project",
            entity_id=project_id,
            project_id=project_id,
            after={"phases": opened},
        )

    # Reads ----------------------------------------------------------------------------------

    def list_phase_runs(self, actor: Actor, project_id: uuid.UUID) -> list[PhaseRunView]:
        self._identity.require_project(actor, project_id, "project.view")
        roles = self._identity.roles_for(actor, project_id)
        tasks_by_run: dict[uuid.UUID, list[Task]] = defaultdict(list)
        for task in repository.tasks_for_project(self._session, project_id):
            tasks_by_run[task.phase_run_id].append(task)
        return [
            self._phase_view(run, tasks_by_run[run.id], roles)
            for run in repository.phase_runs_for_project(self._session, project_id)
        ]

    def task_by_key(self, project_id: uuid.UUID, phase: int, key: str) -> TaskView | None:
        """One task of a phase, or None. Callers authorise first. available_transitions is left empty."""
        run = repository.get_phase_run_for(self._session, project_id, phase)
        if run is None:
            return None
        task = next((t for t in repository.tasks_for_phase_run(self._session, run.id) if t.key == key), None)
        if task is None:
            return None
        return self._task_view(task, self._catalog.lifecycle(self._definition(run).task_lifecycle), frozenset())

    def task_view(self, task_id: uuid.UUID) -> TaskView:
        """Callers authorise first. available_transitions is left empty."""
        task = self._load("task", task_id)
        run = self._load("phase_run", task.phase_run_id)
        return self._task_view(task, self._catalog.lifecycle(self._definition(run).task_lifecycle), frozenset())  # type: ignore[arg-type]

    def sync_tasks(self, actor: Actor, project_id: uuid.UUID) -> list[str]:
        """Adds tasks defined in config after the project opened to its unfinished phases. Returns phase.task keys added."""
        self._identity.require_project(actor, project_id, "project.manage_members")
        now, added = self._clock.now(), []
        for run in repository.phase_runs_for_project(self._session, project_id):
            if run.phase not in self._catalog.phases or run.state in (COMPLETED, CANCELLED):
                continue
            definition = self._catalog.phase(run.phase)
            existing = {task.key for task in repository.tasks_for_phase_run(self._session, run.id)}
            initial = self._catalog.lifecycle(definition.task_lifecycle).initial_state
            for position, task in enumerate(definition.tasks):
                if task.key in existing:
                    continue
                repository.add(
                    self._session,
                    Task(
                        phase_run_id=run.id,
                        project_id=project_id,
                        key=task.key,
                        position=position,
                        title=task.title,
                        agent=task.agent,
                        depends_on=list(task.depends_on),
                        state=initial,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    ),
                )
                added.append(f"{run.phase}.{task.key}")
            run.definition_version = definition.version
        if added:
            self._session.flush()
            self._audit.record(
                actor_id=actor.id,
                action="workflow.sync_tasks",
                entity_type="project",
                entity_id=project_id,
                project_id=project_id,
                after={"added": added},
            )
        return added

    def phase_state(self, project_id: uuid.UUID, phase: int) -> str | None:
        """Current state of one phase, or None if the project has no run for it. Callers authorise first."""
        run = repository.get_phase_run_for(self._session, project_id, phase)
        return run.state if run else None

    def history(self, actor: Actor, entity_type: str, entity_id: uuid.UUID) -> list[StateTransitionView]:
        entity = self._load(entity_type, entity_id)
        self._identity.require_project(actor, entity.project_id, "project.view")
        return [
            StateTransitionView.model_validate(row, from_attributes=True)
            for row in repository.transitions_for(self._session, entity_type, entity_id)
        ]

    # State changes --------------------------------------------------------------------------

    def transition_phase_run(
        self, actor: Actor, phase_run_id: uuid.UUID, request: TransitionRequest
    ) -> PhaseRunView:
        run = self._load("phase_run", phase_run_id)
        self._identity.require_project(actor, run.project_id, "project.view")
        definition = self._definition(run)
        lifecycle = self._catalog.lifecycle(definition.lifecycle)
        initial_state = lifecycle.initial_state

        def gates(from_state: str, to_state: str) -> list[str]:
            failures = []
            if from_state == initial_state and to_state != CANCELLED:
                phase_states = {
                    other.phase: other.state for other in repository.phase_runs_for_project(self._session, run.project_id)
                }
                failures += phase_entry_failures(definition, phase_states)
            if to_state == COMPLETED:
                tasks = repository.tasks_for_phase_run(self._session, run.id)
                failures += phase_exit_failures({task.key: task.state for task in tasks})
                failures += self._decisions.approval_gate_failures(run.project_id, definition.exit.required_approvals)
            return failures

        self._apply(actor, "phase_run", PhaseRun, run, lifecycle, request, gates)
        roles = self._identity.roles_for(actor, run.project_id)
        return self._phase_view(run, repository.tasks_for_phase_run(self._session, run.id), roles)

    def transition_task(self, actor: Actor, task_id: uuid.UUID, request: TransitionRequest) -> TaskView:
        task = self._load("task", task_id)
        self._identity.require_project(actor, task.project_id, "project.view")
        run = self._load("phase_run", task.phase_run_id)
        definition = self._definition(run)
        lifecycle = self._catalog.lifecycle(definition.task_lifecycle)
        if actor.kind == "agent" and self._identity.agent_key_of(actor) != task.agent:
            raise PermissionDeniedError("An agent may only move tasks assigned to it")
        required = next((t.required_approvals for t in definition.tasks if t.key == task.key), ())

        def gates(_from_state: str, to_state: str) -> list[str]:
            if to_state == COMPLETED:
                return self._decisions.approval_gate_failures(run.project_id, required)
            if to_state != IN_PROGRESS:
                return []
            siblings = repository.tasks_for_phase_run(self._session, run.id)
            return task_start_failures(run.state, tuple(task.depends_on), {other.key: other.state for other in siblings})

        self._apply(actor, "task", Task, task, lifecycle, request, gates)
        return self._task_view(task, lifecycle, self._identity.roles_for(actor, task.project_id))

    def _apply(
        self,
        actor: Actor,
        entity_type: str,
        model: type[PhaseRun] | type[Task],
        entity: PhaseRun | Task,
        lifecycle: Lifecycle,
        request: TransitionRequest,
        gate_failures: Callable[[str, str], list[str]],
    ) -> None:
        request = TransitionRequest.model_validate(request)
        label = "phase" if entity_type == "phase_run" else "task"
        reason = request.reason.strip()
        if len(reason) < 3:
            raise ValidationFailedError("A reason of at least 3 characters is required")
        if entity.version != request.expected_version:
            raise ConflictError(
                f"This {label} changed since you loaded it (now version {entity.version}); reload and try again"
            )

        entity_id, project_id, from_state, from_version = entity.id, entity.project_id, entity.state, entity.version
        check_transition(lifecycle, from_state, request.to_state, self._identity.roles_for(actor, project_id))
        failures = gate_failures(from_state, request.to_state)
        if failures:
            raise InvalidTransitionError(f"Cannot move this {label} to '{request.to_state}': " + "; ".join(failures))

        now = self._clock.now()
        if not repository.compare_and_set_state(
            self._session, model, entity_id, request.expected_version, request.to_state, now
        ):
            raise ConflictError(f"This {label} was changed by someone else just now; reload and try again")
        repository.add(
            self._session,
            StateTransition(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
                from_state=from_state,
                to_state=request.to_state,
                actor_id=actor.id,
                reason=reason,
                occurred_at=now,
            ),
        )
        self._audit.record(
            actor_id=actor.id,
            action=f"workflow.{entity_type}_transition",
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            reason=reason,
            before={"state": from_state, "version": from_version},
            after={"state": request.to_state, "version": from_version + 1},
        )

    # Helpers --------------------------------------------------------------------------------

    def _load(self, entity_type: str, entity_id: uuid.UUID) -> PhaseRun | Task:
        entity = (
            repository.get_phase_run(self._session, entity_id)
            if entity_type == "phase_run"
            else repository.get_task(self._session, entity_id)
        )
        if entity is None:
            raise NotFoundError("Phase not found" if entity_type == "phase_run" else "Task not found")
        return entity

    def _definition(self, run: PhaseRun) -> PhaseDefinition:
        if run.phase not in self._catalog.phases:
            raise InvalidTransitionError(f"Phase {run.phase} has no workflow definition")
        return self._catalog.phase(run.phase)

    def _phase_view(self, run: PhaseRun, tasks: list[Task], roles: frozenset[str]) -> PhaseRunView:
        definition = self._definition(run)
        task_lifecycle = self._catalog.lifecycle(definition.task_lifecycle)
        return PhaseRunView(
            id=run.id,
            project_id=run.project_id,
            phase=run.phase,
            name=definition.name,
            primary_agent=definition.primary_agent,
            definition_key=run.definition_key,
            definition_version=run.definition_version,
            state=run.state,
            version=run.version,
            updated_at=run.updated_at,
            available_transitions=allowed_targets(self._catalog.lifecycle(definition.lifecycle), run.state, roles),
            required_approvals=list(definition.exit.required_approvals),
            tasks=[self._task_view(task, task_lifecycle, roles) for task in tasks],
        )

    @staticmethod
    def _task_view(task: Task, lifecycle: Lifecycle, roles: frozenset[str]) -> TaskView:
        return TaskView(
            id=task.id,
            phase_run_id=task.phase_run_id,
            key=task.key,
            title=task.title,
            agent=task.agent,
            depends_on=list(task.depends_on),
            state=task.state,
            version=task.version,
            updated_at=task.updated_at,
            available_transitions=allowed_targets(lifecycle, task.state, roles),
        )
