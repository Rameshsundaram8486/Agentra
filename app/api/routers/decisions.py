"""Decision inbox: requests with recommendations and options, and the human outcomes recorded against them."""

import uuid

from fastapi import APIRouter, status

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.decisions.service import DecisionOutcomeCreate, DecisionRequestCreate, DecisionView

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/projects/{project_id}/decisions")
def list_decisions(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[DecisionView]:
    return services.decisions.list_decisions(actor, project_id)


@router.post("/projects/{project_id}/decisions", status_code=status.HTTP_201_CREATED)
def raise_decision(
    project_id: uuid.UUID, body: DecisionRequestCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> DecisionView:
    decision = services.decisions.raise_decision(actor, project_id, body)
    uow.commit()
    return decision


@router.get("/decisions/{decision_id}")
def get_decision(decision_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> DecisionView:
    return services.decisions.get_decision(actor, decision_id)


@router.post("/decisions/{decision_id}/outcomes")
def record_outcome(
    decision_id: uuid.UUID, body: DecisionOutcomeCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> DecisionView:
    decision = services.decisions.record_outcome(actor, decision_id, body)
    uow.commit()
    return decision
