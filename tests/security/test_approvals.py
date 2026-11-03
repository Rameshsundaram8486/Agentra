"""Approvals are human, role-checked, independent, and bound to the exact version id and content hash."""

from collections.abc import Callable
from typing import Any

import pytest

from app.infrastructure.storage.local import LocalArtifactStore
from app.modules.artifacts.service import ArtifactCreate, ArtifactDetail, VersionCreate
from app.modules.decisions.service import ApprovalCreate, ApprovalView
from app.modules.errors import ConflictError, IntegrityFailureError, PermissionDeniedError, ValidationFailedError
from app.modules.identity.service import SYSTEM_ACTOR
from tests.support import Team, TestUser

Run = Callable[..., Any]


def _create(run: Run, team: Team, author: TestUser, artifact_type: str = "requirements_baseline", title: str = "BRD") -> ArtifactDetail:
    data = ArtifactCreate(artifact_type=artifact_type, title=title, content=f"# {title}\n\nREQ-F-001\n")
    return run(lambda s: s.artifacts.create_artifact(author.actor, team.project.id, data))


def _approve(run: Run, user: Any, version_id: Any, sha: str, decision: str = "approved", comment: str | None = None) -> ApprovalView:
    actor = user.actor if isinstance(user, TestUser) else user
    data = ApprovalCreate(decision=decision, content_sha256=sha, comment=comment)
    return run(lambda s: s.decisions.record_approval(actor, version_id, data))


def test_reviewer_approves_the_exact_version_and_hash(run: Run, team: Team) -> None:
    version = _create(run, team, team.agent).current_version

    approval = _approve(run, team.reviewer, version.id, version.content_sha256)

    assert (approval.decision, approval.version_no, approval.content_sha256) == ("approved", 1, version.content_sha256)
    assert approval.approver_name == team.reviewer.actor.display_name


def test_hash_of_different_content_is_rejected(run: Run, team: Team) -> None:
    version = _create(run, team, team.agent).current_version

    with pytest.raises(ConflictError, match="is not version 1"):
        _approve(run, team.reviewer, version.id, "0" * 64)


def test_malformed_hash_is_rejected(run: Run, team: Team) -> None:
    version = _create(run, team, team.agent).current_version

    with pytest.raises(ValidationFailedError, match="64 hexadecimal"):
        _approve(run, team.reviewer, version.id, "not-a-hash")


def test_old_version_cannot_be_approved_once_a_newer_one_exists(run: Run, team: Team) -> None:
    artifact = _create(run, team, team.agent)
    v1 = artifact.current_version
    run(lambda s: s.artifacts.add_version(team.agent.actor, artifact.id, VersionCreate(content="# BRD v2\n", change_summary="Update", expected_current_version=1)))

    with pytest.raises(ConflictError, match="replaced by a newer version"):
        _approve(run, team.reviewer, v1.id, v1.content_sha256)


@pytest.mark.parametrize("who", ["agent", "system"])
def test_agents_and_the_system_account_never_approve(run: Run, team: Team, who: str) -> None:
    version = _create(run, team, team.pm).current_version
    actor = team.agent if who == "agent" else SYSTEM_ACTOR

    with pytest.raises(PermissionDeniedError, match="Only people"):
        _approve(run, actor, version.id, version.content_sha256)


def test_author_cannot_approve_their_own_artifact(run: Run, team: Team, add_member: Any) -> None:
    add_member(team.owner, team.project.id, team.pm, "reviewer")  # PM is now also a reviewer
    version = _create(run, team, team.pm).current_version

    with pytest.raises(PermissionDeniedError, match="independent reviewer"):
        _approve(run, team.pm, version.id, version.content_sha256)


def test_author_of_an_earlier_version_cannot_approve_a_later_one(run: Run, team: Team, add_member: Any) -> None:
    add_member(team.owner, team.project.id, team.pm, "reviewer")
    artifact = _create(run, team, team.pm)
    v2 = run(
        lambda s: s.artifacts.add_version(team.agent.actor, artifact.id, VersionCreate(content="# BRD v2 by agent\n", change_summary="Agent edit", expected_current_version=1))
    ).current_version

    with pytest.raises(PermissionDeniedError, match="independent reviewer"):
        _approve(run, team.pm, v2.id, v2.content_sha256)


def test_role_must_be_listed_for_the_artifact_type(run: Run, team: Team, make_user: Callable[..., TestUser], add_member: Any) -> None:
    customer = make_user(name="Customer")
    add_member(team.owner, team.project.id, customer, "customer_approver")
    brd = _create(run, team, team.agent).current_version
    signoff = _create(run, team, team.agent, artifact_type="uat_signoff_record", title="UAT sign-off").current_version

    with pytest.raises(PermissionDeniedError, match="needs one of these roles"):
        _approve(run, team.pm, brd.id, brd.content_sha256)
    with pytest.raises(PermissionDeniedError, match="needs one of these roles"):
        _approve(run, customer, brd.id, brd.content_sha256)
    with pytest.raises(PermissionDeniedError, match="needs one of these roles"):
        _approve(run, team.reviewer, signoff.id, signoff.content_sha256)
    assert _approve(run, customer, signoff.id, signoff.content_sha256).decision == "approved"


def test_rejection_and_change_requests_need_a_reason(run: Run, team: Team) -> None:
    version = _create(run, team, team.agent).current_version

    with pytest.raises(ValidationFailedError, match="Explain"):
        _approve(run, team.reviewer, version.id, version.content_sha256, decision="changes_requested")
    assert _approve(run, team.reviewer, version.id, version.content_sha256, decision="changes_requested", comment="Add NFRs").comment == "Add NFRs"


def test_content_tampered_in_storage_cannot_be_approved(run: Run, team: Team, store: LocalArtifactStore) -> None:
    version = _create(run, team, team.agent, title="Tamper-approve 91c2").current_version
    path = next(store._root.rglob(version.content_sha256))  # noqa: SLF001
    original = path.read_bytes()
    try:
        path.write_bytes(b"different words")
        with pytest.raises(IntegrityFailureError):
            _approve(run, team.reviewer, version.id, version.content_sha256)
    finally:
        path.write_bytes(original)


def test_outsider_cannot_approve(run: Run, team: Team, make_user: Callable[..., TestUser]) -> None:
    from app.modules.errors import NotFoundError

    version = _create(run, team, team.agent).current_version

    with pytest.raises(NotFoundError):
        _approve(run, make_user(), version.id, version.content_sha256)
