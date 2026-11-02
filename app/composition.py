"""Wires module services for one unit of work. Used by the API, the CLI, workers and tests."""

from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.infrastructure.settings import ROOT_DIR
from app.modules.audit.service import AuditService
from app.modules.identity.authz import PermissionPolicy, load_permission_policy
from app.modules.identity.service import IdentityService
from app.modules.projects.service import ProjectsService
from app.modules.workflow.definitions import WorkflowCatalog, load_catalog
from app.modules.workflow.service import WorkflowService

CONFIG_DIR = ROOT_DIR / "config"


@dataclass(frozen=True)
class Policies:
    """Declarative configuration loaded once at startup; invalid config fails startup."""

    catalog: WorkflowCatalog
    permissions: PermissionPolicy
    session_ttl: timedelta = timedelta(hours=12)
    min_password_length: int = 12


def load_policies(session_ttl: timedelta = timedelta(hours=12), min_password_length: int = 12) -> Policies:
    return Policies(
        catalog=load_catalog(CONFIG_DIR / "workflows"),
        permissions=load_permission_policy(CONFIG_DIR / "policies" / "permissions.yaml"),
        session_ttl=session_ttl,
        min_password_length=min_password_length,
    )


class Services:
    def __init__(self, session: Session, clock: Clock, policies: Policies) -> None:
        self.session = session
        self.clock = clock
        self.policies = policies

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
    def workflow(self) -> WorkflowService:
        return WorkflowService(self.session, self.clock, self.policies.catalog, self.audit, self.identity)

    @cached_property
    def projects(self) -> ProjectsService:
        return ProjectsService(self.session, self.clock, self.audit, self.identity, self.workflow)
