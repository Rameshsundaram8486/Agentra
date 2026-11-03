"""Database access for approvals and decisions (no business rules). Used only by the decisions service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.decisions.models import Approval, DecisionOutcome, DecisionRequest


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def latest_approval(session: Session, version_id: uuid.UUID) -> Approval | None:
    return session.scalar(
        select(Approval).where(Approval.artifact_version_id == version_id).order_by(Approval.seq.desc()).limit(1)
    )


def approvals_for_artifact(session: Session, artifact_id: uuid.UUID) -> list[Approval]:
    return list(session.scalars(select(Approval).where(Approval.artifact_id == artifact_id).order_by(Approval.seq.desc())))


def get_request(session: Session, decision_id: uuid.UUID) -> DecisionRequest | None:
    return session.get(DecisionRequest, decision_id)


def requests_for_project(session: Session, project_id: uuid.UUID) -> list[DecisionRequest]:
    return list(
        session.scalars(
            select(DecisionRequest).where(DecisionRequest.project_id == project_id).order_by(DecisionRequest.created_at.desc())
        )
    )


def outcomes_for(session: Session, request_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DecisionOutcome]]:
    grouped: dict[uuid.UUID, list[DecisionOutcome]] = {request_id: [] for request_id in request_ids}
    if not request_ids:
        return grouped
    rows = session.scalars(
        select(DecisionOutcome)
        .where(DecisionOutcome.decision_request_id.in_(request_ids))
        .order_by(DecisionOutcome.outcome_no)
    )
    for row in rows:
        grouped[row.decision_request_id].append(row)
    return grouped
