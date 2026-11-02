"""PostgreSQL job queue (SELECT ... FOR UPDATE SKIP LOCKED).

- One job per idempotency key: enqueueing the same key again returns the existing job.
- A claim is a lease. If a worker dies, the lease expires and another worker reclaims the job.
- A worker that lost its lease cannot complete the job.
- After max_attempts failures the job is dead and is not retried.
"""

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, and_, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.clock import Clock
from app.infrastructure.db import Base
from app.infrastructure.ids import new_id
from app.infrastructure.logging import redact
from app.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

DEFAULT_LEASE = timedelta(minutes=5)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(16))  # queued | running | succeeded | dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(64))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_jobs_claimable", "status", "kind", "run_after"),)


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    idempotency_key: str
    attempt: int


class LeaseLostError(Exception):
    """The worker's lease expired and the job was reclaimed by another worker."""


class JobQueue:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        idempotency_key: str,
        *,
        max_attempts: int = 3,
        run_after: datetime | None = None,
    ) -> uuid.UUID:
        now = self._clock.now()
        job_id = self._session.scalar(
            insert(Job)
            .values(
                id=new_id(),
                kind=kind,
                payload=payload,
                idempotency_key=idempotency_key,
                status="queued",
                attempts=0,
                max_attempts=max_attempts,
                run_after=run_after or now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(Job.id)
        )
        if job_id is None:
            job_id = self._session.scalar(select(Job.id).where(Job.idempotency_key == idempotency_key))
        assert job_id is not None
        return job_id

    def claim(self, worker_id: str, kinds: Sequence[str], lease: timedelta = DEFAULT_LEASE) -> ClaimedJob | None:
        """Takes the next due job of these kinds, or a running one whose lease has expired."""
        now = self._clock.now()
        while True:
            job = self._session.scalars(
                select(Job)
                .where(
                    Job.kind.in_(kinds),
                    or_(
                        and_(Job.status == "queued", Job.run_after <= now),
                        and_(Job.status == "running", Job.locked_until < now),
                    ),
                )
                .order_by(Job.run_after)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
            if job is None:
                return None
            if job.attempts >= job.max_attempts:
                # Its last attempt crashed without reporting back.
                job.status, job.locked_by, job.locked_until, job.updated_at = "dead", None, None, now
                job.last_error = job.last_error or "worker lease expired on the final attempt"
                self._session.flush()
                continue
            job.status = "running"
            job.attempts += 1
            job.locked_by = worker_id
            job.locked_until = now + lease
            job.updated_at = now
            self._session.flush()
            return ClaimedJob(job.id, job.kind, dict(job.payload), job.idempotency_key, job.attempts)

    def complete(self, job_id: uuid.UUID, worker_id: str) -> None:
        self._finish(job_id, worker_id, status="succeeded")

    def fail(self, job_id: uuid.UUID, worker_id: str, error: str, retry_delay: timedelta = timedelta(seconds=30)) -> None:
        job = self._session.get(Job, job_id, with_for_update=True, populate_existing=True)
        if job is None or job.status != "running" or job.locked_by != worker_id:
            raise LeaseLostError(f"job {job_id} is no longer held by {worker_id}")
        now = self._clock.now()
        exhausted = job.attempts >= job.max_attempts
        job.status = "dead" if exhausted else "queued"
        job.run_after = now if exhausted else now + retry_delay * (2 ** (job.attempts - 1))
        job.locked_by = job.locked_until = None
        job.last_error = redact(error)[:2000]
        job.updated_at = now
        self._session.flush()

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self._session.get(Job, job_id, populate_existing=True)

    def _finish(self, job_id: uuid.UUID, worker_id: str, *, status: str) -> None:
        result = self._session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "running", Job.locked_by == worker_id)
            .values(status=status, locked_by=None, locked_until=None, updated_at=self._clock.now())
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise LeaseLostError(f"job {job_id} is no longer held by {worker_id}")


JobHandler = Callable[[ClaimedJob], None]


def run_one_job(
    session_factory: sessionmaker[Session],
    clock: Clock,
    worker_id: str,
    handlers: Mapping[str, JobHandler],
    lease: timedelta = DEFAULT_LEASE,
) -> bool:
    """Claims and runs one job. Handlers manage their own transactions. Returns False when nothing was due."""
    with UnitOfWork(session_factory) as uow:
        job = JobQueue(uow.session, clock).claim(worker_id, list(handlers), lease)
        uow.commit()
    if job is None:
        return False

    try:
        handlers[job.kind](job)
    except Exception as exc:
        logger.exception("job failed", extra={"job_id": str(job.id), "kind": job.kind, "attempt": job.attempt})
        with UnitOfWork(session_factory) as uow:
            JobQueue(uow.session, clock).fail(job.id, worker_id, f"{type(exc).__name__}: {exc}")
            uow.commit()
    else:
        with UnitOfWork(session_factory) as uow:
            JobQueue(uow.session, clock).complete(job.id, worker_id)
            uow.commit()
    return True
