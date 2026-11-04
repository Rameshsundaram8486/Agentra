"""Database access for reports (no business rules). Used only by the reporting service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reporting.models import Report


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def get_report(session: Session, report_id: uuid.UUID) -> Report | None:
    return session.get(Report, report_id)


def latest(session: Session, project_id: uuid.UUID, report_type: str) -> Report | None:
    return session.scalar(
        select(Report)
        .where(Report.project_id == project_id, Report.report_type == report_type)
        .order_by(Report.version_no.desc())
        .limit(1)
    )


def reports_for_project(session: Session, project_id: uuid.UUID) -> list[Report]:
    return list(
        session.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.report_type, Report.version_no.desc()))
    )
