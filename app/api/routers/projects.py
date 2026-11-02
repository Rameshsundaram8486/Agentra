"""Project workspace: projects and their members. Phase 6 kickoff features (milestones, RACI, risks) come later."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.identity.service import MemberView, ProjectRole
from app.modules.projects.service import ProjectCreate, ProjectView

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectDetail(BaseModel):
    project: ProjectView
    my_roles: list[str]
    my_permissions: list[str]


class AddMemberRequest(BaseModel):
    email: str = Field(max_length=320)
    role: ProjectRole


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep) -> ProjectView:
    project = services.projects.create_project(actor, body)
    uow.commit()
    return project


@router.get("")
def list_projects(actor: ActorDep, services: ServicesDep) -> list[ProjectView]:
    return services.projects.list_projects(actor)


@router.get("/{project_id}")
def get_project(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> ProjectDetail:
    project = services.projects.get_project(actor, project_id)
    return ProjectDetail(
        project=project,
        my_roles=sorted(services.identity.roles_for(actor, project_id)),
        my_permissions=sorted(services.identity.permissions_for(actor, project_id)),
    )


@router.get("/{project_id}/members")
def list_members(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[MemberView]:
    return services.identity.list_members(actor, project_id)


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: uuid.UUID, body: AddMemberRequest, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> MemberView:
    member = services.identity.add_member(actor, project_id, body.email, body.role)
    uow.commit()
    return member
