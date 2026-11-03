"""A phase completes only when the current version of each required artifact has a valid approval."""

from collections.abc import Callable
from typing import Any

import pytest

from app.modules.artifacts.service import ArtifactCreate, ArtifactDetail, VersionCreate
from app.modules.decisions.service import ApprovalCreate
from app.modules.errors import InvalidTransitionError
from app.modules.workflow.service import PhaseRunView, TransitionRequest
from tests.support import Team

Run = Callable[..., Any]


@pytest.fixture
def team(make_team: Callable[..., Team], close_tasks: Callable[..., None]) -> Team:
    """These tests are about phase gates, so Phase 7's own tasks are closed first."""
    team = make_team()
    close_tasks(team, 7)
    return team


def _phase_7_in_review(run: Run, team: Team) -> PhaseRunView:
    phase = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 7)
    for user, state in ((team.owner, "ready"), (team.pm, "in_progress"), (team.agent, "waiting_for_review")):
        request = TransitionRequest(to_state=state, reason="step", expected_version=phase.version)
        phase = run(lambda s, u=user, r=request: s.workflow.transition_phase_run(u.actor, phase.id, r))
    return phase


def _complete(run: Run, team: Team, phase: PhaseRunView) -> PhaseRunView:
    request = TransitionRequest(to_state="completed", reason="Baseline approved", expected_version=phase.version)
    return run(lambda s: s.workflow.transition_phase_run(team.reviewer.actor, phase.id, request))


def _brd(run: Run, team: Team, title: str = "BRD") -> ArtifactDetail:
    data = ArtifactCreate(artifact_type="requirements_baseline", title=title, content=f"# {title} v1\n")
    return run(lambda s: s.artifacts.create_artifact(team.agent.actor, team.project.id, data))


def _review(run: Run, team: Team, artifact: ArtifactDetail, decision: str = "approved", comment: str | None = None) -> None:
    version = artifact.current_version
    data = ApprovalCreate(decision=decision, content_sha256=version.content_sha256, comment=comment)
    run(lambda s: s.decisions.record_approval(team.reviewer.actor, version.id, data))


def test_phase_shows_which_approvals_it_needs(run: Run, team: Team) -> None:
    phases = run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id))

    assert {p.phase: p.required_approvals for p in phases} == {
        7: ["requirements_baseline"],
        8: ["design_baseline"],
        9: ["implementation_report"],
        10: ["qa_completion_report"],
        11: ["uat_signoff_record"],
    }


def test_no_baseline_means_no_completion(run: Run, team: Team) -> None:
    phase = _phase_7_in_review(run, team)

    with pytest.raises(InvalidTransitionError, match="No requirements baseline exists yet"):
        _complete(run, team, phase)


def test_unapproved_or_rejected_baseline_blocks_completion(run: Run, team: Team) -> None:
    phase = _phase_7_in_review(run, team)
    brd = _brd(run, team)

    with pytest.raises(InvalidTransitionError, match="'BRD' v1 is not approved"):
        _complete(run, team, phase)
    _review(run, team, brd, "changes_requested", "Missing NFRs")
    with pytest.raises(InvalidTransitionError, match="not approved"):
        _complete(run, team, phase)


def test_approval_of_v1_does_not_carry_over_to_v2(run: Run, team: Team) -> None:
    phase = _phase_7_in_review(run, team)
    brd = _brd(run, team)
    _review(run, team, brd)
    v2 = run(lambda s: s.artifacts.add_version(team.agent.actor, brd.id, VersionCreate(content="# BRD v2\n", change_summary="Scope change", expected_current_version=1)))

    with pytest.raises(InvalidTransitionError, match="'BRD' v2 is not approved"):
        _complete(run, team, phase)

    _review(run, team, v2)
    assert _complete(run, team, phase).state == "completed"


def test_a_later_rejection_of_the_same_version_wins(run: Run, team: Team, make_user: Callable[..., Any], add_member: Any) -> None:
    second_reviewer = make_user(name="Second reviewer")
    add_member(team.owner, team.project.id, second_reviewer, "reviewer")
    phase = _phase_7_in_review(run, team)
    brd = _brd(run, team)
    _review(run, team, brd)
    version = brd.current_version
    run(
        lambda s: s.decisions.record_approval(
            second_reviewer.actor, version.id, ApprovalCreate(decision="rejected", content_sha256=version.content_sha256, comment="Wrong scope")
        )
    )

    with pytest.raises(InvalidTransitionError, match="not approved"):
        _complete(run, team, phase)


def test_every_artifact_of_a_required_type_must_be_approved(run: Run, team: Team) -> None:
    phase = _phase_7_in_review(run, team)
    functional, non_functional = _brd(run, team, "Functional"), _brd(run, team, "Non-functional")
    _review(run, team, functional)

    with pytest.raises(InvalidTransitionError, match="'Non-functional' v1 is not approved"):
        _complete(run, team, phase)

    _review(run, team, non_functional)
    assert _complete(run, team, phase).state == "completed"
