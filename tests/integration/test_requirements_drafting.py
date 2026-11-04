"""Phase 7 drafting end to end against the test database, with a scripted model: clarify, answer, draft,
revise, review."""

import base64
import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate, DecisionOutcomeCreate
from app.modules.errors import InvalidTransitionError
from tests.agent_support import ask, draft_items, draft_json, move_task, phase_task, process, req
from tests.support import Team, make_docx, make_pdf

Run = Callable[..., Any]


_ask, _task, _move_task = ask, phase_task, move_task


def _detail(run: Run, team: Team, run_id: uuid.UUID) -> Any:
    return run(lambda s: s.executions.get_run(team.owner.actor, run_id))


def _requirements(run: Run, team: Team) -> Any:
    return run(lambda s: s.requirements.view(team.owner.actor, team.project.id))


def test_draft_becomes_items_with_server_ids_and_derived_statuses(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ba_agent: Any
) -> None:
    team, brief = clarified
    queued = _ask(run, team, "draft_requirements", brief.id).run
    assert (queued.context_documents, queued.context_decisions) == (1, 4)
    assert _task(run, team, "draft_requirements").state == "in_progress"
    model.add(fake_response(draft_json()))

    process(runner_for(), queued.id)

    detail = _detail(run, team, queued.id)
    assert detail.status == "succeeded", detail.error_message
    view = _requirements(run, team)
    by_id = {item.item_id: item for item in view.items}
    assert list(by_id) == ["OBJ-001", "STK-001", "REQ-F-001", "REQ-F-002", "REQ-F-003", "ASM-001", "Q-001"]
    assert by_id["REQ-F-001"].status == "confirmed"  # fact quoting the brief
    assert by_id["REQ-F-002"].status == "confirmed"  # fact resting on the answered stack decision
    assert by_id["REQ-F-002"].sources[0].answer is not None
    assert by_id["REQ-F-003"].sources[0].name == "source document 'Discovery notes' v1"
    assert by_id["ASM-001"].status == "proposed" and by_id["Q-001"].status == "open"
    assert view.counts == {"confirmed": 5, "proposed": 1, "open": 1}
    assert view.version_no == 1 and view.approval_status == "pending"

    # The document version is the rendered BRD, authored by the agent and linked to its inputs.
    content = run(lambda s: s.artifacts.read_version(team.owner.actor, view.version_id))
    assert content.version.author_id == ba_agent.actor.id
    assert "### REQ-F-001 Request leave online" in content.content and "```mermaid" in content.content
    assert any("DEC-1: decision 'Technology stack'" in ref for ref in content.version.source_refs)

    # The open question is in the inbox, and the task waits for input.
    [question] = [d for d in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)) if d.title.startswith("Q-001")]
    assert question.recommended_option == "import" and question.artifact_version_id == view.version_id
    assert detail.decision_ids == [question.id]
    assert _task(run, team, "draft_requirements").state == "waiting_for_input"

    # What the model saw: both documents, and the answered and unanswered decisions.
    sent = model.requests[0].user
    assert 'ref="DOC-1"' in sent and 'ref="DOC-2"' in sent and "reminder after two working days" in sent
    assert "DEC-1: Technology stack" in sent and "Answer: not answered yet" in sent
    assert model.requests[0].max_tokens == 64_000


def test_a_fact_resting_on_an_unanswered_decision_is_never_confirmed(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, brief = clarified
    items = draft_items()
    items[3]["sources"] = [{"ref": "DEC-3", "quote": ""}]  # the approval-chain question nobody answered
    model.add(fake_response(draft_json(items)))

    process(runner_for(), _ask(run, team, "draft_requirements", brief.id).run.id)

    item = next(i for i in _requirements(run, team).items if i.item_id == "REQ-F-002")
    assert item.label == "fact" and item.status == "proposed"
    assert "open_decision" in {flag.check for flag in item.quality_flags}


def test_a_revision_keeps_ids_and_never_reuses_a_removed_one(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, brief = clarified
    model.add(fake_response(draft_json()))
    process(runner_for(), _ask(run, team, "draft_requirements", brief.id).run.id)
    [question] = [d for d in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)) if d.title.startswith("Q-001")]
    run(lambda s: s.decisions.record_outcome(team.owner.actor, question.id, DecisionOutcomeCreate(action="accept")))

    revised = [item for item in draft_items() if item["ref"] not in ("new-5", "new-7")]
    for item, kept in zip(revised, ["OBJ-001", "STK-001", "REQ-F-001", "REQ-F-002", "ASM-001"]):
        item["ref"] = kept
    revised.append(req("new-1", "functional", "Import balances", "Opening balances are imported from the Excel sheet.",
                       sources=[{"ref": "DEC-5", "quote": ""}]))
    model.add(fake_response(draft_json(revised)))
    again = _ask(run, team, "draft_requirements", brief.id)  # an answer changed, so this is a new run
    assert again.created
    process(runner_for(), again.run.id)

    view = _requirements(run, team)
    assert view.version_no == 2
    assert [i.item_id for i in view.items] == ["OBJ-001", "STK-001", "REQ-F-001", "REQ-F-002", "ASM-001", "REQ-F-004"]
    assert view.added == ["REQ-F-004"] and view.removed == ["Q-001", "REQ-F-003"]
    assert "STK-001 [stakeholder, fact, priority not_set] Line managers" in model.requests[-1].user  # current items were shown to it
    assert _task(run, team, "draft_requirements").state == "waiting_for_review"  # no open questions this time


@pytest.mark.parametrize(
    ("change", "check"),
    [
        (lambda items: items[2].update(ref="REQ-F-099"), "item_ref"),  # an ID the server never issued
        (lambda items: items[2].update(ref="draft-a"), "item_ref"),
        (lambda items: items[2].update(sources=[{"ref": "DOC-9", "quote": "anything"}]), "grounding"),
        (lambda items: items[4].update(sources=[{"ref": "DOC-2", "quote": "managers get coffee"}]), "grounding"),
        (lambda items: items[2].update(statement="The customer has approved online leave requests."), "forbidden_claim"),
    ],
)
def test_output_with_bad_refs_or_citations_saves_nothing(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider,
    change: Callable[[list[dict[str, Any]]], None], check: str,
) -> None:
    team, brief = clarified
    items = draft_items()
    change(items)
    model.add(fake_response(draft_json(items)))
    queued = _ask(run, team, "draft_requirements", brief.id).run

    process(runner_for(), queued.id)

    detail = _detail(run, team, queued.id)
    assert (detail.status, detail.error_code) == ("failed", "guardrail_blocked")
    assert check in {f.check for f in detail.findings if f.severity == "block"}
    assert _requirements(run, team) is None
    assert _task(run, team, "draft_requirements").state == "failed"


@pytest.mark.parametrize(
    "change",
    [
        lambda items: items[6].update(suggested_answers=[]),  # an open question without answers
        lambda items: items[2].update(label="open_question", kind="functional", suggested_answers=[{"key": "a", "title": "A", "description": ""}] * 2),
        lambda items: items[6].update(label="fact"),  # an open question labelled as a fact
        lambda items: items[2].update(sources=[]),  # a claim that cites no source
    ],
)
def test_schema_rules_on_labels_and_sources(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, change: Callable[..., None]
) -> None:
    team, brief = clarified
    items = draft_items()
    change(items)
    model.add(fake_response(draft_json(items)))
    queued = _ask(run, team, "draft_requirements", brief.id).run

    process(runner_for(), queued.id)

    assert _detail(run, team, queued.id).error_code == "guardrail_blocked"


def test_missing_input_stops_the_task_at_waiting_for_input_without_a_model_call(
    ba_team: Team, make_brief: Callable[..., Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    brief = make_brief(ba_team, "# Leave app\n\nWe want a leave app.\n")
    for actor, state in ((ba_team.owner, "ready"), (ba_team.pm, "in_progress"), (ba_team.pm, "waiting_for_input"), (ba_team.pm, "completed")):
        _move_task(run, actor.actor, _task(run, ba_team, "clarify_brief"), state)
    queued = _ask(run, ba_team, "draft_requirements", brief.id).run

    process(runner_for(), queued.id)

    detail = _detail(run, ba_team, queued.id)
    assert (detail.status, detail.error_code) == ("blocked", "missing_input")
    assert "only 8 words" in detail.error_message
    assert model.requests == [] and detail.model_calls == []
    assert _task(run, ba_team, "draft_requirements").state == "waiting_for_input"


def test_drafting_waits_for_the_clarify_task(ba_team: Team, make_brief: Callable[..., Any], run: Run) -> None:
    brief = make_brief(ba_team)

    with pytest.raises(InvalidTransitionError, match="Waiting for tasks: clarify_brief"):
        _ask(run, ba_team, "draft_requirements", brief.id)


def test_review_completes_the_task_only_after_approval_and_an_approved_baseline_is_not_redrafted(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, brief = clarified
    items = [item for item in draft_items() if item["kind"] != "open_question"]
    model.add(fake_response(draft_json(items)))
    process(runner_for(), _ask(run, team, "draft_requirements", brief.id).run.id)
    task = _task(run, team, "draft_requirements")
    assert task.state == "waiting_for_review"

    with pytest.raises(InvalidTransitionError, match="Business requirements' v1 is not approved"):
        _move_task(run, team.reviewer.actor, task, "completed")
    view = _requirements(run, team)
    run(lambda s: s.decisions.record_approval(team.reviewer.actor, view.version_id, ApprovalCreate(decision="approved", content_sha256=s.artifacts.version_record(view.version_id).content_sha256)))
    assert _move_task(run, team.reviewer.actor, _task(run, team, "draft_requirements"), "completed").state == "completed"
    assert _requirements(run, team).approval_status == "approved"

    problem = run(lambda s: s.requirements.baseline_problem(team.project.id))
    assert "approved and under change control; raise a change request" in problem


def test_requirement_records_cannot_be_edited_in_place(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, session_factory: sessionmaker[Session]
) -> None:
    team, brief = clarified
    model.add(fake_response(draft_json()))
    process(runner_for(), _ask(run, team, "draft_requirements", brief.id).run.id)

    for statement in (
        "UPDATE requirement_items SET status = 'confirmed' WHERE item_id = 'Q-001'",
        "DELETE FROM requirement_ids WHERE item_id = 'REQ-F-001'",
    ):
        with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


def test_quality_flags_are_stored_with_the_items(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> None:
    team, brief = clarified
    items = draft_items() + [
        req("new-8", "non_functional", "Page speed", "Pages load in under 2 seconds for 200 users.", criteria=[]),
        req("new-9", "non_functional", "Page speed limit", "Pages load in under 5 seconds for 200 users.", criteria=["Measured at the 95th percentile"]),
        req("new-10", "non_functional", "Usable", "The system is user-friendly.", criteria=["Users find it easy"]),
    ]
    model.add(fake_response(draft_json(items)))

    process(runner_for(), _ask(run, team, "draft_requirements", brief.id).run.id)

    flags = {item.item_id: {f.check for f in item.quality_flags} for item in _requirements(run, team).items}
    assert {"conflict", "completeness"} <= flags["REQ-NF-001"]
    assert "conflict" in flags["REQ-NF-002"]
    assert "testability" in flags["REQ-NF-003"]


def test_uploaded_word_and_pdf_documents_become_source_documents(
    ba_team: Team, client_for: Callable[..., Any]
) -> None:
    pm = client_for(ba_team.pm)
    url = f"/api/projects/{ba_team.project.id}/artifacts/upload"
    for filename, data in (("notes.docx", make_docx("Discovery notes", "Leave approvals happen weekly.")), ("policy.pdf", make_pdf("Annual leave is thirty days for all staff."))):
        response = pm.post(url, json={
            "title": filename, "filename": filename, "origin": "Emailed by the customer's HR lead",
            "content_base64": base64.b64encode(data).decode(),
        })
        assert response.status_code == 201, response.text
        version = response.json()["current_version"]
        assert any(ref.startswith("Original file sha256: ") for ref in version["source_refs"])
        assert "Origin: Emailed by the customer's HR lead" in version["source_refs"]

    content = pm.get(f"/api/artifact-versions/{version['id']}/content").json()["content"]
    assert "## Page 1" in content and "thirty days" in content
    reviewer = client_for(ba_team.reviewer)
    denied = reviewer.post(url, json={"title": "x", "filename": "x.txt", "origin": "test", "content_base64": base64.b64encode(b"hello world, enough text here").decode()})
    assert denied.status_code == 403
    bad = pm.post(url, json={"title": "x", "filename": "x.exe", "origin": "test", "content_base64": "aGVsbG8="})
    assert bad.status_code == 422 and "Unsupported file type" in bad.json()["message"]


def test_requirements_api_shows_the_draft_to_project_members_only(
    clarified: tuple[Team, Any], run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider,
    client_for: Callable[..., Any], make_user: Callable[..., Any],
) -> None:
    team, brief = clarified
    url = f"/api/projects/{team.project.id}/requirements"
    assert client_for(team.reviewer).get(url).json() is None
    model.add(fake_response(draft_json()))
    process(runner_for(), _ask(run, team, "draft_requirements", brief.id).run.id)

    body = client_for(team.reviewer).get(url).json()
    assert [item["item_id"] for item in body["items"]][:3] == ["OBJ-001", "STK-001", "REQ-F-001"]
    assert client_for(make_user(name="Outsider")).get(url).status_code == 404
    assert json.dumps(body).count("sk-ant") == 0
