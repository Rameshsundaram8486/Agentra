"""Business rules for artifacts; the only entry point for other modules.

Content goes to the content-addressed store; metadata goes to PostgreSQL. A version is never changed:
editing an artifact always adds a new version, and every read re-checks the content hash.
"""

import base64
import binascii
import difflib
import uuid
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.infrastructure.storage.base import ArtifactStore, ContentIntegrityError
from app.integrations.documents.extraction import ExtractionError, extract
from app.modules.artifacts import repository
from app.modules.artifacts.models import Artifact, ArtifactVersion
from app.modules.artifacts.schemas import (
    MAX_CONTENT_BYTES,
    ArtifactCreate,
    UploadCreate,
    ArtifactDetail,
    ArtifactVersionView,
    ArtifactView,
    VersionContent,
    VersionCreate,
    VersionDiff,
    VersionRecord,
)
from app.modules.audit.service import AuditService
from app.modules.errors import ConflictError, IntegrityFailureError, NotFoundError, ValidationFailedError
from app.modules.identity.service import Actor, IdentityService

__all__ = [
    "ArtifactCreate",
    "ArtifactDetail",
    "ArtifactVersionView",
    "ArtifactView",
    "ArtifactsService",
    "VersionContent",
    "VersionCreate",
    "VersionDiff",
    "UploadCreate",
    "VersionRecord",
]


def _version_view(version: ArtifactVersion) -> ArtifactVersionView:
    return ArtifactVersionView.model_validate(version, from_attributes=True)


def _encode(content: str) -> bytes:
    data = content.encode("utf-8")
    if not data.strip():
        raise ValidationFailedError("Content is empty")
    if len(data) > MAX_CONTENT_BYTES:
        raise ValidationFailedError(f"Content is larger than {MAX_CONTENT_BYTES // 1_000_000} MB")
    return data


class ArtifactsService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        store: ArtifactStore,
        artifact_types: Mapping[str, str],
    ) -> None:
        """artifact_types maps each allowed type to its display title (from the approval matrix)."""
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._store = store
        self._types = artifact_types

    # Authoring ------------------------------------------------------------------------------

    def create_artifact(self, actor: Actor, project_id: uuid.UUID, data: ArtifactCreate) -> ArtifactDetail:
        self._identity.require_project(actor, project_id, "artifact.author")
        data = ArtifactCreate.model_validate(data)
        if data.artifact_type not in self._types:
            raise ValidationFailedError(f"Unknown artifact type '{data.artifact_type}'")
        title = data.title.strip()
        if repository.title_taken(self._session, project_id, data.artifact_type, title):
            raise ConflictError("An artifact of this type with this title already exists; add a version to it instead")
        content = _encode(data.content)
        digest = self._store.put(content)  # content-addressed: safe to keep even if this transaction rolls back

        now = self._clock.now()
        artifact = Artifact(
            project_id=project_id,
            artifact_type=data.artifact_type,
            title=title,
            current_version_no=1,
            created_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        repository.add(self._session, artifact)
        version = self._add_version_row(artifact, 1, digest, len(content), data.media_type, data.change_summary, data.source_refs, actor)
        self._audit.record(
            actor_id=actor.id,
            action="artifact.create",
            entity_type="artifact",
            entity_id=artifact.id,
            project_id=project_id,
            after={"artifact_type": data.artifact_type, "title": title, "version_no": 1, "content_sha256": digest},
        )
        return self._detail(artifact, [version])

    def add_version(self, actor: Actor, artifact_id: uuid.UUID, data: VersionCreate) -> ArtifactDetail:
        artifact = self._load(artifact_id)
        self._identity.require_project(actor, artifact.project_id, "artifact.author")
        data = VersionCreate.model_validate(data)
        if artifact.current_version_no != data.expected_current_version:
            raise ConflictError(
                f"This artifact is now at version {artifact.current_version_no}; reload it and apply your changes again"
            )
        content = _encode(data.content)
        digest = self._store.put(content)
        project_id, previous = artifact.project_id, artifact.current_version_no
        if not repository.advance_version(self._session, artifact.id, previous, self._clock.now()):
            raise ConflictError("Someone else added a version just now; reload it and apply your changes again")
        artifact = self._load(artifact_id)
        self._add_version_row(artifact, previous + 1, digest, len(content), data.media_type, data.change_summary, data.source_refs, actor)
        self._audit.record(
            actor_id=actor.id,
            action="artifact.version_add",
            entity_type="artifact",
            entity_id=artifact.id,
            project_id=project_id,
            reason=data.change_summary,
            before={"version_no": previous},
            after={"version_no": previous + 1, "content_sha256": digest},
        )
        return self._detail(artifact, repository.versions_for(self._session, artifact.id))

    def upload(self, actor: Actor, project_id: uuid.UUID, data: UploadCreate) -> ArtifactDetail:
        """Extracts the text of an uploaded file and stores it as a version; the original file is kept by its hash."""
        self._identity.require_project(actor, project_id, "artifact.author")
        data = UploadCreate.model_validate(data)
        try:
            raw = base64.b64decode(data.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValidationFailedError("The file content is not valid base64") from exc
        try:
            extracted = extract(data.filename, raw)
        except ExtractionError as exc:
            raise ValidationFailedError(f"{data.filename}: {exc}") from exc
        original = self._store.put(raw)
        filename = data.filename.replace("\\", "/").rsplit("/", 1)[-1]
        pages = f", {extracted.pages} pages" if extracted.pages else ""
        sources = [
            f"File: {filename} ({extracted.file_type}{pages})",
            f"Original file sha256: {original}",
            f"Origin: {data.origin.strip()}",
            *(f"Extraction note: {warning}" for warning in extracted.warnings),
        ]
        title = data.title.strip()
        existing = repository.get_by_title(self._session, project_id, data.artifact_type, title)
        if existing is None:
            return self.create_artifact(
                actor,
                project_id,
                ArtifactCreate(
                    artifact_type=data.artifact_type,
                    title=title,
                    content=extracted.text,
                    change_summary=f"Uploaded {filename}",
                    source_refs=sources,
                ),
            )
        return self.add_version(
            actor,
            existing.id,
            VersionCreate(
                content=extracted.text,
                change_summary=f"Uploaded {filename}",
                source_refs=sources,
                expected_current_version=existing.current_version_no,
            ),
        )

    # Reading --------------------------------------------------------------------------------

    def list_artifacts(self, actor: Actor, project_id: uuid.UUID) -> list[ArtifactView]:
        self._identity.require_project(actor, project_id, "artifact.view")
        artifacts = repository.artifacts_for_project(self._session, project_id)
        current = repository.current_versions(self._session, artifacts)
        return [self._view(artifact, current[artifact.id]) for artifact in artifacts]

    def get_artifact(self, actor: Actor, artifact_id: uuid.UUID) -> ArtifactDetail:
        artifact = self._load(artifact_id)
        self._identity.require_project(actor, artifact.project_id, "artifact.view")
        return self._detail(artifact, repository.versions_for(self._session, artifact.id))

    def read_version(self, actor: Actor, version_id: uuid.UUID) -> VersionContent:
        version = self._load_version(version_id)
        self._identity.require_project(actor, version.project_id, "artifact.view")
        return VersionContent(version=_version_view(version), content=self._content(version).decode("utf-8"))

    def diff(self, actor: Actor, artifact_id: uuid.UUID, from_version: int, to_version: int) -> VersionDiff:
        artifact = self._load(artifact_id)
        self._identity.require_project(actor, artifact.project_id, "artifact.view")
        texts = []
        for number in (from_version, to_version):
            version = repository.get_version_by_number(self._session, artifact_id, number)
            if version is None:
                raise NotFoundError(f"Version {number} not found")
            texts.append(self._content(version).decode("utf-8").splitlines(keepends=True))
        lines = difflib.unified_diff(texts[0], texts[1], fromfile=f"v{from_version}", tofile=f"v{to_version}")
        return VersionDiff(from_version=from_version, to_version=to_version, diff="".join(lines))

    # For other modules (callers have already authorised the actor) ---------------------------

    def version_record(self, version_id: uuid.UUID) -> VersionRecord:
        version = self._load_version(version_id)
        artifact = self._load(version.artifact_id)
        return self._record(artifact, version)

    def current_records_of_type(self, project_id: uuid.UUID, artifact_type: str) -> list[VersionRecord]:
        artifacts = repository.artifacts_for_project(self._session, project_id, artifact_type)
        current = repository.current_versions(self._session, artifacts)
        return [self._record(artifact, current[artifact.id]) for artifact in artifacts]

    def author_ids(self, artifact_id: uuid.UUID) -> set[uuid.UUID]:
        return repository.author_ids(self._session, artifact_id)

    def verify_content(self, version_id: uuid.UUID) -> None:
        """Re-hashes the stored bytes; raises IntegrityFailureError if they changed or vanished."""
        self._content(self._load_version(version_id))

    # Helpers --------------------------------------------------------------------------------

    def _add_version_row(
        self,
        artifact: Artifact,
        version_no: int,
        digest: str,
        size: int,
        media_type: str,
        change_summary: str,
        source_refs: list[str],
        actor: Actor,
    ) -> ArtifactVersion:
        version = ArtifactVersion(
            artifact_id=artifact.id,
            project_id=artifact.project_id,
            version_no=version_no,
            content_sha256=digest,
            size_bytes=size,
            media_type=media_type,
            change_summary=change_summary.strip(),
            source_refs=[ref.strip() for ref in source_refs if ref.strip()],
            author_id=actor.id,
            created_at=self._clock.now(),
        )
        repository.add(self._session, version)
        return version

    def _content(self, version: ArtifactVersion) -> bytes:
        try:
            return self._store.get(version.content_sha256)
        except ContentIntegrityError as exc:
            raise IntegrityFailureError(
                f"Stored content for version {version.version_no} failed its integrity check ({exc})"
            ) from exc

    def _load(self, artifact_id: uuid.UUID) -> Artifact:
        artifact = repository.get_artifact(self._session, artifact_id)
        if artifact is None:
            raise NotFoundError("Artifact not found")
        return artifact

    def _load_version(self, version_id: uuid.UUID) -> ArtifactVersion:
        version = repository.get_version(self._session, version_id)
        if version is None:
            raise NotFoundError("Artifact version not found")
        return version

    def _view(self, artifact: Artifact, current: ArtifactVersion) -> ArtifactView:
        return ArtifactView(
            id=artifact.id,
            project_id=artifact.project_id,
            artifact_type=artifact.artifact_type,
            type_title=self._types.get(artifact.artifact_type, artifact.artifact_type),
            title=artifact.title,
            current_version_no=artifact.current_version_no,
            created_by=artifact.created_by,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
            current_version=_version_view(current),
        )

    def _detail(self, artifact: Artifact, versions: list[ArtifactVersion]) -> ArtifactDetail:
        current = next(v for v in versions if v.version_no == artifact.current_version_no)
        return ArtifactDetail(
            **self._view(artifact, current).model_dump(),
            versions=[_version_view(v) for v in sorted(versions, key=lambda v: v.version_no, reverse=True)],
        )

    @staticmethod
    def _record(artifact: Artifact, version: ArtifactVersion) -> VersionRecord:
        return VersionRecord(
            id=version.id,
            artifact_id=artifact.id,
            project_id=artifact.project_id,
            artifact_type=artifact.artifact_type,
            artifact_title=artifact.title,
            version_no=version.version_no,
            content_sha256=version.content_sha256,
            is_current=version.version_no == artifact.current_version_no,
        )
