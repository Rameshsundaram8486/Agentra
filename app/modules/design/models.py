"""Design tables. Each draft is a new design_baseline document version with a full, immutable set of items, tied
to the approved requirements version it was designed against; nothing is edited in place (append-only,
migration 0008). Item IDs are registered once per project and never reused."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class DesignId(Base):
    __tablename__ = "design_ids"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    item_id: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(24))
    number: Mapped[int] = mapped_column(Integer)
    first_artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "item_id", name="uq_design_ids_project_item"),)


class DesignVersion(Base):
    __tablename__ = "design_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), unique=True)
    previous_artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_versions.id"))
    requirements_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))  # designed against
    summary: Mapped[str] = mapped_column(Text)
    component_diagram: Mapped[str] = mapped_column(Text)
    data_flow_diagram: Mapped[str] = mapped_column(Text)
    exceptions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # requirements deliberately not covered, and why
    set_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    input_refs: Mapped[list[str]] = mapped_column(JSONB)
    review_responses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DesignItem(Base):
    __tablename__ = "design_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    item_id: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))  # derived in code, never from the model
    satisfies: Mapped[list[str]] = mapped_column(JSONB)  # requirement IDs
    related: Mapped[list[str]] = mapped_column(JSONB)  # design item IDs
    unverified_capabilities: Mapped[list[str]] = mapped_column(JSONB)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    quality_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("artifact_version_id", "item_id", name="uq_design_items_version_item"),
        Index("ix_design_items_project_item", "project_id", "item_id"),
    )
