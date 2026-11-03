"""Business rules for agent runs and model calls; the only entry point for other modules.

A person asks for an agent task on a document version; the run and its background job are created in one
transaction. Asking again for the same version returns the existing run unless every earlier run failed or
was blocked. Preconditions (phase state, the agent's membership) are checked when asked and again when the
worker starts, because either can change in between. Workers call start_run / finish_run and the ledger
methods; people only request and read.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.guardrails.input.scope import input_problems
from app.harness.registry import AgentRegistry, TaskDefinition
from app.infrastructure.clock import Clock
from app.infrastructure.job_queue import JobQueue
from app.model_gateway.errors import BudgetExceededError
from app.model_gateway.gateway import CallIntent, CallOutcome
from app.modules.artifacts.service import ArtifactsService
from app.modules.audit.service import AuditService
from app.modules.errors import NotFoundError, ValidationFailedError
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
from app.modules.identity.service import Actor, IdentityService
from app.modules.workflow.service import WorkflowService

__all__ = ["AGENT_RUN_JOB", "AgentRunCreate", "AgentRunDetail", "AgentRunView", "ExecutionsService", "StartedRun"]

AGENT_RUN_JOB = "agent_run"
_ACTIVE = ("queued", "running", "succeeded")
_TERMINAL = ("succeeded", "failed", "blocked")


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
        registry: AgentRegistry,
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._workflow = workflow
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
        agent, blockers = self._readiness(project_id, task)
        if problems or blockers:
            raise ValidationFailedError(f"The {task.agent_name} cannot start yet: {'; '.join(problems + blockers)}")
        assert agent is not None

        earlier = repository.runs_for_input(self._session, task.agent_key, task.key, record.id)
        active = next((run for run in reversed(earlier) if run.status in _ACTIVE), None)
        if active is not None:
            return RunRequestResult(run=self._views([active])[0], created=False)

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
            idempotency_key=f"{task.agent_key}.{task.key}:{record.id}:{len(earlier) + 1}",
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
            winner = next(r for r in repository.runs_for_input(self._session, task.agent_key, task.key, record.id) if r.status in _ACTIVE)
            return RunRequestResult(run=self._views([winner])[0], created=False)
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
    ) -> None:
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

    # Helpers --------------------------------------------------------------------------------

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
            views.append(
                AgentRunView(
                    id=run.id,
                    project_id=run.project_id,
                    agent_key=run.agent_key,
                    agent_name=task.agent_name if task else run.agent_key,
                    task_key=run.task_key,
                    task_title=task.spec.title if task else run.task_key,
                    status=run.status,  # type: ignore[arg-type]
                    input_artifact_id=record.artifact_id,
                    input_artifact_version_id=record.id,
                    input_title=record.artifact_title,
                    input_version_no=record.version_no,
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
