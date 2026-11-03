"""Agent runs: ask an agent to work on a document version, and follow what it did (model, cost, findings)."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.executions.service import AgentRunCreate, AgentRunDetail, AgentRunView
from app.modules.executions.schemas import RunRequestResult

router = APIRouter(prefix="/api", tags=["agent runs"])


@router.post("/projects/{project_id}/agent-runs", status_code=status.HTTP_202_ACCEPTED)
def request_run(
    project_id: uuid.UUID,
    body: AgentRunCreate,
    response: Response,
    actor: ActorDep,
    uow: UnitOfWorkDep,
    services: ServicesDep,
) -> RunRequestResult:
    """202 with a new queued run, or 200 with the existing run for the same document version."""
    result = services.executions.request_run(actor, project_id, body)
    uow.commit()
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/projects/{project_id}/agent-runs")
def list_runs(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[AgentRunView]:
    return services.executions.list_runs(actor, project_id)


@router.get("/agent-runs/{run_id}")
def get_run(run_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> AgentRunDetail:
    return services.executions.get_run(actor, run_id)
