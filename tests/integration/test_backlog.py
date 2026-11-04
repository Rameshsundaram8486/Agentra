"""Phase 8 implementation backlog (Increment 4c) with a scripted model: planned from the approved design with server
IDs and traceability, checked for coverage, references, waves and cycles, approved, gating Phase 8, and stale once
the design it plans changes."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate
from app.modules.errors import InvalidTransitionError, PermissionDeniedError, ValidationFailedError
from app.modules.executions.schemas import AgentRunCreate
from app.modules.requirements.service import ChangeRequestCreate, ChangeRequestDecisionCreate
from app.modules.workflow.service import TransitionRequest
from tests.agent_support import ask, backlog_items, backlog_json, design_json, draft_items, draft_json, move_task, phase_task, process, witem
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _backlog(run: Run, team: Team) -> Any:
    return run(lambda s: s.backlog.view(team.owner.actor, team.project.id))


def _approve(run: Run, user: TestUser, version_id: Any, decision: str = "approved", comment: str | None = None) -> None:
    run(lambda s: s.decisions.record_approval(user.actor, version_id, ApprovalCreate(
        decision=decision, comment=comment, content_sha256=s.artifacts.version_record(version_id).content_sha256)))


def _complete_phase_8(run: Run, team: Team) -> Any:
    for key in ("review_security", "review_feasibility", "plan_backlog"):
        task = phase_task(run, team, key, phase=8)
        if task.state == "waiting_for_review":
            move_task(run, team.reviewer.actor, task, "completed")
        elif task.state == "not_started":
            move_task(run, team.owner.actor, task, "cancelled")  # the exit check still requires the backlog
    for actor, state in ((team.pm.actor, "waiting_for_review"), (team.reviewer.actor, "completed")):
        phase = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 8)
        if phase.state != state:
            run(lambda s, a=actor, st=state, ph=phase: s.workflow.transition_phase_run(a, ph.id, TransitionRequest(to_state=st, reason="Test step", expected_version=ph.version)))
    return next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 8)


def test_the_backlog_gets_server_ids_traceability_and_a_document(approved_design: Team, run: Run, plan_backlog: Callable[..., Any], model: FakeProvider) -> None:
    team = approved_design
    detail = plan_backlog(team, approve=False)

    assert detail.status == "succeeded"
    assert detail.output["backlog"]["ids"] == {"new-e1": "EP-001", "new-1": "WI-001", "new-2": "WI-002", "new-3": "WI-003", "new-4": "WI-004", "new-5": "WI-005"}
    view = _backlog(run, team)
    assert (view.version_no, view.design_version_no, view.stale, view.approval_status) == (1, 1, False, "pending")
    assert view.estimates == {"S": 1, "M": 4, "L": 0} and view.waves == {1: 3, 2: 2}
    wi4 = next(i for i in view.items if i.item_id == "WI-004")
    assert wi4.depends_on == ["WI-003", "WI-002"] and wi4.acceptance == ["REQ-F-001.AC1"]
    assert wi4.requirements == ["REQ-F-001", "REQ-F-002"]  # the requirements its design item CMP-001 satisfies
    assert next(i for i in view.items if i.item_id == "WI-005").requirements == ["REQ-F-002", "REQ-F-003"]  # stated plus API-001's
    content = run(lambda s: s.artifacts.read_version(team.owner.actor, view.version_id).content)
    assert "Plans Solution design v1" in content and "### WI-004 Build CMP-001" in content and "- Wave 2: WI-004, WI-005" in content
    assert phase_task(run, team, "plan_backlog", phase=8).state == "waiting_for_review"
    rows = {r.item_id: r for r in run(lambda s: s.requirements.traceability(team.owner.actor, team.project.id)).rows}
    assert rows["REQ-F-001"].backlog == "WI-002, WI-003, WI-004" and rows["REQ-F-003"].backlog == "WI-005"  # via SEC-001, ENT-001, CMP-001
    # The model saw the design, its own feasibility sizes and the numbered acceptance criteria.
    prompt = model.requests[-1].user
    assert "CMP-001: feasible, size M." in prompt and "REQ-F-001.AC1:" in prompt and "<document" in prompt


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        ([i for i in backlog_items() if i["ref"] != "new-2"] , "No work item implements SEC-001"),
        (backlog_items() + [witem("new-6", ["CMP-404"])], "'CMP-404' is not a design item in the approved design"),
        (backlog_items()[:3] + [witem("new-4", ["CMP-001"], wave=2, acceptance_criteria=["REQ-F-001.AC9"])] + backlog_items()[4:], "'REQ-F-001.AC9' is not an acceptance criterion"),
        ([witem("new-1", ["ENV-001"], depends_on=["new-3"]), *backlog_items()[1:]], "Dependency cycle: new-1 -> new-3 -> new-1"),
        ([witem("new-1", ["ENV-001"], depends_on=["new-5"]), *backlog_items()[1:]], "new-1 (wave 1) depends on new-5 in a later wave"),
        ([*backlog_items()[:4], witem("new-5", ["API-001"], wave=2, epic="new-e9")], "epic 'new-e9' is not an epic in this backlog"),
        ([*backlog_items(), witem("WI-007", ["CMP-001"])], "WI-007 is not an existing ID on this project"),
    ],
    ids=["uncovered", "unknown_design_item", "unknown_criterion", "cycle", "later_wave", "unknown_epic", "invented_id"],
)
def test_bad_backlogs_save_nothing(approved_design: Team, run: Run, plan_backlog: Callable[..., Any], items: list[dict[str, Any]], expected: str) -> None:
    detail = plan_backlog(approved_design, backlog_json(items), approve=False)

    assert detail.error_code == "guardrail_blocked"
    assert any(expected in f.message for f in detail.findings), [f.message for f in detail.findings]
    assert _backlog(run, approved_design) is None


def test_only_an_approved_current_design_is_planned(designed_only: Team, run: Run) -> None:
    team = designed_only
    design = run(lambda s: s.design.current_version_id(team.project.id))
    data = AgentRunCreate(agent_key="developer", task_key="plan_backlog", artifact_version_id=design)

    with pytest.raises(ValidationFailedError, match="not approved yet"):
        run(lambda s: s.executions.request_run(team.pm.actor, team.project.id, data))


@pytest.fixture
def designed_only(review_team: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, developer_agent: TestUser) -> Team:
    requirements = run(lambda s: s.requirements.view(review_team.owner.actor, review_team.project.id)).version_id
    data = AgentRunCreate(agent_key="solution_architect", task_key="draft_design", artifact_version_id=requirements)
    model.add(fake_response(design_json()))
    process(runner_for(), run(lambda s: s.executions.request_run(review_team.pm.actor, review_team.project.id, data)).run.id)
    return review_team


def test_phase_8_completes_only_with_an_approved_backlog(approved_design: Team, run: Run, plan_backlog: Callable[..., Any], developer_agent: TestUser) -> None:
    team = approved_design
    gate = lambda: run(lambda s: s.backlog.gate_failures(team.project.id))  # noqa: E731  (the exit check backlog_current)
    assert gate() == ["No implementation backlog yet; ask the Developer agent to plan the approved design"]

    plan_backlog(team, approve=False)
    version_id = _backlog(run, team).version_id
    with pytest.raises(PermissionDeniedError):
        _approve(run, developer_agent, version_id)  # agents never approve
    assert gate() == ["Implementation backlog v1 is not approved"]

    _approve(run, team.pm, version_id)  # a project manager may approve the backlog
    assert _complete_phase_8(run, team).state == "completed"


def test_a_redraft_keeps_ids_and_answers_review_comments(approved_design: Team, run: Run, plan_backlog: Callable[..., Any]) -> None:
    team = approved_design
    plan_backlog(team, approve=False)
    _approve(run, team.reviewer, _backlog(run, team).version_id, "changes_requested", "Split the app build into screens and logic.")

    kept = [{**i, "ref": f"WI-00{n}", "depends_on": [f"WI-00{d[-1]}" for d in i["depends_on"]]} for n, i in enumerate(backlog_items(), start=1)]
    kept += [witem("new-1", ["CMP-001"], wave=2, depends_on=["WI-004"], title="App screens")]
    epics = [{"ref": "EP-001", "title": "Leave app", "description": "The Power Apps leave app."}]
    for item in kept:
        item["epic"] = "EP-001"
    unanswered = plan_backlog(team, backlog_json(kept, epics), approve=False)
    assert unanswered.error_code == "guardrail_blocked"
    assert "Review comment REV-1 needs exactly one response (it has 0)" in [f.message for f in unanswered.findings]

    answered = plan_backlog(team, backlog_json(kept, epics, review_responses=[{"ref": "REV-1", "response": "Added WI-006 for the screens."}]), approve=False)
    assert answered.status == "succeeded"
    view = _backlog(run, team)
    assert view.version_no == 2 and [i.item_id for i in view.items] == ["WI-001", "WI-002", "WI-003", "WI-004", "WI-005", "WI-006"]
    assert view.review_responses[0].response == "Added WI-006 for the screens."


def test_a_requirements_change_makes_the_backlog_stale(
    approved_design: Team, run: Run, plan_backlog: Callable[..., Any], runner_for: Callable[..., AgentRunner], model: FakeProvider,
    make_user: Callable[..., TestUser], add_member: Callable[..., None],
) -> None:
    team = approved_design
    plan_backlog(team, approve=False)
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

    view = _backlog(run, team)
    assert view.stale and "design v1 is no longer approved" in view.stale_reason
    with pytest.raises(InvalidTransitionError, match="backlog is stale"):
        _approve(run, team.pm, view.version_id)


def test_backlog_records_cannot_be_edited(approved_design: Team, plan_backlog: Callable[..., Any], session_factory: sessionmaker[Session]) -> None:
    plan_backlog(approved_design)
    for statement in ("UPDATE backlog_items SET wave = 9", "DELETE FROM backlog_versions", "DELETE FROM backlog_ids"):
        with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


def test_the_backlog_over_http(approved_design: Team, plan_backlog: Callable[..., Any], client_for: Callable[..., Any], make_user: Callable[..., TestUser]) -> None:
    url = f"/api/projects/{approved_design.project.id}/backlog"
    assert client_for(approved_design.reviewer).get(url).json() is None
    plan_backlog(approved_design)

    body = client_for(approved_design.reviewer).get(url).json()
    assert body["approval_status"] == "approved" and len(body["items"]) == 5 and body["epics"][0]["epic_id"] == "EP-001"
    assert client_for(make_user(name="Outsider")).get(url).status_code == 404
