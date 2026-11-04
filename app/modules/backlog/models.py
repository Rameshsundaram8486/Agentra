"""Implementation backlog tables. Each draft is a new implementation_backlog document version with a full, immutable
set of epics and work items, tied to the approved design version it plans; nothing is edited in place
(append-only, migration 0010). Epic and work item IDs are registered once per project and never reused."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class BacklogId(Base):
    __tablename__ = "backlog_ids"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    item_id: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(16))  # epic | work_item
    number: Mapped[int] = mapped_column(Integer)
    first_artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "item_id", name="uq_backlog_ids_project_item"),)


class BacklogVersion(Base):
    __tablename__ = "backlog_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), unique=True)
    design_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))  # the approved design it plans
    summary: Mapped[str] = mapped_column(Text)
    epics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # [{epic_id, title, description}]
    review_responses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BacklogItem(Base):
    __tablename__ = "backlog_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    item_id: Mapped[str] = mapped_column(String(20))
    epic_id: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    work_type: Mapped[str] = mapped_column(String(16))
    design_items: Mapped[list[str]] = mapped_column(JSONB)
    requirements: Mapped[list[str]] = mapped_column(JSONB)  # stated by the agent plus those of its design items
    acceptance: Mapped[list[str]] = mapped_column(JSONB)  # REQ-F-001.AC1 ...
    estimate: Mapped[str] = mapped_column(String(2))  # S | M | L
    depends_on: Mapped[list[str]] = mapped_column(JSONB)  # work item IDs
    wave: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("artifact_version_id", "item_id", name="uq_backlog_items_version_item"),)
