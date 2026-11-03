import uuid

import pytest
from pydantic import ValidationError

from app.composition import CONFIG_DIR
from app.modules.identity.authz import PermissionPolicy, load_permission_policy
from app.modules.identity.service import Actor

POLICY = load_permission_policy(CONFIG_DIR / "policies" / "permissions.yaml")


def _actor(admin: bool = False) -> Actor:
    return Actor(id=uuid.uuid4(), kind="human", display_name="Someone", is_platform_admin=admin)


def test_permissions_come_only_from_project_roles_for_ordinary_users() -> None:
    assert POLICY.permissions_for(_actor(), ["reviewer"]) == {
        "project.view", "audit.view", "artifact.view", "decision.view", "agent_run.view"
    }
    assert POLICY.permissions_for(_actor(), []) == frozenset()


def test_reviewers_and_customers_cannot_author_or_raise_decisions() -> None:
    for role in ("reviewer", "customer_approver"):
        granted = POLICY.permissions_for(_actor(), [role])
        assert "artifact.author" not in granted
        assert "decision.raise" not in granted


def test_agents_author_and_raise_decisions() -> None:
    assert {"artifact.author", "decision.raise"} <= POLICY.permissions_for(_actor(), ["agent"])


def test_roles_combine() -> None:
    granted = POLICY.permissions_for(_actor(), ["owner", "customer_approver"])

    assert {"project.view", "project.manage_members", "audit.view"} <= granted


def test_agents_and_customers_cannot_manage_members_or_read_audit() -> None:
    for role in ("agent", "customer_approver"):
        granted = POLICY.permissions_for(_actor(), [role])
        assert "project.manage_members" not in granted
        assert "audit.view" not in granted


def test_platform_admin_gets_platform_permissions_everywhere() -> None:
    granted = POLICY.permissions_for(_actor(admin=True), [])

    assert {"project.create", "project.view", "audit.verify", "user.manage"} <= granted
    assert "project.manage_members" not in granted


def test_unknown_role_in_policy_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown roles"):
        PermissionPolicy.model_validate({"version": 1, "platform_admin": [], "roles": {"intern": ["project.view"]}})
