"""Database access for artifacts (no business rules). Used only by the artifacts service."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.artifacts.models import Artifact, ArtifactVersion


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def get_artifact(session: Session, artifact_id: uuid.UUID) -> Artifact | None:
    return session.get(Artifact, artifact_id)


def get_version(session: Session, version_id: uuid.UUID) -> ArtifactVersion | None:
    return session.get(ArtifactVersion, version_id)


def get_version_by_number(session: Session, artifact_id: uuid.UUID, version_no: int) -> ArtifactVersion | None:
    return session.scalar(
        select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id, ArtifactVersion.version_no == version_no)
    )


def title_taken(session: Session, project_id: uuid.UUID, artifact_type: str, title: str) -> bool:
    return (
        session.scalar(
            select(Artifact.id).where(
                Artifact.project_id == project_id, Artifact.artifact_type == artifact_type, Artifact.title == title
            )
        )
        is not None
    )


def artifacts_for_project(session: Session, project_id: uuid.UUID, artifact_type: str | None = None) -> list[Artifact]:
    query = select(Artifact).where(Artifact.project_id == project_id)
    if artifact_type is not None:
        query = query.where(Artifact.artifact_type == artifact_type)
    return list(session.scalars(query.order_by(Artifact.artifact_type, Artifact.title)))


def versions_for(session: Session, artifact_id: uuid.UUID) -> list[ArtifactVersion]:
    return list(
        session.scalars(
            select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id).order_by(ArtifactVersion.version_no)
        )
    )


def current_versions(session: Session, artifacts: list[Artifact]) -> dict[uuid.UUID, ArtifactVersion]:
    if not artifacts:
        return {}
    wanted = {(a.id, a.current_version_no) for a in artifacts}
    rows = session.scalars(select(ArtifactVersion).where(ArtifactVersion.artifact_id.in_([a.id for a in artifacts])))
    return {row.artifact_id: row for row in rows if (row.artifact_id, row.version_no) in wanted}


def author_ids(session: Session, artifact_id: uuid.UUID) -> set[uuid.UUID]:
    return set(session.scalars(select(ArtifactVersion.author_id).where(ArtifactVersion.artifact_id == artifact_id)))


def advance_version(session: Session, artifact_id: uuid.UUID, expected_version_no: int, now: datetime) -> bool:
    """Optimistic lock: moves current_version_no forward only if nobody else did first."""
    result = session.execute(
        update(Artifact)
        .where(Artifact.id == artifact_id, Artifact.current_version_no == expected_version_no)
        .values(current_version_no=expected_version_no + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        return False
    session.expire_all()
    return True
