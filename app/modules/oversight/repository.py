"""Database access for incidents (no business rules). Used only by the oversight service."""

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.oversight.models import Incident, IncidentEvent


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def get_incident(session: Session, incident_id: uuid.UUID) -> Incident | None:
    return session.get(Incident, incident_id)


def incidents_for_project(session: Session, project_id: uuid.UUID) -> list[Incident]:
    return list(session.scalars(select(Incident).where(Incident.project_id == project_id).order_by(Incident.number.desc())))


def incidents_like(session: Session, project_id: uuid.UUID, task_key: str | None, category: str) -> list[Incident]:
    return list(
        session.scalars(
            select(Incident)
            .where(Incident.project_id == project_id, Incident.task_key == task_key, Incident.category == category)
            .order_by(Incident.number.desc())
        )
    )


def next_number(session: Session, project_id: uuid.UUID) -> int:
    return (session.scalar(select(func.max(Incident.number)).where(Incident.project_id == project_id)) or 0) + 1


def events_for(session: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[IncidentEvent]]:
    grouped: dict[uuid.UUID, list[IncidentEvent]] = defaultdict(list)
    if ids:
        for row in session.scalars(select(IncidentEvent).where(IncidentEvent.incident_id.in_(ids)).order_by(IncidentEvent.seq)):
            grouped[row.incident_id].append(row)
    return {incident_id: grouped[incident_id] for incident_id in ids}
