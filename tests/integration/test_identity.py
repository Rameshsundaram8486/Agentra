from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.modules.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.identity.service import SYSTEM_ACTOR
from tests.support import DEFAULT_PASSWORD, Team, TestUser

Run = Callable[..., Any]


def _create(run: Run, actor: Any = SYSTEM_ACTOR, **kwargs: Any) -> Any:
    defaults: dict[str, Any] = {"email": "someone@example.test", "display_name": "Someone"}
    return run(lambda s: s.identity.create_user(actor, **{**defaults, **kwargs}))


def test_short_password_is_rejected(run: Run) -> None:
    with pytest.raises(ValidationFailedError, match="at least 12"):
        _create(run, email="short@example.test", password="short")


def test_agent_accounts_cannot_have_passwords_or_admin_rights(run: Run) -> None:
    with pytest.raises(ValidationFailedError, match="cannot have a password"):
        _create(run, email="a1@agents.test", kind="agent", agent_key="agent_one", password=DEFAULT_PASSWORD)
    with pytest.raises(ValidationFailedError, match="platform administrators"):
        _create(run, email="a2@agents.test", kind="agent", agent_key="agent_two", is_platform_admin=True)


def test_email_is_normalised_and_unique_ignoring_case(run: Run, make_user: Callable[..., TestUser]) -> None:
    user = make_user()

    with pytest.raises(ConflictError):
        _create(run, email=f"  {user.email.upper()} ", password=DEFAULT_PASSWORD)


def test_only_platform_admins_create_users(run: Run, make_user: Callable[..., TestUser]) -> None:
    ordinary = make_user()

    with pytest.raises(PermissionDeniedError):
        _create(run, actor=ordinary.actor, email="new@example.test", password=DEFAULT_PASSWORD)


def test_database_also_refuses_a_password_on_an_agent_account(engine: Engine) -> None:
    with pytest.raises(IntegrityError, match="only_humans_have_passwords"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name, kind, agent_key, password_hash, is_platform_admin, is_active, created_at) "
                    "VALUES (gen_random_uuid(), 'raw@agents.test', 'Raw', 'agent', 'raw_agent', 'x', false, true, now())"
                )
            )


def test_roles_must_match_the_account_kind(run: Run, team: Team, make_user: Callable[..., TestUser]) -> None:
    person, agent = make_user(), make_user("agent")

    with pytest.raises(ValidationFailedError, match="Only agent accounts"):
        run(lambda s: s.identity.add_member(team.owner.actor, team.project.id, person.email, "agent"))
    with pytest.raises(ValidationFailedError, match="only hold the agent role"):
        run(lambda s: s.identity.add_member(team.owner.actor, team.project.id, agent.email, "reviewer"))


def test_only_owners_manage_members(run: Run, team: Team, make_user: Callable[..., TestUser]) -> None:
    newcomer = make_user()

    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.identity.add_member(team.pm.actor, team.project.id, newcomer.email, "reviewer"))
    with pytest.raises(NotFoundError):
        run(lambda s: s.identity.add_member(newcomer.actor, team.project.id, newcomer.email, "owner"))


def test_duplicate_membership_and_second_initial_owner_are_conflicts(run: Run, team: Team) -> None:
    with pytest.raises(ConflictError):
        run(lambda s: s.identity.add_member(team.owner.actor, team.project.id, team.pm.email, "project_manager"))
    with pytest.raises(ConflictError):
        run(lambda s: s.identity.add_initial_owner(team.pm.actor, team.project.id))


def test_login_rejects_agents_and_wrong_passwords_and_audits_failures(
    run: Run, make_user: Callable[..., TestUser], engine: Engine
) -> None:
    person, agent = make_user(), make_user("agent")

    assert run(lambda s: s.identity.login(person.email, "wrong-password-123")) is None
    assert run(lambda s: s.identity.login(agent.email, "anything-at-all")) is None
    assert run(lambda s: s.identity.login("nobody@example.test", DEFAULT_PASSWORD)) is None
    assert run(lambda s: s.identity.login(person.email, DEFAULT_PASSWORD)) is not None

    with engine.connect() as connection:
        actions = connection.execute(
            text("SELECT action FROM audit_events WHERE entity_id = :id ORDER BY seq"), {"id": str(person.actor.id)}
        ).scalars().all()
    assert actions == ["user.create", "auth.login_failed", "auth.login"]
