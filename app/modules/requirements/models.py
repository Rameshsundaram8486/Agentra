"""Requirement tables. Each draft is a new requirements_baseline document version with a full, immutable set of
items; nothing is edited in place (items and versions are append-only, migration 0005). Item IDs are
registered once per project and never reused, so REQ-F-003 means the same requirement in every version.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("artifact_version_id", "item_id", name="uq_requirement_items_version_item"),
        Index("ix_requirement_items_project_item", "project_id", "item_id"),
    )
