"""Business rules for projects; the only entry point for other modules."""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.audit.service import AuditService
from app.modules.errors import ConflictError, NotFoundError
from app.modules.identity.service import Actor, IdentityService
from app.modules.projects import repository
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectView
from app.modules.workflow.service import WorkflowService

__all__ = ["ProjectCreate", "ProjectView", "ProjectsService"]


class ProjectsService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        workflow: WorkflowService,
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._workflow = workflow

    def create_project(self, actor: Actor, data: ProjectCreate) -> ProjectView:
        """Creates the project, makes the creator its owner and opens a phase run for each workflow phase."""
        self._identity.require_platform(actor, "project.create")
        data = ProjectCreate.model_validate(data)
        if repository.code_exists(self._session, data.code):
            raise ConflictError(f"Project code '{data.code}' is already used")
        project = Project(**data.model_dump(), created_by=actor.id, created_at=self._clock.now())
        repository.add(self._session, project)
        self._audit.record(
            actor_id=actor.id,
            action="project.create",
            entity_type="project",
            entity_id=project.id,
            project_id=project.id,
            after=data.model_dump(),
        )
        self._identity.add_initial_owner(actor, project.id)
        self._workflow.open_project(actor, project.id)
        return ProjectView.model_validate(project, from_attributes=True)

    def list_projects(self, actor: Actor) -> list[ProjectView]:
        visible = self._identity.visible_project_ids(actor)
        return [
            ProjectView.model_validate(project, from_attributes=True)
            for project in repository.list_projects(self._session, visible)
        ]

    def get_project(self, actor: Actor, project_id: uuid.UUID) -> ProjectView:
        self._identity.require_project(actor, project_id, "project.view")
        project = repository.get(self._session, project_id)
        if project is None:
            raise NotFoundError("Project not found")
        return ProjectView.model_validate(project, from_attributes=True)
