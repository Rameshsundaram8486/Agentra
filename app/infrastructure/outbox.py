"""Transactional outbox for external side effects.

A module adds a message in the same transaction as the state change that causes it, so the message exists
only if the change committed. A dispatcher later delivers it at least once; handlers receive the idempotency
key and must use it so that a repeated delivery has no extra effect.
"""

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.clock import Clock
from app.infrastructure.db import Base
from app.infrastructure.ids import new_id
from app.infrastructure.logging import redact
from app.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(16))  # pending | sent | dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_outbox_messages_pending", "status", "kind", "next_attempt_at"),)


@dataclass(frozen=True)
class OutboxDelivery:
    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    idempotency_key: str
    attempt: int


OutboxHandler = Callable[[OutboxDelivery], None]


class Outbox:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    def add(self, kind: str, payload: dict[str, Any], idempotency_key: str, *, max_attempts: int = 5) -> uuid.UUID:
        now = self._clock.now()
        message_id = self._session.scalar(
            insert(OutboxMessage)
            .values(
                id=new_id(),
                kind=kind,
                payload=payload,
                idempotency_key=idempotency_key,
                status="pending",
                attempts=0,
                max_attempts=max_attempts,
                next_attempt_at=now,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(OutboxMessage.id)
        )
        if message_id is None:
            message_id = self._session.scalar(
                select(OutboxMessage.id).where(OutboxMessage.idempotency_key == idempotency_key)
            )
        assert message_id is not None
        return message_id

    def get(self, message_id: uuid.UUID) -> OutboxMessage | None:
        return self._session.get(OutboxMessage, message_id, populate_existing=True)


def dispatch_one(
    session_factory: sessionmaker[Session],
    clock: Clock,
    handlers: Mapping[str, OutboxHandler],
    retry_delay: timedelta = timedelta(seconds=30),
) -> bool:
    """Delivers one due message. The row stays locked while its handler runs. Returns False when nothing was due."""
    kinds: Sequence[str] = list(handlers)
    with UnitOfWork(session_factory) as uow:
        now = clock.now()
        message = uow.session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.status == "pending", OutboxMessage.kind.in_(kinds), OutboxMessage.next_attempt_at <= now)
            .order_by(OutboxMessage.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if message is None:
            return False
        message.attempts += 1
        delivery = OutboxDelivery(message.id, message.kind, dict(message.payload), message.idempotency_key, message.attempts)
        try:
            handlers[message.kind](delivery)
        except Exception as exc:
            logger.exception("outbox delivery failed", extra={"message_id": str(message.id), "kind": message.kind})
            message.last_error = redact(f"{type(exc).__name__}: {exc}")[:2000]
            if message.attempts >= message.max_attempts:
                message.status = "dead"
            else:
                message.next_attempt_at = now + retry_delay * (2 ** (message.attempts - 1))
        else:
            message.status = "sent"
            message.sent_at = now
        uow.commit()
    return True
