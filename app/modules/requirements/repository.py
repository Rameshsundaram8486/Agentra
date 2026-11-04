"""Database access for requirements (no business rules). Used only by the requirements service."""

import uuid

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.requirements.models import ChangeRequest, ChangeRequestEvent, RequirementId, RequirementItem, RequirementVersion


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



def get_change_request(session: Session, change_request_id: uuid.UUID) -> ChangeRequest | None:
    return session.get(ChangeRequest, change_request_id)


def change_requests_for_project(session: Session, project_id: uuid.UUID) -> list[ChangeRequest]:
    return list(session.scalars(select(ChangeRequest).where(ChangeRequest.project_id == project_id).order_by(ChangeRequest.number.desc())))


def next_change_request_number(session: Session, project_id: uuid.UUID) -> int:
    current = session.scalar(select(func.max(ChangeRequest.number)).where(ChangeRequest.project_id == project_id))
    return (current or 0) + 1


def change_request_events(session: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ChangeRequestEvent]]:
    grouped: dict[uuid.UUID, list[ChangeRequestEvent]] = defaultdict(list)
    if ids:
        rows = session.scalars(select(ChangeRequestEvent).where(ChangeRequestEvent.change_request_id.in_(ids)).order_by(ChangeRequestEvent.seq))
        for row in rows:
            grouped[row.change_request_id].append(row)
    return {request_id: grouped[request_id] for request_id in ids}
