"""Creates throwaway users in the database named by DATABASE_URL (the test database) for the UI run, the
Business Analyst agent account if missing, and a second project with an approved requirements baseline and
an open change request (drafted with the scripted fake model; no real model is called)."""

import contextlib
import io
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from app.cli import main
from app.composition import Services, load_policies
from app.harness.runner import AgentRunner
from app.infrastructure.clock import SystemClock
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.settings import get_settings
from app.infrastructure.storage.local import LocalArtifactStore
from app.infrastructure.unit_of_work import UnitOfWork
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.artifacts.service import ArtifactCreate
from app.modules.decisions.service import ApprovalCreate, DecisionOutcomeCreate
from app.modules.executions.schemas import AgentRunCreate
from app.modules.identity.service import Actor
from app.modules.projects.service import ProjectCreate
from app.modules.requirements.service import ChangeRequestCreate
from app.modules.workflow.service import TransitionRequest
from tests.agent_support import (
    BRIEF, DISCOVERY_NOTES, ba_json, backlog_json, compare_output, design_json, draft_items, draft_json, feasibility_json, kept_design_items, process,
    security_findings, security_json,
)
from tests.support import make_docx

suffix = uuid.uuid4().hex[:6]
password = "ui-test-pass-123"
users = {
    "admin": (f"admin_{suffix}@ui.test", "UI Admin", True),
    "pm": (f"pm_{suffix}@ui.test", "UI Project Manager", False),
    "reviewer": (f"reviewer_{suffix}@ui.test", "UI Reviewer", False),
    "customer": (f"customer_{suffix}@ui.test", "UI Customer", False),
}
for email, name, admin in users.values():
    args = ["create-user", "--email", email, "--name", name] + (["--admin"] if admin else [])
    if main(args, read_password=lambda: password) != 0:
        sys.exit(1)

AGENT_EMAIL = "business_analyst@agents.agentra.local"
SA_EMAIL = "solution_architect@agents.agentra.local"
with contextlib.redirect_stderr(io.StringIO()):  # "already exists" is fine: the accounts are shared by every run
    main(["create-agent", "--key", "business_analyst", "--name", "Business Analyst Agent"])
    main(["create-agent", "--key", "solution_architect", "--name", "Solution Architect Agent"])
    main(["create-agent", "--key", "security_reviewer", "--name", "Security Reviewer Agent"])
    main(["create-agent", "--key", "developer", "--name", "Developer Agent"])

docx_path = Path(sys.argv[1]).with_name("discovery-notes.docx")
docx_path.write_bytes(make_docx("Discovery notes", "Leave approvals happen weekly."))


def change_control_project() -> str:
    """Brief clarified; a failed draft (INC-001) then a good one, approved; CR-001 raised and still open; Phase 7
    completed; Phase 8 options compared and chosen; design v1 with a high security gap (SC-03), redrafted as v2
    answering it, reviewed again, signed off and approved; the implementation backlog planned and approved."""
    settings = get_settings()
    policies = load_policies(min_password_length=settings.min_password_length)
    engine = create_db_engine(settings.database_url.get_secret_value())
    factory, clock, store = make_session_factory(engine), SystemClock(), LocalArtifactStore(settings.artifact_root)

    def run(fn: Any) -> Any:
        with UnitOfWork(factory) as uow:
            result = fn(Services(uow.session, clock, policies, store))
            uow.commit()
            return result

    def actor(key: str) -> Actor:
        return run(lambda s: s.identity.actor_by_email(users[key][0]))

    admin, pm, reviewer = actor("admin"), actor("pm"), actor("reviewer")
    project = run(lambda s: s.projects.create_project(admin, ProjectCreate(code=f"CR-{suffix.upper()}", name="UI Change control", customer_name="Example Co")))
    for key, role in (("pm", "project_manager"), ("reviewer", "reviewer"), ("customer", "customer_approver")):
        run(lambda s, k=key, r=role: s.identity.add_member(admin, project.id, users[k][0], r))
    run(lambda s: s.identity.add_member(admin, project.id, AGENT_EMAIL, "agent"))

    def move(who: Actor, kind: str, key: str | int, state: str) -> None:
        def step(s: Services) -> None:
            phase = next(p for p in s.workflow.list_phase_runs(admin, project.id) if p.phase == 7)
            if kind == "phase":
                s.workflow.transition_phase_run(who, phase.id, TransitionRequest(to_state=state, reason="UI seed", expected_version=phase.version))
            else:
                task = next(t for t in phase.tasks if t.key == key)
                s.workflow.transition_task(who, task.id, TransitionRequest(to_state=state, reason="UI seed", expected_version=task.version))

        run(step)

    move(admin, "phase", 7, "ready")
    move(pm, "phase", 7, "in_progress")
    brief = run(lambda s: s.artifacts.create_artifact(pm, project.id, ArtifactCreate(artifact_type="project_brief", title="Brief", content=BRIEF))).current_version
    run(lambda s: s.artifacts.create_artifact(pm, project.id, ArtifactCreate(artifact_type="source_document", title="Discovery notes", content=DISCOVERY_NOTES)))

    model = FakeProvider([fake_response(ba_json())])
    runner = AgentRunner(factory, clock, policies, store, ModelGateway(policies.models, model))

    def ask_agent(task_key: str) -> None:
        data = AgentRunCreate(agent_key="business_analyst", task_key=task_key, artifact_version_id=brief.id)
        process(runner, run(lambda s: s.executions.request_run(pm, project.id, data)).run.id)

    ask_agent("clarify_brief")
    for decision in run(lambda s: s.decisions.list_decisions(admin, project.id)):
        run(lambda s, d=decision: s.decisions.record_outcome(admin, d.id, DecisionOutcomeCreate(action="defer", comment="Later")))
    move(pm, "task", "clarify_brief", "completed")

    model.add(fake_response("not JSON"))  # a failed draft first, so the project has an incident (INC-001)
    ask_agent("draft_requirements")
    move(admin, "task", "draft_requirements", "ready")
    items = [item for item in draft_items() if item["kind"] != "open_question"]
    model.add(fake_response(draft_json(items)))
    ask_agent("draft_requirements")
    view = run(lambda s: s.requirements.view(admin, project.id))
    run(lambda s: s.decisions.record_approval(
        reviewer, view.version_id, ApprovalCreate(decision="approved", content_sha256=s.artifacts.version_record(view.version_id).content_sha256)
    ))
    move(reviewer, "task", "draft_requirements", "completed")
    run(lambda s: s.requirements.raise_change_request(pm, project.id, ChangeRequestCreate(
        title="Add half-day leave", reason="HR asked for half days", change="Allow half-day requests",
        impact="About two days of build", affected_item_ids=["REQ-F-001"],
    )))

    # Phase 7 completed; Phase 8: options compared and chosen, design drafted (waiting for review).
    move(pm, "phase", 7, "waiting_for_review")
    move(reviewer, "phase", 7, "completed")
    run(lambda s: s.identity.add_member(admin, project.id, SA_EMAIL, "agent"))

    def move8(who: Actor, kind: str, key: str | int, state: str) -> None:
        def step(s: Services) -> None:
            phase = next(p for p in s.workflow.list_phase_runs(admin, project.id) if p.phase == 8)
            if kind == "phase":
                s.workflow.transition_phase_run(who, phase.id, TransitionRequest(to_state=state, reason="UI seed", expected_version=phase.version))
            else:
                task = next(t for t in phase.tasks if t.key == key)
                s.workflow.transition_task(who, task.id, TransitionRequest(to_state=state, reason="UI seed", expected_version=task.version))

        run(step)

    move8(admin, "phase", 8, "ready")
    move8(pm, "phase", 8, "in_progress")
    requirements_version = run(lambda s: s.requirements.view(admin, project.id)).version_id

    def ask_architect(task_key: str) -> None:
        data = AgentRunCreate(agent_key="solution_architect", task_key=task_key, artifact_version_id=requirements_version)
        process(runner, run(lambda s: s.executions.request_run(pm, project.id, data)).run.id)

    model.add(fake_response(json.dumps(compare_output())))
    ask_architect("compare_options")
    option = next(d for d in run(lambda s: s.decisions.list_decisions(admin, project.id)) if d.title == "Architecture option")
    run(lambda s: s.decisions.record_outcome(admin, option.id, DecisionOutcomeCreate(action="accept")))
    move8(pm, "task", "compare_options", "completed")
    model.add(fake_response(design_json()))
    ask_architect("draft_design")

    def ask_agent(key: str, task_key: str, output: str) -> None:
        design_version = run(lambda s: s.design.current_version_id(project.id))
        model.add(fake_response(output))
        data = AgentRunCreate(agent_key=key, task_key=task_key, artifact_version_id=design_version)
        process(runner, run(lambda s: s.executions.request_run(pm, project.id, data)).run.id)

    def approve(who: Actor, version_id: Any) -> None:
        run(lambda s: s.decisions.record_approval(who, version_id, ApprovalCreate(
            decision="approved", content_sha256=s.artifacts.version_record(version_id).content_sha256)))

    for key in ("security_reviewer", "developer"):
        run(lambda s, k=key: s.identity.add_member(admin, project.id, f"{k}@agents.agentra.local", "agent"))
    # Design v1: a high security gap; the redraft (v2) answers it; v2 is reviewed cleanly, signed off and approved.
    ask_agent("security_reviewer", "review_security", security_json(security_findings(SC_03="high")))
    ask_agent("developer", "review_feasibility", feasibility_json())
    model.add(fake_response(design_json(kept_design_items(), review_responses=[{"ref": "FND-1", "response": "SEC-001 now encrypts leave data at rest."}])))
    ask_architect("draft_design")
    ask_agent("security_reviewer", "review_security", security_json(security_findings(SC_08="medium")))
    ask_agent("developer", "review_feasibility", feasibility_json())
    approve(reviewer, run(lambda s: s.design_reviews.view(admin, project.id)).security.version_id)
    approve(reviewer, run(lambda s: s.design.current_version_id(project.id)))
    move8(reviewer, "task", "draft_design", "completed")
    # The backlog planned from design v2, approved by the PM.
    ask_agent("developer", "plan_backlog", backlog_json())
    approve(pm, run(lambda s: s.backlog.view(admin, project.id)).version_id)
    engine.dispose()
    return str(project.id)


change_project_id = change_control_project()

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(
        {
            "suffix": suffix,
            "password": password,
            "users": {k: v[0] for k, v in users.items()},
            "agent": AGENT_EMAIL,
            "docx": str(docx_path),
            "change_project": change_project_id,
        },
        handle,
    )
