"""Phase 9: work items and their change sets, sandbox runs and merges. Change sets are approved through the
approvals endpoint like any document version; asking the Developer agent goes through agent runs (with a subject)."""

import uuid

from fastapi import APIRouter, status

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.implementation.schemas import ChangeSetDetail, ImplementationView, SandboxRunView

router = APIRouter(prefix="/api", tags=["implementation"])


@router.get("/projects/{project_id}/implementation")
def implementation(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> ImplementationView:
    """Each work item of the approved backlog with its Phase 9 task, whether it can start, and its latest change set."""
    return services.implementation.view(actor, project_id)


@router.get("/change-sets/{version_id}")
def change_set(version_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> ChangeSetDetail:
    """One change set version with its diff against the main it was based on."""
    return services.implementation.change_set(actor, version_id)


@router.post("/change-sets/{version_id}/sandbox-runs", status_code=status.HTTP_202_ACCEPTED)
def run_checks_again(version_id: uuid.UUID, actor: ActorDep, services: ServicesDep, uow: UnitOfWorkDep) -> SandboxRunView:
    """Builds and tests the latest change set version of a work item again in a sandbox VM."""
    view = services.implementation.request_sandbox_run(actor, version_id)
    uow.commit()
    return view
