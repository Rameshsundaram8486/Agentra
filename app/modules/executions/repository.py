"""Database access for agent runs and model calls (no business rules). Used only by the executions service."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select, text, update
from sqlalchemy.orm import Session

from app.modules.executions.models import AgentRun, ModelCall

# Arbitrary constant (the audit chain uses another): serialises budget checks so two calls cannot both fit
# under the cap when only one does.
_BUDGET_LOCK_KEY = 7_242_002


def add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def get_run(session: Session, run_id: uuid.UUID, *, for_update: bool = False) -> AgentRun | None:
    return session.get(AgentRun, run_id, with_for_update=for_update, populate_existing=for_update)


def runs_for_input(session: Session, agent_key: str, task_key: str, version_id: uuid.UUID) -> list[AgentRun]:
    return list(
        session.scalars(
            select(AgentRun)
            .where(
                AgentRun.agent_key == agent_key,
                AgentRun.task_key == task_key,
                AgentRun.input_artifact_version_id == version_id,
            )
            .order_by(AgentRun.created_at)
        )
    )


def succeeded_runs(session: Session, project_id: uuid.UUID, agent_key: str, task_keys: tuple[str, ...]) -> list[AgentRun]:
    if not task_keys:
        return []
    return list(
        session.scalars(
            select(AgentRun)
            .where(
                AgentRun.project_id == project_id,
                AgentRun.agent_key == agent_key,
                AgentRun.task_key.in_(task_keys),
                AgentRun.status == "succeeded",
            )
            .order_by(AgentRun.created_at)
        )
    )


def unlinked_runs(session: Session, project_id: uuid.UUID) -> list[AgentRun]:
    return list(
        session.scalars(
            select(AgentRun).where(AgentRun.project_id == project_id, AgentRun.task_id.is_(None)).order_by(AgentRun.created_at)
        )
    )


def runs_for_project(session: Session, project_id: uuid.UUID, limit: int = 50) -> list[AgentRun]:
    return list(
        session.scalars(
            select(AgentRun).where(AgentRun.project_id == project_id).order_by(AgentRun.created_at.desc()).limit(limit)
        )
    )


def calls_for_runs(session: Session, run_ids: list[uuid.UUID]) -> list[ModelCall]:
    if not run_ids:
        return []
    return list(session.scalars(select(ModelCall).where(ModelCall.agent_run_id.in_(run_ids)).order_by(ModelCall.created_at)))


def get_call(session: Session, call_id: uuid.UUID) -> ModelCall | None:
    return session.get(ModelCall, call_id, with_for_update=True, populate_existing=True)


def abandon_pending_calls(session: Session, run_id: uuid.UUID, now: datetime) -> int:
    """Calls from an attempt that died mid-call. They keep their reserved cost: the provider may have billed them."""
    result = session.execute(
        update(ModelCall)
        .where(ModelCall.agent_run_id == run_id, ModelCall.status == "pending")
        .values(status="abandoned", settled_at=now, error="worker stopped before the call settled")
        .execution_options(synchronize_session=False)
    )
    return result.rowcount  # type: ignore[attr-defined,no-any-return]


def lock_budget(session: Session) -> None:
    """Held until the transaction ends."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BUDGET_LOCK_KEY})


def spend_since(session: Session, since: datetime) -> Decimal:
    """Settled calls at their real cost; unsettled or abandoned calls at their reserved worst case."""
    counted = case(
        (ModelCall.status.in_(("pending", "abandoned")), ModelCall.reserved_usd),
        else_=func.coalesce(ModelCall.cost_usd, 0),
    )
    return Decimal(session.scalar(select(func.coalesce(func.sum(counted), 0)).where(ModelCall.created_at >= since)) or 0)
