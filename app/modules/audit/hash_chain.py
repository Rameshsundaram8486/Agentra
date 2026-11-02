"""Tamper-evident chaining of audit events.

Each event's hash covers its own fields plus the previous event's hash, so editing,
inserting or deleting any row breaks every hash after it.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

GENESIS_HASH = "0" * 64


def compute_hash(
    *,
    prev_hash: str,
    occurred_at: datetime,
    actor_id: UUID,
    action: str,
    entity_type: str,
    entity_id: str,
    project_id: UUID | None,
    reason: str | None,
    before: Any,
    after: Any,
) -> str:
    canonical = json.dumps(
        {
            "prev_hash": prev_hash,
            # Normalise to UTC: PostgreSQL returns timestamps in the session time zone.
            "occurred_at": occurred_at.astimezone(UTC).isoformat(),
            "actor_id": str(actor_id),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": str(project_id) if project_id else None,
            "reason": reason,
            "before": before,
            "after": after,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
