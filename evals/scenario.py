"""Builds a throwaway project in the test database for one case and runs the task under test through the real
path: prompt, structured output, guardrails, records. Prerequisite steps (a closed clarify task, an approved
baseline and an approved change request) are scripted, so a live run pays only for the task being evaluated."""

import json
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.composition import Policies, Services
from app.harness.runner import AgentRunner
from app.infrastructure.clock import SystemClock
from app.infrastructure.job_queue import ClaimedJob
from app.infrastructure.storage.base import ArtifactStore
from app.infrastructure.unit_of_work import UnitOfWork
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.providers.base import ModelRequest, ModelResponse, Provider
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.artifacts.service import ArtifactCreate
from app.modules.decisions.service import ApprovalCreate
from app.modules.executions.schemas import AgentRunCreate
from app.modules.identity.service import SYSTEM_ACTOR, Actor
from app.modules.projects.service import ProjectCreate
from app.modules.requirements.service import ChangeRequestCreate, ChangeRequestDecisionCreate
from app.modules.workflow.service import TransitionRequest
from evals.cases import Case


class RecordingProvider:
    """Passes calls to a real provider and keeps each response, so a live run can be replayed for free."""

    def __init__(self, inner: Provider) -> None:
        self._inner = inner
        self.name = inner.name
        self.responses: list[ModelResponse] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        response = self._inner.complete(request)
        self.responses.append(response)
        return response


@dataclass
class Outcome:
    case_id: str
    run: Any  # AgentRunDetail of the task under test
    decisions: list[Any] = field(default_factory=list)  # DecisionViews the run raised, in order
    requirements: Any = None  # RequirementsView after the run
    baseline_item_ids: list[str] = field(default_factory=list)  # apply cases: IDs before the change
    response_text: str = ""


class Scenario:
    def __init__(self, session_factory: Any, policies: Policies, store: ArtifactStore) -> None:
        self._factory = session_factory
        self._policies = policies
        self._store = store
        self._clock = SystemClock()

    def _run(self, fn: Any) -> Any:
        with UnitOfWork(self._factory) as uow:
            result = fn(Services(uow.session, self._clock, self._policies, self._store))
            uow.commit()
            return result

    def _runner(self, provider: Provider) -> AgentRunner:
        return AgentRunner(self._factory, self._clock, self._policies, self._store, ModelGateway(self._policies.models, provider))

    def _person(self, label: str, admin: bool = False) -> tuple[Actor, str]:
        email = f"eval_{label}_{uuid.uuid4().hex[:8]}@evals.test"
        self._run(lambda s: s.identity.create_user(SYSTEM_ACTOR, email=email, display_name=f"Eval {label}", password=secrets.token_urlsafe(18), is_platform_admin=admin))
        return self._run(lambda s: s.identity.actor_by_email(email)), email

    def _agent(self) -> Actor:
        def get(s: Services) -> Actor:
            if s.identity.agent_by_key("business_analyst") is None:
                s.identity.create_user(SYSTEM_ACTOR, email="business_analyst@agents.agentra.local", display_name="Business Analyst Agent", kind="agent", agent_key="business_analyst")
            return s.identity.agent_by_key("business_analyst")  # type: ignore[return-value]

        return self._run(get)

    def _move(self, actor: Actor, project_id: uuid.UUID, task_key: str | None, state: str) -> None:
        def step(s: Services) -> None:
            phase = next(p for p in s.workflow.list_phase_runs(actor, project_id) if p.phase == 7)
            if task_key is None:
                s.workflow.transition_phase_run(actor, phase.id, TransitionRequest(to_state=state, reason="Eval setup", expected_version=phase.version))
            else:
                task = next(t for t in phase.tasks if t.key == task_key)
                s.workflow.transition_task(actor, task.id, TransitionRequest(to_state=state, reason="Eval setup", expected_version=task.version))

        self._run(step)

    def _process(self, provider: Provider, run_id: uuid.UUID) -> None:
        self._runner(provider).handle(ClaimedJob(uuid.uuid4(), "agent_run", {"agent_run_id": str(run_id)}, "eval", 1))

    def run(self, case: Case, provider: Provider) -> Outcome:
        owner, _ = self._person("owner", admin=True)
        (pm, pm_email), (reviewer, reviewer_email), (customer, customer_email) = (self._person(k) for k in ("pm", "reviewer", "customer"))
        self._agent()
        code = f"EV-{uuid.uuid4().hex[:6].upper()}"
        project = self._run(lambda s: s.projects.create_project(owner, ProjectCreate(code=code, name=f"Eval {case.id}", customer_name="Example Co (synthetic)")))
        members = ((pm_email, "project_manager"), (reviewer_email, "reviewer"), (customer_email, "customer_approver"), ("business_analyst@agents.agentra.local", "agent"))
        for email, role in members:
            self._run(lambda s, e=email, r=role: s.identity.add_member(owner, project.id, e, r))
        self._move(owner, project.id, None, "ready")
        self._move(pm, project.id, None, "in_progress")
        brief = self._run(lambda s: s.artifacts.create_artifact(pm, project.id, ArtifactCreate(artifact_type="project_brief", title="Brief", content=case.brief))).current_version
        for document in case.documents:
            self._run(lambda s, d=document: s.artifacts.create_artifact(pm, project.id, ArtifactCreate(artifact_type="source_document", title=d.title, content=d.content)))

        def ask(task_key: str, version_id: uuid.UUID, change_request_id: uuid.UUID | None = None) -> uuid.UUID:
            data = AgentRunCreate(agent_key="business_analyst", task_key=task_key, artifact_version_id=version_id, change_request_id=change_request_id)
            return self._run(lambda s: s.executions.request_run(pm, project.id, data)).run.id

        baseline_ids: list[str] = []
        if case.task in ("draft_requirements", "apply_change_request"):
            for actor, state in ((owner, "ready"), (pm, "in_progress"), (pm, "waiting_for_input"), (pm, "completed")):
                self._move(actor, project.id, "clarify_brief", state)
        if case.task == "apply_change_request":
            scripted = {"summary": "Baseline for the eval.", "items": case.baseline_items, "process_flow_mermaid": "", "review_responses": []}
            draft_id = ask("draft_requirements", brief.id)
            self._process(FakeProvider([fake_response(json.dumps(scripted))]), draft_id)
            view = self._run(lambda s: s.requirements.view(owner, project.id))
            if view is None:
                draft = self._run(lambda s: s.executions.get_run(owner, draft_id))
                problems = "; ".join(f"{f.path}: {f.message}" for f in draft.findings if f.severity == "block") or draft.error_message
                raise RuntimeError(f"{case.id}: the scripted baseline was not accepted: {problems}")
            baseline_ids = [item.item_id for item in view.items]
            self._run(lambda s: s.decisions.record_approval(reviewer, view.version_id, ApprovalCreate(
                decision="approved", content_sha256=s.artifacts.version_record(view.version_id).content_sha256)))
            spec = case.change_request
            assert spec is not None
            request = self._run(lambda s: s.requirements.raise_change_request(pm, project.id, ChangeRequestCreate(**spec.model_dump())))
            for approver in (owner, customer):
                self._run(lambda s, a=approver: s.requirements.decide_change_request(a, request.id, ChangeRequestDecisionCreate(decision="approved")))
            run_id = ask("apply_change_request", view.version_id, request.id)
        else:
            run_id = ask(case.task, brief.id)

        self._process(provider, run_id)
        detail = self._run(lambda s: s.executions.get_run(owner, run_id))
        decisions = self._run(lambda s: [s.decisions.get_decision(owner, d) for d in detail.decision_ids])
        requirements = self._run(lambda s: s.requirements.view(owner, project.id))
        responses = getattr(provider, "responses", [])
        return Outcome(case.id, detail, decisions, requirements, baseline_ids, responses[-1].text if responses else "")
