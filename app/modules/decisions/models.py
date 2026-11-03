"""Approval and decision tables. All three are append-only: a database trigger refuses UPDATE and DELETE
(migration 0003). A recommendation is never edited; a human outcome is a separate row."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)  # orders same-instant rows
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"), index=True)
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), index=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(24))
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected', 'changes_requested')", name="decision"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
    )


class DecisionRequest(Base):
    """What was asked and what the agent (or person) recommended, exactly as raised."""

    __tablename__ = "decision_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    recommended_option: Mapped[str | None] = mapped_column(String(64))
    recommendation_rationale: Mapped[str] = mapped_column(Text)
    assumptions: Mapped[list[str]] = mapped_column(JSONB)
    risks: Mapped[list[str]] = mapped_column(JSONB)
    artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_versions.id"))
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionOutcome(Base):
    """A human's response. Deferring adds a row; a later final outcome adds another."""

    __tablename__ = "decision_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    decision_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decision_requests.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    outcome_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))
    selected_option: Mapped[str | None] = mapped_column(String(64))
    custom_choice: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Two people answering at once: one insert wins, the other gets a conflict.
        UniqueConstraint("decision_request_id", "outcome_no", name="uq_decision_outcomes_request_outcome_no"),
        CheckConstraint("action IN ('accept', 'select_option', 'other', 'modify', 'reject', 'defer')", name="action"),
    )
