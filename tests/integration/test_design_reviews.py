"""Phase 8 reviews (Increment 4b) with a scripted model: the security checklist review and its sign-off, the
feasibility review, and the gate that lets a design version be approved only with both reviews of that version."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.harness.runner import AgentRunner
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate
from app.modules.errors import InvalidTransitionError, PermissionDeniedError
from app.modules.executions.schemas import AgentRunCreate
from tests.agent_support import (
    CHECK_IDS,
    DESIGN_IDS,
    design_json,
    feasibility_json,
    kept_design_items,
    ffinding,
    move_task,
    phase_task,
    process,
    security_findings,
    security_json,
    sfinding,
)
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _approve(run: Run, user: TestUser, version_id: Any, decision: str = "approved", comment: str | None = None) -> None:
    run(lambda s: s.decisions.record_approval(user.actor, version_id, ApprovalCreate(
        decision=decision, comment=comment, content_sha256=s.artifacts.version_record(version_id).content_sha256)))


def _reviews(run: Run, team: Team) -> Any:
    return run(lambda s: s.design_reviews.view(team.owner.actor, team.project.id))


def _design(run: Run, team: Team) -> Any:
    return run(lambda s: s.design.view(team.owner.actor, team.project.id))


def _run_detail(run: Run, team: Team, run_id: Any) -> Any:
    return run(lambda s: s.executions.get_run(team.owner.actor, run_id))


def _draft_design(run: Run, team: Team, runner: AgentRunner, model: FakeProvider, output: str, actor: Any = None) -> Any:
    requirements = run(lambda s: s.requirements.view(team.owner.actor, team.project.id)).version_id
    data = AgentRunCreate(agent_key="solution_architect", task_key="draft_design", artifact_version_id=requirements)
    model.add(fake_response(output))
    run_id = run(lambda s: s.executions.request_run(actor or team.pm.actor, team.project.id, data)).run.id
    process(runner, run_id)
    return _run_detail(run, team, run_id)


@pytest.fixture
def designed(review_team: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> Team:
    """A first design drafted; the Security Reviewer and Developer agents are on the team."""
    _draft_design(run, review_team, runner_for(), model, design_json())
    model.requests.clear()
    return review_team


def _review(run: Run, team: Team, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any], kind: str, output: str, **kwargs: Any) -> Any:
    model.add(fake_response(output))
    run_id = ask_review(team, kind, **kwargs).run.id
    process(runner_for(), run_id)
    return _run_detail(run, team, run_id)


# The security review ----------------------------------------------------------------------------------


def test_a_security_review_answers_every_check_for_one_design_version(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]
) -> None:
    detail = _review(run, designed, runner_for, model, ask_review, "security", security_json(security_findings(SC_08="medium")))

    assert detail.status == "succeeded"
    review = _reviews(run, designed).security
    assert (review.version_no, review.design_version_no, review.current, review.approval_status) == (1, 1, True, "pending")
    assert review.counts == {"addressed": 9, "gap": 1}
    assert [f.ref for f in review.findings] == CHECK_IDS
    assert review.findings[7].title == "Personal data and retention" and review.findings[7].severity == "medium"
    assert review.checklist.startswith("security_checklist v1 (sha256 ") and review.blocking == []
    content = run(lambda s: s.artifacts.read_version(designed.owner.actor, review.version_id).content)
    assert "Reviews Solution design v1" in content and "### SC-08 Personal data and retention" in content
    assert phase_task(run, designed, "review_security", phase=8).state == "waiting_for_review"
    # The checklist and the design reached the model; the design went as screened, wrapped data.
    prompt = model.requests[-1].user
    assert "SC-10 Backup, recovery and availability:" in prompt and "SEC-001 [security_control" in prompt and "<document" in prompt


@pytest.mark.parametrize(
    ("findings", "summary", "check"),
    [
        (security_findings()[:-1], None, "review_content"),  # SC-10 not answered
        (security_findings() + [sfinding("SC-01")], None, "review_content"),  # answered twice
        ([sfinding(c, design_items=[]) if c == "SC-02" else sfinding(c) for c in CHECK_IDS], None, "review_content"),  # addressed, nothing cited
        ([sfinding(c, "gap", None) if c == "SC-03" else sfinding(c) for c in CHECK_IDS], None, "review_content"),  # gap without severity
        ([sfinding(c, items=["CMP-099"]) if c == "SC-04" else sfinding(c) for c in CHECK_IDS], None, "review_content"),  # unknown design item
        ([sfinding("SC-99")] + security_findings(), None, "review_content"),  # not a checklist check
        (security_findings(), "Overall the design is secure and meets all security requirements.", "assurance_claim"),
    ],
    ids=["missing", "duplicate", "uncited", "no_severity", "unknown_item", "unknown_check", "assurance"],
)
def test_bad_security_reviews_save_nothing(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any],
    findings: list[dict[str, Any]], summary: str | None, check: str,
) -> None:
    output = security_json(findings, **({"summary": summary} if summary else {}))
    detail = _review(run, designed, runner_for, model, ask_review, "security", output)

    assert detail.error_code == "guardrail_blocked"
    assert check in {f.check for f in detail.findings}
    assert _reviews(run, designed).security is None


def test_hedged_security_wording_is_allowed(designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]) -> None:
    summary = "Access would be secure once conditional access is confirmed; the design is not yet compliant with the retention rule."
    detail = _review(run, designed, runner_for, model, ask_review, "security", security_json(summary=summary))

    assert detail.status == "succeeded"


# The feasibility review -------------------------------------------------------------------------------


def test_a_feasibility_review_rates_every_design_item(designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]) -> None:
    findings = [ffinding(i, "concerns", "L") if i == "API-001" else ffinding(i) for i in DESIGN_IDS]
    detail = _review(run, designed, runner_for, model, ask_review, "feasibility", feasibility_json(findings))

    assert detail.status == "succeeded"
    review = _reviews(run, designed).feasibility
    assert review.counts == {"feasible": 5, "concerns": 1} and review.blocking == []
    assert review.findings[1].title == "Reminder emails" and review.findings[1].complexity == "L"
    assert phase_task(run, designed, "review_feasibility", phase=8).state == "waiting_for_review"


@pytest.mark.parametrize(
    "findings",
    [
        [ffinding(i) for i in DESIGN_IDS[:-1]],  # ADR-001 not rated
        [ffinding(i) for i in DESIGN_IDS] + [ffinding("CMP-099")],  # not a design item
        [ffinding(i, "not_feasible", recommendation="") if i == "CMP-001" else ffinding(i) for i in DESIGN_IDS],  # no way forward
    ],
    ids=["missing", "unknown_item", "no_recommendation"],
)
def test_bad_feasibility_reviews_save_nothing(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any], findings: list[dict[str, Any]]
) -> None:
    detail = _review(run, designed, runner_for, model, ask_review, "feasibility", feasibility_json(findings))

    assert detail.error_code == "guardrail_blocked" and "review_content" in {f.check for f in detail.findings}
    assert _reviews(run, designed).feasibility is None


# The gate ---------------------------------------------------------------------------------------------


def test_a_design_needs_both_reviews_of_its_exact_version(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]
) -> None:
    team = designed
    design_v1 = _design(run, team)
    with pytest.raises(InvalidTransitionError, match="no security review yet.*no feasibility review yet"):
        _approve(run, team.reviewer, design_v1.version_id)

    # A high gap: the review cannot be signed off and the design cannot be approved.
    _review(run, team, runner_for, model, ask_review, "security", security_json(security_findings(SC_03="high", SC_08="low")))
    _review(run, team, runner_for, model, ask_review, "feasibility", feasibility_json())
    reviews = _reviews(run, team)
    assert reviews.security.blocking == ["High-severity gaps: SC-03"]
    assert reviews.gate == ["Security review v1 of design v1 has high-severity gaps: SC-03"]
    with pytest.raises(InvalidTransitionError, match=r"high-severity gaps \(SC-03\)"):
        _approve(run, team.reviewer, reviews.security.version_id)
    with pytest.raises(InvalidTransitionError, match="high-severity gaps: SC-03"):
        _approve(run, team.reviewer, design_v1.version_id)

    # The redraft must answer both gaps; without the answers nothing is saved.
    unanswered = _draft_design(run, team, runner_for(), model, design_json(), actor=team.owner.actor)
    assert unanswered.error_code == "guardrail_blocked"
    assert "Review finding FND-1 needs exactly one response (it has 0)" in [f.message for f in unanswered.findings]
    assert "FND-1 (Security review v1: SC-03 (gap, high)) Data protection in transit and at rest" in model.requests[-1].user
    replies = [{"ref": "FND-1", "response": "Added SEC-002 for encryption."}, {"ref": "FND-2", "response": "Accepted as low."}]
    redrafted = _draft_design(run, team, runner_for(), model, design_json(kept_design_items(), review_responses=replies), actor=team.owner.actor)
    assert redrafted.status == "succeeded"
    design_v2 = _design(run, team)
    assert design_v2.version_no == 2
    assert [r.finding for r in design_v2.review_responses] == ["Security review v1: SC-03 (gap, high)", "Security review v1: SC-08 (gap, low)"]

    # The reviews of v1 no longer count, and cannot be approved now.
    reviews = _reviews(run, team)
    assert not reviews.security.current and not reviews.feasibility.current
    assert reviews.gate == ["Design v2 has no security review yet; ask the Security Reviewer agent", "Design v2 has no feasibility review yet; ask the Developer agent"]
    _review(run, team, runner_for, model, ask_review, "feasibility", feasibility_json())
    with pytest.raises(InvalidTransitionError, match="no longer the current design"):
        _approve(run, team.reviewer, reviews.security.version_id)

    # Reviews of v2 with only a medium gap: signed off, then the design is approved.
    detail = _review(run, team, runner_for, model, ask_review, "security", security_json(security_findings(SC_08="medium")))
    assert detail.status == "succeeded", (detail.error_code, detail.error_message, [f.message for f in detail.findings])
    security = _reviews(run, team).security
    assert (security.version_no, security.design_version_no) == (2, 2)
    with pytest.raises(InvalidTransitionError, match="not signed off"):
        _approve(run, team.reviewer, design_v2.version_id)
    _approve(run, team.reviewer, security.version_id)
    assert _reviews(run, team).gate == []
    _approve(run, team.reviewer, design_v2.version_id)
    assert _design(run, team).approval_status == "approved"


def test_an_item_rated_not_feasible_blocks_the_design(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]
) -> None:
    _review(run, designed, runner_for, model, ask_review, "security", security_json())
    _approve(run, designed.reviewer, _reviews(run, designed).security.version_id)
    findings = [ffinding(i, "not_feasible") if i == "API-001" else ffinding(i) for i in DESIGN_IDS]
    _review(run, designed, runner_for, model, ask_review, "feasibility", feasibility_json(findings))

    assert _reviews(run, designed).feasibility.blocking == ["Rated not feasible: API-001"]
    with pytest.raises(InvalidTransitionError, match="rates items not feasible: API-001"):
        _approve(run, designed.reviewer, _design(run, designed).version_id)


def test_only_a_reviewer_signs_off_a_security_review(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any], security_agent: TestUser
) -> None:
    _review(run, designed, runner_for, model, ask_review, "security", security_json())
    version_id = _reviews(run, designed).security.version_id

    for user in (security_agent, designed.pm, designed.owner):  # the agent never; project managers and owners are not security reviewers
        with pytest.raises(PermissionDeniedError):
            _approve(run, user, version_id)
    _approve(run, designed.reviewer, version_id)
    assert _reviews(run, designed).security.approval_status == "approved"


def test_review_comments_on_a_review_must_be_answered(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]
) -> None:
    _review(run, designed, runner_for, model, ask_review, "security", security_json(security_findings(SC_09="medium")))
    _approve(run, designed.reviewer, _reviews(run, designed).security.version_id, "changes_requested", "SC-09 is a high gap: the HR system link has no authentication.")

    unanswered = _review(run, designed, runner_for, model, ask_review, "security", security_json(security_findings(SC_09="high")))
    assert unanswered.error_code == "guardrail_blocked" and "Review comment REV-1 needs exactly one response (it has 0)" in [f.message for f in unanswered.findings]
    answered = _review(run, designed, runner_for, model, ask_review, "security", security_json(
        security_findings(SC_09="high"), review_responses=[{"ref": "REV-1", "response": "Raised SC-09 to high."}]))
    assert answered.status == "succeeded"
    review = _reviews(run, designed).security
    assert review.version_no == 2 and review.review_responses[0].response == "Raised SC-09 to high."


def test_only_the_current_design_version_can_be_reviewed(
    designed: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, ask_review: Callable[..., Any]
) -> None:
    design_v1 = _design(run, designed).version_id
    _review(run, designed, runner_for, model, ask_review, "feasibility", feasibility_json())  # nothing open, but a new input for the redraft
    assert _draft_design(run, designed, runner_for(), model, design_json(kept_design_items())).status == "succeeded"  # the PM may ask
    calls = len(model.requests)

    detail = _review(run, designed, runner_for, model, ask_review, "security", security_json(), design_version_id=design_v1)

    assert (detail.status, detail.error_code) == ("failed", "input_rejected")
    assert "no longer the current version" in detail.error_message
    assert len(model.requests) == calls  # refused before any model call (its scripted answer stays queued)
    # The current version is reviewed again; the PM's request sends the reviewed task back, recorded as Agentra's step.
    assert _review(run, designed, runner_for, model, ask_review, "security", security_json()).status == "succeeded"
    assert _reviews(run, designed).security.design_version_no == 2


def test_review_tasks_close_only_after_the_design_is_approved(designed: Team, run: Run, pass_reviews: Callable[[Team], None]) -> None:
    pass_reviews(designed)
    task = phase_task(run, designed, "review_security", phase=8)
    with pytest.raises(InvalidTransitionError, match="Design baseline 'Solution design' v1 is not approved"):
        move_task(run, designed.reviewer.actor, task, "completed")

    _approve(run, designed.reviewer, _design(run, designed).version_id)
    for key in ("review_security", "review_feasibility"):
        assert move_task(run, designed.reviewer.actor, phase_task(run, designed, key, phase=8), "completed").state == "completed"


def test_review_records_cannot_be_edited(designed: Team, run: Run, pass_reviews: Callable[[Team], None], session_factory: sessionmaker[Session]) -> None:
    pass_reviews(designed)
    for statement in ("UPDATE design_review_findings SET severity = NULL", "DELETE FROM design_reviews"):
        with session_factory() as session, pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


def test_the_reviews_over_http(designed: Team, run: Run, pass_reviews: Callable[[Team], None], client_for: Callable[..., Any], make_user: Callable[..., TestUser]) -> None:
    url = f"/api/projects/{designed.project.id}/design/reviews"
    body = client_for(designed.reviewer).get(url).json()
    assert (body["security"], body["feasibility"], body["design_version_no"]) == (None, None, 1)
    assert len(body["gate"]) == 2

    pass_reviews(designed)
    body = client_for(designed.reviewer).get(url).json()
    assert body["gate"] == [] and body["security"]["approval_status"] == "approved" and len(body["feasibility"]["findings"]) == 6
    assert client_for(make_user(name="Outsider")).get(url).status_code == 404
