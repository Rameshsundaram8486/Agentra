"""Queries on Phase 9 tables. Used only by the implementation service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.implementation.models import ChangeSet, Merge, ProjectRepository, SandboxRun


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def project_repository(session: Session, project_id: uuid.UUID) -> ProjectRepository | None:
    return session.get(ProjectRepository, project_id)


def change_set(session: Session, version_id: uuid.UUID) -> ChangeSet | None:
    return session.scalar(select(ChangeSet).where(ChangeSet.artifact_version_id == version_id))


def change_sets_for(session: Session, project_id: uuid.UUID, work_item_id: str | None = None) -> list[ChangeSet]:
    """Oldest first."""
    query = select(ChangeSet).where(ChangeSet.project_id == project_id)
    if work_item_id is not None:
        query = query.where(ChangeSet.work_item_id == work_item_id)
    return list(session.scalars(query.order_by(ChangeSet.created_at, ChangeSet.id)))


def sandbox_runs_for(session: Session, version_ids: list[uuid.UUID]) -> list[SandboxRun]:
    """Newest first, by the order they were asked for (not the clock, which two runs can share)."""
    if not version_ids:
        return []
    query = select(SandboxRun).where(SandboxRun.change_set_version_id.in_(version_ids))
    return list(session.scalars(query.order_by(SandboxRun.seq.desc())))


def sandbox_run(session: Session, run_id: uuid.UUID, *, for_update: bool = False) -> SandboxRun | None:
    return session.get(SandboxRun, run_id, with_for_update=for_update, populate_existing=for_update)


def merges_for(session: Session, version_ids: list[uuid.UUID]) -> list[Merge]:
    if not version_ids:
        return []
    return list(session.scalars(select(Merge).where(Merge.change_set_version_id.in_(version_ids))))
