"""Generated report versions. A version is never edited (append-only, migration 0007); the rendered HTML is kept in
the content-addressed store under its hash, next to the exact data it was rendered from."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(64))
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)  # everything the report shows, taken from records
    data_sha256: Mapped[str] = mapped_column(String(64))
    template_version: Mapped[str] = mapped_column(String(32))
    content_sha256: Mapped[str] = mapped_column(String(64))  # the rendered HTML, in the content store
    size_bytes: Mapped[int] = mapped_column(Integer)
    sources: Mapped[list[str]] = mapped_column(JSONB)  # the records it was built from, with versions and hashes
    data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # the newest record it includes
    generated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "report_type", "version_no", name="uq_reports_project_type_version"),)
