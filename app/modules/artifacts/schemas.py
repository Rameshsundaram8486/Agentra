"""Artifact data accepted from and returned to callers."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MAX_CONTENT_BYTES = 2_000_000
MediaType = Literal["text/markdown", "text/plain", "application/json"]
SourceRef = str


class ArtifactCreate(BaseModel):
    artifact_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    title: str = Field(min_length=1, max_length=200)
    content: str
    media_type: MediaType = "text/markdown"
    change_summary: str = Field(default="Initial version", min_length=3, max_length=2000)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=50)


class VersionCreate(BaseModel):
    content: str
    media_type: MediaType = "text/markdown"
    change_summary: str = Field(min_length=3, max_length=2000)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=50)
    expected_current_version: int = Field(ge=1, description="The version the author started from")


class ArtifactVersionView(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    version_no: int
    content_sha256: str
    size_bytes: int
    media_type: str
    change_summary: str
    source_refs: list[str]
    author_id: uuid.UUID
    created_at: datetime


class ArtifactView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    artifact_type: str
    type_title: str
    title: str
    current_version_no: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    current_version: ArtifactVersionView


class ArtifactDetail(ArtifactView):
    versions: list[ArtifactVersionView]


class VersionContent(BaseModel):
    version: ArtifactVersionView
    content: str


class VersionDiff(BaseModel):
    from_version: int
    to_version: int
    diff: str


class VersionRecord(BaseModel):
    """What other modules need to bind a decision to a version. No content."""

    id: uuid.UUID
    artifact_id: uuid.UUID
    project_id: uuid.UUID
    artifact_type: str
    artifact_title: str
    version_no: int
    content_sha256: str
    is_current: bool
