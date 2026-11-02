import pytest

from app.composition import CONFIG_DIR
from app.modules.errors import InvalidTransitionError, PermissionDeniedError
from app.modules.workflow.definitions import load_catalog
from app.modules.workflow.gates import phase_entry_failures, phase_exit_failures, task_start_failures
from app.modules.workflow.state_machine import allowed_targets, check_transition

CATALOG = load_catalog(CONFIG_DIR / "workflows")
PHASE = CATALOG.lifecycle("standard_phase")


def test_allowed_transition_for_permitted_role_passes() -> None:
    rule = check_transition(PHASE, "ready", "in_progress", {"project_manager"})

    assert rule.to == "in_progress"


def test_transition_missing_from_lifecycle_is_invalid() -> None:
    with pytest.raises(InvalidTransitionError, match="Cannot move from 'not_started' to 'completed'"):
        check_transition(PHASE, "not_started", "completed", {"owner"})


def test_role_not_listed_for_transition_is_denied() -> None:
    with pytest.raises(PermissionDeniedError, match="needs one of these roles"):
        check_transition(PHASE, "ready", "in_progress", {"agent", "reviewer"})


def test_terminal_state_cannot_change() -> None:
    with pytest.raises(InvalidTransitionError, match="final state"):
        check_transition(PHASE, "completed", "in_progress", {"owner"})


def test_only_the_system_can_mark_work_failed() -> None:
    with pytest.raises(PermissionDeniedError):
        check_transition(PHASE, "in_progress", "failed", {"owner", "project_manager"})

    assert check_transition(PHASE, "in_progress", "failed", {"system"}).to == "failed"


def test_agents_cannot_complete_a_review() -> None:
    with pytest.raises(PermissionDeniedError):
        check_transition(PHASE, "waiting_for_review", "completed", {"agent"})


def test_allowed_targets_depend_on_role() -> None:
    assert allowed_targets(PHASE, "not_started", {"owner"}) == ["ready", "cancelled"]
    assert allowed_targets(PHASE, "not_started", {"agent"}) == []
    assert allowed_targets(PHASE, "waiting_for_review", {"reviewer"}) == ["changes_requested", "completed"]


def test_entry_gate_lists_each_unfinished_required_phase() -> None:
    failures = phase_entry_failures(CATALOG.phase(8), {7: "in_progress", 8: "not_started"})

    assert failures == ["Phase 7 must be completed first (it is 'in_progress')"]
    assert phase_entry_failures(CATALOG.phase(8), {7: "completed"}) == []


def test_exit_gate_lists_open_tasks_and_accepts_cancelled_ones() -> None:
    assert phase_exit_failures({"a": "completed", "b": "in_progress", "c": "ready"}) == ["Tasks still open: b, c"]
    assert phase_exit_failures({"a": "completed", "b": "cancelled"}) == []


def test_task_start_gate_needs_running_phase_and_completed_dependencies() -> None:
    failures = task_start_failures("ready", ("gather",), {"gather": "in_progress"})

    assert failures == ["The phase must be in progress (it is 'ready')", "Waiting for tasks: gather"]
    assert task_start_failures("in_progress", ("gather",), {"gather": "completed"}) == []
