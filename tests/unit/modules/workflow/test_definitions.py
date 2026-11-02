from typing import Any

import pytest
from pydantic import ValidationError

from app.composition import CONFIG_DIR
from app.modules.workflow.definitions import Lifecycle, PhaseDefinition, WorkflowCatalog, load_catalog


def _lifecycle_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "key": "sample",
        "version": 1,
        "initial_state": "draft",
        "states": ["draft", "review", "done"],
        "terminal_states": ["done"],
        "transitions": [
            {"from": "draft", "to": "review", "roles": ["agent"]},
            {"from": "review", "to": "done", "roles": ["reviewer"]},
        ],
    }
    data.update(overrides)
    return data


def _phase_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "key": "phase_07_x",
        "version": 1,
        "phase": 7,
        "name": "X",
        "primary_agent": "business_analyst",
        "lifecycle": "sample",
        "task_lifecycle": "sample",
    }
    data.update(overrides)
    return data


def test_real_workflow_config_loads_mvp_phases_in_sequence() -> None:
    catalog = load_catalog(CONFIG_DIR / "workflows")

    assert sorted(catalog.phases) == [7, 8, 9, 10, 11]
    assert catalog.phase(7).entry.requires_completed_phases == ()
    for number in (8, 9, 10, 11):
        assert catalog.phase(number).entry.requires_completed_phases == (number - 1,)


def test_real_lifecycles_have_every_state_the_specs_require() -> None:
    catalog = load_catalog(CONFIG_DIR / "workflows")
    required = {
        "not_started", "ready", "in_progress", "waiting_for_input", "waiting_for_review",
        "changes_requested", "blocked", "failed", "completed", "cancelled",
    }  # fmt: skip

    for lifecycle in catalog.lifecycles.values():
        assert required <= set(lifecycle.states)


def test_unknown_state_in_transition_is_rejected() -> None:
    data = _lifecycle_data(transitions=[{"from": "draft", "to": "published", "roles": ["agent"]}])

    with pytest.raises(ValidationError, match="unknown state"):
        Lifecycle.model_validate(data)


def test_unknown_role_is_rejected() -> None:
    data = _lifecycle_data(transitions=[{"from": "draft", "to": "review", "roles": ["intern"]}])

    with pytest.raises(ValidationError, match="unknown roles"):
        Lifecycle.model_validate(data)


def test_transition_out_of_terminal_state_is_rejected() -> None:
    data = _lifecycle_data(transitions=[{"from": "done", "to": "draft", "roles": ["owner"]}])

    with pytest.raises(ValidationError, match="terminal"):
        Lifecycle.model_validate(data)


def test_duplicate_transition_is_rejected() -> None:
    rule = {"from": "draft", "to": "review", "roles": ["agent"]}

    with pytest.raises(ValidationError, match="twice"):
        Lifecycle.model_validate(_lifecycle_data(transitions=[rule, rule]))


def test_task_depending_on_unknown_task_is_rejected() -> None:
    tasks = [{"key": "draft_requirements", "title": "Draft", "depends_on": ["gather_sources"]}]

    with pytest.raises(ValidationError, match="unknown tasks"):
        PhaseDefinition.model_validate(_phase_data(tasks=tasks))


def test_task_dependency_cycle_is_rejected() -> None:
    tasks = [
        {"key": "first_task", "title": "A", "depends_on": ["second_task"]},
        {"key": "second_task", "title": "B", "depends_on": ["first_task"]},
    ]

    with pytest.raises(ValidationError, match="cycle"):
        PhaseDefinition.model_validate(_phase_data(tasks=tasks))


def test_phase_using_unknown_lifecycle_is_rejected() -> None:
    lifecycle = Lifecycle.model_validate(_lifecycle_data())
    phase = PhaseDefinition.model_validate(_phase_data(lifecycle="missing"))

    with pytest.raises(ValidationError, match="unknown lifecycle"):
        WorkflowCatalog(lifecycles={"sample": lifecycle}, phases={7: phase})


def test_phase_requiring_a_later_or_missing_phase_is_rejected() -> None:
    lifecycle = Lifecycle.model_validate(_lifecycle_data())
    phase = PhaseDefinition.model_validate(_phase_data(entry={"requires_completed_phases": [8]}))

    with pytest.raises(ValidationError, match="earlier defined phase"):
        WorkflowCatalog(lifecycles={"sample": lifecycle}, phases={7: phase})
