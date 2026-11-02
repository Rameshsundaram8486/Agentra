"""Audit event table. UPDATE, DELETE and TRUNCATE are refused by a database trigger (migration 0002)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    before: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
    after: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)

    __table_args__ = (Index("ix_audit_events_project_seq", "project_id", "seq"),)
