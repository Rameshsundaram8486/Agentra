"""Queries on identity tables. Used only by the identity service."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.identity.models import ProjectMembership, User, UserSession


def get_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def get_active_session(session: Session, token_hash: str, now: datetime) -> UserSession | None:
    return session.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )


def revoke_session(session: Session, token_hash: str, now: datetime) -> None:
    session.execute(
        update(UserSession)
        .where(UserSession.token_hash == token_hash, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def roles_for(session: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> set[str]:
    return set(
        session.scalars(
            select(ProjectMembership.role).where(
                ProjectMembership.user_id == user_id, ProjectMembership.project_id == project_id
            )
        )
    )


def project_ids_for(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(select(ProjectMembership.project_id).where(ProjectMembership.user_id == user_id).distinct())
    )


def membership_exists(session: Session, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> bool:
    return (
        session.scalar(
            select(ProjectMembership.id).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user_id,
                ProjectMembership.role == role,
            )
        )
        is not None
    )


def list_members(session: Session, project_id: uuid.UUID) -> list[tuple[ProjectMembership, User]]:
    rows = session.execute(
        select(ProjectMembership, User)
        .join(User, User.id == ProjectMembership.user_id)
        .where(ProjectMembership.project_id == project_id)
        .order_by(User.display_name, ProjectMembership.role)
    )
    return [(membership, user) for membership, user in rows]
