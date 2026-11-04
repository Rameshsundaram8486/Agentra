"""Phase 8: the latest drafted solution design, with its items, requirement coverage and staleness."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import ActorDep, ServicesDep
from app.modules.design.service import DesignView

router = APIRouter(prefix="/api", tags=["design"])


@router.get("/projects/{project_id}/design")
def current_design(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> DesignView | None:
    """null until the Solution Architect agent has drafted a design for the project."""
    return services.design.view(actor, project_id)
