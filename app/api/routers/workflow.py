"""Phase and task state: read the workflow, request transitions, read transition history."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.workflow.service import PhaseRunView, StateTransitionView, TaskView, TransitionRequest

router = APIRouter(prefix="/api", tags=["workflow"])


@router.get("/projects/{project_id}/phases")
def list_phases(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[PhaseRunView]:
    return services.workflow.list_phase_runs(actor, project_id)


@router.post("/phase-runs/{phase_run_id}/transitions")
def transition_phase(
    phase_run_id: uuid.UUID, body: TransitionRequest, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> PhaseRunView:
    view = services.workflow.transition_phase_run(actor, phase_run_id, body)
    uow.commit()
    return view


@router.post("/tasks/{task_id}/transitions")
def transition_task(
    task_id: uuid.UUID, body: TransitionRequest, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> TaskView:
    view = services.workflow.transition_task(actor, task_id, body)
    uow.commit()
    return view


@router.get("/phase-runs/{phase_run_id}/history")
def phase_history(phase_run_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[StateTransitionView]:
    return services.workflow.history(actor, "phase_run", phase_run_id)
