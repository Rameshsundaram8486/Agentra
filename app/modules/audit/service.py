"""Records consequential actions and verifies the hash chain. The only entry point for other modules.

Callers authorise reads before calling `list_for_project`; this module does not know about roles.
"""

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.audit import repository
from app.modules.audit.hash_chain import GENESIS_HASH, compute_hash
from app.modules.audit.models import AuditEvent
from app.modules.audit.schemas import AuditEventView, ChainVerification


def _to_json(value: Any) -> Any:
    """Plain JSON types only, so the stored value hashes the same after a round trip."""
    return None if value is None else json.loads(json.dumps(value, default=str))


class AuditService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    def record(
        self,
        *,
        actor_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | str,
        project_id: uuid.UUID | None = None,
        reason: str | None = None,
        before: Any = None,
        after: Any = None,
    ) -> None:
        """Append one event in the caller's transaction."""
        repository.lock_chain(self._session)
        fields = {
            "occurred_at": self._clock.now(),
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "project_id": project_id,
            "reason": reason,
            "before": _to_json(before),
            "after": _to_json(after),
        }
        prev_hash = repository.latest_hash(self._session) or GENESIS_HASH
        event = AuditEvent(**fields, prev_hash=prev_hash, hash=compute_hash(prev_hash=prev_hash, **fields))
        repository.add(self._session, event)

    def list_for_project(
        self, project_id: uuid.UUID, *, limit: int = 100, before_seq: int | None = None
    ) -> list[AuditEventView]:
        events = repository.list_for_project(self._session, project_id, min(limit, 500), before_seq)
        return [AuditEventView.model_validate(event, from_attributes=True) for event in events]

    def verify_chain(self) -> ChainVerification:
        expected_prev = GENESIS_HASH
        checked = 0
        for event in repository.iterate_all(self._session):
            recomputed = compute_hash(
                prev_hash=event.prev_hash,
                occurred_at=event.occurred_at,
                actor_id=event.actor_id,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                project_id=event.project_id,
                reason=event.reason,
                before=event.before,
                after=event.after,
            )
            if event.prev_hash != expected_prev or event.hash != recomputed:
                return ChainVerification(ok=False, events_checked=checked, first_broken_seq=event.seq)
            expected_prev = event.hash
            checked += 1
        return ChainVerification(ok=True, events_checked=checked)
