"""Workflow tables: phase runs, tasks and the record of every state change."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class PhaseRun(Base):
    __tablename__ = "phase_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    phase: Mapped[int] = mapped_column(Integer)
    definition_key: Mapped[str] = mapped_column(String(100))
    definition_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "phase", name="uq_phase_runs_project_phase"),)


class Task(Base):
    """Task data is copied from the phase definition when the run opens, so later config edits do not rewrite history."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    phase_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("phase_runs.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    # What a generated task works on (for example the work item WI-005); None for tasks from the phase definition.
    subject: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)  # order in the phase definition
    title: Mapped[str] = mapped_column(String(200))
    agent: Mapped[str | None] = mapped_column(String(64))
    depends_on: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    state: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("phase_run_id", "key", name="uq_tasks_phase_run_key"),)


class StateTransition(Base):
    __tablename__ = "state_transitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)  # orders same-instant rows
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("entity_type IN ('phase_run', 'task')", name="entity_type"),
        Index("ix_state_transitions_entity", "entity_type", "entity_id"),
        Index("ix_state_transitions_project_id", "project_id"),
    )
