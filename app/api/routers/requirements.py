"""Phase 7 requirements: the latest drafted set, with IDs, labels, statuses, sources and quality flags."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import ActorDep, ServicesDep
from app.modules.requirements.service import RequirementsView

router = APIRouter(prefix="/api", tags=["requirements"])


@router.get("/projects/{project_id}/requirements")
def current_requirements(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> RequirementsView | None:
    """null until the Business Analyst agent has drafted requirements for the project."""
    return services.requirements.view(actor, project_id)
