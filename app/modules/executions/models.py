"""Agent runs and the model calls made for them.

A model call row is written (and committed) at its worst-case cost before the provider is called, then
settled with the real usage, so the monthly cap counts every call that may have been billed.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id

RUN_STATUSES = ("queued", "running", "succeeded", "failed", "blocked")
CALL_STATUSES = ("pending", "completed", "refused", "truncated", "failed", "abandoned")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_key: Mapped[str] = mapped_column(String(64))
    task_key: Mapped[str] = mapped_column(String(64))
    agent_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    agent_version: Mapped[int] = mapped_column(Integer)
    prompt_version: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(100))
    input_artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    # Everything else the run read, fixed when it was asked: {"documents": [version ids],
    # "decisions": [{"id", "outcomes"}], "fingerprint": ...}. The same inputs never produce a second run.
    input_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"))  # the workflow task it works on
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column()
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="status"),
        Index("ix_agent_runs_input", "agent_key", "task_key", "input_artifact_version_id"),
    )


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    agent_key: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    requested_model: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))  # the model that actually answered
    effort: Mapped[str] = mapped_column(String(16))
    max_tokens: Mapped[int] = mapped_column(Integer)
    prompt_version: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16))
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    refusal_category: Mapped[str | None] = mapped_column(String(64))
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    cost_exact: Mapped[bool | None] = mapped_column(Boolean)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(f"status IN {CALL_STATUSES}", name="status"),)
