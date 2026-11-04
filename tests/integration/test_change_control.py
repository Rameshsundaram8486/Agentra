"""Increment 3b: review comments drive the redraft; an approved baseline changes only through a change request
approved by both an owner and a customer approver; the traceability matrix."""

import uuid
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
from app.modules.requirements.service import ChangeRequestCreate, ChangeRequestDecisionCreate
from tests.agent_support import ask, draft_items, draft_json, move_task, phase_task, process, req
from tests.support import Team, TestUser

Run = Callable[..., Any]

# The sample draft without its open question, so the task goes straight to review.
def _items() -> list[dict[str, Any]]:
    return [item for item in draft_items() if item["kind"] != "open_question"]


def _view(run: Run, team: Team) -> Any:
    return run(lambda s: s.requirements.view(team.owner.actor, team.project.id))


def _detail(run: Run, team: Team, run_id: uuid.UUID) -> Any:
    return run(lambda s: s.executions.get_run(team.owner.actor, run_id))


def _review(run: Run, reviewer: TestUser, version_id: uuid.UUID, decision: str = "approved", comment: str | None = None) -> None:
    run(lambda s: s.decisions.record_approval(
        reviewer.actor, version_id, ApprovalCreate(decision=decision, content_sha256=s.artifacts.version_record(version_id).content_sha256, comment=comment)
    ))


@pytest.fixture
def drafted(clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> tuple[Team, Any]:
    """A first draft (no open questions) waiting for review."""
    team, brief = clarified
    model.add(fake_response(draft_json(_items())))
    process(runner_for(), ask(run, team, "draft_requirements", brief.id).run.id)
    assert phase_task(run, team, "draft_requirements").state == "waiting_for_review"
    model.requests.clear()
    return team, brief


@pytest.fixture
def customer(make_user: Callable[..., TestUser], add_member: Callable[..., None], drafted: tuple[Team, Any]) -> TestUser:
    team, _ = drafted
    user = make_user(name="Customer approver")
    add_member(team.owner, team.project.id, user, "customer_approver")
    return user


@pytest.fixture
def baselined(drafted: tuple[Team, Any], run: Run) -> tuple[Team, Any]:
    """The draft approved by the reviewer and the task completed: an approved baseline under change control."""
    team, brief = drafted
    _review(run, team.reviewer, _view(run, team).version_id)
    move_task(run, team.reviewer.actor, phase_task(run, team, "draft_requirements"), "completed")
    assert _view(run, team).locked
    return team, brief


def _raise(run: Run, team: Team, actor: Any = None, **changes: Any) -> Any:
    fields: dict[str, Any] = {
        "title": "Add half-day leave",
        "reason": "HR confirmed half days are common",
        "change": "Allow requests for half days",
        "impact": "About two extra days of build",
        "affected_item_ids": ["REQ-F-001"],
    }
    data = ChangeRequestCreate(**{**fields, **changes})
    return run(lambda s: s.requirements.raise_change_request(actor or team.pm.actor, team.project.id, data))


def _decide(run: Run, actor: Any, request: Any, decision: str = "approved", comment: str | None = None) -> Any:
    return run(lambda s: s.requirements.decide_change_request(actor, request.id, ChangeRequestDecisionCreate(decision=decision, comment=comment)))


def _baseline_as_output() -> list[dict[str, Any]]:
    """The baseline items as the agent would return them unchanged, by ID."""
    items = _items()
    for item, item_id in zip(items, ["OBJ-001", "STK-001", "REQ-F-001", "REQ-F-002", "REQ-F-003", "ASM-001"]):
        item["ref"] = item_id
        item["related"] = ["OBJ-001"] if item_id in ("REQ-F-001", "REQ-F-002") else []
    return items


# Review loop -------------------------------------------------------------------------------------

def test_a_reviewers_comments_reach_the_redraft_and_each_gets_a_response(
    drafted: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, brief = drafted
    _review(run, team.reviewer, _view(run, team).version_id, "changes_requested", "Add a non-functional requirement for page speed")

    queued = ask(run, team, "draft_requirements", brief.id).run  # the PM asks; Agentra records changes_requested itself
    history = run(lambda s: s.workflow.history(team.owner.actor, "task", phase_task(run, team, "draft_requirements").id))
    assert [(h.from_state, h.to_state) for h in history][-2:] == [("waiting_for_review", "changes_requested"), ("changes_requested", "in_progress")]

    items = _baseline_as_output() + [req("new-1", "non_functional", "Page speed", "Pages load in under 2 seconds for 200 users.", related=["OBJ-001"])]
    model.add(fake_response(draft_json(items, review_responses=[{"ref": "REV-1", "response": "Added new-1 for page speed."}])))
    process(runner_for(), queued.id)

    assert "REV-1 (Reviewer requested changes on v1): Add a non-functional requirement" in model.requests[-1].user
    view = _view(run, team)
    assert view.version_no == 2 and view.added == ["REQ-NF-001"]
    assert [r.response for r in view.review_responses] == ["Added REQ-NF-001 for page speed."]
    content = run(lambda s: s.artifacts.read_version(team.owner.actor, view.version_id)).content
    assert "## Changes in this version" in content and 'Review comment: "Add a non-functional requirement for page speed"' in content
    assert _detail(run, team, queued.id).prompt_version.startswith("draft_requirements.v2@")


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ([], "REV-1 needs exactly one response (it has 0)"),
        ([{"ref": "REV-1", "response": "Done"}, {"ref": "REV-1", "response": "Again"}], "it has 2"),
        ([{"ref": "REV-1", "response": "Done"}, {"ref": "REV-7", "response": "Invented"}], "REV-7, which is not a review comment"),
    ],
)
def test_a_redraft_that_ignores_or_invents_review_comments_saves_nothing(
    drafted: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, responses: list[dict[str, str]], message: str
) -> None:
    team, brief = drafted
    _review(run, team.reviewer, _view(run, team).version_id, "changes_requested", "Tighten the wording")
    model.add(fake_response(draft_json(_baseline_as_output(), review_responses=responses)))
    queued = ask(run, team, "draft_requirements", brief.id).run

    process(runner_for(), queued.id)

    detail = _detail(run, team, queued.id)
    assert detail.error_code == "guardrail_blocked"
    assert any(message in f.message for f in detail.findings if f.check == "review")
    assert _view(run, team).version_no == 1


def test_links_must_point_at_items_in_the_output(drafted: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> None:
    team, brief = drafted
    _review(run, team.reviewer, _view(run, team).version_id, "changes_requested", "Link the requirements")
    items = _baseline_as_output()
    items[2]["related"] = ["OBJ-009"]
    model.add(fake_response(draft_json(items, review_responses=[{"ref": "REV-1", "response": "Linked"}])))
    queued = ask(run, team, "draft_requirements", brief.id).run

    process(runner_for(), queued.id)

    assert any("OBJ-009" in f.message for f in _detail(run, team, queued.id).findings if f.check == "item_ref")


# Baseline lock ------------------------------------------------------------------------------------

def test_an_approved_baseline_cannot_be_edited_or_redrafted_directly(
    baselined: tuple[Team, Any], run: Run, client_for: Callable[..., Any]
) -> None:
    team, brief = baselined
    view = _view(run, team)
    response = client_for(team.pm).post(
        f"/api/artifacts/{view.artifact_id}/versions",
        json={"content": "# Quiet edit\n", "change_summary": "Small fix", "expected_current_version": 1},
    )
    assert response.status_code == 409 and "under change control" in response.json()["message"]
    with pytest.raises(InvalidTransitionError, match="task is completed"):
        ask(run, team, "draft_requirements", brief.id)
    assert "under change control" in run(lambda s: s.requirements.baseline_problem(team.project.id))


# Change requests ----------------------------------------------------------------------------------

def test_raising_a_change_request_needs_an_approved_baseline_known_items_and_the_right_role(
    drafted: tuple[Team, Any], run: Run
) -> None:
    team, _ = drafted
    with pytest.raises(InvalidTransitionError, match="no approved requirements baseline yet"):
        _raise(run, team)
    _review(run, team.reviewer, _view(run, team).version_id)

    with pytest.raises(ValidationFailedError, match="Not in the baseline v1: REQ-F-099"):
        _raise(run, team, affected_item_ids=["REQ-F-001", "REQ-F-099"])
    with pytest.raises(PermissionDeniedError, match="change.raise"):
        _raise(run, team, actor=team.reviewer.actor)
    request = _raise(run, team)
    assert (request.cr_id, request.status, request.affected_item_ids) == ("CR-001", "open", ["REQ-F-001"])
    assert request.required_roles == ["owner", "customer_approver"]


def test_a_change_request_needs_an_owner_and_a_customer_approver_who_are_different_people_and_not_the_raiser(
    baselined: tuple[Team, Any], customer: TestUser, run: Run, add_member: Callable[..., None], ba_agent: TestUser
) -> None:
    team, _ = baselined
    add_member(team.owner, team.project.id, team.owner, "customer_approver")  # the owner now holds both roles
    request = _raise(run, team)

    with pytest.raises(PermissionDeniedError, match="You raised this change request"):
        _decide(run, team.pm.actor, request)
    with pytest.raises(PermissionDeniedError, match="Only people"):
        _decide(run, ba_agent.actor, request)
    with pytest.raises(PermissionDeniedError, match="needs one of these roles: owner, customer_approver"):
        _decide(run, team.reviewer.actor, request)

    after_owner = _decide(run, team.owner.actor, request)
    assert (after_owner.status, after_owner.approved_roles) == ("open", ["owner"])
    with pytest.raises(PermissionDeniedError, match="already decided"):
        _decide(run, team.owner.actor, request)  # holds customer_approver too, but one person counts once

    approved = _decide(run, customer.actor, request)
    assert (approved.status, approved.approved_roles) == ("approved", ["owner", "customer_approver"])
    with pytest.raises(InvalidTransitionError, match="already approved"):
        _decide(run, customer.actor, request)


def test_a_rejection_needs_a_reason_and_a_rejected_change_cannot_be_applied(
    baselined: tuple[Team, Any], customer: TestUser, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, _ = baselined
    request = _raise(run, team)
    with pytest.raises(ValidationFailedError, match="Explain why"):
        _decide(run, customer.actor, request, "rejected")
    rejected = _decide(run, customer.actor, request, "rejected", "Not in budget this phase")
    assert rejected.status == "rejected"

    queued = ask(run, team, "apply_change_request", rejected.baseline_version_id, change_request_id=rejected.id).run
    process(runner_for(), queued.id)

    detail = _detail(run, team, queued.id)
    assert (detail.status, detail.error_code) == ("failed", "input_rejected")
    assert "CR-001 is rejected" in detail.error_message
    assert model.requests == []


@pytest.fixture
def approved_change(baselined: tuple[Team, Any], customer: TestUser, run: Run) -> tuple[Team, Any]:
    team, _ = baselined
    request = _raise(run, team)
    _decide(run, team.owner.actor, request)
    return team, _decide(run, customer.actor, request)


def test_applying_an_approved_change_request_creates_the_next_version_for_approval(
    approved_change: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, request = approved_change
    items = _baseline_as_output()
    items[2]["statement"] = "Employees can request annual, sick and unpaid leave online, in full or half days."
    model.add(fake_response(draft_json(items)))
    queued = ask(run, team, "apply_change_request", request.baseline_version_id, change_request_id=request.id)
    assert queued.run.task_id is None  # not tied to the completed phase task

    process(runner_for(), queued.run.id)

    detail = _detail(run, team, queued.run.id)
    assert detail.status == "succeeded", detail.error_message
    assert "Approved change request CR-001: Add half-day leave" in model.requests[-1].user
    assert "Affected items: REQ-F-001" in model.requests[-1].user
    view = _view(run, team)
    assert (view.version_no, view.change_request, view.approval_status, view.locked) == (2, "CR-001", "pending", False)
    assert next(i for i in view.items if i.item_id == "REQ-F-001").statement.endswith("in full or half days.")
    after = run(lambda s: s.requirements.get_change_request(team.owner.actor, request.id))
    assert (after.status, after.applied_version_no) == ("applied", 2)
    content = run(lambda s: s.artifacts.read_version(team.owner.actor, view.version_id)).content
    assert "This version applies the approved change request CR-001: Add half-day leave." in content

    again = ask(run, team, "apply_change_request", request.baseline_version_id, change_request_id=request.id)
    assert (again.created, again.run.id) == (False, queued.run.id)  # same inputs: the earlier run, no second call
    assert "CR-001 is applied" in run(lambda s: s.requirements.baseline_problem(team.project.id, request.id))


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda items: items[3].update(statement="Built on SharePoint instead."), "REQ-F-002 was changed, but the change request does not list it"),
        (lambda items: items.pop(4), "REQ-F-003 was removed, but the change request does not list it"),
        (lambda items: items.append(req("new-1", "functional", "Half days", "Half days are allowed.", related=["OBJ-001"])), "does not allow new items"),
    ],
)
def test_changes_the_request_does_not_authorise_save_nothing(
    approved_change: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider,
    change: Callable[[list[dict[str, Any]]], Any], problem: str,
) -> None:
    team, request = approved_change
    items = _baseline_as_output()
    change(items)
    model.add(fake_response(draft_json(items)))
    queued = ask(run, team, "apply_change_request", request.baseline_version_id, change_request_id=request.id).run

    process(runner_for(), queued.id)

    detail = _detail(run, team, queued.id)
    assert detail.error_code == "guardrail_blocked"
    assert any(problem in f.message for f in detail.findings if f.check == "change_control")
    assert _view(run, team).version_no == 1
    assert run(lambda s: s.requirements.get_change_request(team.owner.actor, request.id)).status == "approved"


def test_the_service_enforces_change_control_even_without_the_agent_check(approved_change: tuple[Team, Any], run: Run, ba_agent: TestUser) -> None:
    from app.modules.requirements.service import DraftItem, RequirementsDraft, SourceRef

    team, request = approved_change
    current = run(lambda s: s.requirements.current_items(team.project.id))
    items = [
        DraftItem(ref=i.item_id, related=[], kind=i.kind, title=i.title, statement=i.statement + (" Changed." if i.item_id == "REQ-F-002" else ""),
                  label=i.label, priority=i.priority, acceptance_criteria=i.acceptance_criteria, sources=[SourceRef(type="document", name="x", quote="x")])
        for i in current
    ]
    draft = RequirementsDraft(summary="s", process_flow_mermaid="", items=items, input_refs=[], change_summary="x", change_request_id=request.id)

    with pytest.raises(ValidationFailedError, match="REQ-F-002 was changed"):
        run(lambda s: s.requirements.record_draft(ba_agent.actor, team.project.id, draft))


def test_change_requests_and_their_decisions_cannot_be_edited(approved_change: tuple[Team, Any], session_factory: sessionmaker[Session]) -> None:
    for statement in ("UPDATE change_request_events SET event = 'rejected'", "DELETE FROM change_requests"):
        with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


def test_change_requests_over_http(baselined: tuple[Team, Any], customer: TestUser, client_for: Callable[..., Any]) -> None:
    team, _ = baselined
    pm, owner, cust = client_for(team.pm), client_for(team.owner), client_for(customer)
    created = pm.post(f"/api/projects/{team.project.id}/change-requests", json={
        "title": "Half days", "reason": "HR asked", "change": "Allow half days", "impact": "Small", "affected_item_ids": ["req-f-001"],
    })
    assert created.status_code == 201, created.text
    cr = created.json()
    assert cr["affected_item_ids"] == ["REQ-F-001"]  # IDs are normalised
    assert pm.post(f"/api/change-requests/{cr['id']}/decisions", json={"decision": "approved"}).status_code == 403
    assert owner.post(f"/api/change-requests/{cr['id']}/decisions", json={"decision": "approved"}).json()["status"] == "open"
    final = cust.post(f"/api/change-requests/{cr['id']}/decisions", json={"decision": "approved", "comment": "Fine"}).json()
    assert final["status"] == "approved" and [e["role"] for e in final["events"]] == ["owner", "customer_approver"]
    assert [c["cr_id"] for c in cust.get(f"/api/projects/{team.project.id}/change-requests").json()] == ["CR-001"]


# Traceability ---------------------------------------------------------------------------------------

def test_traceability_links_requirements_to_objectives_stories_criteria_and_sources(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, client_for: Callable[..., Any]
) -> None:
    team, brief = clarified
    items = _items() + [
        req("new-8", "user_story", "Request on phone", "As an employee, I want to request leave on my phone so that I do not need email.", related=["new-3"]),
        req("new-9", "user_story", "Orphan story", "As HR, I want a report so that I can plan.", related=[]),
        req("new-10", "objective", "Unserved objective", "HR stops reconciling by hand."),
    ]
    model.add(fake_response(draft_json(items)))
    process(runner_for(), ask(run, team, "draft_requirements", brief.id).run.id)

    matrix = run(lambda s: s.requirements.traceability(team.owner.actor, team.project.id))
    rows = {row.item_id: row for row in matrix.rows}
    assert list(rows) == ["REQ-F-001", "REQ-F-002", "REQ-F-003"]
    assert rows["REQ-F-001"].objectives == ["OBJ-001"] and rows["REQ-F-001"].user_stories == ["US-001"]
    assert rows["REQ-F-001"].acceptance_criteria[0].startswith("REQ-F-001.AC1 ")
    assert rows["REQ-F-001"].sources[0].startswith("project brief '")
    assert rows["REQ-F-002"].sources[0].startswith("Decision: Technology stack (")
    assert rows["REQ-F-003"].gaps == ["No objective"]
    assert rows["REQ-F-001"].design == "Not yet (Phase 8)" and rows["REQ-F-001"].tests == "Not yet (Phase 10)"
    assert matrix.gaps == ["OBJ-002 has no requirement tracing to it", "US-002 does not trace to any requirement"]

    client = client_for(team.reviewer)
    first = client.get(f"/api/projects/{team.project.id}/requirements/traceability.csv")
    second = client.get(f"/api/projects/{team.project.id}/requirements/traceability.csv")
    assert first.status_code == 200 and first.headers["content-type"].startswith("text/csv")
    assert first.content == second.content
    assert first.text.splitlines()[0].startswith("Requirement,Kind,Title,Status,Objectives,User stories")
