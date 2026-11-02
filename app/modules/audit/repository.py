"""Queries on the audit table. Used only by the audit service."""

import uuid
from collections.abc import Iterator

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent

# Arbitrary constant: serialises audit writers so each new event chains to the latest committed one.
_CHAIN_LOCK_KEY = 7_242_001


def lock_chain(session: Session) -> None:
    """Held until the transaction ends."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _CHAIN_LOCK_KEY})


def latest_hash(session: Session) -> str | None:
    return session.scalar(select(AuditEvent.hash).order_by(AuditEvent.seq.desc()).limit(1))


def add(session: Session, event: AuditEvent) -> None:
    session.add(event)
    session.flush()


def list_for_project(
    session: Session, project_id: uuid.UUID, limit: int, before_seq: int | None
) -> list[AuditEvent]:
    query = select(AuditEvent).where(AuditEvent.project_id == project_id)
    if before_seq is not None:
        query = query.where(AuditEvent.seq < before_seq)
    return list(session.scalars(query.order_by(AuditEvent.seq.desc()).limit(limit)))


def iterate_all(session: Session) -> Iterator[AuditEvent]:
    yield from session.scalars(select(AuditEvent).order_by(AuditEvent.seq).execution_options(yield_per=1000))
