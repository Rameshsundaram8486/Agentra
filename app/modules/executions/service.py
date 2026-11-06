"""Business rules for agent runs and model calls; the only entry point for other modules.

A person asks for an agent task on a document version; the run and its background job are created in one
transaction. Asking again for the same version returns the existing run unless every earlier run failed or
was blocked. Preconditions (phase state, the agent's membership) are checked when asked and again when the
worker starts, because either can change in between. Workers call start_run / finish_run and the ledger
methods; people only request and read.
"""

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.guardrails.input.scope import input_problems
from app.harness.registry import AgentRegistry, TaskDefinition, task_refs
from app.infrastructure.clock import Clock
from app.infrastructure.job_queue import JobQueue
from app.model_gateway.errors import BudgetExceededError
from app.model_gateway.gateway import CallIntent, CallOutcome
from app.modules.artifacts.service import ArtifactsService
from app.modules.audit.service import AuditService
from app.modules.decisions.service import DecisionsService
from app.modules.errors import DomainError, InvalidTransitionError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.executions import repository
from app.modules.executions.models import AgentRun, ModelCall
from app.modules.executions.schemas import (
    AgentRunCreate,
    AgentRunDetail,
    AgentRunView,
    FindingView,
    ModelCallView,
    RunRequestResult,
    RunStatus,
    StartedRun,
)
from app.modules.identity.service import SYSTEM_ACTOR, Actor, IdentityService
from app.modules.oversight.service import OversightService
from app.modules.workflow.service import TaskView, TransitionRequest, WorkflowService

__all__ = ["AGENT_RUN_JOB", "AgentRunCreate", "AgentRunDetail", "AgentRunView", "ExecutionsService", "StartedRun"]

AGENT_RUN_JOB = "agent_run"
_ACTIVE = ("queued", "running", "succeeded")
_BUSY = ("queued", "running")
_TERMINAL = ("succeeded", "failed", "blocked")
# How asking for a run moves its workflow task to in_progress, from each state.
_START_PATHS: dict[str, list[str]] = {
    "not_started": ["ready", "in_progress"],
    "ready": ["in_progress"],
    "blocked": ["ready", "in_progress"],
    "failed": ["ready", "in_progress"],
    "waiting_for_input": ["in_progress"],
    "changes_requested": ["in_progress"],
    "waiting_for_review": ["changes_requested", "in_progress"],
    "in_progress": [],
}


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class ExecutionsService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        artifacts: ArtifactsService,
        workflow: WorkflowService,
        decisions: DecisionsService,
        oversight: OversightService,
        registry: AgentRegistry,
        subject_context: Mapping[str, Callable[[uuid.UUID, str], dict[str, Any]]] | None = None,
    ) -> None:
        """subject_context[kind](project_id, subject): what a run on one subject works from besides its input (review
        comment IDs under "reviews", and whatever else should make asking again start a new run). Raises a
        DomainError for an unknown subject. From the module that owns the subject (app/composition.py)."""
        self._subject_context = subject_context or {}
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._workflow = workflow
        self._decisions = decisions
        self._oversight = oversight
        self._registry = registry

    # Requests and reads ---------------------------------------------------------------------

    def request_run(self, actor: Actor, project_id: uuid.UUID, data: AgentRunCreate) -> RunRequestResult:
        self._identity.require_project(actor, project_id, "agent.run")
        data = AgentRunCreate.model_validate(data)
        task = self._registry.task(data.agent_key, data.task_key)
        if task is None:
            raise NotFoundError(f"Unknown agent task {data.agent_key}.{data.task_key}")
        record = self._artifacts.version_record(data.artifact_version_id)
        if record.project_id != project_id:
            raise NotFoundError("Document version not found")
        problems = input_problems(record, project_id, task.spec.input_artifact_types)
        if task.spec.input_must_be_approved and self._decisions.approval_statuses([record.id])[record.id] != "approved":
            problems.append(f"'{record.artifact_title}' v{record.version_no} is not approved yet; this task builds on an approved version")
        agent, blockers = self._readiness(project_id, task)
        if problems or blockers:
            raise ValidationFailedError(f"The {task.agent_name} cannot start yet: {'; '.join(problems + blockers)}")
        assert agent is not None
        if task.spec.requires_change_request != (data.change_request_id is not None):
            raise ValidationFailedError(
                "Name the change request to apply" if task.spec.requires_change_request else "This task does not apply a change request"
            )
        if (task.spec.subject is not None) != (data.subject is not None):
            raise ValidationFailedError("Name the work item to work on" if task.spec.subject else "This task does not work on one work item")
        workflow_task = None
        if task.spec.subject is not None:
            assert data.subject is not None
            subject_context = self._subject_context[task.spec.subject](project_id, data.subject)
            workflow_task = self._workflow.task_by_subject(project_id, task.spec.phase, data.subject)
            if workflow_task is None:
                raise ValidationFailedError(f"Phase {task.spec.phase} has no task for {data.subject} yet; it is added when the phase starts")
        elif task.spec.workflow_task is not None:
            workflow_task = self._workflow.task_by_key(project_id, task.spec.phase, task.spec.workflow_task)
            if workflow_task is None:
                raise ValidationFailedError(f"This project has no '{task.spec.workflow_task}' task in Phase {task.spec.phase}")
        if workflow_task is not None and workflow_task.state not in _START_PATHS and not self._new_input_for_closed_task(workflow_task, record.id):
            raise InvalidTransitionError(f"The '{workflow_task.title}' task is {workflow_task.state.replace('_', ' ')}")

        context = self._context_snapshot(actor, project_id, task)
        if data.change_request_id is not None:
            context["change_request"] = str(data.change_request_id)
        if data.subject is not None:
            context = {**context, **subject_context, "subject": data.subject}
        fingerprint = hashlib.sha256(json.dumps({"input": str(record.id), **context}, sort_keys=True).encode()).hexdigest()[:16]
        earlier = repository.runs_for_input(self._session, task.agent_key, task.key, record.id)
        if data.subject is not None:
            earlier = [r for r in earlier if (r.input_refs or {}).get("subject") == data.subject]
        same = next((r for r in reversed(earlier) if r.status in _ACTIVE and r.input_refs.get("fingerprint") == fingerprint), None)
        if same is not None:
            return RunRequestResult(run=self._views([same])[0], created=False)
        busy = [
            r
            for r in repository.runs_for_project(self._session, project_id)
            if r.status in _BUSY and (r.task_id == workflow_task.id if workflow_task else (r.agent_key, r.task_key) == (task.agent_key, task.key))
        ]
        if busy:
            raise InvalidTransitionError(f"The {task.agent_name} is already working on '{task.spec.title}'; wait for that run to finish")

        now = self._clock.now()
        run = AgentRun(
            project_id=project_id,
            agent_key=task.agent_key,
            task_key=task.key,
            agent_user_id=agent.id,
            agent_version=task.agent_version,
            prompt_version=task.prompt.version,
            schema_version=task.schema_file.version,
            input_artifact_version_id=record.id,
            input_refs={**context, "fingerprint": fingerprint},
            task_id=workflow_task.id if workflow_task else None,
            idempotency_key=f"{task.agent_key}.{task.key}:{record.id}:{data.subject or '-'}:{fingerprint}:{len(earlier) + 1}",
            status="queued",
            attempts=0,
            max_attempts=task.spec.max_attempts,
            requested_by=actor.id,
            findings=[],
            cost_usd=Decimal(0),
            created_at=now,
            updated_at=now,
        )
        try:
            with self._session.begin_nested():
                repository.add(self._session, run)
        except IntegrityError:
            # Someone asked for the same thing at the same moment; theirs won.
            winner = next(
                r
                for r in repository.runs_for_input(self._session, task.agent_key, task.key, record.id)
                if r.status in _ACTIVE and (r.input_refs or {}).get("subject") == data.subject
            )
            return RunRequestResult(run=self._views([winner])[0], created=False)
        if workflow_task is not None and workflow_task.state in _START_PATHS:
            # Why Agentra may send a task waiting for review back itself: comments or findings to answer, or a new
            # version of what the task works from (for example a redrafted design to review again).
            system_reason = None
            if context["reviews"] or context.get("findings"):
                system_reason = "A reviewer requested changes on the document, or a review has findings to answer"
            else:
                done = [r for r in repository.runs_for_task(self._session, workflow_task.id) if r.status == "succeeded"]
                if done and done[-1].input_artifact_version_id != record.id:
                    system_reason = f"There is a new version to work from: '{record.artifact_title}' v{record.version_no}"
            self._start_task(workflow_task, f"Asked the {task.agent_name}: {task.spec.title}", actor, agent, system_reason=system_reason)
        run.job_id = JobQueue(self._session, self._clock).enqueue(
            AGENT_RUN_JOB, {"agent_run_id": str(run.id)}, run.idempotency_key, max_attempts=task.spec.max_attempts
        )
        self._session.flush()
        self._audit.record(
            actor_id=actor.id,
            action="agent_run.request",
            entity_type="agent_run",
            entity_id=run.id,
            project_id=project_id,
            after={
                "agent": task.agent_key,
                "task": task.key,
                "input": {"artifact_id": str(record.artifact_id), "version_no": record.version_no, "sha256": record.content_sha256},
                "prompt_version": run.prompt_version,
                "context": context,
            },
        )
        return RunRequestResult(run=self._views([run])[0], created=True)

    def list_runs(self, actor: Actor, project_id: uuid.UUID) -> list[AgentRunView]:
        self._identity.require_project(actor, project_id, "agent_run.view")
        return self._views(repository.runs_for_project(self._session, project_id))

    def get_run(self, actor: Actor, run_id: uuid.UUID) -> AgentRunDetail:
        run = repository.get_run(self._session, run_id)
        if run is None:
            raise NotFoundError("Agent run not found")
        self._identity.require_project(actor, run.project_id, "agent_run.view")
        view = self._views([run])[0]
        calls = repository.calls_for_runs(self._session, [run.id])
        return AgentRunDetail(
            **view.model_dump(),
            model_calls=[ModelCallView.model_validate(call, from_attributes=True) for call in calls],
            output=run.output,
        )

    # Worker side ----------------------------------------------------------------------------

    def start_run(self, run_id: uuid.UUID) -> StartedRun | None:
        """Starts one attempt. None when there is nothing to do: already finished, or blocked just now."""
        run = repository.get_run(self._session, run_id, for_update=True)
        if run is None:
            raise NotFoundError("Agent run not found")
        if run.status in _TERMINAL:
            return None
        now = self._clock.now()
        repository.abandon_pending_calls(self._session, run.id, now)
        run.attempts += 1
        run.status = "running"
        run.started_at = run.started_at or now
        run.updated_at = now
        task = self._registry.task(run.agent_key, run.task_key)
        blockers = ["this agent task no longer exists"] if task is None else self._readiness(run.project_id, task)[1]
        if run.task_id is not None and (current := self._workflow.task_view(run.task_id)).state != "in_progress":
            if not self._new_input_for_closed_task(current, run.input_artifact_version_id):
                blockers.append(f"the '{current.title}' task is now {current.state.replace('_', ' ')}")
        if blockers:
            self._session.flush()
            self.finish_run(run.id, status="blocked", error_code="precondition", error_message="; ".join(blockers))
            return None
        self._session.flush()
        return StartedRun(
            run_id=run.id,
            project_id=run.project_id,
            agent_key=run.agent_key,
            task_key=run.task_key,
            agent=self._identity.get_actor(run.agent_user_id),
            input_artifact_version_id=run.input_artifact_version_id,
            input_refs=dict(run.input_refs or {}),
            task_id=run.task_id,
            attempt=run.attempts,
            max_attempts=run.max_attempts,
        )

    def finish_run(
        self,
        run_id: uuid.UUID,
        *,
        status: RunStatus,
        output: dict[str, Any] | None = None,
        findings: list[dict[str, Any]] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        task_state: str | None = None,
    ) -> None:
        """Records the outcome and moves the workflow task: to task_state if given, otherwise to failed or blocked
        for a failed or blocked run. A task someone already moved elsewhere is left alone."""
        run = repository.get_run(self._session, run_id, for_update=True)
        if run is None:
            raise NotFoundError("Agent run not found")
        if status not in _TERMINAL:
            raise ValueError(f"finish_run needs a final status, not {status}")
        if run.status in _TERMINAL:
            return  # the first final status stands
        now = self._clock.now()
        run.status = status
        run.output = output
        run.findings = findings or []
        run.error_code = error_code
        run.error_message = (error_message or "")[:4000] or None
        run.finished_at = run.updated_at = now
        self._session.flush()
        self._audit.record(
            actor_id=run.agent_user_id,
            action=f"agent_run.{status}",
            entity_type="agent_run",
            entity_id=run.id,
            project_id=run.project_id,
            reason=run.error_message,
            after={
                "status": status,
                "error_code": error_code,
                "attempts": run.attempts,
                "decision_ids": (output or {}).get("decision_ids", []),
                "findings": len(run.findings),
                "cost_usd": str(run.cost_usd),
            },
        )
        if status in ("failed", "blocked"):
            self._record_incident(run)
        target = task_state or {"failed": "failed", "blocked": "blocked"}.get(status)
        if run.task_id is not None and target is not None:
            agent = self._identity.get_actor(run.agent_user_id)
            actor = agent if target in ("waiting_for_input", "waiting_for_review") else SYSTEM_ACTOR
            reason = f"Agent run {status}" + (f": {run.error_message}" if run.error_message else "")
            self._move_task(run.task_id, target, actor, reason[:2000])

    # Spend ledger (called by the model gateway through the harness) -------------------------

    def reserve_model_call(self, run_id: uuid.UUID, intent: CallIntent) -> uuid.UUID:
        run = repository.get_run(self._session, run_id)
        if run is None:
            raise NotFoundError("Agent run not found")
        repository.lock_budget(self._session)
        now = self._clock.now()
        spent = repository.spend_since(self._session, _month_start(now))
        if spent + intent.reserved_usd > intent.budget_usd:
            raise BudgetExceededError(
                f"The monthly model budget of ${intent.budget_usd} would be exceeded: ${spent:.2f} used this month, "
                f"and this call may cost up to ${intent.reserved_usd:.2f}. Raise budget.monthly_usd in config/models.yaml "
                "or wait until next month."
            )
        call = ModelCall(
            agent_run_id=run.id,
            project_id=run.project_id,
            agent_key=intent.agent_key,
            provider=intent.provider,
            requested_model=intent.profile.model,
            effort=intent.profile.effort,
            max_tokens=intent.profile.max_tokens,
            prompt_version=intent.prompt_version,
            schema_version=intent.schema_version,
            status="pending",
            fallback_used=False,
            input_tokens=0,
            output_tokens=0,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            reserved_usd=intent.reserved_usd,
            created_at=now,
        )
        repository.add(self._session, call)
        return call.id

    def settle_model_call(self, call_id: uuid.UUID, outcome: CallOutcome) -> None:
        call = repository.get_call(self._session, call_id)
        if call is None:
            raise NotFoundError("Model call not found")
        response = outcome.response
        call.status = outcome.status
        call.cost_usd = outcome.cost_usd
        call.cost_exact = outcome.cost_exact
        call.latency_ms = outcome.latency_ms
        call.error = outcome.error
        call.settled_at = self._clock.now()
        if response is not None:
            usage = response.usage
            call.model = response.model
            call.stop_reason = response.stop_reason
            call.refusal_category = response.refusal_category
            call.fallback_used = response.fallback_used
            call.input_tokens = usage.input_tokens
            call.output_tokens = usage.output_tokens
            call.cache_creation_input_tokens = usage.cache_creation_input_tokens
            call.cache_read_input_tokens = usage.cache_read_input_tokens
            call.request_id = response.request_id
        run = repository.get_run(self._session, call.agent_run_id, for_update=True)
        if run is not None:
            run.cost_usd += outcome.cost_usd
            run.updated_at = self._clock.now()
        self._session.flush()

    def month_spend(self) -> Decimal:
        return repository.spend_since(self._session, _month_start(self._clock.now()))

    def open_questions(self, task_id: uuid.UUID) -> int:
        """How many questions raised by succeeded runs of this task are still open (not decided or deferred)."""
        ids = [
            uuid.UUID(value)
            for run in repository.runs_for_task(self._session, task_id)
            if run.status == "succeeded"
            for value in (run.output or {}).get("decision_ids", [])
        ]
        return sum(1 for status in self._decisions.decision_statuses(ids).values() if status == "open")

    def link_earlier_runs(self, actor: Actor, project_id: uuid.UUID) -> int:
        """Links runs made before their workflow task existed (projects opened before Increment 3a), and moves a
        task whose run already succeeded to waiting for input. Returns how many runs were linked."""
        self._identity.require_project(actor, project_id, "project.manage_members")
        linked = 0
        for run in repository.unlinked_runs(self._session, project_id):
            task = self._registry.task(run.agent_key, run.task_key)
            view = self._workflow.task_by_key(project_id, task.spec.phase, task.spec.workflow_task) if task else None
            if view is None:
                continue
            run.task_id = view.id
            linked += 1
            if run.status == "succeeded" and view.state == "not_started":
                self._session.flush()
                agent = self._identity.get_actor(run.agent_user_id)
                for target, mover in (("ready", SYSTEM_ACTOR), ("in_progress", SYSTEM_ACTOR), ("waiting_for_input", agent)):
                    self._move_task(view.id, target, mover, "Linked to an agent run made before this task existed")
        self._session.flush()
        return linked

    # Helpers --------------------------------------------------------------------------------

    def _record_incident(self, run: AgentRun) -> None:
        """The evidence as it stands when the run ends; the incident is opened (or recurs) in this transaction."""
        task = self._registry.task(run.agent_key, run.task_key)
        task_state = self._workflow.task_view(run.task_id).state if run.task_id else None
        calls = repository.calls_for_runs(self._session, [run.id])
        record = self._artifacts.version_record(run.input_artifact_version_id)
        evidence = {
            "run_id": str(run.id),
            "agent": run.agent_key,
            "task": run.task_key,
            "status": run.status,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "attempts": run.attempts,
            "max_attempts": run.max_attempts,
            "prompt_version": run.prompt_version,
            "input": f"{record.artifact_title} v{record.version_no} (sha256 {record.content_sha256[:12]})",
            "workflow_task_state": task_state,
            "blocking_findings": [f for f in run.findings if f.get("severity") == "block"],
            "model_calls": [
                {
                    "status": c.status,
                    "model": c.model,
                    "stop_reason": c.stop_reason,
                    "refusal_category": c.refusal_category,
                    "cost_usd": str(c.cost_usd if c.cost_usd is not None else c.reserved_usd),
                    "request_id": c.request_id,
                    "error": c.error,
                }
                for c in calls
            ],
            "recorded_at": self._clock.now().isoformat(),
        }
        name = task.spec.title if task else run.task_key
        self._oversight.record_run_failure(
            project_id=run.project_id,
            run_id=run.id,
            task_id=run.task_id,
            agent_key=run.agent_key,
            task_key=run.task_key,
            error_code=run.error_code,
            title=f"{name}: {run.error_code or run.status}",
            evidence=evidence,
        )

    def _context_snapshot(self, actor: Actor, project_id: uuid.UUID, task: TaskDefinition) -> dict[str, Any]:
        documents = [
            str(record.id)
            for artifact_type in task.spec.context_artifact_types
            for record in sorted(self._artifacts.current_records_of_type(project_id, artifact_type), key=lambda r: r.artifact_title)
        ]
        decision_ids: list[str] = []
        for run in repository.succeeded_runs(self._session, project_id, task_refs(task.agent_key, task.spec.context_decisions_from)):
            decision_ids += [value for value in (run.output or {}).get("decision_ids", []) if value not in decision_ids]
        decisions = [
            {"id": value, "outcomes": len(self._decisions.get_decision(actor, uuid.UUID(value)).outcomes)} for value in decision_ids
        ]
        reviews = []
        for artifact_type in task.spec.context_reviews_of:
            for record in self._artifacts.current_records_of_type(project_id, artifact_type):
                history = self._decisions.artifact_approvals(actor, record.artifact_id).history
                reviews += [
                    str(review.id)
                    for review in sorted(history, key=lambda r: r.created_at)
                    if review.artifact_version_id == record.id and review.decision != "approved"
                ]
        context: dict[str, Any] = {"documents": documents, "decisions": decisions, "reviews": reviews}
        if task.spec.context_findings_of:
            # The current review versions; the task itself picks out the open findings on the current design.
            context["findings"] = [
                str(record.id) for artifact_type in task.spec.context_findings_of for record in self._artifacts.current_records_of_type(project_id, artifact_type)
            ]
        return context

    def _new_input_for_closed_task(self, task: TaskView, input_version_id: uuid.UUID) -> bool:
        """A completed task may be asked again for a new version of what it works from (for example a design
        changed by a design change request needs new reviews and a new backlog). The task stays completed; the
        run is recorded against it, and the version-bound gates decide what counts."""
        if task.state != "completed":
            return False
        done = [r for r in repository.runs_for_task(self._session, task.id) if r.status == "succeeded"]
        return bool(done) and done[-1].input_artifact_version_id != input_version_id

    def _start_task(self, task: TaskView, reason: str, requester: Actor, agent: Actor, *, system_reason: str | None = None) -> None:
        """Moves the task to in_progress, each step as the requester, or as the agent where only it may. A task
        waiting for review goes back through changes_requested; when there is a recorded reason for that (review
        comments or findings to answer, or a new input version), Agentra records that step itself."""
        for target in _START_PATHS[task.state]:
            if target == "changes_requested" and system_reason:
                self._move_task(task.id, target, SYSTEM_ACTOR, system_reason, strict=True)
                continue
            try:
                self._move_task(task.id, target, requester, reason, strict=True)
            except PermissionDeniedError:
                self._move_task(task.id, target, agent, reason, strict=True)

    def _move_task(self, task_id: uuid.UUID, target: str, actor: Actor, reason: str, *, strict: bool = False) -> None:
        current = self._workflow.task_view(task_id)
        if current.state == target:
            return
        try:
            self._workflow.transition_task(
                actor, task_id, TransitionRequest(to_state=target, reason=reason, expected_version=current.version)
            )
        except DomainError:
            if strict:
                raise

    def _readiness(self, project_id: uuid.UUID, task: TaskDefinition) -> tuple[Actor | None, list[str]]:
        blockers = []
        phase_state = self._workflow.phase_state(project_id, task.spec.phase)
        if phase_state not in task.spec.phase_states:
            wanted = " or ".join(state.replace("_", " ") for state in task.spec.phase_states)
            current = (phase_state or "missing").replace("_", " ")
            blockers.append(f"Phase {task.spec.phase} must be {wanted} (it is {current})")
        agent = self._identity.agent_by_key(task.agent_key)
        if agent is None:
            blockers.append(f"no {task.agent_name} account exists (create it with the create-agent command)")
        elif "agent" not in self._identity.roles_for(agent, project_id):
            blockers.append(f"the {task.agent_name} is not on this project's team (add it with the Agent role)")
        return agent, blockers

    def _views(self, runs: list[AgentRun]) -> list[AgentRunView]:
        calls_by_run: dict[uuid.UUID, list[ModelCall]] = {}
        for call in repository.calls_for_runs(self._session, [run.id for run in runs]):
            calls_by_run.setdefault(call.agent_run_id, []).append(call)
        names = self._identity.display_names({run.requested_by for run in runs})
        views = []
        for run in runs:
            task = self._registry.task(run.agent_key, run.task_key)
            record = self._artifacts.version_record(run.input_artifact_version_id)
            answered = [call.model for call in calls_by_run.get(run.id, []) if call.model]
            refs = run.input_refs or {}
            views.append(
                AgentRunView(
                    id=run.id,
                    project_id=run.project_id,
                    agent_key=run.agent_key,
                    agent_name=task.agent_name if task else run.agent_key,
                    task_key=run.task_key,
                    task_title=task.spec.title if task else run.task_key,
                    subject=refs.get("subject"),
                    status=run.status,  # type: ignore[arg-type]
                    input_artifact_id=record.artifact_id,
                    input_artifact_version_id=record.id,
                    input_title=record.artifact_title,
                    input_version_no=record.version_no,
                    context_documents=len(refs.get("documents", [])),
                    context_decisions=len(refs.get("decisions", [])),
                    task_id=run.task_id,
                    requested_by=run.requested_by,
                    requested_by_name=names.get(run.requested_by),
                    attempts=run.attempts,
                    max_attempts=run.max_attempts,
                    prompt_version=run.prompt_version,
                    model=answered[-1] if answered else None,
                    cost_usd=run.cost_usd,
                    error_code=run.error_code,
                    error_message=run.error_message,
                    findings=[FindingView.model_validate(finding) for finding in run.findings],
                    decision_ids=[uuid.UUID(value) for value in (run.output or {}).get("decision_ids", [])],
                    created_at=run.created_at,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
            )
        return views
