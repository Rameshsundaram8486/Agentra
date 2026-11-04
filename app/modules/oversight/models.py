"""Incident records. An incident is never edited: recurrences, resolutions (with their root-cause analysis) and
closure are separate events, and the status is derived from them (append-only, migration 0007)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(64))  # the error code that opened it
    severity: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(32))  # agent_run
    source_id: Mapped[uuid.UUID] = mapped_column()
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"))
    task_key: Mapped[str | None] = mapped_column(String(64))  # agent task key, for grouping recurrences
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("project_id", "number", name="uq_incidents_project_number"),
        UniqueConstraint("source_type", "source_id", name="uq_incidents_source"),
        CheckConstraint("severity IN ('low', 'medium', 'high')", name="severity"),
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    event: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("event IN ('recurrence', 'resolved', 'closed')", name="event"),)
