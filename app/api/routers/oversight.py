"""Incidents: list and read them, resolve with a root-cause analysis, close once verified."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.oversight.service import IncidentClose, IncidentView, RcaCreate

router = APIRouter(prefix="/api", tags=["incidents"])


@router.get("/projects/{project_id}/incidents")
def list_incidents(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[IncidentView]:
    return services.oversight.list_incidents(actor, project_id)


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> IncidentView:
    return services.oversight.get_incident(actor, incident_id)


@router.post("/incidents/{incident_id}/resolution")
def resolve_incident(incident_id: uuid.UUID, body: RcaCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep) -> IncidentView:
    incident = services.oversight.resolve(actor, incident_id, body)
    uow.commit()
    return incident


@router.post("/incidents/{incident_id}/closure")
def close_incident(incident_id: uuid.UUID, body: IncidentClose, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep) -> IncidentView:
    incident = services.oversight.close(actor, incident_id, body)
    uow.commit()
    return incident
