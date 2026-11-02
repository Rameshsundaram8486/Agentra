"""Audit trail of a project, and verification of the whole hash chain."""

import uuid

from fastapi import APIRouter, Query

from app.api.dependencies import ActorDep, ServicesDep
from app.modules.audit.schemas import AuditEventView, ChainVerification

router = APIRouter(prefix="/api", tags=["audit"])


class AuditEntry(AuditEventView):
    actor_name: str | None


@router.get("/projects/{project_id}/audit")
def project_audit(
    project_id: uuid.UUID,
    actor: ActorDep,
    services: ServicesDep,
    limit: int = Query(default=100, ge=1, le=500),
    before_seq: int | None = Query(default=None, ge=1),
) -> list[AuditEntry]:
    services.identity.require_project(actor, project_id, "audit.view")
    events = services.audit.list_for_project(project_id, limit=limit, before_seq=before_seq)
    names = services.identity.display_names({event.actor_id for event in events})
    return [AuditEntry(**event.model_dump(), actor_name=names.get(event.actor_id)) for event in events]


@router.get("/audit/verify")
def verify_chain(actor: ActorDep, services: ServicesDep) -> ChainVerification:
    services.identity.require_platform(actor, "audit.verify")
    return services.audit.verify_chain()
