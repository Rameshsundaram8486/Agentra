"""Database access for the implementation backlog (no business rules). Used only by the backlog service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.backlog.models import BacklogId, BacklogItem, BacklogVersion


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def registered_ids(session: Session, project_id: uuid.UUID) -> list[BacklogId]:
    return list(session.scalars(select(BacklogId).where(BacklogId.project_id == project_id)))


def version_for(session: Session, artifact_version_id: uuid.UUID) -> BacklogVersion | None:
    return session.scalar(select(BacklogVersion).where(BacklogVersion.artifact_version_id == artifact_version_id))


def items_for(session: Session, artifact_version_id: uuid.UUID) -> list[BacklogItem]:
    return list(session.scalars(select(BacklogItem).where(BacklogItem.artifact_version_id == artifact_version_id).order_by(BacklogItem.position)))
