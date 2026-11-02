import uuid

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.clock import FixedClock
from app.infrastructure.outbox import Outbox, OutboxDelivery, dispatch_one
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture
def kind() -> str:
    return f"test_{uuid.uuid4().hex[:12]}"


def _add(session_factory: sessionmaker[Session], clock: FixedClock, kind: str, key: str, **kwargs: int) -> uuid.UUID:
    with UnitOfWork(session_factory) as uow:
        message_id = Outbox(uow.session, clock).add(kind, {"to": "pm@example.test"}, key, **kwargs)
        uow.commit()
    return message_id


def test_message_exists_only_if_its_transaction_commits(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    with UnitOfWork(session_factory) as uow:
        Outbox(uow.session, clock).add(kind, {"x": 1}, f"{kind}:rolled-back")
        # no commit: the state change failed, so the side effect must not happen either

    delivered: list[OutboxDelivery] = []
    assert not dispatch_one(session_factory, clock, {kind: delivered.append})
    assert delivered == []


def test_same_key_is_stored_and_delivered_once(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    key = f"{kind}:notify-review"
    first = _add(session_factory, clock, kind, key)
    second = _add(session_factory, clock, kind, key)
    delivered: list[OutboxDelivery] = []

    results = [dispatch_one(session_factory, clock, {kind: delivered.append}) for _ in range(2)]

    assert first == second
    assert results == [True, False]
    assert [d.idempotency_key for d in delivered] == [key]
    with UnitOfWork(session_factory) as uow:
        message = Outbox(uow.session, clock).get(first)
        assert message is not None and message.status == "sent" and message.sent_at == clock.now()


def test_failed_delivery_is_retried_then_dead_with_a_redacted_error(
    session_factory: sessionmaker[Session], clock: FixedClock, kind: str
) -> None:
    message_id = _add(session_factory, clock, kind, f"{kind}:fail", max_attempts=2)

    def fail(_: OutboxDelivery) -> None:
        raise ConnectionError("smtp refused, token=abc123secret")

    assert dispatch_one(session_factory, clock, {kind: fail})
    assert not dispatch_one(session_factory, clock, {kind: fail})  # waiting for backoff
    clock.advance(seconds=31)
    assert dispatch_one(session_factory, clock, {kind: fail})
    clock.advance(hours=1)
    assert not dispatch_one(session_factory, clock, {kind: fail})

    with UnitOfWork(session_factory) as uow:
        message = Outbox(uow.session, clock).get(message_id)
        assert message is not None
        assert (message.status, message.attempts) == ("dead", 2)
        assert "smtp refused" in (message.last_error or "")
        assert "abc123secret" not in (message.last_error or "")
