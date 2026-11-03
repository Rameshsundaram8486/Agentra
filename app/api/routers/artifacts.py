"""Artifacts, versions, content, diffs and version-bound approvals."""

import uuid

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.api.dependencies import ActorDep, ServicesDep, UnitOfWorkDep
from app.modules.artifacts.service import (
    ArtifactCreate,
    ArtifactDetail,
    ArtifactView,
    VersionContent,
    VersionCreate,
    VersionDiff,
)
from app.modules.decisions.service import ApprovalCreate, ApprovalView, ArtifactApprovals

router = APIRouter(prefix="/api", tags=["artifacts"])


class ArtifactTypeView(BaseModel):
    key: str
    title: str
    approver_roles: list[str]
    independent_review: bool


class ArtifactSummary(ArtifactView):
    approval_status: str


class ArtifactPage(BaseModel):
    artifact: ArtifactDetail
    approvals: ArtifactApprovals
    people: dict[uuid.UUID, str]  # display names of authors and the creator


@router.get("/artifact-types")
def artifact_types(_: ActorDep, services: ServicesDep) -> list[ArtifactTypeView]:
    return [
        ArtifactTypeView(
            key=key,
            title=policy.title,
            approver_roles=sorted(policy.approver_roles),
            independent_review=policy.independent_review,
        )
        for key, policy in services.policies.approvals.artifact_types.items()
    ]


@router.get("/projects/{project_id}/artifacts")
def list_artifacts(project_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> list[ArtifactSummary]:
    artifacts = services.artifacts.list_artifacts(actor, project_id)
    statuses = services.decisions.approval_statuses(a.current_version.id for a in artifacts)
    return [ArtifactSummary(**a.model_dump(), approval_status=statuses[a.current_version.id]) for a in artifacts]


@router.post("/projects/{project_id}/artifacts", status_code=status.HTTP_201_CREATED)
def create_artifact(
    project_id: uuid.UUID, body: ArtifactCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> ArtifactDetail:
    artifact = services.artifacts.create_artifact(actor, project_id, body)
    uow.commit()
    return artifact


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> ArtifactPage:
    artifact = services.artifacts.get_artifact(actor, artifact_id)
    people = {version.author_id for version in artifact.versions} | {artifact.created_by}
    return ArtifactPage(
        artifact=artifact,
        approvals=services.decisions.artifact_approvals(actor, artifact_id),
        people=services.identity.display_names(people),
    )


@router.post("/artifacts/{artifact_id}/versions", status_code=status.HTTP_201_CREATED)
def add_version(
    artifact_id: uuid.UUID, body: VersionCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> ArtifactDetail:
    artifact = services.artifacts.add_version(actor, artifact_id, body)
    uow.commit()
    return artifact


@router.get("/artifact-versions/{version_id}/content")
def version_content(version_id: uuid.UUID, actor: ActorDep, services: ServicesDep) -> VersionContent:
    return services.artifacts.read_version(actor, version_id)


@router.get("/artifacts/{artifact_id}/diff")
def diff(
    artifact_id: uuid.UUID,
    actor: ActorDep,
    services: ServicesDep,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
) -> VersionDiff:
    return services.artifacts.diff(actor, artifact_id, from_version, to_version)


@router.post("/artifact-versions/{version_id}/approvals", status_code=status.HTTP_201_CREATED)
def record_approval(
    version_id: uuid.UUID, body: ApprovalCreate, actor: ActorDep, uow: UnitOfWorkDep, services: ServicesDep
) -> ApprovalView:
    approval = services.decisions.record_approval(actor, version_id, body)
    uow.commit()
    return approval
