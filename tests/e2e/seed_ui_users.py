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
from tests.agent_support import BRIEF, DISCOVERY_NOTES, ba_json, draft_items, draft_json, process
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
with contextlib.redirect_stderr(io.StringIO()):  # "already exists" is fine: the account is shared by every run
    main(["create-agent", "--key", "business_analyst", "--name", "Business Analyst Agent"])

docx_path = Path(sys.argv[1]).with_name("discovery-notes.docx")
docx_path.write_bytes(make_docx("Discovery notes", "Leave approvals happen weekly."))


def change_control_project() -> str:
    """Brief clarified; a failed draft (INC-001) then a good one, approved; CR-001 raised by the PM and still open."""
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
