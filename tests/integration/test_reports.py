"""Requirements reports: built only from records, versioned, unchanged data gives the same version, values are
escaped, customers see only the summary, and stored reports are never edited."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate
from app.modules.errors import PermissionDeniedError
from app.modules.reporting.rendering import render
from app.modules.reporting.schemas import ReportCreate
from tests.agent_support import ask, draft_items, draft_json, move_task, phase_task, process, req
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _generate(run: Run, actor: Any, team: Team, report_type: str) -> Any:
    return run(lambda s: s.reporting.generate(actor, team.project.id, ReportCreate(report_type=report_type)))


@pytest.fixture
def drafted(clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> Team:
    """Clarified and drafted; one item's title tries to inject markup; one failed run left an incident."""
    team, brief = clarified
    items = [i for i in draft_items() if i["kind"] != "open_question"] + [
        req("new-9", "functional", "<script>alert('x')</script> Export", "Managers can export the team calendar.", related=["new-1"]),
    ]
    model.add(fake_response("not JSON"))  # a failed draft first: an incident to report
    process(runner_for(), ask(run, team, "draft_requirements", brief.id).run.id)
    move_task(run, team.owner.actor, phase_task(run, team, "draft_requirements"), "ready")
    model.add(fake_response(draft_json(items)))
    process(runner_for(), ask(run, team, "draft_requirements", brief.id).run.id)
    return team


def test_the_summary_reconciles_with_the_records(drafted: Team, run: Run) -> None:
    team = drafted
    result = _generate(run, team.pm.actor, team, "requirements_summary")
    data = run(lambda s: s.reporting.report_data(team.owner.actor, result.report.id))

    view = run(lambda s: s.requirements.view(team.owner.actor, team.project.id))
    matrix = run(lambda s: s.requirements.traceability(team.owner.actor, team.project.id))
    decisions = run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id))
    incidents = run(lambda s: s.oversight.list_incidents(team.owner.actor, team.project.id))

    assert result.created and result.report.version_no == 1
    assert data["baseline"]["counts"] == view.counts and data["baseline"]["item_count"] == len(view.items)
    assert data["baseline"]["traced"] == {"rows": len(matrix.rows), "with_objective": sum(1 for r in matrix.rows if r.objectives)}
    assert len(data["decisions_deferred"]) == sum(1 for d in decisions if d.status == "deferred")
    assert [i["id"] for i in data["risks"]["incidents"]] == [i.incident_id for i in incidents if i.status != "closed"] == ["INC-001"]
    assert data["baseline"]["approval_status"] == "pending"
    actions = {a["action"]: a for a in data["next_actions"]}
    assert actions["Review and approve Business requirements v1 (pending)"]["due"] == "No due date set"
    assert any(a.startswith("Resolve INC-001") for a in actions)
    assert any("Defects: not applicable until Phase 10" in limitation for limitation in data["limitations"])
    assert data["period"]["to"] is not None and result.report.data_as_of is not None


def test_unchanged_records_give_the_same_version_and_a_change_gives_a_new_one(drafted: Team, run: Run) -> None:
    team = drafted
    first = _generate(run, team.pm.actor, team, "requirements_summary")
    again = _generate(run, team.owner.actor, team, "requirements_summary")
    assert (again.created, again.report.id) == (False, first.report.id)

    view = run(lambda s: s.requirements.view(team.owner.actor, team.project.id))
    run(lambda s: s.decisions.record_approval(team.reviewer.actor, view.version_id, ApprovalCreate(
        decision="approved", content_sha256=s.artifacts.version_record(view.version_id).content_sha256)))
    changed = _generate(run, team.pm.actor, team, "requirements_summary")

    assert changed.created and changed.report.version_no == 2
    assert changed.report.data_sha256 != first.report.data_sha256
    html = run(lambda s: s.reporting.report_html(team.owner.actor, changed.report.id))
    assert "approved by Reviewer" in html and "Report version</dt><dd>2" in html
    assert f"{len(view.items)} items:" in html  # a count, not a method name
    assert [r.version_no for r in run(lambda s: s.reporting.list_reports(team.owner.actor, team.project.id))] == [2, 1]


def test_the_detailed_report_shows_activity_approvals_and_incidents_with_values_escaped(drafted: Team, run: Run) -> None:
    team = drafted
    view = run(lambda s: s.requirements.view(team.owner.actor, team.project.id))
    sha = run(lambda s: s.artifacts.version_record(view.version_id).content_sha256)
    run(lambda s: s.decisions.record_approval(team.reviewer.actor, view.version_id, ApprovalCreate(decision="approved", content_sha256=sha)))

    report = _generate(run, team.pm.actor, team, "requirements_detailed").report
    html = run(lambda s: s.reporting.report_html(team.owner.actor, report.id))

    assert "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt; Export" in html and "<script>" not in html
    assert sha in html  # the approval names the exact content approved
    assert "INC-001: Draft the requirements: guardrail_blocked" in html and "No root-cause analysis yet." in html
    assert "Total model cost: USD 0.16." in html  # clarify, failed draft and draft: three fake calls at $0.052
    assert "Not yet (Phase 8)" in html and "Defects: Not applicable until Phase 10" in html
    assert 'link rel="stylesheet" href="/app/assets/css/report.css"' in html


def test_rendering_is_byte_identical_for_the_same_data(drafted: Team, run: Run) -> None:
    team = drafted
    report = _generate(run, team.pm.actor, team, "requirements_detailed").report
    data = run(lambda s: s.reporting.report_data(team.owner.actor, report.id))
    meta = {"title": report.title, "version_no": 1, "generated_at": "2026-11-04 09:00 UTC", "generated_by": "PM",
            "data_sha256": report.data_sha256[:16], "template_version": report.template_version, "sources": report.sources}

    first, second = render("requirements_detailed", data, meta), render("requirements_detailed", data, meta)
    assert first == second
    stored = run(lambda s: s.reporting.report_html(team.owner.actor, report.id))
    assert first.split("<main>")[1] == stored.split("<main>")[1]  # the stored body came from exactly this data


def test_who_may_generate_and_see_which_reports(
    drafted: Team, run: Run, make_user: Callable[..., TestUser], add_member: Callable[..., None], client_for: Callable[..., Any]
) -> None:
    team = drafted
    customer = make_user(name="Customer")
    add_member(team.owner, team.project.id, customer, "customer_approver")
    summary = _generate(run, team.pm.actor, team, "requirements_summary").report
    detailed = _generate(run, team.pm.actor, team, "requirements_detailed").report

    with pytest.raises(PermissionDeniedError):
        _generate(run, team.reviewer.actor, team, "requirements_summary")
    assert [r.report_type for r in run(lambda s: s.reporting.list_reports(customer.actor, team.project.id))] == ["requirements_summary"]
    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.reporting.report_html(customer.actor, detailed.id))
    assert "Requirements executive summary" in run(lambda s: s.reporting.report_html(customer.actor, summary.id))

    client = client_for(customer)
    assert client.get(f"/api/reports/{detailed.id}/html").status_code == 403
    response = client.get(f"/api/reports/{summary.id}/html")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in response.headers["content-security-policy"] and response.headers["x-frame-options"] == "SAMEORIGIN"
    assert client_for(make_user(name="Outsider")).get(f"/api/reports/{summary.id}").status_code == 404
    assert [t["key"] for t in client.get(f"/api/projects/{team.project.id}/report-types").json()] == ["requirements_summary", "design_summary"]


def test_report_versions_cannot_be_edited(drafted: Team, run: Run, session_factory: sessionmaker[Session]) -> None:
    _generate(run, drafted.pm.actor, drafted, "requirements_summary")
    with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("UPDATE reports SET data_sha256 = 'x'"))
