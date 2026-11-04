"""Phase 8 (Increment 4a) end to end with a scripted model: compare options, draft the design, requirement
coverage, staleness after a requirements change, and the phase gate."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate, DecisionOutcomeCreate
from app.modules.errors import InvalidTransitionError, PermissionDeniedError, ValidationFailedError
from app.modules.executions.schemas import AgentRunCreate
from app.modules.requirements.service import ChangeRequestCreate, ChangeRequestDecisionCreate
from app.modules.workflow.service import TransitionRequest
from tests.agent_support import ask, compare_output, design_items, design_json, draft_items, draft_json, move_task, phase_task, process
from tests.support import Team, TestUser

Run = Callable[..., Any]


# Fixtures ------------------------------------------------------------------------------------------

def _approve(run: Run, reviewer: TestUser, version_id: Any, decision: str = "approved", comment: str | None = None) -> None:
    run(lambda s: s.decisions.record_approval(reviewer.actor, version_id, ApprovalCreate(
        decision=decision, comment=comment, content_sha256=s.artifacts.version_record(version_id).content_sha256)))


def _move_phase(run: Run, actor: Any, team: Team, number: int, state: str) -> Any:
    phase = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == number)
    return run(lambda s: s.workflow.transition_phase_run(actor, phase.id, TransitionRequest(to_state=state, reason="Test step", expected_version=phase.version)))


def _requirements(run: Run, team: Team) -> Any:
    return run(lambda s: s.requirements.view(team.owner.actor, team.project.id))


def _design(run: Run, team: Team) -> Any:
    return run(lambda s: s.design.view(team.owner.actor, team.project.id))


def _ask_sa(run: Run, team: Team, task_key: str, actor: Any = None) -> Any:
    data = AgentRunCreate(agent_key="solution_architect", task_key=task_key, artifact_version_id=_requirements(run, team).version_id)
    return run(lambda s: s.executions.request_run(actor or team.pm.actor, team.project.id, data))


def _sa_task(run: Run, team: Team, key: str) -> Any:
    return phase_task(run, team, key, phase=8)


# Compare options -------------------------------------------------------------------------------------

def test_options_are_scored_by_the_agent_and_totalled_by_agentra(
    phase8: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, sa_agent: TestUser
) -> None:
    team = phase8
    model.add(fake_response(json.dumps(compare_output())))
    queued = _ask_sa(run, team, "compare_options").run
    assert (queued.context_documents, queued.context_decisions) == (2, 4)

    process(runner_for(), queued.id)

    detail = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
    assert detail.status == "succeeded", detail.error_message
    [decision] = [d for d in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)) if d.raised_by == sa_agent.actor.id]
    # power_apps: (5*4 + 3*4 + 2*5) / 50 = 84%; custom_web_app: (25 + 6 + 4) / 50 = 70%
    assert "Weighted scores, calculated by Agentra from the agent's scores: Power Apps 84%, Custom Web App 70%." in decision.context
    assert decision.recommended_option == "power_apps" and "Weighted score (calculated by Agentra): 84%" in decision.options[0].description
    assert "To verify: Dataverse capacity included in current licences" in decision.risks
    assert detail.output["weighted_scores"] == {"power_apps": 84, "custom_web_app": 70}
    sent = model.requests[0].user
    assert "REQ-F-001 [functional, confirmed, priority must]" in sent and "DEC-1: Technology stack" in sent
    assert _sa_task(run, team, "compare_options").state == "waiting_for_input"
    with pytest.raises(InvalidTransitionError, match="question\\(s\\) the agent raised are still open"):
        move_task(run, team.pm.actor, _sa_task(run, team, "compare_options"), "completed")


def test_recommending_a_lower_scoring_option_is_noted(phase8: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> None:
    model.add(fake_response(json.dumps(compare_output(recommended_option="custom_web_app"))))
    queued = _ask_sa(run, phase8, "compare_options").run

    process(runner_for(), queued.id)

    detail = run(lambda s: s.executions.get_run(phase8.owner.actor, queued.id))
    assert detail.status == "succeeded"
    assert [f.message for f in detail.findings if f.check == "scoring"] == ["Recommends custom_web_app (70%) although power_apps scores higher (84%)"]


@pytest.mark.parametrize(
    ("changes", "check"),
    [
        ({"sources": [{"ref": "REQ-F-099", "quote": ""}]}, "grounding"),  # not a requirement it was given
        ({"recommended_option": "low_code"}, "schema"),
    ],
)
def test_bad_comparisons_save_nothing(phase8: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, changes: dict[str, Any], check: str) -> None:
    model.add(fake_response(json.dumps(compare_output(**changes))))
    queued = _ask_sa(run, phase8, "compare_options").run

    process(runner_for(), queued.id)

    detail = run(lambda s: s.executions.get_run(phase8.owner.actor, queued.id))
    assert detail.error_code == "guardrail_blocked" and check in {f.check for f in detail.findings}


def test_every_option_must_score_every_criterion(phase8: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> None:
    output = compare_output()
    output["options"][1]["scores"] = output["options"][1]["scores"][:2]
    model.add(fake_response(json.dumps(output)))
    queued = _ask_sa(run, phase8, "compare_options").run

    process(runner_for(), queued.id)

    detail = run(lambda s: s.executions.get_run(phase8.owner.actor, queued.id))
    assert any("must score every criterion exactly once" in f.message for f in detail.findings)


# Draft design ----------------------------------------------------------------------------------------

def test_the_design_gets_server_ids_coverage_and_a_document(option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, sa_agent: TestUser) -> None:
    team = option_chosen
    model.add(fake_response(design_json()))
    queued = _ask_sa(run, team, "draft_design").run

    process(runner_for(), queued.id)

    detail = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
    assert detail.status == "succeeded", detail.error_message
    view = _design(run, team)
    assert [i.item_id for i in view.items] == ["CMP-001", "API-001", "ENT-001", "SEC-001", "ENV-001", "ADR-001"]
    assert view.items[1].related == ["CMP-001"] and view.items[0].satisfies == ["REQ-F-001", "REQ-F-002"]
    assert (view.coverage.confirmed, view.coverage.covered, view.coverage.gaps) == (3, 3, [])
    assert (view.requirements_version_no, view.stale, view.approval_status) == (1, False, "pending")
    assert "unverified" in {f.check for f in view.items[3].quality_flags}
    content = run(lambda s: s.artifacts.read_version(team.owner.actor, view.version_id))
    assert content.version.author_id == sa_agent.actor.id
    assert "Designed against Business requirements v1" in content.content and "```mermaid" in content.content
    assert "| REQ-F-003 Manager reminders | confirmed | API-001 | - |" in content.content
    sent = model.requests[0].user
    assert "DEC-5: Architecture option" in sent and "Answer: Power Apps" in sent
    assert _sa_task(run, team, "draft_design").state == "waiting_for_review"

    matrix = run(lambda s: s.requirements.traceability(team.owner.actor, team.project.id))
    assert {r.item_id: r.design for r in matrix.rows} == {
        "REQ-F-001": "CMP-001, ENT-001, SEC-001", "REQ-F-002": "CMP-001, ADR-001", "REQ-F-003": "API-001",
    }


def test_drafting_waits_for_the_option_decision(phase8: Team, run: Run) -> None:
    with pytest.raises(InvalidTransitionError, match="Waiting for tasks: compare_options"):
        _ask_sa(run, phase8, "draft_design")


@pytest.mark.parametrize(
    ("change", "check"),
    [
        (lambda items: items[0].update(satisfies=["REQ-F-099"]), "requirement_ref"),
        (lambda items: items[1].update(related=["new-9"]), "item_ref"),
        (lambda items: items[0].update(ref="CMP-007"), "item_ref"),
    ],
)
def test_designs_with_unknown_requirements_or_items_save_nothing(
    option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, change: Callable[..., Any], check: str
) -> None:
    items = design_items()
    change(items)
    model.add(fake_response(design_json(items)))
    queued = _ask_sa(run, option_chosen, "draft_design").run

    process(runner_for(), queued.id)

    detail = run(lambda s: s.executions.get_run(option_chosen.owner.actor, queued.id))
    assert detail.error_code == "guardrail_blocked" and check in {f.check for f in detail.findings if f.severity == "block"}
    assert _design(run, option_chosen) is None


def _complete_phase_8(run: Run, team: Team) -> Any:
    for key in ("draft_design", "review_security", "review_feasibility", "plan_backlog"):
        task = _sa_task(run, team, key)
        if task.state == "not_started":
            move_task(run, team.owner.actor, task, "cancelled")  # the backlog_current exit check still applies
        elif task.state != "completed":
            move_task(run, team.reviewer.actor, task, "completed")
    _move_phase(run, team.pm.actor, team, 8, "waiting_for_review")
    return _move_phase(run, team.reviewer.actor, team, 8, "completed")


def test_phase_8_cannot_complete_while_a_confirmed_requirement_is_uncovered(
    option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, pass_reviews: Callable[[Team], None]
) -> None:
    team = option_chosen
    items = design_items()
    items[1]["satisfies"] = []  # nothing covers REQ-F-003 any more
    items[1]["sources"] = [{"ref": "REQ-F-001", "quote": ""}]
    model.add(fake_response(design_json(items)))
    process(runner_for(), _ask_sa(run, team, "draft_design").run.id)
    view = _design(run, team)
    assert view.coverage.gaps == ["REQ-F-003"]
    assert "1 confirmed requirement(s) not covered: REQ-F-003" in [f.message for f in view.set_flags]
    pass_reviews(team)
    _approve(run, team.reviewer, view.version_id)

    with pytest.raises(InvalidTransitionError, match="not covered by the design and without a documented exception: REQ-F-003"):
        _complete_phase_8(run, team)


def test_a_documented_exception_counts_as_covered_and_the_phase_completes(
    option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, pass_reviews: Callable[[Team], None],
    plan_backlog: Callable[..., Any],
) -> None:
    team = option_chosen
    items = design_items()
    items[1]["satisfies"] = []
    items[1]["sources"] = [{"ref": "REQ-F-001", "quote": ""}]
    exceptions = [{"requirement_id": "REQ-F-003", "reason": "Reminders are sent by the existing HR mail process"}]
    model.add(fake_response(design_json(items, exceptions=exceptions)))
    process(runner_for(), _ask_sa(run, team, "draft_design").run.id)
    view = _design(run, team)
    assert (view.coverage.gaps, view.coverage.excepted) == ([], 1)
    pass_reviews(team)
    _approve(run, team.reviewer, view.version_id)
    move_task(run, team.reviewer.actor, _sa_task(run, team, "draft_design"), "completed")
    plan_backlog(team)

    assert _complete_phase_8(run, team).state == "completed"


def test_nobody_but_an_independent_person_approves_a_design(option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, sa_agent: TestUser) -> None:
    model.add(fake_response(design_json()))
    process(runner_for(), _ask_sa(run, option_chosen, "draft_design").run.id)
    view = _design(run, option_chosen)

    with pytest.raises(PermissionDeniedError):
        _approve(run, sa_agent, view.version_id)
    with pytest.raises(PermissionDeniedError):
        _approve(run, option_chosen.pm, view.version_id)  # project managers are not design approvers


def test_a_requirements_change_makes_the_design_stale_until_it_is_redrafted(
    option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider,
    make_user: Callable[..., TestUser], add_member: Callable[..., None],
) -> None:
    team = option_chosen
    model.add(fake_response(design_json()))
    process(runner_for(), _ask_sa(run, team, "draft_design").run.id)
    design_v1 = _design(run, team)

    # An approved change to the requirements: REQ-F-001 now allows half days.
    customer = make_user(name="Customer")
    add_member(team.owner, team.project.id, customer, "customer_approver")
    request = run(lambda s: s.requirements.raise_change_request(team.pm.actor, team.project.id, ChangeRequestCreate(
        title="Half days", reason="HR asked", change="Allow half days", impact="Small", affected_item_ids=["REQ-F-001"])))
    for approver in (team.owner, customer):
        run(lambda s, a=approver: s.requirements.decide_change_request(a.actor, request.id, ChangeRequestDecisionCreate(decision="approved")))
    baseline = [i for i in draft_items() if i["kind"] != "open_question"]
    ids = dict(zip([i["ref"] for i in baseline], ["OBJ-001", "STK-001", "REQ-F-001", "REQ-F-002", "REQ-F-003", "ASM-001"]))
    for item in baseline:
        item["ref"], item["related"] = ids[item["ref"]], [ids[r] for r in item["related"]]
    baseline[2]["statement"] = "Employees can request annual, sick and unpaid leave online, in full or half days."
    model.add(fake_response(draft_json(baseline)))
    process(runner_for(), ask(run, team, "apply_change_request", request.baseline_version_id, change_request_id=request.id).run.id)

    stale = _design(run, team)
    assert stale.stale and "drafted against requirements v1, and the requirements are now v2" in stale.stale_reason
    with pytest.raises(InvalidTransitionError, match="design is stale"):
        _approve(run, team.reviewer, design_v1.version_id)
    with pytest.raises(ValidationFailedError, match="not approved yet"):
        _ask_sa(run, team, "draft_design")  # design builds on approved requirements only

    _approve(run, team.reviewer, _requirements(run, team).version_id)  # requirements v2 approved
    model.add(fake_response(design_json(design_items())))
    process(runner_for(), _ask_sa(run, team, "draft_design", actor=team.owner.actor).run.id)  # sends the reviewed task back

    redrafted = _design(run, team)
    assert (redrafted.version_no, redrafted.requirements_version_no, redrafted.stale) == (2, 2, False)


def test_design_records_cannot_be_edited(option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, session_factory: sessionmaker[Session]) -> None:
    model.add(fake_response(design_json()))
    process(runner_for(), _ask_sa(run, option_chosen, "draft_design").run.id)
    with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("UPDATE design_items SET satisfies = '[]'"))


def test_the_design_over_http(option_chosen: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, client_for: Callable[..., Any], make_user: Callable[..., TestUser]) -> None:
    url = f"/api/projects/{option_chosen.project.id}/design"
    assert client_for(option_chosen.reviewer).get(url).json() is None
    model.add(fake_response(design_json()))
    process(runner_for(), _ask_sa(run, option_chosen, "draft_design").run.id)

    body = client_for(option_chosen.reviewer).get(url).json()
    assert body["coverage"]["covered"] == 3 and body["items"][0]["item_id"] == "CMP-001"
    assert client_for(make_user(name="Outsider")).get(url).status_code == 404
