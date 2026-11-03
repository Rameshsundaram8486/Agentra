from collections.abc import Callable
from typing import Any

import pytest

from app.composition import Policies
from app.modules.errors import InvalidTransitionError
from app.modules.workflow.definitions import TaskDefinition
from app.modules.workflow.service import PhaseRunView, TaskView, TransitionRequest
from tests.support import Team, TestUser, with_phase_tasks

Run = Callable[..., Any]

TASKS = [
    TaskDefinition(key="gather_sources", title="Gather source documents", agent="business_analyst"),
    TaskDefinition(key="draft_requirements", title="Draft requirements", agent="business_analyst", depends_on=("gather_sources",)),
]


@pytest.fixture
def task_policies(policies: Policies) -> Policies:
    return with_phase_tasks(policies, 7, TASKS)


@pytest.fixture
def task_team(make_team: Callable[..., Team], task_policies: Policies) -> Team:
    return make_team(policies=task_policies)


@pytest.fixture
def run_tasks(run: Run, task_policies: Policies) -> Run:
    return lambda fn: run(fn, policies=task_policies)


def _phase_7(run_tasks: Run, team: Team) -> PhaseRunView:
    return next(p for p in run_tasks(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 7)


def _task(run_tasks: Run, team: Team, key: str) -> TaskView:
    return next(t for t in _phase_7(run_tasks, team).tasks if t.key == key)


def _move_task(run_tasks: Run, user: TestUser, task: TaskView, to_state: str) -> TaskView:
    request = TransitionRequest(to_state=to_state, reason="task step", expected_version=task.version)
    return run_tasks(lambda s: s.workflow.transition_task(user.actor, task.id, request))


def _move_phase(run_tasks: Run, user: TestUser, phase: PhaseRunView, to_state: str) -> PhaseRunView:
    request = TransitionRequest(to_state=to_state, reason="phase step", expected_version=phase.version)
    return run_tasks(lambda s: s.workflow.transition_phase_run(user.actor, phase.id, request))


def _start_phase(run_tasks: Run, team: Team) -> PhaseRunView:
    phase = _move_phase(run_tasks, team.owner, _phase_7(run_tasks, team), "ready")
    return _move_phase(run_tasks, team.pm, phase, "in_progress")


def _finish_task(run_tasks: Run, team: Team, key: str) -> TaskView:
    task = _move_task(run_tasks, team.owner, _task(run_tasks, team, key), "ready")
    task = _move_task(run_tasks, team.agent, task, "in_progress")
    task = _move_task(run_tasks, team.agent, task, "waiting_for_review")
    return _move_task(run_tasks, team.reviewer, task, "completed")


def test_tasks_are_created_from_the_phase_definition(run_tasks: Run, task_team: Team) -> None:
    tasks = _phase_7(run_tasks, task_team).tasks

    assert [(t.key, t.state, t.depends_on) for t in tasks] == [
        ("gather_sources", "not_started", []),
        ("draft_requirements", "not_started", ["gather_sources"]),
    ]


def test_task_cannot_start_while_its_phase_is_not_in_progress(run_tasks: Run, task_team: Team) -> None:
    task = _move_task(run_tasks, task_team.owner, _task(run_tasks, task_team, "gather_sources"), "ready")

    with pytest.raises(InvalidTransitionError, match="phase must be in progress"):
        _move_task(run_tasks, task_team.agent, task, "in_progress")


def test_task_waits_for_its_dependencies(run_tasks: Run, task_team: Team) -> None:
    _start_phase(run_tasks, task_team)
    draft = _move_task(run_tasks, task_team.owner, _task(run_tasks, task_team, "draft_requirements"), "ready")

    with pytest.raises(InvalidTransitionError, match="Waiting for tasks: gather_sources"):
        _move_task(run_tasks, task_team.agent, draft, "in_progress")

    _finish_task(run_tasks, task_team, "gather_sources")
    assert _move_task(run_tasks, task_team.agent, draft, "in_progress").state == "in_progress"


def test_phase_cannot_complete_while_tasks_are_open(
    run_tasks: Run, task_team: Team, task_policies: Policies, approve_phase_documents: Callable[..., Any]
) -> None:
    phase = _start_phase(run_tasks, task_team)
    _finish_task(run_tasks, task_team, "gather_sources")
    phase = _move_phase(run_tasks, task_team.agent, phase, "waiting_for_review")

    with pytest.raises(InvalidTransitionError, match="Tasks still open: draft_requirements"):
        _move_phase(run_tasks, task_team.reviewer, phase, "completed")

    _move_task(run_tasks, task_team.pm, _task(run_tasks, task_team, "draft_requirements"), "cancelled")
    approve_phase_documents(task_team, 7, policies=task_policies)
    assert _move_phase(run_tasks, task_team.reviewer, phase, "completed").state == "completed"


def test_tasks_cannot_start_once_the_phase_has_moved_to_review(run_tasks: Run, task_team: Team) -> None:
    phase = _start_phase(run_tasks, task_team)
    task = _move_task(run_tasks, task_team.owner, _task(run_tasks, task_team, "gather_sources"), "ready")
    _move_phase(run_tasks, task_team.agent, phase, "waiting_for_review")

    with pytest.raises(InvalidTransitionError, match="it is 'waiting_for_review'"):
        _move_task(run_tasks, task_team.agent, task, "in_progress")
