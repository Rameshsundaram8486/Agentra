"""Decision records keep the original recommendation separate from human input and the final outcome."""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, text

from app.composition import Services
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.artifacts.service import ArtifactCreate
from app.modules.decisions.service import DecisionOutcomeCreate, DecisionRequestCreate, DecisionView
from app.modules.errors import (
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from tests.support import Team, TestUser

Run = Callable[..., Any]

PLATFORM_QUESTION = DecisionRequestCreate(
    title="Intranet platform",
    question="Which SharePoint platform should the intranet use?",
    context="Customer has Microsoft 365 E3 licences.",
    options=[
        {"key": "spo", "title": "SharePoint Online", "description": "Included in E3; no servers."},
        {"key": "spse", "title": "SharePoint Subscription Edition", "description": "On-premises; full control."},
        {"key": "hybrid", "title": "Hybrid", "description": "Both, with search federation."},
    ],
    recommended_option="spo",
    recommendation_rationale="Licences already include it and there is no on-premises requirement in the brief.",
    assumptions=["No data residency rule forces on-premises hosting"],
    risks=["Custom web parts must use SPFx"],
)


def _raise(run: Run, team: Team, raiser: TestUser | None = None, data: DecisionRequestCreate = PLATFORM_QUESTION) -> DecisionView:
    return run(lambda s: s.decisions.raise_decision((raiser or team.agent).actor, team.project.id, data))


def _decide(run: Run, user: TestUser, decision: DecisionView, **fields: Any) -> DecisionView:
    return run(lambda s: s.decisions.record_outcome(user.actor, decision.id, DecisionOutcomeCreate(**fields)))


def test_agent_raises_and_owner_accepts_the_recommendation(run: Run, team: Team) -> None:
    raised = _raise(run, team)

    decided = _decide(run, team.owner, raised, action="accept")

    assert raised.status == "open" and raised.raised_by_name == team.agent.actor.display_name
    assert decided.status == "decided"
    assert decided.final_choice == "SharePoint Online"
    assert decided.outcomes[0].decided_by == team.owner.actor.id


def test_choosing_other_keeps_the_original_recommendation_intact(run: Run, team: Team, engine: Engine) -> None:
    raised = _raise(run, team)

    decided = _decide(run, team.pm, raised, action="other", custom_choice="SharePoint Online now, migrate archives later", comment="Phased")

    assert decided.final_choice == "SharePoint Online now, migrate archives later"
    assert decided.recommended_option == "spo"
    assert decided.recommendation_rationale == PLATFORM_QUESTION.recommendation_rationale
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT recommended_option, recommendation_rationale, options FROM decision_requests WHERE id = :id"), {"id": raised.id}
        ).one()
    assert stored.recommended_option == "spo"
    assert [option["key"] for option in stored.options] == ["spo", "spse", "hybrid"]


def test_selecting_another_listed_option(run: Run, team: Team) -> None:
    decided = _decide(run, team.owner, _raise(run, team), action="select_option", selected_option="hybrid")

    assert decided.final_choice == "Hybrid"


def test_selecting_the_recommended_option_or_an_unknown_one_is_rejected(run: Run, team: Team) -> None:
    raised = _raise(run, team)

    with pytest.raises(ValidationFailedError, match="use accept"):
        _decide(run, team.owner, raised, action="select_option", selected_option="spo")
    with pytest.raises(ValidationFailedError, match="Unknown option"):
        _decide(run, team.owner, raised, action="select_option", selected_option="sharepoint_2013")


def test_defer_then_decide_keeps_both_outcomes(run: Run, team: Team) -> None:
    raised = _raise(run, team)

    deferred = _decide(run, team.owner, raised, action="defer", comment="Waiting for licence audit")
    decided = _decide(run, team.owner, raised, action="modify", comment="SharePoint Online, but keep the archive on-premises")

    assert deferred.status == "deferred"
    assert decided.status == "decided"
    assert [(o.outcome_no, o.action) for o in decided.outcomes] == [(1, "defer"), (2, "modify")]
    assert decided.final_choice == "SharePoint Online (modified)"


def test_a_decided_request_cannot_be_decided_again(run: Run, team: Team) -> None:
    raised = _raise(run, team)
    _decide(run, team.owner, raised, action="accept")

    with pytest.raises(InvalidTransitionError, match="already been made"):
        _decide(run, team.pm, raised, action="reject", comment="Changed my mind")


def test_rejecting_records_no_final_choice(run: Run, team: Team) -> None:
    decided = _decide(run, team.owner, _raise(run, team), action="reject", comment="Out of scope for this project")

    assert (decided.status, decided.final_choice) == ("decided", None)


def test_question_without_recommendation_cannot_be_accepted(run: Run, team: Team) -> None:
    open_question = PLATFORM_QUESTION.model_copy(update={"recommended_option": None, "recommendation_rationale": ""})
    raised = _raise(run, team, data=open_question)

    with pytest.raises(ValidationFailedError, match="no recommendation"):
        _decide(run, team.owner, raised, action="accept")
    assert _decide(run, team.owner, raised, action="select_option", selected_option="spse").final_choice == "SharePoint Subscription Edition"


def test_agents_reviewers_and_outsiders_cannot_decide(run: Run, team: Team, make_user: Callable[..., TestUser]) -> None:
    raised = _raise(run, team)

    with pytest.raises(PermissionDeniedError, match="Only people"):
        _decide(run, team.agent, raised, action="accept")
    with pytest.raises(PermissionDeniedError, match="needs one of these roles"):
        _decide(run, team.reviewer, raised, action="accept")
    with pytest.raises(NotFoundError):
        _decide(run, make_user(), raised, action="accept")


def test_reviewers_cannot_raise_decisions(run: Run, team: Team) -> None:
    with pytest.raises(PermissionDeniedError):
        _raise(run, team, raiser=team.reviewer)


def test_linked_artifact_version_must_belong_to_the_same_project(run: Run, team: Team, make_team: Callable[..., Team]) -> None:
    other = make_team()
    foreign = run(
        lambda s: s.artifacts.create_artifact(
            other.agent.actor, other.project.id, ArtifactCreate(artifact_type="working_document", title="Other", content="x")
        )
    )

    with pytest.raises(ValidationFailedError, match="another project"):
        _raise(run, team, data=PLATFORM_QUESTION.model_copy(update={"artifact_version_id": foreign.current_version.id}))


def test_two_people_answering_at_once_produce_one_outcome(
    session_factory: Any, services_for: Callable[..., Services], run: Run, team: Team
) -> None:
    raised = _raise(run, team)
    barrier = threading.Barrier(2)
    results: list[str] = []

    def answer(user: TestUser, action: str) -> None:
        barrier.wait()
        try:
            with UnitOfWork(session_factory) as uow:
                fields = {"action": action} if action == "accept" else {"action": action, "comment": "No"}
                services_for(uow.session).decisions.record_outcome(user.actor, raised.id, DecisionOutcomeCreate(**fields))
                uow.commit()
            results.append("ok")
        except (ConflictError, InvalidTransitionError):
            results.append("refused")
        except Exception as exc:  # unique-constraint race surfacing at commit
            results.append(f"refused:{type(exc).__name__}")

    threads = [
        threading.Thread(target=answer, args=(team.owner, "accept")),
        threading.Thread(target=answer, args=(team.pm, "reject")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert results.count("ok") == 1
    assert len(run(lambda s: s.decisions.get_decision(team.owner.actor, raised.id)).outcomes) == 1


def test_raising_and_deciding_are_audited(run: Run, team: Team, engine: Engine) -> None:
    raised = _raise(run, team)
    _decide(run, team.owner, raised, action="defer", comment="Next week")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT action, actor_id, reason FROM audit_events WHERE entity_id = :id ORDER BY seq"), {"id": str(raised.id)}
        ).all()
    assert [(r.action, r.actor_id, r.reason) for r in rows] == [
        ("decision.raise", team.agent.actor.id, None),
        ("decision.outcome", team.owner.actor.id, "Next week"),
    ]
