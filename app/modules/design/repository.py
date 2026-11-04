"""Database access for design (no business rules). Used only by the design service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.design.models import DesignId, DesignItem, DesignVersion


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def registered_ids(session: Session, project_id: uuid.UUID) -> list[DesignId]:
    return list(session.scalars(select(DesignId).where(DesignId.project_id == project_id)))


def version_for(session: Session, artifact_version_id: uuid.UUID) -> DesignVersion | None:
    return session.scalar(select(DesignVersion).where(DesignVersion.artifact_version_id == artifact_version_id))


def items_for(session: Session, artifact_version_id: uuid.UUID) -> list[DesignItem]:
    return list(
        session.scalars(select(DesignItem).where(DesignItem.artifact_version_id == artifact_version_id).order_by(DesignItem.position))
    )
