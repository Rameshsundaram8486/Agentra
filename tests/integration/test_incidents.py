"""Incident records: opened from failed or blocked agent runs by configured rules, resolved with a root-cause
analysis by people, closed by someone else with verification evidence. Never edited."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.errors import InvalidTransitionError, PermissionDeniedError, ValidationFailedError
from app.modules.oversight.service import IncidentClose, RcaCreate
from tests.agent_support import ask, move_task, phase_task, process
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _incidents(run: Run, team: Team) -> list[Any]:
    return run(lambda s: s.oversight.list_incidents(team.owner.actor, team.project.id))


def _rca(owner_email: str, **changes: Any) -> RcaCreate:
    fields: dict[str, Any] = {
        "cause": "The model quoted text that is not in the brief",
        "cause_certainty": "probable",
        "contributing_factors": "Long brief with similar wording",
        "containment": "Nothing was saved; the run failed safely",
        "corrective_action": "Ask again after shortening the brief",
        "action_owner_email": owner_email,
        "target_date": date(2026, 12, 1),
        "verification_criteria": "The next run succeeds without grounding findings",
    }
    return RcaCreate(**{**fields, **changes})


@pytest.fixture
def failed(ba_team: Team, make_brief: Callable[..., Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> tuple[Team, Any]:
    """A clarify run whose output failed its checks: one incident."""
    brief = make_brief(ba_team)
    model.add(fake_response("this is not JSON"))
    queued = ask(run, ba_team, "clarify_brief", brief.id).run
    process(runner_for(), queued.id)
    return ba_team, queued


def test_a_failed_run_opens_an_incident_with_the_evidence_and_configured_severity(failed: tuple[Team, Any], run: Run) -> None:
    team, queued = failed

    [incident] = _incidents(run, team)

    assert (incident.incident_id, incident.category, incident.severity, incident.status) == ("INC-001", "guardrail_blocked", "medium", "open")
    assert incident.source_id == queued.id and incident.task_id == phase_task(run, team, "clarify_brief").id
    assert incident.title == "Ask about the project brief: guardrail_blocked"
    evidence = incident.evidence
    assert evidence["error_code"] == "guardrail_blocked" and evidence["attempts"] == 1
    assert evidence["workflow_task_state"] == "in_progress"  # the state when it failed
    assert evidence["blocking_findings"][0]["check"] == "schema"
    assert evidence["model_calls"][0]["status"] == "completed" and evidence["model_calls"][0]["request_id"] == "req_fake"


def test_a_repeat_failure_of_the_same_kind_is_a_recurrence_not_a_new_incident(
    failed: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, queued = failed
    move_task(run, team.owner.actor, phase_task(run, team, "clarify_brief"), "ready")  # failed -> ready, then ask again
    model.add(fake_response("still not JSON"))
    again = ask(run, team, "clarify_brief", queued.input_artifact_version_id)
    assert again.created
    process(runner_for(), again.run.id)

    [incident] = _incidents(run, team)
    assert incident.occurrences == 2
    assert [e.event for e in incident.events] == ["recurrence"]
    assert incident.events[0].data["run_id"] == str(again.run.id)


def test_waiting_states_do_not_open_incidents(ba_team: Team, make_brief: Callable[..., Any], run: Run, runner_for: Callable[..., AgentRunner], move_phase: Callable[..., None]) -> None:
    brief = make_brief(ba_team)
    queued = ask(run, ba_team, "clarify_brief", brief.id).run
    move_phase(ba_team.owner.actor, ba_team.project.id, 7, "blocked")  # the run will be blocked: precondition

    process(runner_for(), queued.id)

    assert run(lambda s: s.executions.get_run(ba_team.owner.actor, queued.id)).error_code == "precondition"
    assert _incidents(run, ba_team) == []


def test_resolving_needs_a_full_root_cause_analysis_by_a_person(failed: tuple[Team, Any], run: Run, ba_agent: TestUser) -> None:
    team, _ = failed
    incident = _incidents(run, team)[0]

    with pytest.raises(ValidationFailedError, match="must be a person on this project"):
        run(lambda s: s.oversight.resolve(team.pm.actor, incident.id, _rca("someone@else.test")))
    with pytest.raises(ValueError):
        _rca(team.pm.email, cause_certainty="certain")  # only confirmed, probable or unknown
    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.oversight.resolve(team.reviewer.actor, incident.id, _rca(team.pm.email)))  # no incident.manage
    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.oversight.resolve(ba_agent.actor, incident.id, _rca(team.pm.email)))

    resolved = run(lambda s: s.oversight.resolve(team.pm.actor, incident.id, _rca(team.pm.email)))

    assert resolved.status == "resolved"
    assert (resolved.rca.cause_certainty, resolved.rca.action_owner_name, resolved.rca.target_date) == ("probable", "PM", date(2026, 12, 1))
    with pytest.raises(InvalidTransitionError, match="is not open"):
        run(lambda s: s.oversight.resolve(team.pm.actor, incident.id, _rca(team.pm.email)))


def test_closing_needs_verification_by_someone_other_than_the_resolver(failed: tuple[Team, Any], run: Run) -> None:
    team, _ = failed
    incident = _incidents(run, team)[0]
    evidence = IncidentClose(verification_evidence="Run 2 succeeded with no grounding findings")

    with pytest.raises(InvalidTransitionError, match="must be resolved"):
        run(lambda s: s.oversight.close(team.owner.actor, incident.id, evidence))
    run(lambda s: s.oversight.resolve(team.owner.actor, incident.id, _rca(team.pm.email)))
    with pytest.raises(PermissionDeniedError, match="another person must verify"):
        run(lambda s: s.oversight.close(team.owner.actor, incident.id, evidence))
    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.oversight.close(team.pm.actor, incident.id, evidence))  # project managers resolve, not close
    with pytest.raises(ValueError):
        IncidentClose(verification_evidence="ok")

    closed = run(lambda s: s.oversight.close(team.reviewer.actor, incident.id, evidence))

    assert (closed.status, closed.closed_by_name, closed.verification_evidence) == ("closed", "Reviewer", evidence.verification_evidence)


def test_a_recurrence_reopens_a_resolved_incident_but_a_closed_one_starts_a_new_incident(
    failed: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, queued = failed
    incident = _incidents(run, team)[0]
    run(lambda s: s.oversight.resolve(team.owner.actor, incident.id, _rca(team.pm.email)))

    def fail_again() -> None:
        move_task(run, team.owner.actor, phase_task(run, team, "clarify_brief"), "ready")
        model.add(fake_response("not JSON"))
        process(runner_for(), ask(run, team, "clarify_brief", queued.input_artifact_version_id).run.id)

    fail_again()
    assert _incidents(run, team)[0].status == "open"  # the fix did not hold
    run(lambda s: s.oversight.resolve(team.owner.actor, incident.id, _rca(team.pm.email)))
    run(lambda s: s.oversight.close(team.reviewer.actor, incident.id, IncidentClose(verification_evidence="Verified on a later run")))
    fail_again()

    assert [(i.incident_id, i.status) for i in _incidents(run, team)] == [("INC-002", "open"), ("INC-001", "closed")]


def test_incidents_cannot_be_edited(failed: tuple[Team, Any], session_factory: sessionmaker[Session]) -> None:
    for statement in ("UPDATE incidents SET severity = 'low'", "DELETE FROM incident_events"):
        with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


def test_incidents_over_http(failed: tuple[Team, Any], client_for: Callable[..., Any], make_user: Callable[..., TestUser]) -> None:
    team, _ = failed
    pm = client_for(team.pm)
    [incident] = pm.get(f"/api/projects/{team.project.id}/incidents").json()
    body = _rca(team.pm.email).model_dump(mode="json")

    assert pm.post(f"/api/incidents/{incident['id']}/resolution", json=body).json()["status"] == "resolved"
    closed = client_for(team.reviewer).post(f"/api/incidents/{incident['id']}/closure", json={"verification_evidence": "Next run succeeded cleanly"})
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    assert client_for(make_user(name="Outsider")).get(f"/api/incidents/{incident['id']}").status_code == 404
