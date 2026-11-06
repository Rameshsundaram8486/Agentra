"""Design change requests (Increment 4d) with a scripted model: raised in the shared change request register against
the approved design with computed impact, decided by an owner and a reviewer, applied by the Solution Architect
within the listed items only, and followed by fresh reviews, approval and a replanned backlog."""

from collections.abc import Callable
from typing import Any

import pytest

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate
from app.modules.errors import InvalidTransitionError, PermissionDeniedError, ValidationFailedError
from app.modules.executions.schemas import AgentRunCreate
from app.modules.reporting.schemas import ReportCreate
from app.modules.requirements.service import ChangeRequestCreate, ChangeRequestDecisionCreate
from app.modules.workflow.service import TransitionRequest
from tests.agent_support import ask, design_json, ditem, feasibility_json, kept_design_items, move_task, phase_task, process, security_json
from tests.support import Team, TestUser

Run = Callable[..., Any]

NEW_REMINDERS = "Reminder emails are sent by a scheduled Power Automate flow at 08:00 Gulf Standard Time."


def _raise(run: Run, team: Team, affected: list[str] | None = None, allows_new_items: bool = False, actor: Any = None) -> Any:
    data = ChangeRequestCreate(
        baseline_type="design_baseline", title="Scheduled reminders", reason="The developer found push reminders unreliable",
        change="Send reminders from a scheduled flow", impact="One flow instead of a trigger", affected_item_ids=affected or ["API-001"],
        allows_new_items=allows_new_items,
    )
    return run(lambda s: s.requirements.raise_change_request(actor or team.pm.actor, team.project.id, data))


def _decide(run: Run, user: TestUser, request: Any, decision: str = "approved") -> Any:
    comment = None if decision == "approved" else "Not now"
    return run(lambda s: s.requirements.decide_change_request(user.actor, request.id, ChangeRequestDecisionCreate(decision=decision, comment=comment)))


def _approve(run: Run, user: TestUser, version_id: Any) -> None:
    run(lambda s: s.decisions.record_approval(user.actor, version_id, ApprovalCreate(
        decision="approved", content_sha256=s.artifacts.version_record(version_id).content_sha256)))


def _apply(run: Run, team: Team, runner: AgentRunner, model: FakeProvider, request: Any, output: str) -> Any:
    requirements = run(lambda s: s.requirements.view(team.owner.actor, team.project.id)).version_id
    data = AgentRunCreate(agent_key="solution_architect", task_key="apply_design_change", artifact_version_id=requirements, change_request_id=request.id)
    model.add(fake_response(output))
    run_id = run(lambda s: s.executions.request_run(team.pm.actor, team.project.id, data)).run.id
    process(runner, run_id)
    return run(lambda s: s.executions.get_run(team.owner.actor, run_id))


def _changed_items(**changes: Any) -> list[dict[str, Any]]:
    items = kept_design_items()
    items[1]["description"] = NEW_REMINDERS  # API-001, the listed item
    for index, change in changes.items():
        items[int(index[1:])].update(change)
    return items


@pytest.fixture
def baselined(approved_design: Team, run: Run, plan_backlog: Callable[..., Any]) -> Team:
    """Design v1 approved with both reviews, backlog v1 approved, and every Phase 8 task closed; Phase 8 still open."""
    team = approved_design
    plan_backlog(team)
    for key in ("review_security", "review_feasibility", "plan_backlog"):
        move_task(run, team.reviewer.actor, phase_task(run, team, key, phase=8), "completed")
    return team


def test_a_design_change_request_records_its_impact_and_needs_an_owner_and_a_reviewer(baselined: Team, run: Run, make_user: Callable[..., TestUser], add_member: Callable[..., None]) -> None:
    team = baselined
    with pytest.raises(ValidationFailedError, match="Not in the design v1: CMP-404"):
        _raise(run, team, ["API-001", "CMP-404"])
    request = _raise(run, team)

    assert (request.cr_id, request.baseline_type, request.status, request.baseline_version_no) == ("CR-001", "design_baseline", "open", 1)
    assert request.required_roles == ["owner", "reviewer"]
    assert (request.impacted_requirements, request.impacted_work_items) == (["REQ-F-003"], ["WI-005"])

    customer = make_user(name="Customer")
    add_member(team.owner, team.project.id, customer, "customer_approver")
    for user in (team.pm, customer):  # the raiser never; customer approvers are not design change approvers
        with pytest.raises(PermissionDeniedError):
            _decide(run, user, request)
    assert _decide(run, team.owner, request).status == "open"
    with pytest.raises(PermissionDeniedError, match="already decided"):
        _decide(run, team.owner, request)
    assert _decide(run, team.reviewer, request).status == "approved"


def test_applying_it_changes_only_the_listed_items_and_reopens_the_gates(
    baselined: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any], plan_backlog: Callable[..., Any],
) -> None:
    team = baselined
    request = _raise(run, team)
    for user in (team.owner, team.reviewer):
        _decide(run, user, request)

    detail = _apply(run, team, runner_for(), model, request, design_json(_changed_items(), summary="Reminders now come from a scheduled flow."))

    assert detail.status == "succeeded", (detail.error_code, [f.message for f in detail.findings])
    assert "Approved design change request CR-001: Scheduled reminders" in model.requests[-1].user
    design = run(lambda s: s.design.view(team.owner.actor, team.project.id))
    assert (design.version_no, design.approval_status, design.change_request) == (2, "pending", "CR-001: Scheduled reminders")
    assert next(i for i in design.items if i.item_id == "API-001").description == NEW_REMINDERS
    assert run(lambda s: s.requirements.get_change_request(team.owner.actor, request.id)).status == "applied"
    # The new version is not approvable until it is reviewed again, and the backlog plans the old version.
    gate = run(lambda s: s.design_reviews.view(team.owner.actor, team.project.id)).gate
    assert gate == ["Design v2 has no security review yet; ask the Security Reviewer agent", "Design v2 has no feasibility review yet; ask the Developer agent"]
    backlog = run(lambda s: s.backlog.view(team.owner.actor, team.project.id))
    assert backlog.stale and "plans design v1, and the design is now v2" in backlog.stale_reason

    # The closed review and backlog tasks can work on the new version; they stay closed.
    for kind, output in (("security", security_json()), ("feasibility", feasibility_json())):
        model.add(fake_response(output))
        queued = ask_review(team, kind).run
        process(runner_for(), queued.id)
        reviewed = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
        assert reviewed.status == "succeeded", (kind, reviewed.error_code, reviewed.error_message)
    _approve(run, team.reviewer, run(lambda s: s.design_reviews.view(team.owner.actor, team.project.id)).security.version_id)
    _approve(run, team.reviewer, design.version_id)
    assert plan_backlog(team).status == "succeeded"
    assert run(lambda s: s.backlog.view(team.owner.actor, team.project.id)).design_version_no == 2
    for key in ("review_security", "review_feasibility", "plan_backlog"):
        assert phase_task(run, team, key, phase=8).state == "completed"
    phase = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 8)
    phase = run(lambda s: s.workflow.transition_phase_run(team.pm.actor, phase.id, TransitionRequest(to_state="waiting_for_review", reason="Test", expected_version=phase.version)))
    assert run(lambda s: s.workflow.transition_phase_run(team.reviewer.actor, phase.id, TransitionRequest(to_state="completed", reason="Test", expected_version=phase.version))).state == "completed"

    pack = run(lambda s: s.reporting.report_data(team.owner.actor, s.reporting.generate(team.pm.actor, team.project.id, ReportCreate(report_type="design_detailed")).report.id))
    assert [(r["id"], r["status"], r["applied_version_no"]) for r in pack["change_requests"]] == [("CR-001", "applied", 2)]


@pytest.mark.parametrize(
    ("changes", "allows_new_items", "expected"),
    [
        ({"i0": {"title": "Leave app (renamed)"}}, False, "CMP-001 was changed, but the change request does not list it"),
        ({"i2": {"satisfies": ["REQ-F-002"]}}, False, "ENT-001 was changed, but the change request does not list it"),
        ({}, False, "The change request does not allow new items"),
    ],
    ids=["unlisted_title", "unlisted_coverage", "new_item"],
)
def test_changes_outside_the_request_save_nothing(
    baselined: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, changes: dict[str, Any], allows_new_items: bool, expected: str,
) -> None:
    team = baselined
    request = _raise(run, team, allows_new_items=allows_new_items)
    for user in (team.owner, team.reviewer):
        _decide(run, user, request)
    items = _changed_items(**changes)
    if not changes:
        items.append(ditem("new-1", "data_flow", "Reminder schedule", ["REQ-F-003"], related=["API-001"]))

    detail = _apply(run, team, runner_for(), model, request, design_json(items))

    assert detail.error_code == "guardrail_blocked"
    assert any(f.check == "change_control" and expected in f.message for f in detail.findings), [f.message for f in detail.findings]
    assert run(lambda s: s.design.view(team.owner.actor, team.project.id)).version_no == 1


def test_removing_an_unlisted_item_is_refused(baselined: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> None:
    request = _raise(run, baselined)
    for user in (baselined.owner, baselined.reviewer):
        _decide(run, user, request)

    detail = _apply(run, baselined, runner_for(), model, request, design_json([i for i in _changed_items() if i["ref"] != "ENV-001"]))

    assert "ENV-001 was removed, but the change request does not list it" in [f.message.split(": ", 1)[1] for f in detail.findings if f.check == "change_control"]


def test_only_an_approved_design_change_request_is_applied_and_by_the_right_agent(
    baselined: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ba_agent: TestUser, add_member: Callable[..., None],
) -> None:
    team = baselined
    request = _raise(run, team)
    calls = len(model.requests)
    detail = _apply(run, team, runner_for(), model, request, design_json(_changed_items()))
    assert (detail.status, detail.error_code) == ("failed", "input_rejected") and "CR-001 is open" in detail.error_message
    assert len(model.requests) == calls

    for user in (team.owner, team.reviewer):
        _decide(run, user, request)
    requirements = run(lambda s: s.requirements.view(team.owner.actor, team.project.id)).version_id
    queued = ask(run, team, "apply_change_request", requirements, change_request_id=request.id).run  # the Business Analyst
    process(runner_for(), queued.id)
    detail = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
    assert detail.error_code == "input_rejected" and "changes the design; ask the Solution Architect" in detail.error_message


def test_design_change_requests_need_phase_8_open(baselined: Team, run: Run) -> None:
    team = baselined
    phase = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 8)
    phase = run(lambda s: s.workflow.transition_phase_run(team.pm.actor, phase.id, TransitionRequest(to_state="waiting_for_review", reason="Test", expected_version=phase.version)))
    run(lambda s: s.workflow.transition_phase_run(team.reviewer.actor, phase.id, TransitionRequest(to_state="completed", reason="Test", expected_version=phase.version)))

    with pytest.raises(InvalidTransitionError, match="only while Phase 8 is open"):
        _raise(run, team)


def test_requirements_reports_leave_design_change_requests_out(baselined: Team, run: Run) -> None:
    team = baselined
    _raise(run, team)
    data = run(lambda s: s.reporting.report_data(team.owner.actor, s.reporting.generate(team.pm.actor, team.project.id, ReportCreate(report_type="requirements_detailed")).report.id))
    design = run(lambda s: s.reporting.report_data(team.owner.actor, s.reporting.generate(team.pm.actor, team.project.id, ReportCreate(report_type="design_summary")).report.id))

    assert data["change_requests"] == []
    assert {"action": "Decide CR-001: Scheduled reminders", "owner": "owner and reviewer", "due": "No due date set"} in design["next_actions"]
