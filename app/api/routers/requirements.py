"""Phase 7 requirements: the latest drafted set, the traceability matrix and change requests."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.requirements.service import (
    ChangeRequestCreate,
    ChangeRequestDecisionCreate,
    ChangeRequestView,
    RequirementsView,
    TraceabilityView,
)

router = APIRouter(prefix="/api", tags=["requirements"])


@router.get("/projects/{project_id}/requirements")
def current_requirements(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> RequirementsView | None:
    """null until the Business Analyst agent has drafted requirements for the project."""
    return services.requirements.view(actor, project_id)


@router.get("/projects/{project_id}/requirements/traceability")
def traceability(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> TraceabilityView | None:
    return services.requirements.traceability(actor, project_id)


@router.get("/projects/{project_id}/requirements/traceability.csv", response_class=Response)
def traceability_csv(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> Response:
    content = services.requirements.traceability_csv(actor, project_id)
    if content is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="traceability.csv"'},
    )


@router.get("/projects/{project_id}/change-requests")
def list_change_requests(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[ChangeRequestView]:
    return services.requirements.list_change_requests(actor, project_id)


@router.post("/projects/{project_id}/change-requests", status_code=status.HTTP_201_CREATED)
def raise_change_request(
    project_id: uuid.UUID, body: ChangeRequestCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> ChangeRequestView:
    request = services.requirements.raise_change_request(actor, project_id, body)
    uow.commit()
    return request


@router.get("/change-requests/{change_request_id}")
def get_change_request(change_request_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> ChangeRequestView:
    return services.requirements.get_change_request(actor, change_request_id)


@router.post("/change-requests/{change_request_id}/decisions")
def decide_change_request(
    change_request_id: uuid.UUID, body: ChangeRequestDecisionCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> ChangeRequestView:
    """Approve or reject in the first required role you hold that is still undecided."""
    request = services.requirements.decide_change_request(actor, change_request_id, body)
    uow.commit()
    return request
