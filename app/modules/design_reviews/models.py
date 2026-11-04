"""Design review tables. Each review is one version of a Security review or Feasibility review document, tied to
the exact design version it reviews, with one finding per checklist item or design item. Nothing is edited in
place (append-only, migration 0009)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class DesignReview(Base):
    __tablename__ = "design_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # security | feasibility
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), unique=True)
    design_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))  # the design version reviewed
    checklist: Mapped[str | None] = mapped_column(String(120))  # security: checklist version and hash
    summary: Mapped[str] = mapped_column(Text)
    review_responses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_design_reviews_design_version", "design_version_id", "kind"),)


class DesignReviewFinding(Base):
    __tablename__ = "design_review_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    review_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))
    position: Mapped[int] = mapped_column(Integer)
    ref: Mapped[str] = mapped_column(String(20))  # SC-01 (security) or a design item ID (feasibility)
    title: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str | None] = mapped_column(String(8))  # security gaps: high | medium | low
    complexity: Mapped[str | None] = mapped_column(String(2))  # feasibility: S | M | L
    assessment: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    design_items: Mapped[list[str]] = mapped_column(JSONB)
    requirements: Mapped[list[str]] = mapped_column(JSONB)
    unverified: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("review_version_id", "ref", name="uq_design_review_findings_version_ref"),)
