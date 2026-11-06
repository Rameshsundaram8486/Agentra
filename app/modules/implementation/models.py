"""Phase 9 tables: the project's repository, change sets, sandbox runs and merges (migration 0012).

A change set is one version of a work item's Change set document (artifact type change_set) plus the commit it
became on a branch of the project repository; nothing is edited in place. Sandbox runs and merges are records of
what happened to one change set version. The code itself lives in the git repository (git_repo.py)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base
from app.infrastructure.ids import new_id


class ProjectRepository(Base):
    __tablename__ = "project_repositories"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    initial_commit: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChangeSet(Base):
    __tablename__ = "change_sets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    work_item_id: Mapped[str] = mapped_column(String(20))
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), unique=True)
    backlog_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"))  # the approved backlog it implements
    base_commit: Mapped[str] = mapped_column(String(40))  # main when it was drafted
    commit: Mapped[str] = mapped_column(String(40))
    branch: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # [{path, action, bytes, sha256}]
    design_items: Mapped[list[str]] = mapped_column(JSONB)
    requirements: Mapped[list[str]] = mapped_column(JSONB)
    acceptance: Mapped[list[str]] = mapped_column(JSONB)
    test_command: Mapped[str] = mapped_column(String(300))
    limitations: Mapped[list[str]] = mapped_column(JSONB)
    review_responses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_change_sets_project_work_item", "project_id", "work_item_id"),)


class SandboxRun(Base):
    """One build and test run of one change set version. not_run: no sandbox could run it (never passed or failed)."""

    __tablename__ = "sandbox_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)  # orders runs asked for in the same instant
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    change_set_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), index=True)
    commit: Mapped[str] = mapped_column(String(40))
    command: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str | None] = mapped_column(String(32))
    image: Mapped[str | None] = mapped_column(String(100))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    output_excerpt: Mapped[str | None] = mapped_column(Text)  # the end of the output, secrets redacted
    output_sha256: Mapped[str | None] = mapped_column(String(64))  # of the full output as the sandbox reported it
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'passed', 'failed', 'not_run', 'error')", name="status"),
    )


class Merge(Base):
    """What happened when an approved change set version was merged into main: merged, or a conflict (nothing changed)."""

    __tablename__ = "change_set_merges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    change_set_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact_versions.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16))
    main_before: Mapped[str] = mapped_column(String(40))
    main_after: Mapped[str | None] = mapped_column(String(40))
    conflicts: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("status IN ('merged', 'conflict')", name="status"),)
