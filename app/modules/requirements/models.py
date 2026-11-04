"""Requirement tables. Each draft is a new requirements_baseline document version with a full, immutable set of
items; nothing is edited in place (items and versions are append-only, migration 0005). Item IDs are
registered once per project and never reused, so REQ-F-003 means the same requirement in every version.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class RequirementId(Base):
    __tablename__ = "requirement_ids"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    item_id: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(24))
    number: Mapped[int] = mapped_column(Integer)
    first_artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "item_id", name="uq_requirement_ids_project_item"),)


class RequirementVersion(Base):
    """What a draft says as a whole: summary, process flow, set-level quality flags, inputs."""

    __tablename__ = "requirement_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), unique=True)
    previous_artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_versions.id"))
    summary: Mapped[str] = mapped_column(Text)
    process_flow: Mapped[str] = mapped_column(Text)
    set_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    input_refs: Mapped[list[str]] = mapped_column(JSONB)
    # Each review comment the draft answered: {"approval_id", "comment", "response"}.
    review_responses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    change_request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("change_requests.id"))  # the change it applied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RequirementItem(Base):
    __tablename__ = "requirement_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    item_id: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))  # derived in code from label and sources, never from the model
    priority: Mapped[str] = mapped_column(String(16))
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSONB)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    quality_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    related: Mapped[list[str]] = mapped_column(JSONB, default=list)  # item IDs it traces to (objective, requirement)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("artifact_version_id", "item_id", name="uq_requirement_items_version_item"),
        Index("ix_requirement_items_project_item", "project_id", "item_id"),
    )


class ChangeRequest(Base):
    """A request to change an approved requirements baseline, exactly as raised. Never edited."""

    __tablename__ = "change_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    baseline_artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    baseline_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    change: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(Text)
    affected_item_ids: Mapped[list[str]] = mapped_column(JSONB)
    allows_new_items: Mapped[bool] = mapped_column(Boolean)
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_change_requests_project_number"),)


class ChangeRequestEvent(Base):
    """An approval or rejection in one role, or the version that applied the change. Never edited."""

    __tablename__ = "change_request_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    change_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("change_requests.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    event: Mapped[str] = mapped_column(String(16))  # approved | rejected | applied
    role: Mapped[str | None] = mapped_column(String(32))  # the capacity an approval or rejection was given in
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_versions.id"))  # for applied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("event IN ('approved', 'rejected', 'applied')", name="event"),
        # One decision per role, and one application per change request, even under concurrent requests.
        Index("uq_change_request_events_role", "change_request_id", "role", unique=True, postgresql_where=text("role IS NOT NULL")),
        Index("uq_change_request_events_applied", "change_request_id", unique=True, postgresql_where=text("event = 'applied'")),
    )
