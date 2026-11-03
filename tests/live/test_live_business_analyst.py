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
