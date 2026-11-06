"""Agent run and model call data accepted from and returned to callers."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.identity.schemas import Actor

RunStatus = Literal["queued", "running", "succeeded", "failed", "blocked"]


class AgentRunCreate(BaseModel):
    agent_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    task_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    artifact_version_id: uuid.UUID
    change_request_id: uuid.UUID | None = Field(default=None, description="For tasks that apply a change request")
    subject: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9]{0,7}-\d{1,6}$", description="For tasks on one work item, e.g. WI-005")


class FindingView(BaseModel):
    check: str
    severity: Literal["block", "warn"]
    message: str
    path: str | None = None


class ModelCallView(BaseModel):
    id: uuid.UUID
    provider: str
    requested_model: str
    model: str | None
    effort: str
    status: str
    stop_reason: str | None
    refusal_category: str | None
    fallback_used: bool
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    reserved_usd: Decimal
    cost_usd: Decimal | None
    cost_exact: bool | None
    latency_ms: int | None
    request_id: str | None
    prompt_version: str
    schema_version: str | None
    error: str | None
    created_at: datetime


class AgentRunView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    agent_key: str
    agent_name: str
    task_key: str
    task_title: str
    subject: str | None = None  # the work item a run works on
    status: RunStatus
    input_artifact_id: uuid.UUID
    input_artifact_version_id: uuid.UUID
    input_title: str
    input_version_no: int
    context_documents: int = Field(description="Other documents the run read")
    context_decisions: int = Field(description="Decisions the run read")
    task_id: uuid.UUID | None
    requested_by: uuid.UUID
    requested_by_name: str | None
    attempts: int
    max_attempts: int
    prompt_version: str
    model: str | None = Field(description="The model that answered the latest call, if any")
    cost_usd: Decimal
    error_code: str | None
    error_message: str | None
    findings: list[FindingView]
    decision_ids: list[uuid.UUID]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AgentRunDetail(AgentRunView):
    model_calls: list[ModelCallView]
    output: dict[str, Any] | None = Field(description="The validated agent output, or a redacted excerpt if it was blocked")


class RunRequestResult(BaseModel):
    run: AgentRunView
    created: bool = Field(description="False when an earlier run for the same document version was returned instead")


@dataclass(frozen=True)
class StartedRun:
    """What a worker needs to execute one attempt of a run."""

    run_id: uuid.UUID
    project_id: uuid.UUID
    agent_key: str
    task_key: str
    agent: Actor
    input_artifact_version_id: uuid.UUID
    input_refs: dict[str, Any]
    task_id: uuid.UUID | None
    attempt: int
    max_attempts: int
