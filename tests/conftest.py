"""Shared pytest fixtures: test PostgreSQL database, settings, clock, policies and data factories.

The test database is rebuilt from the migrations once per test run. Tests create their own uniquely named
data, so they never depend on each other. Agent tests use the scripted FakeProvider; no test calls a real
model unless AGENTRA_LIVE_TESTS=1 is set (tests/live).
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers every table)
from app.composition import Policies, Services, load_policies
from app.harness.runner import AgentRunner
from app.infrastructure.clock import FixedClock
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.settings import ENV_FILE, Settings
from app.infrastructure.unit_of_work import UnitOfWork
from app.infrastructure.storage.local import LocalArtifactStore
from app.main import create_app
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.providers.fake import FakeProvider
from app.modules.artifacts.service import ArtifactCreate
from app.model_gateway.providers.fake import fake_response
from app.modules.decisions.service import ApprovalCreate, DecisionOutcomeCreate
from app.modules.errors import InvalidTransitionError
from app.modules.identity.service import SYSTEM_ACTOR, Actor
from app.modules.projects.service import ProjectCreate, ProjectView
from app.modules.workflow.service import TransitionRequest
from tests.agent_support import BRIEF, DISCOVERY_NOTES, ask, ba_json, draft_items, draft_json, move_task, phase_task, process
from tests.support import DEFAULT_PASSWORD, Team, TestUser, alembic_config


class _TestEnvironment(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_ignore_empty=True, extra="ignore")

    test_database_url: SecretStr | None = None


@pytest.fixture(scope="session")
def test_database_url() -> str:
    configured = _TestEnvironment().test_database_url
    if configured is None:
        pytest.fail("TEST_DATABASE_URL is not set; see docs/development-guide.md")
    url = configured.get_secret_value()
    # Guard: tests drop and recreate schema objects, so never point them at a real database.
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in '_test'")
    return url


@pytest.fixture(scope="session")
def migrated_database(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def test_settings(test_database_url: str, migrated_database: None) -> Settings:
    return Settings(database_url=test_database_url, agentra_env="test")


@pytest.fixture(scope="session")
def engine(test_database_url: str, migrated_database: None) -> Iterator[Engine]:
    engine = create_db_engine(test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def policies() -> Policies:
    return load_policies()


@pytest.fixture(scope="session")
def store(tmp_path_factory: pytest.TempPathFactory) -> LocalArtifactStore:
    return LocalArtifactStore(tmp_path_factory.mktemp("artifact-store"))


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime.now(UTC).replace(microsecond=0))


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture
def services_for(clock: FixedClock, policies: Policies, store: LocalArtifactStore) -> Callable[..., Services]:
    """services_for(session) wires services the same way the API does."""

    def _services(session: Session, *, policies: Policies = policies) -> Services:
        return Services(session, clock, policies, store)

    return _services


@pytest.fixture
def run(session_factory: sessionmaker[Session], services_for: Callable[..., Services], policies: Policies) -> Callable[..., Any]:
    """Runs fn(services) in one committed unit of work, like a single API request."""

    def _run(fn: Callable[[Services], Any], *, policies: Policies = policies) -> Any:
        with UnitOfWork(session_factory) as uow:
            result = fn(services_for(uow.session, policies=policies))
            uow.commit()
            return result

    return _run


@pytest.fixture
def make_user(run: Callable[..., Any]) -> Callable[..., TestUser]:
    def _make(kind: str = "human", *, admin: bool = False, name: str | None = None) -> TestUser:
        suffix = uuid.uuid4().hex[:10]
        if kind == "agent":
            email = f"agent_{suffix}@agents.agentra.local"
            view = run(
                lambda s: s.identity.create_user(
                    SYSTEM_ACTOR, email=email, display_name=name or f"Agent {suffix}", kind="agent", agent_key=f"agent_{suffix}"
                )
            )
            password = None
        else:
            email = f"user_{suffix}@example.test"
            view = run(
                lambda s: s.identity.create_user(
                    SYSTEM_ACTOR, email=email, display_name=name or f"User {suffix}", password=DEFAULT_PASSWORD, is_platform_admin=admin
                )
            )
            password = DEFAULT_PASSWORD
        actor = Actor(id=view.id, kind=view.kind, display_name=view.display_name, is_platform_admin=view.is_platform_admin)
        return TestUser(actor=actor, email=email, password=password)

    return _make


@pytest.fixture
def make_project(run: Callable[..., Any], make_user: Callable[..., TestUser]) -> Callable[..., tuple[ProjectView, TestUser]]:
    """Creates a project owned by a new (or given) platform admin."""

    def _make(owner: TestUser | None = None, *, policies: Policies | None = None) -> tuple[ProjectView, TestUser]:
        owner = owner or make_user(admin=True)
        data = ProjectCreate(code=f"P-{uuid.uuid4().hex[:8].upper()}", name="Synthetic project", customer_name="Example Co")
        kwargs = {"policies": policies} if policies else {}
        project = run(lambda s: s.projects.create_project(owner.actor, data), **kwargs)
        return project, owner

    return _make


@pytest.fixture
def add_member(run: Callable[..., Any]) -> Callable[[TestUser, uuid.UUID, TestUser, str], None]:
    def _add(owner: TestUser, project_id: uuid.UUID, user: TestUser, role: str) -> None:
        run(lambda s: s.identity.add_member(owner.actor, project_id, user.email, role))

    return _add


@pytest.fixture
def make_team(
    make_project: Callable[..., tuple[ProjectView, TestUser]],
    make_user: Callable[..., TestUser],
    add_member: Callable[[TestUser, uuid.UUID, TestUser, str], None],
) -> Callable[..., Team]:
    """A project with an owner (platform admin), a project manager, a reviewer and an agent."""

    def _make(*, policies: Policies | None = None) -> Team:
        project, owner = make_project(policies=policies)
        pm, reviewer, agent = make_user(name="PM"), make_user(name="Reviewer"), make_user("agent")
        add_member(owner, project.id, pm, "project_manager")
        add_member(owner, project.id, reviewer, "reviewer")
        add_member(owner, project.id, agent, "agent")
        return Team(project, owner, pm, reviewer, agent)

    return _make


@pytest.fixture
def team(make_team: Callable[..., Team]) -> Team:
    return make_team()


@pytest.fixture
def approve_phase_documents(run: Callable[..., Any]) -> Callable[..., list[Any]]:
    """Creates each artifact a phase needs (authored by the team's agent) and has the reviewer approve it."""

    def _approve(team: Team, phase: int, *, policies: Policies | None = None) -> list[Any]:
        kwargs = {"policies": policies} if policies else {}
        definition = run(lambda s: s.policies.catalog.phase(phase), **kwargs)
        approved = []
        for artifact_type in definition.exit.required_approvals:
            artifact = run(
                lambda s, t=artifact_type: s.artifacts.create_artifact(
                    team.agent.actor, team.project.id, ArtifactCreate(artifact_type=t, title=f"Phase {phase} {t}", content=f"# {t}\n")
                ),
                **kwargs,
            )
            version = artifact.current_version
            approved.append(
                run(
                    lambda s, v=version: s.decisions.record_approval(
                        team.reviewer.actor, v.id, ApprovalCreate(decision="approved", content_sha256=v.content_sha256)
                    ),
                    **kwargs,
                )
            )
        return approved

    return _approve


@pytest.fixture
def ba_agent(run: Callable[..., Any]) -> TestUser:
    """The Business Analyst agent account. There is one per database, as in a real installation."""
    email = "business_analyst@agents.agentra.local"

    def _get(s: Services) -> Actor:
        if s.identity.agent_by_key("business_analyst") is None:
            s.identity.create_user(
                SYSTEM_ACTOR, email=email, display_name="Business Analyst Agent", kind="agent", agent_key="business_analyst"
            )
        return s.identity.agent_by_key("business_analyst")  # type: ignore[return-value]

    return TestUser(actor=run(_get), email=email, password=None)


@pytest.fixture
def sa_agent(run: Callable[..., Any]) -> TestUser:
    """The Solution Architect agent account (one per database)."""
    email = "solution_architect@agents.agentra.local"

    def _get(s: Services) -> Actor:
        if s.identity.agent_by_key("solution_architect") is None:
            s.identity.create_user(
                SYSTEM_ACTOR, email=email, display_name="Solution Architect Agent", kind="agent", agent_key="solution_architect"
            )
        return s.identity.agent_by_key("solution_architect")  # type: ignore[return-value]

    return TestUser(actor=run(_get), email=email, password=None)


@pytest.fixture
def move_phase(run: Callable[..., Any]) -> Callable[..., None]:
    """move_phase(actor, project_id, phase, *states) applies each transition in turn."""

    def _move(actor: Actor, project_id: uuid.UUID, phase: int, *states: str) -> None:
        for state in states:
            def _step(s: Services, state: str = state) -> None:
                current = next(p for p in s.workflow.list_phase_runs(actor, project_id) if p.phase == phase)
                s.workflow.transition_phase_run(
                    actor, current.id, TransitionRequest(to_state=state, reason="Test step", expected_version=current.version)
                )

            run(_step)

    return _move


@pytest.fixture
def close_tasks(run: Callable[..., Any]) -> Callable[..., None]:
    """close_tasks(team, phase) cancels the phase's open tasks as the owner, for tests about phase gates."""

    def _close(team: Team, phase: int, *, policies: Policies | None = None) -> None:
        kwargs = {"policies": policies} if policies else {}

        def _step(s: Services) -> None:
            current = next(p for p in s.workflow.list_phase_runs(team.owner.actor, team.project.id) if p.phase == phase)
            for task in current.tasks:
                if task.state not in ("completed", "cancelled"):
                    s.workflow.transition_task(
                        team.owner.actor, task.id, TransitionRequest(to_state="cancelled", reason="Not part of this test", expected_version=task.version)
                    )

        run(_step, **kwargs)

    return _close


@pytest.fixture
def ba_team(team: Team, ba_agent: TestUser, add_member: Callable[..., None], move_phase: Callable[..., None]) -> Team:
    """A team whose project has the Business Analyst agent on it and Phase 7 in progress."""
    add_member(team.owner, team.project.id, ba_agent, "agent")
    move_phase(team.pm.actor, team.project.id, 7, "ready", "in_progress")
    return team


@pytest.fixture
def make_brief(run: Callable[..., Any]) -> Callable[..., Any]:
    """make_brief(team, content=BRIEF, artifact_type="project_brief") -> the version view, authored by the PM."""

    def _make(team: Team, content: str = BRIEF, artifact_type: str = "project_brief") -> Any:
        artifact = run(
            lambda s: s.artifacts.create_artifact(
                team.pm.actor,
                team.project.id,
                ArtifactCreate(artifact_type=artifact_type, title=f"Brief {uuid.uuid4().hex[:6]}", content=content),
            )
        )
        return artifact.current_version

    return _make


@pytest.fixture
def model() -> FakeProvider:
    """The scripted model every agent test uses; add responses with model.add(...)."""
    return FakeProvider()


@pytest.fixture
def runner_for(
    session_factory: sessionmaker[Session], clock: FixedClock, policies: Policies, store: LocalArtifactStore, model: FakeProvider
) -> Callable[..., AgentRunner]:
    """runner_for(policies=...) builds the agent runner on the fake model."""

    def _runner(policies: Policies = policies) -> AgentRunner:
        return AgentRunner(session_factory, clock, policies, store, ModelGateway(policies.models, model))

    return _runner


@pytest.fixture
def clarified(
    ba_team: Team, make_brief: Callable[..., Any], run: Callable[..., Any], runner_for: Callable[..., AgentRunner], model: FakeProvider
) -> tuple[Team, Any]:
    """The brief was clarified (stack decision answered, the other questions deferred, task closed), with
    synthetic discovery notes as a source document. Returns (team, brief version)."""
    team = ba_team
    brief = make_brief(team)
    run(lambda s: s.artifacts.create_artifact(
        team.pm.actor, team.project.id, ArtifactCreate(artifact_type="source_document", title="Discovery notes", content=DISCOVERY_NOTES)
    ))
    model.add(fake_response(ba_json()))
    process(runner_for(), ask(run, team, "clarify_brief", brief.id).run.id)
    assert phase_task(run, team, "clarify_brief").state == "waiting_for_input"

    stack = next(d for d in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)) if d.title == "Technology stack")
    run(lambda s: s.decisions.record_outcome(team.owner.actor, stack.id, DecisionOutcomeCreate(action="accept")))
    with pytest.raises(InvalidTransitionError, match="3 question\\(s\\) the agent raised are still open"):
        move_task(run, team.pm.actor, phase_task(run, team, "clarify_brief"), "completed")
    for decision in run(lambda s: s.decisions.list_decisions(team.owner.actor, team.project.id)):
        if decision.status == "open":
            run(lambda s, d=decision: s.decisions.record_outcome(team.owner.actor, d.id, DecisionOutcomeCreate(action="defer", comment="Later")))
    move_task(run, team.pm.actor, phase_task(run, team, "clarify_brief"), "completed")
    model.requests.clear()
    return team, brief


@pytest.fixture
def phase8(
    clarified: tuple[Team, Any], run: Callable[..., Any], runner_for: Callable[..., AgentRunner], model: FakeProvider,
    sa_agent: TestUser, add_member: Callable[..., None], move_phase: Callable[..., None],
) -> Team:
    """Requirements drafted and approved, Phase 7 completed, the Solution Architect on the team, Phase 8 in progress."""
    team, brief = clarified
    model.add(fake_response(draft_json([i for i in draft_items() if i["kind"] != "open_question"])))
    process(runner_for(), ask(run, team, "draft_requirements", brief.id).run.id)
    version_id = run(lambda s: s.requirements.view(team.owner.actor, team.project.id)).version_id
    run(lambda s: s.decisions.record_approval(team.reviewer.actor, version_id, ApprovalCreate(
        decision="approved", content_sha256=s.artifacts.version_record(version_id).content_sha256)))
    move_task(run, team.reviewer.actor, phase_task(run, team, "draft_requirements"), "completed")
    move_phase(team.pm.actor, team.project.id, 7, "waiting_for_review")
    move_phase(team.reviewer.actor, team.project.id, 7, "completed")
    add_member(team.owner, team.project.id, sa_agent, "agent")
    move_phase(team.owner.actor, team.project.id, 8, "ready")
    move_phase(team.pm.actor, team.project.id, 8, "in_progress")
    model.requests.clear()
    return team


@pytest.fixture
def client_for(
    test_settings: Settings, clock: FixedClock, policies: Policies, store: LocalArtifactStore
) -> Iterator[Callable[..., TestClient]]:
    """client_for(user) returns an API client signed in as that user; client_for() an anonymous one."""
    app = create_app(test_settings, clock=clock, policies=policies, store=store)
    clients: list[TestClient] = []

    def _client(user: TestUser | None = None) -> TestClient:
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        if user is not None:
            response = client.post("/api/auth/login", json={"email": user.email, "password": user.password})
            assert response.status_code == 200, response.text
        return client

    yield _client
    for client in clients:
        client.__exit__(None, None, None)
