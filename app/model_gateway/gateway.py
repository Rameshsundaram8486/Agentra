"""Single entry point for model calls: routing, the spending cap, telemetry and normalised errors.

Persist before side effects: the call is reserved in the ledger (and committed) at its worst-case cost before
the provider is called, then settled with the real usage. A call that never settles keeps its reservation,
so a crash cannot make spend disappear.
"""

import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from app.model_gateway.errors import ModelProviderError
from app.model_gateway.providers.base import ModelRequest, ModelResponse, Provider
from app.model_gateway.router import ModelConfig, ModelProfile
from app.model_gateway.telemetry import cost_of, worst_case_cost

CallStatus = Literal["completed", "refused", "truncated", "failed"]


@dataclass(frozen=True)
class CallIntent:
    agent_key: str
    provider: str
    profile: ModelProfile
    prompt_version: str
    schema_version: str | None
    reserved_usd: Decimal
    budget_usd: Decimal


@dataclass(frozen=True)
class CallOutcome:
    status: CallStatus
    response: ModelResponse | None
    cost_usd: Decimal
    cost_exact: bool
    latency_ms: int
    error: str | None = None


class SpendLedger(Protocol):
    def reserve(self, intent: CallIntent) -> uuid.UUID:
        """Records the call and commits; raises BudgetExceededError if the cap would be exceeded."""
        ...

    def settle(self, call_id: uuid.UUID, outcome: CallOutcome) -> None:
        """Records the outcome and commits."""
        ...


@dataclass(frozen=True)
class ModelResult:
    call_id: uuid.UUID
    status: CallStatus
    response: ModelResponse
    cost_usd: Decimal


def _status(response: ModelResponse) -> CallStatus:
    if response.stop_reason == "refusal":
        return "refused"
    if response.stop_reason == "max_tokens":
        return "truncated"
    return "completed"


class ModelGateway:
    def __init__(self, config: ModelConfig, provider: Provider) -> None:
        self.config = config
        self._provider = provider

    def call(
        self,
        agent_key: str,
        *,
        task_key: str | None = None,
        system: str,
        user: str,
        output_schema: dict[str, Any] | None,
        prompt_version: str,
        schema_version: str | None,
        ledger: SpendLedger,
    ) -> ModelResult:
        """Raises BudgetExceededError before calling, or ModelProviderError when no response came back.
        Refusals and truncation are results, not exceptions: the caller decides what they mean."""
        profile = self.config.profile(agent_key, task_key)
        call_id = ledger.reserve(
            CallIntent(
                agent_key=agent_key,
                provider=self._provider.name,
                profile=profile,
                prompt_version=prompt_version,
                schema_version=schema_version,
                reserved_usd=worst_case_cost(self.config, profile, len(system) + len(user)),
                budget_usd=self.config.budget.monthly_usd,
            )
        )
        request = ModelRequest(
            model=profile.model,
            effort=profile.effort,
            max_tokens=profile.max_tokens,
            system=system,
            user=user,
            output_schema=output_schema,
            refusal_fallback=profile.refusal_fallback,
            timeout_seconds=profile.timeout_seconds,
            max_retries=profile.max_retries,
        )
        started = time.monotonic()
        try:
            response = self._provider.complete(request)
        except ModelProviderError as exc:
            ledger.settle(
                call_id,
                CallOutcome("failed", None, Decimal(0), True, _elapsed_ms(started), error=f"{exc.code}: {exc}"),
            )
            raise
        cost = cost_of(self.config, response)
        status = _status(response)
        ledger.settle(call_id, CallOutcome(status, response, cost.usd, cost.exact, _elapsed_ms(started)))
        return ModelResult(call_id=call_id, status=status, response=response, cost_usd=cost.usd)


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
