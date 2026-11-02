"""Audit data returned to callers."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventView(BaseModel):
    seq: int
    occurred_at: datetime
    actor_id: uuid.UUID
    action: str
    entity_type: str
    entity_id: str
    project_id: uuid.UUID | None
    reason: str | None
    before: Any
    after: Any
    hash: str


class ChainVerification(BaseModel):
    ok: bool
    events_checked: int
    first_broken_seq: int | None = None
