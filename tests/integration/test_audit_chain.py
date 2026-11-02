import threading
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.clock import FixedClock
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.identity.service import SYSTEM_USER_ID
from tests.support import Team

Run = Callable[..., Any]


def _latest_seq(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.scalar(select(func.max(AuditEvent.seq)))


def test_chain_verifies_after_real_activity(run: Run, team: Team) -> None:
    result = run(lambda s: s.audit.verify_chain())

    assert result.ok, result
    assert result.events_checked > 0


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET reason = 'edited' WHERE seq = :seq",
        "DELETE FROM audit_events WHERE seq = :seq",
        "TRUNCATE audit_events",
    ],
)
def test_database_refuses_to_change_or_remove_audit_events(engine: Engine, team: Team, statement: str) -> None:
    params = {"seq": _latest_seq(engine)} if ":seq" in statement else {}
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text(statement), params)


def test_tampering_is_detected_at_the_edited_event(engine: Engine, team: Team, clock: FixedClock) -> None:
    target = _latest_seq(engine)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            # Simulates someone with table-owner rights bypassing the trigger; rolled back afterwards.
            connection.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_no_update_delete"))
            connection.execute(text("UPDATE audit_events SET reason = 'quietly edited' WHERE seq = :seq"), {"seq": target})
            result = AuditService(Session(bind=connection), clock).verify_chain()
        finally:
            transaction.rollback()

    assert not result.ok
    assert result.first_broken_seq == target


def test_concurrent_writers_keep_a_single_valid_chain(
    session_factory: sessionmaker[Session], clock: FixedClock, run: Run
) -> None:
    def write_events(worker: int) -> None:
        for index in range(5):
            with UnitOfWork(session_factory) as uow:
                AuditService(uow.session, clock).record(
                    actor_id=SYSTEM_USER_ID, action="test.concurrent", entity_type="test", entity_id=f"{worker}-{index}"
                )
                uow.commit()

    threads = [threading.Thread(target=write_events, args=(worker,)) for worker in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert run(lambda s: s.audit.verify_chain()).ok
