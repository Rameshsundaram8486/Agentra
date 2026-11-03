"""Wires module services for one unit of work. Used by the API, the CLI, workers and tests."""

from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property

from sqlalchemy.orm import Session

from app.harness.registry import AgentDefinitionError, AgentRegistry, load_registry
from app.infrastructure.clock import Clock
from app.infrastructure.settings import ROOT_DIR
from app.infrastructure.storage.base import ArtifactStore
from app.model_gateway.router import ModelConfig, load_model_config
from app.modules.artifacts.service import ArtifactsService
from app.modules.audit.service import AuditService
from app.modules.decisions.authority import ApprovalMatrix, load_approval_matrix
from app.modules.decisions.service import DecisionsService
from app.modules.executions.service import ExecutionsService
from app.modules.identity.authz import PermissionPolicy, load_permission_policy
from app.modules.identity.service import IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.workflow.definitions import WorkflowCatalog, WorkflowDefinitionError, load_catalog
from app.modules.workflow.service import WorkflowService

CONFIG_DIR = ROOT_DIR / "config"


@dataclass(frozen=True)
class Policies:
    """Declarative configuration loaded once at startup; invalid config fails startup."""

    catalog: WorkflowCatalog
    permissions: PermissionPolicy
    approvals: ApprovalMatrix
    agents: AgentRegistry
    models: ModelConfig
    session_ttl: timedelta = timedelta(hours=12)
    min_password_length: int = 12


def _check_cross_references(catalog: WorkflowCatalog, approvals: ApprovalMatrix, agents: AgentRegistry) -> None:
    for number, phase in catalog.phases.items():
        unknown = set(phase.exit.required_approvals) - set(approvals.artifact_types)
        if unknown:
            raise WorkflowDefinitionError(
                f"phase {number} requires approval of unknown artifact types {sorted(unknown)} (see approval_matrix.yaml)"
            )
    for (agent_key, task_key), task in agents.tasks.items():
        name = f"{agent_key}.{task_key}"
        unknown = set(task.spec.input_artifact_types) - set(approvals.artifact_types)
        if unknown:
            raise AgentDefinitionError(f"{name} reads unknown artifact types {sorted(unknown)} (see approval_matrix.yaml)")
        if task.spec.phase not in catalog.phases:
            raise AgentDefinitionError(f"{name} runs in phase {task.spec.phase}, which has no workflow definition")
        lifecycle = catalog.lifecycle(catalog.phase(task.spec.phase).lifecycle)
        unknown = set(task.spec.phase_states) - set(lifecycle.states)
        if unknown:
            raise AgentDefinitionError(f"{name} names unknown phase states {sorted(unknown)}")


def load_policies(session_ttl: timedelta = timedelta(hours=12), min_password_length: int = 12) -> Policies:
    catalog = load_catalog(CONFIG_DIR / "workflows")
    approvals = load_approval_matrix(CONFIG_DIR / "policies" / "approval_matrix.yaml")
    agents = load_registry(CONFIG_DIR / "agents")
    _check_cross_references(catalog, approvals, agents)
    return Policies(
        catalog=catalog,
        permissions=load_permission_policy(CONFIG_DIR / "policies" / "permissions.yaml"),
        approvals=approvals,
        agents=agents,
        models=load_model_config(CONFIG_DIR / "models.yaml"),
        session_ttl=session_ttl,
        min_password_length=min_password_length,
    )


class Services:
    def __init__(self, session: Session, clock: Clock, policies: Policies, store: ArtifactStore) -> None:
        self.session = session
        self.clock = clock
        self.policies = policies
        self.store = store

    @cached_property
    def audit(self) -> AuditService:
        return AuditService(self.session, self.clock)

    @cached_property
    def identity(self) -> IdentityService:
        return IdentityService(
            self.session,
            self.clock,
            self.audit,
            self.policies.permissions,
            self.policies.session_ttl,
            self.policies.min_password_length,
        )

    @cached_property
    def artifacts(self) -> ArtifactsService:
        types = {name: policy.title for name, policy in self.policies.approvals.artifact_types.items()}
        return ArtifactsService(self.session, self.clock, self.audit, self.identity, self.store, types)

    @cached_property
    def decisions(self) -> DecisionsService:
        return DecisionsService(
            self.session, self.clock, self.audit, self.identity, self.artifacts, self.policies.approvals
        )

    @cached_property
    def workflow(self) -> WorkflowService:
        return WorkflowService(
            self.session, self.clock, self.policies.catalog, self.audit, self.identity, self.decisions
        )

    @cached_property
    def projects(self) -> ProjectsService:
        return ProjectsService(self.session, self.clock, self.audit, self.identity, self.workflow)

    @cached_property
    def executions(self) -> ExecutionsService:
        return ExecutionsService(
            self.session, self.clock, self.audit, self.identity, self.artifacts, self.workflow, self.policies.agents
        )
