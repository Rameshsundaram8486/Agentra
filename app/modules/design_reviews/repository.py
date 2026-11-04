"""Database access for design reviews (no business rules). Used only by the design reviews service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.design_reviews.models import DesignReview, DesignReviewFinding


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def review_for(session: Session, artifact_version_id: uuid.UUID) -> DesignReview | None:
    return session.scalar(select(DesignReview).where(DesignReview.artifact_version_id == artifact_version_id))


def latest_for_design(session: Session, design_version_id: uuid.UUID, kind: str) -> DesignReview | None:
    query = (
        select(DesignReview)
        .where(DesignReview.design_version_id == design_version_id, DesignReview.kind == kind)
        .order_by(DesignReview.created_at.desc(), DesignReview.id.desc())
        .limit(1)
    )
    return session.scalar(query)


def findings_for(session: Session, review_version_id: uuid.UUID) -> list[DesignReviewFinding]:
    query = select(DesignReviewFinding).where(DesignReviewFinding.review_version_id == review_version_id).order_by(DesignReviewFinding.position)
    return list(session.scalars(query))
