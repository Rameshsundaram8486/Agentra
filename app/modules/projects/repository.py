"""Queries on the project table. Used only by the projects service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.models import Project


def get(session: Session, project_id: uuid.UUID) -> Project | None:
    return session.get(Project, project_id)


def code_exists(session: Session, code: str) -> bool:
    return session.scalar(select(Project.id).where(Project.code == code)) is not None


def add(session: Session, project: Project) -> None:
    session.add(project)
    session.flush()


def list_projects(session: Session, project_ids: list[uuid.UUID] | None) -> list[Project]:
    query = select(Project).order_by(Project.created_at.desc())
    if project_ids is not None:
        query = query.where(Project.id.in_(project_ids))
    return list(session.scalars(query))
