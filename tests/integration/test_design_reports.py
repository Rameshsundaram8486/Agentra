"""Phase 8 reports (Increment 4c): the design summary and the detailed design pack are built only from records,
reconcile with them, change version only when the records change, keep review findings out of the
customer-visible summary, and render agent text escaped."""

from collections.abc import Callable
from typing import Any

import pytest

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.errors import PermissionDeniedError
from app.modules.executions.schemas import AgentRunCreate
from app.modules.reporting.schemas import ReportCreate
from tests.agent_support import design_items, design_json, feasibility_json, process, security_findings, security_json, sfinding
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _generate(run: Run, actor: Any, team: Team, report_type: str) -> Any:
    return run(lambda s: s.reporting.generate(actor, team.project.id, ReportCreate(report_type=report_type)))


def _data(run: Run, team: Team, report: Any) -> dict[str, Any]:
    return run(lambda s: s.reporting.report_data(team.owner.actor, report.report.id))


def _html(run: Run, team: Team, report: Any) -> str:
    return run(lambda s: s.reporting.report_html(team.owner.actor, report.report.id))


def test_before_any_design_the_summary_says_what_is_missing(option_chosen: Team, run: Run) -> None:
    data = _data(run, option_chosen, _generate(run, option_chosen.pm.actor, option_chosen, "design_summary"))

    assert data["design"] is None and data["backlog"] is None and data["security"] is None
    assert data["option"]["chosen"] and data["option"]["options"] == ["Power Apps", "Custom Web App"]
    assert {"action": "Ask the Solution Architect to draft the design", "owner": "Owner or project manager", "due": "No due date set"} in data["next_actions"]


@pytest.fixture
def reviewed(review_team: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]) -> Team:
    """A design whose security review has a high gap (SC-03) whose text tries to inject markup; nothing approved."""
    team = review_team
    items = design_items()
    items[0]["title"] = "<script>alert('x')</script> Leave app"
    requirements = run(lambda s: s.requirements.view(team.owner.actor, team.project.id)).version_id
    data = AgentRunCreate(agent_key="solution_architect", task_key="draft_design", artifact_version_id=requirements)
    model.add(fake_response(design_json(items)))
    process(runner_for(), run(lambda s: s.executions.request_run(team.pm.actor, team.project.id, data)).run.id)
    findings = [sfinding("SC-03", "gap", "high", assessment="Nothing encrypts <b>leave</b> data at rest.") if f["check"] == "SC-03" else f for f in security_findings()]
    model.add(fake_response(security_json(findings)))
    process(runner_for(), ask_review(team, "security").run.id)
    return team


def test_the_summary_reconciles_and_shows_counts_not_findings(reviewed: Team, run: Run) -> None:
    team = reviewed
    report = _generate(run, team.pm.actor, team, "design_summary")
    data = _data(run, team, report)
    design = run(lambda s: s.design.view(team.owner.actor, team.project.id))

    assert data["design"]["item_count"] == len(design.items) and data["design"]["coverage"]["covered"] == design.coverage.covered
    assert data["design"]["decisions"] == [{"id": "ADR-001", "title": "Use Power Apps"}]
    assert data["security"]["gaps"] == {"high": 1, "medium": 0, "low": 0} and data["security"]["signed_off"] is None
    assert data["feasibility"] is None and data["approvable"] is False
    actions = [a["action"] for a in data["next_actions"]]
    assert "Close 1 high-severity security gap(s) in a redraft of the design" in actions
    assert "Have the Developer review the feasibility of design v1" in actions
    html = _html(run, team, report)
    assert "SC-03" not in html and "encrypts" not in html  # findings stay in the internal design pack
    assert "<script>" not in html


def test_the_design_pack_has_findings_escaped_and_the_gate(reviewed: Team, run: Run) -> None:
    team = reviewed
    report = _generate(run, team.pm.actor, team, "design_detailed")  # reviewers view reports; owners and PMs generate them
    data = _data(run, team, report)
    html = _html(run, team, report)

    assert data["gate"][0] == "Security review v1 of design v1 has high-severity gaps: SC-03"
    assert next(f for f in data["security_findings"] if f["ref"] == "SC-03")["severity"] == "high"
    assert [r["task"] for r in data["agent_runs"]] == ["Compare solution options", "Draft the design", "Review the design's security"]
    assert "Nothing encrypts &lt;b&gt;leave&lt;/b&gt; data at rest." in html and "<b>leave</b>" not in html
    assert "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt; Leave app" in html and "<script>" not in html
    assert "Security review v1" in html and "Solution design v1" in html


def test_a_finished_phase_8_reports_approvals_and_the_backlog(approved_design: Team, run: Run, plan_backlog: Callable[..., Any]) -> None:
    team = approved_design
    plan_backlog(team)
    summary = _data(run, team, _generate(run, team.pm.actor, team, "design_summary"))
    pack = _data(run, team, _generate(run, team.pm.actor, team, "design_detailed"))

    assert summary["design"]["approved"]["by"] == "Reviewer" and summary["security"]["signed_off"]["by"] == "Reviewer"
    assert summary["backlog"] == {
        "title": "Implementation backlog", "version_no": 1, "design_version_no": 1, "approval_status": "approved",
        "approved": summary["backlog"]["approved"], "stale_reason": None, "epics": 1, "items": 5,
        "estimates": {"S": 1, "M": 4, "L": 0}, "waves": {"1": 3, "2": 2},
    }
    assert summary["next_actions"] == [] and summary["approvable"] is True
    assert [w["id"] for w in pack["work_items"]] == ["WI-001", "WI-002", "WI-003", "WI-004", "WI-005"]
    approved = {(a["artifact"], a["decision"]) for a in pack["approvals"]}
    assert {("Solution design", "approved"), ("Security review", "approved"), ("Implementation backlog", "approved")} <= approved


def test_unchanged_records_give_the_same_version(reviewed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]) -> None:
    team = reviewed
    first = _generate(run, team.pm.actor, team, "design_summary")
    again = _generate(run, team.pm.actor, team, "design_summary")
    model.add(fake_response(feasibility_json()))
    process(runner_for(), ask_review(team, "feasibility").run.id)
    changed = _generate(run, team.pm.actor, team, "design_summary")

    assert (first.created, again.created, again.report.version_no) == (True, False, 1)
    assert changed.created and changed.report.version_no == 2


def test_customers_see_the_design_summary_only(reviewed: Team, run: Run, make_user: Callable[..., TestUser], add_member: Callable[..., None]) -> None:
    team = reviewed
    customer = make_user(name="Customer")
    add_member(team.owner, team.project.id, customer, "customer_approver")
    summary = _generate(run, team.pm.actor, team, "design_summary")
    pack = _generate(run, team.pm.actor, team, "design_detailed")

    assert run(lambda s: s.reporting.report_html(customer.actor, summary.report.id)).startswith("<!doctype html>")
    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.reporting.report_html(customer.actor, pack.report.id))
    with pytest.raises(PermissionDeniedError):
        _generate(run, customer.actor, team, "design_summary")
