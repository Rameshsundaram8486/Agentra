"""One real Business Analyst run against the Claude API. Costs money (about $0.15-0.50), so it is skipped
unless switched on:

    $env:AGENTRA_LIVE_TESTS = "1"; uv run pytest tests/live -q

It uses the synthetic brief, the test database and the key in .env, and counts against the monthly cap.
It checks the integration, not the quality of the questions: a person should read those.
"""

import os
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.composition import Policies
from app.harness.runner import AgentRunner
from app.infrastructure.clock import FixedClock
from app.infrastructure.job_queue import ClaimedJob
from app.infrastructure.settings import Settings
from app.infrastructure.storage.local import LocalArtifactStore
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.providers.anthropic_provider import AnthropicProvider
from app.modules.executions.schemas import AgentRunCreate
from tests.support import Team

pytestmark = pytest.mark.skipif(os.environ.get("AGENTRA_LIVE_TESTS") != "1", reason="live model calls are opt-in (AGENTRA_LIVE_TESTS=1)")


def test_business_analyst_asks_grounded_questions_about_a_real_brief(
    ba_team: Team, make_brief: Callable[..., Any], run: Callable[..., Any], test_settings: Settings,
    session_factory: sessionmaker[Session], clock: FixedClock, policies: Policies, store: LocalArtifactStore,
) -> None:
    if test_settings.anthropic_api_key is None:
        pytest.fail("ANTHROPIC_API_KEY is not set in .env")
    provider = AnthropicProvider(test_settings.anthropic_api_key.get_secret_value())
    runner = AgentRunner(session_factory, clock, policies, store, ModelGateway(policies.models, provider))
    brief = make_brief(ba_team)
    data = AgentRunCreate(agent_key="business_analyst", task_key="clarify_brief", artifact_version_id=brief.id)
    queued = run(lambda s: s.executions.request_run(ba_team.pm.actor, ba_team.project.id, data)).run

    runner.handle(ClaimedJob(uuid.uuid4(), "agent_run", {"agent_run_id": str(queued.id)}, "live", 1))

    detail = run(lambda s: s.executions.get_run(ba_team.owner.actor, queued.id))
    call = detail.model_calls[0]
    print(f"\nstatus={detail.status} model={call.model} fallback={call.fallback_used} cost=${call.cost_usd} "
          f"tokens in/out={call.input_tokens}/{call.output_tokens} request_id={call.request_id}")
    for finding in detail.findings:
        print(f"finding: {finding.severity} {finding.check} {finding.path}: {finding.message}")
    assert detail.status == "succeeded", f"{detail.error_code}: {detail.error_message}"
    assert call.request_id and call.cost_usd and call.cost_usd > 0
    decisions = run(lambda s: s.decisions.list_decisions(ba_team.owner.actor, ba_team.project.id))
    assert len(decisions) >= 3
    for decision in decisions:
        print(f"- {decision.title}: {decision.question} [{', '.join(o.key for o in decision.options)}] -> {decision.recommended_option}")


def test_business_analyst_drafts_grounded_requirements(
    ba_team: Team, make_brief: Callable[..., Any], run: Callable[..., Any], test_settings: Settings,
    session_factory: sessionmaker[Session], clock: FixedClock, policies: Policies, store: LocalArtifactStore,
) -> None:
    """A real draft from the demo brief and synthetic discovery notes (the clarify task is closed directly)."""
    from app.demo import DEMO_BRIEF
    from app.modules.artifacts.service import ArtifactCreate
    from app.modules.workflow.service import TransitionRequest
    from tests.agent_support import DISCOVERY_NOTES

    if test_settings.anthropic_api_key is None:
        pytest.fail("ANTHROPIC_API_KEY is not set in .env")
    provider = AnthropicProvider(test_settings.anthropic_api_key.get_secret_value())
    runner = AgentRunner(session_factory, clock, policies, store, ModelGateway(policies.models, provider))
    team = ba_team
    brief = make_brief(team, DEMO_BRIEF)
    run(lambda s: s.artifacts.create_artifact(
        team.pm.actor, team.project.id, ArtifactCreate(artifact_type="source_document", title="Discovery notes", content=DISCOVERY_NOTES)
    ))
    for actor, state in ((team.owner, "ready"), (team.pm, "in_progress"), (team.pm, "waiting_for_input"), (team.pm, "completed")):
        def step(s: Any, actor: Any = actor, state: str = state) -> None:
            phase = next(p for p in s.workflow.list_phase_runs(team.owner.actor, team.project.id) if p.phase == 7)
            task = next(t for t in phase.tasks if t.key == "clarify_brief")
            s.workflow.transition_task(actor.actor, task.id, TransitionRequest(to_state=state, reason="Live test", expected_version=task.version))
        run(step)
    data = AgentRunCreate(agent_key="business_analyst", task_key="draft_requirements", artifact_version_id=brief.id)
    queued = run(lambda s: s.executions.request_run(team.pm.actor, team.project.id, data)).run

    runner.handle(ClaimedJob(uuid.uuid4(), "agent_run", {"agent_run_id": str(queued.id)}, "live", 1))

    detail = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
    call = detail.model_calls[0]
    print(f"\nstatus={detail.status} model={call.model} fallback={call.fallback_used} cost=${call.cost_usd} "
          f"tokens in/out={call.input_tokens}/{call.output_tokens} cache_write={call.cache_creation_input_tokens} latency={call.latency_ms}ms")
    for finding in detail.findings:
        print(f"finding: {finding.severity} {finding.check} {finding.path}: {finding.message}")
    assert detail.status == "succeeded", f"{detail.error_code}: {detail.error_message}"
    view = run(lambda s: s.requirements.view(team.owner.actor, team.project.id))
    print(f"counts={view.counts} set_flags={[f.message for f in view.set_flags]}")
    for item in view.items:
        flags = "; ".join(f.message for f in item.quality_flags)
        print(f"- {item.item_id} [{item.label}/{item.status}] {item.title}: {item.statement}" + (f"  <{flags}>" if flags else ""))
    assert view.counts["confirmed"] > 0 and any(item.kind == "functional" for item in view.items)


def test_business_analyst_answers_a_review_and_applies_a_change_request(
    ba_team: Team, make_brief: Callable[..., Any], run: Callable[..., Any], test_settings: Settings, make_user: Callable[..., Any],
    add_member: Callable[..., None], session_factory: sessionmaker[Session], clock: FixedClock, policies: Policies, store: LocalArtifactStore,
) -> None:
    """Three real calls: draft, redraft answering a reviewer's comment, and applying an approved change request."""
    from app.demo import DEMO_BRIEF
    from app.modules.artifacts.service import ArtifactCreate
    from app.modules.decisions.service import ApprovalCreate
    from app.modules.requirements.service import ChangeRequestCreate, ChangeRequestDecisionCreate
    from tests.agent_support import DISCOVERY_NOTES, ask, move_task, phase_task

    if test_settings.anthropic_api_key is None:
        pytest.fail("ANTHROPIC_API_KEY is not set in .env")
    runner = AgentRunner(session_factory, clock, policies, store, ModelGateway(policies.models, AnthropicProvider(test_settings.anthropic_api_key.get_secret_value())))
    team = ba_team
    customer = make_user(name="Customer")
    add_member(team.owner, team.project.id, customer, "customer_approver")
    brief = make_brief(team, DEMO_BRIEF)
    run(lambda s: s.artifacts.create_artifact(team.pm.actor, team.project.id, ArtifactCreate(artifact_type="source_document", title="Discovery notes", content=DISCOVERY_NOTES)))
    for actor, state in ((team.owner, "ready"), (team.pm, "in_progress"), (team.pm, "waiting_for_input"), (team.pm, "completed")):
        move_task(run, actor.actor, phase_task(run, team, "clarify_brief"), state)

    def go(queued: Any) -> Any:
        runner.handle(ClaimedJob(uuid.uuid4(), "agent_run", {"agent_run_id": str(queued.id)}, "live", 1))
        detail = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
        call = detail.model_calls[0] if detail.model_calls else None
        print(f"\n{detail.task_key}: status={detail.status} cost=${detail.cost_usd} out_tokens={call.output_tokens if call else '-'} prompt={detail.prompt_version}")
        for finding in detail.findings:
            print(f"  finding: {finding.severity} {finding.check} {finding.path}: {finding.message}")
        assert detail.status == "succeeded", f"{detail.error_code}: {detail.error_message}"
        return run(lambda s: s.requirements.view(team.owner.actor, team.project.id))

    first = go(ask(run, team, "draft_requirements", brief.id).run)
    matrix = run(lambda s: s.requirements.traceability(team.owner.actor, team.project.id))
    print(f"v{first.version_no}: {first.counts}; traced rows={len(matrix.rows)}, rows with gaps={sum(1 for r in matrix.rows if r.gaps)}, set gaps={matrix.gaps}")

    def approve(version_id: Any, decision: str = "approved", comment: str | None = None) -> None:
        run(lambda s: s.decisions.record_approval(team.reviewer.actor, version_id, ApprovalCreate(
            decision=decision, comment=comment, content_sha256=s.artifacts.version_record(version_id).content_sha256)))

    if phase_task(run, team, "draft_requirements").state == "waiting_for_input":  # open questions: answer by deferring for the test
        from app.modules.decisions.service import DecisionOutcomeCreate
        for d in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)):
            if d.status == "open":
                run(lambda s, d=d: s.decisions.record_outcome(team.owner.actor, d.id, DecisionOutcomeCreate(action="defer", comment="Live test")))
    approve(first.version_id, "changes_requested", "Add a measurable availability target for the system, and make sure every requirement traces to an objective.")
    second = go(ask(run, team, "draft_requirements", brief.id).run)
    print(f"v{second.version_no}: added={second.added} removed={second.removed}")
    for response in second.review_responses:
        print(f"  review response: {response.response}")
    assert second.version_no == 2 and len(second.review_responses) == 1

    approve(second.version_id)
    task = phase_task(run, team, "draft_requirements")
    if task.state == "waiting_for_input":
        move_task(run, team.pm.actor, task, "in_progress")
        task = move_task(run, team.pm.actor, phase_task(run, team, "draft_requirements"), "waiting_for_review")
    move_task(run, team.reviewer.actor, phase_task(run, team, "draft_requirements"), "completed")
    target = next(i.item_id for i in second.items if i.kind == "functional")
    request = run(lambda s: s.requirements.raise_change_request(team.pm.actor, team.project.id, ChangeRequestCreate(
        title="Half-day leave", reason="HR confirmed staff often take half days",
        change=f"Change {target} so employees can request leave in half days as well as full days",
        impact="Small: one extra option in the request form and balance calculation", affected_item_ids=[target])))
    for approver in (team.owner, customer):
        run(lambda s, a=approver: s.requirements.decide_change_request(a.actor, request.id, ChangeRequestDecisionCreate(decision="approved")))
    third = go(ask(run, team, "apply_change_request", request.baseline_version_id, change_request_id=request.id).run)
    changed = next(i for i in third.items if i.item_id == target)
    print(f"v{third.version_no} applies {third.change_request}: {target} now reads: {changed.statement}")
    assert third.change_request == "CR-001" and third.version_no == 3


def test_solution_architect_compares_options_and_drafts_a_covering_design(
    phase8: Team, run: Callable[..., Any], test_settings: Settings,
    session_factory: sessionmaker[Session], clock: FixedClock, policies: Policies, store: LocalArtifactStore,
) -> None:
    """Two real calls on small synthetic requirements (drafted by the scripted model): compare options, then design."""
    from app.modules.decisions.service import DecisionOutcomeCreate
    from tests.agent_support import move_task, phase_task

    if test_settings.anthropic_api_key is None:
        pytest.fail("ANTHROPIC_API_KEY is not set in .env")
    runner = AgentRunner(session_factory, clock, policies, store, ModelGateway(policies.models, AnthropicProvider(test_settings.anthropic_api_key.get_secret_value())))
    team = phase8
    requirements = run(lambda s: s.requirements.view(team.owner.actor, team.project.id))

    def go(task_key: str) -> Any:
        data = AgentRunCreate(agent_key="solution_architect", task_key=task_key, artifact_version_id=requirements.version_id)
        queued = run(lambda s: s.executions.request_run(team.pm.actor, team.project.id, data)).run
        runner.handle(ClaimedJob(uuid.uuid4(), "agent_run", {"agent_run_id": str(queued.id)}, "live", 1))
        detail = run(lambda s: s.executions.get_run(team.owner.actor, queued.id))
        call = detail.model_calls[0] if detail.model_calls else None
        print(f"\n{task_key}: status={detail.status} cost=${detail.cost_usd} out_tokens={call.output_tokens if call else '-'} latency={call.latency_ms if call else '-'}ms")
        for finding in detail.findings:
            print(f"  finding: {finding.severity} {finding.check} {finding.path}: {finding.message}")
        assert detail.status == "succeeded", f"{detail.error_code}: {detail.error_message}"
        return detail

    compared = go("compare_options")
    decision = next(d for d in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)) if d.title == "Architecture option")
    print(f"options: {[(o.key, o.title) for o in decision.options]} recommended={decision.recommended_option} scores={compared.output['weighted_scores']}")
    run(lambda s: s.decisions.record_outcome(team.owner.actor, decision.id, DecisionOutcomeCreate(action="accept")))
    move_task(run, team.pm.actor, phase_task(run, team, "compare_options", phase=8), "completed")

    go("draft_design")
    design = run(lambda s: s.design.view(team.owner.actor, team.project.id))
    print(f"design v{design.version_no}: {len(design.items)} items {design.counts}; coverage {design.coverage.covered}/{design.coverage.confirmed}, "
          f"excepted {design.coverage.excepted}, gaps {design.coverage.gaps}")
    for item in design.items:
        flags = "; ".join(f.message for f in item.quality_flags)
        print(f"- {item.item_id} [{item.kind}/{item.status}] {item.title} -> {', '.join(item.satisfies) or '-'}" + (f"  <{flags}>" if flags else ""))
    assert design.coverage.gaps == [] and any(i.kind == "security_control" for i in design.items)
