"""Wires module services for one unit of work. Used by the API, the CLI, workers and tests."""

from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property

from sqlalchemy.orm import Session

from app.harness.registry import AgentDefinitionError, AgentRegistry, load_registry, task_refs
from app.infrastructure.clock import Clock
from app.infrastructure.settings import ROOT_DIR
from app.infrastructure.storage.base import ArtifactStore
from app.model_gateway.router import ModelConfig, load_model_config
from app.modules.artifacts.service import ArtifactsService
from app.modules.audit.service import AuditService
from app.modules.backlog.service import BACKLOG_TYPE, BacklogService
from app.modules.decisions.authority import ApprovalMatrix, load_approval_matrix
from app.modules.decisions.service import DecisionsService
from app.modules.design.service import DESIGN_TYPE, DesignService
from app.modules.design_reviews.checklist import SecurityChecklist, load_security_checklist
from app.modules.design_reviews.service import DesignReviewsService
from app.modules.executions.service import ExecutionsService
from app.modules.identity.authz import PermissionPolicy, load_permission_policy
from app.modules.identity.service import IdentityService
from app.modules.oversight.rules import IncidentRules, load_incident_rules
from app.modules.oversight.service import OversightService
from app.modules.projects.service import ProjectsService
from app.modules.reporting.catalog import ReportCatalog, load_report_catalog
from app.modules.reporting.service import ReportingService
from app.modules.requirements.service import RequirementsService
from app.modules.workflow.definitions import WorkflowCatalog, WorkflowDefinitionError, load_catalog
from app.modules.workflow.service import WorkflowService

CONFIG_DIR = ROOT_DIR / "config"
EXIT_CHECKS = frozenset({"design_coverage", "design_reviews", "backlog_current"})  # named phase exit checks wired in Services.workflow


@dataclass(frozen=True)
class Policies:
    """Declarative configuration loaded once at startup; invalid config fails startup."""

    catalog: WorkflowCatalog
    permissions: PermissionPolicy
    approvals: ApprovalMatrix
    agents: AgentRegistry
    models: ModelConfig
    incidents: IncidentRules
    reports: ReportCatalog
    security_checklist: SecurityChecklist
    session_ttl: timedelta = timedelta(hours=12)
    min_password_length: int = 12


def _check_cross_references(catalog: WorkflowCatalog, approvals: ApprovalMatrix, agents: AgentRegistry) -> None:
    for number, phase in catalog.phases.items():
        unknown_checks = set(phase.exit.checks) - EXIT_CHECKS
        if unknown_checks:
            raise WorkflowDefinitionError(f"phase {number} names unknown exit checks {sorted(unknown_checks)}")
        required = set(phase.exit.required_approvals).union(*(task.required_approvals for task in phase.tasks))
        unknown = required - set(approvals.artifact_types)
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
        workflow_task = next((t for t in catalog.phase(task.spec.phase).tasks if t.key == task.spec.workflow_task), None)
        if task.spec.workflow_task is not None and (workflow_task is None or workflow_task.agent != agent_key):
            raise AgentDefinitionError(f"{name} names workflow task '{task.spec.workflow_task}', which phase {task.spec.phase} does not assign to {agent_key}")
        unknown = set(task.spec.context_artifact_types + task.spec.context_reviews_of + task.spec.context_findings_of) - set(approvals.artifact_types)
        if unknown:
            raise AgentDefinitionError(f"{name} reads unknown context artifact types {sorted(unknown)}")
        unknown = set(task_refs(agent_key, task.spec.context_decisions_from)) - set(agents.tasks)
        if unknown:
            raise AgentDefinitionError(f"{name} takes decisions from unknown tasks {sorted(unknown)}")
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
        incidents=load_incident_rules(CONFIG_DIR / "policies" / "incident_rules.yaml"),
        reports=load_report_catalog(CONFIG_DIR / "policies" / "report_visibility.yaml"),
        security_checklist=load_security_checklist(CONFIG_DIR / "policies" / "security_checklist.yaml"),
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
        return ArtifactsService(
            self.session,
            self.clock,
            self.audit,
            self.identity,
            self.store,
            types,
            baselines=self.policies.approvals.baselines,
            # Resolved lazily: the decisions service is built on top of this one.
            approval_status=lambda version_id: self.decisions.approval_statuses([version_id])[version_id],
        )

    @cached_property
    def decisions(self) -> DecisionsService:
        return DecisionsService(
            self.session,
            self.clock,
            self.audit,
            self.identity,
            self.artifacts,
            self.policies.approvals,
            # Resolved lazily: the design and design review services are built on top of this one.
            approval_checks={
                DESIGN_TYPE: lambda version_id: self.design.approval_problems(version_id) + self.design_reviews.design_problems(version_id),
                "security_review": lambda version_id: self.design_reviews.security_approval_problems(version_id),
                BACKLOG_TYPE: lambda version_id: self.backlog.approval_problems(version_id),
            },
        )

    @cached_property
    def workflow(self) -> WorkflowService:
        return WorkflowService(
            self.session,
            self.clock,
            self.policies.catalog,
            self.audit,
            self.identity,
            self.decisions,
            # Resolved lazily: the executions and design services are built on top of this one.
            open_questions=lambda task_id: self.executions.open_questions(task_id),
            exit_checks={
                "design_coverage": lambda project_id: self.design.coverage_failures(project_id),
                "design_reviews": lambda project_id: self.design_reviews.gate_failures(project_id),
                "backlog_current": lambda project_id: self.backlog.gate_failures(project_id),
            },
        )

    @cached_property
    def projects(self) -> ProjectsService:
        return ProjectsService(self.session, self.clock, self.audit, self.identity, self.workflow)

    @cached_property
    def executions(self) -> ExecutionsService:
        return ExecutionsService(
            self.session,
            self.clock,
            self.audit,
            self.identity,
            self.artifacts,
            self.workflow,
            self.decisions,
            self.oversight,
            self.policies.agents,
        )

    @cached_property
    def oversight(self) -> OversightService:
        return OversightService(self.session, self.clock, self.audit, self.identity, self.policies.incidents)

    @cached_property
    def reporting(self) -> ReportingService:
        return ReportingService(
            self.session,
            self.clock,
            self.audit,
            self.identity,
            self.store,
            self.policies.reports,
            projects=self.projects,
            workflow=self.workflow,
            artifacts=self.artifacts,
            decisions=self.decisions,
            requirements=self.requirements,
            executions=self.executions,
            oversight=self.oversight,
            design=self.design,
            design_reviews=self.design_reviews,
            backlog=self.backlog,
        )

    @cached_property
    def requirements(self) -> RequirementsService:
        return RequirementsService(
            self.session,
            self.clock,
            self.audit,
            self.identity,
            self.artifacts,
            self.decisions,
            self.projects,
            {baseline: self.policies.approvals.change_requests.roles_for(baseline) for baseline in self.policies.approvals.baselines},
            design_lookup=lambda project_id: self.design.coverage_by_requirement(project_id),
            backlog_lookup=lambda project_id: self.backlog.requirement_lookup(project_id),
            design_change_target=lambda project_id: self.design.change_target(project_id),
            design_backlog_lookup=lambda project_id: self.backlog.design_item_lookup(project_id),
        )

    @cached_property
    def design(self) -> DesignService:
        return DesignService(
            self.session, self.clock, self.audit, self.identity, self.artifacts, self.decisions, self.projects, self.requirements, self.workflow
        )

    @cached_property
    def design_reviews(self) -> DesignReviewsService:
        return DesignReviewsService(
            self.session,
            self.clock,
            self.audit,
            self.identity,
            self.artifacts,
            self.decisions,
            self.projects,
            self.requirements,
            self.design,
            self.policies.security_checklist,
        )

    @cached_property
    def backlog(self) -> BacklogService:
        return BacklogService(
            self.session, self.clock, self.audit, self.identity, self.artifacts, self.decisions, self.projects, self.requirements, self.design
        )
