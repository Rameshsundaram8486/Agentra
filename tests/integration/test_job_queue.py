import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.clock import FixedClock
from app.infrastructure.job_queue import ClaimedJob, JobQueue, LeaseLostError, run_one_job
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture
def kind() -> str:
    """A job kind unique to this test, so tests never claim each other's jobs."""
    return f"test_{uuid.uuid4().hex[:12]}"


def _enqueue(session_factory: sessionmaker[Session], clock: FixedClock, kind: str, key: str, **kwargs: int) -> uuid.UUID:
    with UnitOfWork(session_factory) as uow:
        job_id = JobQueue(uow.session, clock).enqueue(kind, {"n": 1}, key, **kwargs)
        uow.commit()
    return job_id


def _status(session_factory: sessionmaker[Session], clock: FixedClock, job_id: uuid.UUID) -> tuple[str, int]:
    with UnitOfWork(session_factory) as uow:
        job = JobQueue(uow.session, clock).get(job_id)
        assert job is not None
        return job.status, job.attempts


def test_same_idempotency_key_creates_one_job_and_runs_it_once(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    key = f"{kind}:project-1:send-report"
    first = _enqueue(session_factory, clock, kind, key)
    second = _enqueue(session_factory, clock, kind, key)
    calls: list[ClaimedJob] = []

    ran = [run_one_job(session_factory, clock, "worker-a", {kind: calls.append}) for _ in range(3)]
    third = _enqueue(session_factory, clock, kind, key)

    assert first == second == third
    assert ran == [True, False, False]
    assert len(calls) == 1 and calls[0].idempotency_key == key
    assert _status(session_factory, clock, first) == ("succeeded", 1)


def test_crashed_worker_job_is_reclaimed_after_its_lease_expires(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    job_id = _enqueue(session_factory, clock, kind, f"{kind}:crash")
    with UnitOfWork(session_factory) as uow:
        assert JobQueue(uow.session, clock).claim("worker-a", [kind], lease=timedelta(minutes=5)) is not None
        uow.commit()
    # worker-a dies here without completing.

    with UnitOfWork(session_factory) as uow:
        assert JobQueue(uow.session, clock).claim("worker-b", [kind]) is None  # lease still valid
    clock.advance(minutes=6)
    with UnitOfWork(session_factory) as uow:
        reclaimed = JobQueue(uow.session, clock).claim("worker-b", [kind])
        uow.commit()

    assert reclaimed is not None and reclaimed.id == job_id and reclaimed.attempt == 2
    with UnitOfWork(session_factory) as uow, pytest.raises(LeaseLostError):
        JobQueue(uow.session, clock).complete(job_id, "worker-a")
    with UnitOfWork(session_factory) as uow:
        JobQueue(uow.session, clock).complete(job_id, "worker-b")
        uow.commit()
    assert _status(session_factory, clock, job_id) == ("succeeded", 2)


def test_failing_job_is_retried_with_backoff_then_dead(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    job_id = _enqueue(session_factory, clock, kind, f"{kind}:flaky", max_attempts=2)

    def explode(_: ClaimedJob) -> None:
        raise RuntimeError("upstream unavailable password=hunter2secret")

    assert run_one_job(session_factory, clock, "worker-a", {kind: explode})
    assert _status(session_factory, clock, job_id) == ("queued", 1)
    assert not run_one_job(session_factory, clock, "worker-a", {kind: explode})  # backoff not elapsed
    clock.advance(seconds=31)
    assert run_one_job(session_factory, clock, "worker-a", {kind: explode})

    clock.advance(hours=1)
    assert not run_one_job(session_factory, clock, "worker-a", {kind: explode})
    with UnitOfWork(session_factory) as uow:
        job = JobQueue(uow.session, clock).get(job_id)
        assert job is not None
        assert (job.status, job.attempts) == ("dead", 2)
        assert "upstream unavailable" in (job.last_error or "")
        assert "hunter2secret" not in (job.last_error or "")


def test_lease_expiring_on_the_final_attempt_marks_the_job_dead(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    job_id = _enqueue(session_factory, clock, kind, f"{kind}:last", max_attempts=1)
    with UnitOfWork(session_factory) as uow:
        JobQueue(uow.session, clock).claim("worker-a", [kind], lease=timedelta(minutes=1))
        uow.commit()

    clock.advance(minutes=2)
    with UnitOfWork(session_factory) as uow:
        assert JobQueue(uow.session, clock).claim("worker-b", [kind]) is None
        uow.commit()

    assert _status(session_factory, clock, job_id) == ("dead", 1)


def test_concurrent_workers_skip_jobs_locked_by_each_other(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    first = _enqueue(session_factory, clock, kind, f"{kind}:1")
    second = _enqueue(session_factory, clock, kind, f"{kind}:2")

    with UnitOfWork(session_factory) as uow_a, UnitOfWork(session_factory) as uow_b:
        claim_a = JobQueue(uow_a.session, clock).claim("worker-a", [kind])
        claim_b = JobQueue(uow_b.session, clock).claim("worker-b", [kind])  # while A's transaction is open
        claim_c = JobQueue(uow_b.session, clock).claim("worker-b", [kind])

    assert claim_a is not None and claim_b is not None
    assert {claim_a.id, claim_b.id} == {first, second}
    assert claim_c is None
