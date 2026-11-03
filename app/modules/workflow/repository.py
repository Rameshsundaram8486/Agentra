"""Queries on workflow tables. Used only by the workflow service."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.workflow.models import PhaseRun, StateTransition, Task


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def get_phase_run(session: Session, phase_run_id: uuid.UUID) -> PhaseRun | None:
    return session.get(PhaseRun, phase_run_id)


def get_phase_run_for(session: Session, project_id: uuid.UUID, phase: int) -> PhaseRun | None:
    return session.scalar(select(PhaseRun).where(PhaseRun.project_id == project_id, PhaseRun.phase == phase))


def get_task(session: Session, task_id: uuid.UUID) -> Task | None:
    return session.get(Task, task_id)


def phase_runs_for_project(session: Session, project_id: uuid.UUID) -> list[PhaseRun]:
    return list(session.scalars(select(PhaseRun).where(PhaseRun.project_id == project_id).order_by(PhaseRun.phase)))


def tasks_for_project(session: Session, project_id: uuid.UUID) -> list[Task]:
    return list(session.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.position)))


def tasks_for_phase_run(session: Session, phase_run_id: uuid.UUID) -> list[Task]:
    return list(session.scalars(select(Task).where(Task.phase_run_id == phase_run_id).order_by(Task.position)))


def compare_and_set_state(
    session: Session,
    model: type[PhaseRun] | type[Task],
    entity_id: uuid.UUID,
    expected_version: int,
    new_state: str,
    now: datetime,
) -> bool:
    """Optimistic lock: changes the row only if nobody else changed it since it was read."""
    result = session.execute(
        update(model)
        .where(model.id == entity_id, model.version == expected_version)
        .values(state=new_state, version=model.version + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        return False
    session.expire_all()
    return True


def transitions_for(session: Session, entity_type: str, entity_id: uuid.UUID) -> list[StateTransition]:
    return list(
        session.scalars(
            select(StateTransition)
            .where(StateTransition.entity_type == entity_type, StateTransition.entity_id == entity_id)
            .order_by(StateTransition.occurred_at, StateTransition.seq)
        )
    )
