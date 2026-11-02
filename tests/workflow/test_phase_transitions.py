import threading
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, func, select

from app.composition import Services
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.audit.models import AuditEvent
from app.modules.errors import ConflictError, InvalidTransitionError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.identity.service import SYSTEM_ACTOR, Actor
from app.modules.workflow.models import PhaseRun, StateTransition
from app.modules.workflow.service import PhaseRunView, TransitionRequest
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _phase(run: Run, actor: Actor, project_id: uuid.UUID, number: int) -> PhaseRunView:
    return next(p for p in run(lambda s: s.workflow.list_phase_runs(actor, project_id)) if p.phase == number)


def _move(run: Run, user: TestUser | Actor, phase: PhaseRunView, to_state: str, reason: str = "test step") -> PhaseRunView:
    actor = user.actor if isinstance(user, TestUser) else user
    request = TransitionRequest(to_state=to_state, reason=reason, expected_version=phase.version)
    return run(lambda s: s.workflow.transition_phase_run(actor, phase.id, request))


def _complete_phase(run: Run, team: Team, number: int) -> PhaseRunView:
    phase = _phase(run, team.owner.actor, team.project.id, number)
    phase = _move(run, team.owner, phase, "ready")
    phase = _move(run, team.pm, phase, "in_progress")
    phase = _move(run, team.agent, phase, "waiting_for_review")
    return _move(run, team.reviewer, phase, "completed")


def _audit_count(engine: Engine, project_id: uuid.UUID) -> int:
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.project_id == project_id))


def test_new_project_opens_every_defined_phase_as_not_started(run: Run, team: Team) -> None:
    phases = run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id))

    assert [(p.phase, p.state, p.version) for p in phases] == [(n, "not_started", 1) for n in (7, 8, 9, 10, 11)]
    assert [p.primary_agent for p in phases] == ["business_analyst", "solution_architect", "developer", "qa_tester", "uat_release"]


def test_phase_7_happy_path_records_actor_and_reason_for_every_step(run: Run, team: Team) -> None:
    completed = _complete_phase(run, team, 7)

    history = run(lambda s: s.workflow.history(team.owner.actor, "phase_run", completed.id))
    assert completed.state == "completed" and completed.version == 5
    assert [(h.from_state, h.to_state, h.actor_id) for h in history] == [
        ("not_started", "ready", team.owner.actor.id),
        ("ready", "in_progress", team.pm.actor.id),
        ("in_progress", "waiting_for_review", team.agent.actor.id),
        ("waiting_for_review", "completed", team.reviewer.actor.id),
    ]
    assert all(h.reason == "test step" for h in history)


def test_each_transition_writes_one_transition_row_and_one_audit_event(run: Run, team: Team, engine: Engine) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)
    audit_before = _audit_count(engine, team.project.id)

    _move(run, team.owner, phase, "ready", reason="Inputs received")

    assert _audit_count(engine, team.project.id) == audit_before + 1
    with engine.connect() as connection:
        event = connection.execute(
            select(AuditEvent).where(AuditEvent.project_id == team.project.id).order_by(AuditEvent.seq.desc()).limit(1)
        ).one()
        transitions = connection.scalar(
            select(func.count()).select_from(StateTransition).where(StateTransition.entity_id == phase.id)
        )
    assert transitions == 1
    assert event.action == "workflow.phase_run_transition"
    assert event.actor_id == team.owner.actor.id
    assert event.reason == "Inputs received"
    assert event.before == {"state": "not_started", "version": 1}
    assert event.after == {"state": "ready", "version": 2}


def test_transition_not_in_lifecycle_is_rejected_and_changes_nothing(run: Run, team: Team, engine: Engine) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)
    audit_before = _audit_count(engine, team.project.id)

    with pytest.raises(InvalidTransitionError, match="Cannot move from 'not_started' to 'completed'"):
        _move(run, team.owner, phase, "completed")

    assert _phase(run, team.owner.actor, team.project.id, 7).state == "not_started"
    assert run(lambda s: s.workflow.history(team.owner.actor, "phase_run", phase.id)) == []
    assert _audit_count(engine, team.project.id) == audit_before


def test_role_not_allowed_for_a_transition_is_denied(run: Run, team: Team) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)

    with pytest.raises(PermissionDeniedError):
        _move(run, team.reviewer, phase, "ready")

    phase = _move(run, team.owner, phase, "ready")
    with pytest.raises(PermissionDeniedError):
        _move(run, team.agent, phase, "in_progress")


def test_agent_cannot_complete_its_own_review(run: Run, team: Team) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)
    for user, state in ((team.owner, "ready"), (team.pm, "in_progress"), (team.agent, "waiting_for_review")):
        phase = _move(run, user, phase, state)

    with pytest.raises(PermissionDeniedError):
        _move(run, team.agent, phase, "completed")


def test_outsider_can_neither_see_nor_move_a_phase(run: Run, team: Team, make_user: Callable[..., TestUser]) -> None:
    outsider = make_user()
    phase = _phase(run, team.owner.actor, team.project.id, 7)

    with pytest.raises(NotFoundError):
        run(lambda s: s.workflow.list_phase_runs(outsider.actor, team.project.id))
    with pytest.raises(NotFoundError):
        _move(run, outsider, phase, "ready")


def test_platform_admin_who_is_not_a_member_can_view_but_not_move(
    run: Run, team: Team, make_user: Callable[..., TestUser]
) -> None:
    admin = make_user(admin=True)
    phase = _phase(run, admin.actor, team.project.id, 7)

    assert phase.available_transitions == []
    with pytest.raises(PermissionDeniedError):
        _move(run, admin, phase, "ready")


def test_entry_gate_requires_the_previous_phase_completed(run: Run, team: Team) -> None:
    phase_8 = _phase(run, team.owner.actor, team.project.id, 8)

    with pytest.raises(InvalidTransitionError, match="Phase 7 must be completed first"):
        _move(run, team.owner, phase_8, "ready")

    _complete_phase(run, team, 7)
    assert _move(run, team.owner, phase_8, "ready").state == "ready"


def test_cancelling_skips_the_entry_gate_and_cancelled_is_final(run: Run, team: Team) -> None:
    phase_9 = _move(run, team.owner, _phase(run, team.owner.actor, team.project.id, 9), "cancelled")

    assert phase_9.state == "cancelled"
    with pytest.raises(InvalidTransitionError, match="final state"):
        _move(run, team.owner, phase_9, "ready")


def test_only_the_system_account_marks_a_phase_failed(run: Run, team: Team) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)
    phase = _move(run, team.owner, phase, "ready")
    phase = _move(run, team.pm, phase, "in_progress")

    with pytest.raises(PermissionDeniedError):
        _move(run, team.pm, phase, "failed")
    failed = _move(run, SYSTEM_ACTOR, phase, "failed", reason="Agent run crashed")
    assert failed.state == "failed"
    assert _move(run, team.pm, failed, "in_progress", reason="Retry after fix").state == "in_progress"


def test_blank_reason_is_rejected(run: Run, team: Team) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)

    with pytest.raises(ValidationFailedError, match="reason"):
        _move(run, team.owner, phase, "ready", reason="   ")


def test_stale_version_is_a_conflict(run: Run, team: Team) -> None:
    stale = _phase(run, team.owner.actor, team.project.id, 7)
    _move(run, team.owner, stale, "ready")

    with pytest.raises(ConflictError, match="changed since you loaded it"):
        _move(run, team.owner, stale, "cancelled")


def test_concurrent_transitions_on_the_same_version_let_exactly_one_win(
    session_factory: Any, clock: Any, policies: Any, run: Run, team: Team, engine: Engine
) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt(target: str) -> None:
        barrier.wait()
        try:
            with UnitOfWork(session_factory) as uow:
                Services(uow.session, clock, policies).workflow.transition_phase_run(
                    team.owner.actor, phase.id, TransitionRequest(to_state=target, reason="race", expected_version=1)
                )
                uow.commit()
            outcomes.append("ok")
        except ConflictError:
            outcomes.append("conflict")

    threads = [threading.Thread(target=attempt, args=(target,)) for target in ("ready", "cancelled")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == ["conflict", "ok"]
    with engine.connect() as connection:
        rows = connection.scalar(select(func.count()).select_from(StateTransition).where(StateTransition.entity_id == phase.id))
    assert rows == 1
    assert _phase(run, team.owner.actor, team.project.id, 7).version == 2


def test_database_guard_catches_a_change_committed_after_the_record_was_read(
    session_factory: Any, clock: Any, policies: Any, run: Run, team: Team
) -> None:
    phase = _phase(run, team.owner.actor, team.project.id, 7)
    with UnitOfWork(session_factory) as slow:
        slow_services = Services(slow.session, clock, policies)
        stale_copy = slow.session.get(PhaseRun, phase.id)  # this session now holds version 1
        assert stale_copy is not None and stale_copy.version == 1

        _move(run, team.owner, phase, "ready")  # another request commits version 2

        with pytest.raises(ConflictError, match="just now"):
            slow_services.workflow.transition_phase_run(
                team.owner.actor, phase.id, TransitionRequest(to_state="cancelled", reason="late", expected_version=1)
            )

    assert _phase(run, team.owner.actor, team.project.id, 7).state == "ready"


def test_available_transitions_reflect_the_callers_roles(run: Run, team: Team) -> None:
    def available(user: TestUser) -> list[str]:
        return _phase(run, user.actor, team.project.id, 7).available_transitions

    assert available(team.owner) == ["ready", "cancelled"]
    assert available(team.pm) == ["ready"]
    assert available(team.reviewer) == []
    assert available(team.agent) == []
