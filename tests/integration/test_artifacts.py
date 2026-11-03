from collections.abc import Callable
from typing import Any

import pytest

from app.infrastructure.storage.base import sha256_hex
from app.infrastructure.storage.local import LocalArtifactStore
from app.modules.artifacts.service import ArtifactCreate, ArtifactDetail, VersionCreate
from app.modules.errors import ConflictError, IntegrityFailureError, NotFoundError, PermissionDeniedError, ValidationFailedError
from tests.support import Team, TestUser

Run = Callable[..., Any]
BRD_V1 = "# Requirements\n\nREQ-F-001: Staff can submit a leave request.\n"
BRD_V2 = "# Requirements\n\nREQ-F-001: Staff can submit a leave request.\nREQ-F-002: Managers approve or reject it.\n"


def _create(run: Run, team: Team, author: TestUser | None = None, **overrides: Any) -> ArtifactDetail:
    data = {"artifact_type": "requirements_baseline", "title": "Leave app BRD", "content": BRD_V1, "source_refs": ["brief.docx p.2"]}
    data.update(overrides)
    return run(lambda s: s.artifacts.create_artifact((author or team.agent).actor, team.project.id, ArtifactCreate(**data)))


def _add_version(run: Run, team: Team, artifact: ArtifactDetail, content: str, expected: int, author: TestUser | None = None) -> ArtifactDetail:
    data = VersionCreate(content=content, change_summary="Added manager approval", expected_current_version=expected)
    return run(lambda s: s.artifacts.add_version((author or team.agent).actor, artifact.id, data))


def test_first_version_records_hash_size_author_and_sources(run: Run, team: Team, store: LocalArtifactStore) -> None:
    artifact = _create(run, team)
    version = artifact.current_version

    assert artifact.current_version_no == 1 and version.version_no == 1
    assert version.content_sha256 == sha256_hex(BRD_V1.encode())
    assert version.size_bytes == len(BRD_V1.encode())
    assert version.author_id == team.agent.actor.id
    assert version.source_refs == ["brief.docx p.2"]
    assert store.get(version.content_sha256) == BRD_V1.encode()


def test_new_version_keeps_the_old_one_unchanged(run: Run, team: Team) -> None:
    artifact = _create(run, team)
    updated = _add_version(run, team, artifact, BRD_V2, expected=1)

    v1 = run(lambda s: s.artifacts.read_version(team.reviewer.actor, artifact.current_version.id))
    assert updated.current_version_no == 2
    assert [v.version_no for v in updated.versions] == [2, 1]
    assert v1.content == BRD_V1
    assert v1.version.content_sha256 == artifact.current_version.content_sha256


def test_version_based_on_a_stale_copy_is_a_conflict(run: Run, team: Team) -> None:
    artifact = _create(run, team)
    _add_version(run, team, artifact, BRD_V2, expected=1)

    with pytest.raises(ConflictError, match="now at version 2"):
        _add_version(run, team, artifact, BRD_V2 + "more\n", expected=1)


def test_diff_shows_what_changed_between_versions(run: Run, team: Team) -> None:
    artifact = _create(run, team)
    _add_version(run, team, artifact, BRD_V2, expected=1)

    diff = run(lambda s: s.artifacts.diff(team.reviewer.actor, artifact.id, 1, 2))

    assert "+REQ-F-002: Managers approve or reject it." in diff.diff
    assert diff.diff.startswith("--- v1")


def test_reviewers_and_customers_cannot_author(run: Run, team: Team, make_user: Callable[..., TestUser], add_member: Any) -> None:
    customer = make_user()
    add_member(team.owner, team.project.id, customer, "customer_approver")

    for user in (team.reviewer, customer):
        with pytest.raises(PermissionDeniedError):
            _create(run, team, author=user, title=f"By {user.email}")


def test_outsiders_cannot_see_artifacts(run: Run, team: Team, make_user: Callable[..., TestUser]) -> None:
    artifact = _create(run, team)
    outsider = make_user()

    with pytest.raises(NotFoundError):
        run(lambda s: s.artifacts.get_artifact(outsider.actor, artifact.id))
    with pytest.raises(NotFoundError):
        run(lambda s: s.artifacts.read_version(outsider.actor, artifact.current_version.id))


def test_unknown_type_empty_content_and_duplicate_titles_are_rejected(run: Run, team: Team) -> None:
    _create(run, team)

    with pytest.raises(ValidationFailedError, match="Unknown artifact type"):
        _create(run, team, artifact_type="secret_plans")
    with pytest.raises(ValidationFailedError, match="empty"):
        _create(run, team, title="Blank", content="  \n")
    with pytest.raises(ConflictError, match="already exists"):
        _create(run, team)


def test_reading_tampered_content_fails_loudly(run: Run, team: Team, store: LocalArtifactStore) -> None:
    artifact = _create(run, team, title="Tamper target", content="# Original unique text 7f3a\n")
    digest = artifact.current_version.content_sha256
    path = next(p for p in store._root.rglob(digest))  # noqa: SLF001  (test reaches into the store on purpose)
    original = path.read_bytes()
    try:
        path.write_bytes(b"# Edited outside Agentra\n")
        with pytest.raises(IntegrityFailureError, match="integrity check"):
            run(lambda s: s.artifacts.read_version(team.reviewer.actor, artifact.current_version.id))
    finally:
        path.write_bytes(original)


def test_create_and_new_version_are_audited(run: Run, team: Team, engine: Any) -> None:
    from sqlalchemy import text

    artifact = _create(run, team, title="Audited")
    _add_version(run, team, artifact, BRD_V2, expected=1)

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT action, reason FROM audit_events WHERE entity_id = :id ORDER BY seq"), {"id": str(artifact.id)}
        ).all()
    assert [tuple(row) for row in rows] == [("artifact.create", None), ("artifact.version_add", "Added manager approval")]
