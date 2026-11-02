import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.modules.audit.hash_chain import GENESIS_HASH, compute_hash

ACTOR = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "prev_hash": GENESIS_HASH,
        "occurred_at": datetime(2026, 11, 2, 9, 30, tzinfo=UTC),
        "actor_id": ACTOR,
        "action": "workflow.phase_run_transition",
        "entity_type": "phase_run",
        "entity_id": "abc",
        "project_id": PROJECT,
        "reason": "Ready to start",
        "before": {"state": "not_started", "version": 1},
        "after": {"state": "ready", "version": 2},
    }
    fields.update(overrides)
    return fields


def test_hash_is_deterministic_sha256_hex() -> None:
    first = compute_hash(**_fields())

    assert first == compute_hash(**_fields())
    assert len(first) == 64 and int(first, 16) >= 0


def test_every_field_changes_the_hash() -> None:
    baseline = compute_hash(**_fields())
    changes = {
        "prev_hash": "f" * 64,
        "occurred_at": datetime(2026, 11, 2, 9, 31, tzinfo=UTC),
        "actor_id": uuid.uuid4(),
        "action": "workflow.task_transition",
        "entity_type": "task",
        "entity_id": "abd",
        "project_id": None,
        "reason": "Ready to start!",
        "before": {"state": "ready", "version": 1},
        "after": {"state": "ready", "version": 3},
    }

    for name, value in changes.items():
        assert compute_hash(**_fields(**{name: value})) != baseline, name


def test_same_instant_in_another_time_zone_hashes_the_same() -> None:
    dubai = timezone(timedelta(hours=4))
    instant_in_dubai = datetime(2026, 11, 2, 13, 30, tzinfo=dubai)

    assert compute_hash(**_fields(occurred_at=instant_in_dubai)) == compute_hash(**_fields())


def test_json_key_order_does_not_matter() -> None:
    reordered = {"version": 2, "state": "ready"}

    assert compute_hash(**_fields(after=reordered)) == compute_hash(**_fields())
