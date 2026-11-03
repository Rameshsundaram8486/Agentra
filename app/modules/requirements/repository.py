"""Database access for requirements (no business rules). Used only by the requirements service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.requirements.models import RequirementId, RequirementItem, RequirementVersion


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def registered_ids(session: Session, project_id: uuid.UUID) -> list[RequirementId]:
    return list(session.scalars(select(RequirementId).where(RequirementId.project_id == project_id)))


def version_for(session: Session, artifact_version_id: uuid.UUID) -> RequirementVersion | None:
    return session.scalar(select(RequirementVersion).where(RequirementVersion.artifact_version_id == artifact_version_id))


def items_for(session: Session, artifact_version_id: uuid.UUID) -> list[RequirementItem]:
    return list(
        session.scalars(
            select(RequirementItem).where(RequirementItem.artifact_version_id == artifact_version_id).order_by(RequirementItem.position)
        )
    )

