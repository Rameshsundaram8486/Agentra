"""Phase 8: the latest drafted solution design, with its items, requirement coverage and staleness, and its security
and feasibility reviews, and the implementation backlog planned from it."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import ActorDep, ServicesDep
from app.modules.backlog.service import BacklogView
from app.modules.design.service import DesignView
from app.modules.design_reviews.service import DesignReviewsView

router = APIRouter(prefix="/api", tags=["design"])


@router.get("/projects/{project_id}/design")
def current_design(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> DesignView | None:
    """null until the Solution Architect agent has drafted a design for the project."""
    return services.design.view(actor, project_id)


@router.get("/projects/{project_id}/design/reviews")
def design_reviews(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> DesignReviewsView:
    """The latest security and feasibility reviews, and what still stops the current design from being approved."""
    return services.design_reviews.view(actor, project_id)


@router.get("/projects/{project_id}/backlog")
def implementation_backlog(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> BacklogView | None:
    """null until the Developer agent has planned a backlog from the approved design."""
    return services.backlog.view(actor, project_id)
