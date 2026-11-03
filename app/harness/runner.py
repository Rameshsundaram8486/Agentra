"""Agent loop for one attempt of an agent run:

start (preconditions re-checked) -> prepare (inputs through G1; missing input ends here, unpaid) -> model call
through the gateway (reserved against the cap first) -> output through G4 and the task's own checks -> apply
(records and proposals created as the agent) -> finish, which also moves the workflow task.

Each step has its own transaction, so nothing a model produced is saved unless every guardrail passed, and
the run always ends with a recorded status and reason. Only transient provider errors are retried (by the
job queue, up to the task's max_attempts); refusals, guardrail failures and the budget are final.
"""

import logging
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.agents import task_implementation
from app.agents.base import MissingInput
from app.composition import Policies, Services
from app.guardrails.findings import Finding, blocking
from app.guardrails.output.secret_scan import redact_secrets
from app.guardrails.pipeline import check_output
from app.infrastructure.clock import Clock
from app.infrastructure.job_queue import ClaimedJob
from app.infrastructure.logging import redact
from app.infrastructure.storage.base import ArtifactStore
from app.infrastructure.unit_of_work import UnitOfWork
from app.model_gateway.errors import BudgetExceededError, ModelProviderError
from app.model_gateway.gateway import CallIntent, CallOutcome, ModelGateway
from app.modules.errors import DomainError
from app.modules.executions.schemas import RunStatus, StartedRun

logger = logging.getLogger(__name__)

_RAW_EXCERPT_CHARS = 20_000
_LEASE_MARGIN = timedelta(minutes=2)
_MIN_TOKENS_PER_SECOND = 40


class _RunLedger:
    """The gateway's spend ledger for one run; each entry is committed before the gateway continues."""

    def __init__(self, transaction: Callable[[], Any], run_id: uuid.UUID) -> None:
        self._transaction = transaction
        self._run_id = run_id

    def reserve(self, intent: CallIntent) -> uuid.UUID:
        with self._transaction() as services:
            return services.executions.reserve_model_call(self._run_id, intent)  # type: ignore[no-any-return]

    def settle(self, call_id: uuid.UUID, outcome: CallOutcome) -> None:
        with self._transaction() as services:
            services.executions.settle_model_call(call_id, outcome)


class AgentRunner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        clock: Clock,
        policies: Policies,
        store: ArtifactStore,
        gateway: ModelGateway,
    ) -> None:
        self.session_factory = session_factory
        self.clock = clock
        self._policies = policies
        self._store = store
        self._gateway = gateway

    @property
    def lease(self) -> timedelta:
        """Long enough for the slowest model call including SDK retries, so a busy job is not reclaimed.
        The timeout is per read, and a long answer streams for a while, so output length counts too."""
        profiles = [self._gateway.config.profile(agent, task) for agent, task in self._policies.agents.tasks]
        longest = max(
            ((p.timeout_seconds + p.max_tokens / _MIN_TOKENS_PER_SECOND) * (p.max_retries + 1) for p in profiles), default=300
        )
        return timedelta(seconds=longest) + _LEASE_MARGIN

    @contextmanager
    def _transaction(self) -> Iterator[Services]:
        """Commits if the block succeeds; rolls back otherwise."""
        with UnitOfWork(self.session_factory) as uow:
            yield Services(uow.session, self.clock, self._policies, self._store)
            uow.commit()

    def _finish(
        self,
        run_id: uuid.UUID,
        status: RunStatus,
        code: str,
        message: str,
        findings: list[Finding] | None = None,
        output: dict[str, Any] | None = None,
        task_state: str | None = None,
    ) -> None:
        with self._transaction() as services:
            services.executions.finish_run(
                run_id,
                status=status,
                error_code=code,
                error_message=message,
                findings=[finding.to_dict() for finding in findings or []],
                output=output,
                task_state=task_state,
            )
        logger.info("agent run ended", extra={"agent_run_id": str(run_id), "status": status, "error_code": code})

    def handle(self, job: ClaimedJob) -> None:
        run_id = uuid.UUID(job.payload["agent_run_id"])
        with self._transaction() as services:
            started = services.executions.start_run(run_id)
        if started is None:
            return  # finished earlier, or blocked just now (recorded by start_run)
        try:
            self._attempt(started)
        except Exception as exc:
            # Raised errors are retried by the job queue; on the last attempt the run must still end with a status.
            if started.attempt >= started.max_attempts:
                code = exc.code if isinstance(exc, ModelProviderError) else "internal_error"
                self._finish(run_id, "failed", code, redact(f"{type(exc).__name__}: {exc}"))
            raise

    def _attempt(self, started: StartedRun) -> None:
        run_id = started.run_id
        definition = self._policies.agents.task(started.agent_key, started.task_key)
        task = task_implementation(started.agent_key, started.task_key)
        if definition is None or task is None:
            self._finish(run_id, "failed", "unknown_task", f"No implementation for {started.agent_key}.{started.task_key}")
            return

        try:
            with self._transaction() as services:
                prepared = task.prepare(services, started, definition)
        except MissingInput as exc:
            self._finish(run_id, "blocked", "missing_input", str(exc), task_state="waiting_for_input")
            return
        except DomainError as exc:
            self._finish(run_id, "failed", "input_rejected", str(exc))
            return

        try:
            result = self._gateway.call(
                started.agent_key,
                task_key=started.task_key,
                system=definition.prompt.text,
                user=prepared.user,
                output_schema=definition.schema_file.schema,
                prompt_version=definition.prompt.version,
                schema_version=definition.schema_file.version,
                ledger=_RunLedger(self._transaction, run_id),
            )
        except BudgetExceededError as exc:
            self._finish(run_id, "blocked", exc.code, str(exc), prepared.input_findings)
            return
        except ModelProviderError as exc:
            if exc.retryable and started.attempt < started.max_attempts:
                raise  # the job queue retries with back-off
            self._finish(run_id, "failed", exc.code, f"{exc} (attempt {started.attempt} of {started.max_attempts})", prepared.input_findings)
            return

        response = result.response
        if result.status == "refused":
            self._finish(
                run_id,
                "failed",
                "refused",
                f"The model declined the request (category: {response.refusal_category}). Nothing was saved; "
                "review the brief and ask again, or raise it with the platform owner.",
                prepared.input_findings,
            )
            return
        if result.status == "truncated":
            self._finish(run_id, "failed", "truncated", "The answer hit the token limit and was incomplete; nothing was saved.", prepared.input_findings)
            return

        check = check_output(response.text, task.output_model, sources=prepared.sources)
        output_findings = check.findings + (task.check(check.value, prepared) if check.value is not None else [])
        findings = prepared.input_findings + output_findings
        if check.value is None or blocking(output_findings):
            blocked = len(blocking(output_findings))
            self._finish(
                run_id,
                "failed",
                "guardrail_blocked",
                f"{blocked} output check(s) failed, so nothing was saved. See the findings.",
                findings,
                output={"raw_excerpt": redact_secrets(response.text)[0][:_RAW_EXCERPT_CHARS]},
            )
            return

        try:
            with self._transaction() as services:
                applied = task.apply(services, started, check.value, prepared)
                services.executions.finish_run(
                    run_id,
                    status="succeeded",
                    output={
                        "result": check.value.model_dump(mode="json"),
                        "decision_ids": [str(i) for i in applied.decision_ids],
                        **applied.records,
                    },
                    findings=[finding.to_dict() for finding in findings],
                    task_state=applied.task_state,
                )
        except DomainError as exc:
            self._finish(run_id, "failed", "apply_failed", f"The output passed its checks but could not be saved: {exc}", findings)
            return
        logger.info(
            "agent run succeeded",
            extra={"agent_run_id": str(run_id), "decisions": len(applied.decision_ids), "cost_usd": str(result.cost_usd), "model": response.model},
        )
