import uuid
from collections.abc import Callable
from typing import Any

import pytest

from app.cli import main
from app.infrastructure.settings import Settings
from tests.support import DEFAULT_PASSWORD

Run = Callable[..., Any]


def test_create_user_then_sign_in(test_settings: Settings, run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    email = f"cli_{uuid.uuid4().hex[:8]}@example.test"

    code = main(
        ["create-user", "--email", email, "--name", "CLI Admin", "--admin"],
        settings=test_settings,
        read_password=lambda: DEFAULT_PASSWORD,
    )

    assert code == 0
    assert f"Created platform administrator {email}" in capsys.readouterr().out
    assert run(lambda s: s.identity.login(email, DEFAULT_PASSWORD)) is not None


def test_errors_are_reported_without_a_traceback(test_settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["create-user", "--email", "weak@example.test", "--name", "Weak"],
        settings=test_settings,
        read_password=lambda: "short",
    )

    assert code == 1
    assert capsys.readouterr().err.strip() == "error: Password must be at least 12 characters"


def test_development_accepts_a_short_demo_password_that_test_and_production_refuse(
    test_settings: Settings, run: Run
) -> None:
    development = test_settings.model_copy(update={"agentra_env": "development"})
    production = test_settings.model_copy(update={"agentra_env": "production"})
    demo_email = f"demo_{uuid.uuid4().hex[:8]}@example.test"

    refused = main(["create-user", "--email", demo_email, "--name", "Demo"], settings=production, read_password=lambda: "admin@123")
    accepted = main(["create-user", "--email", demo_email, "--name", "Demo"], settings=development, read_password=lambda: "admin@123")

    assert (refused, accepted) == (1, 0)
    assert run(lambda s: s.identity.login(demo_email, "admin@123")) is not None


def test_seed_demo_gives_the_admin_every_review_role_on_the_demo_project_only(
    test_settings: Settings, run: Run, make_team: Callable[..., Any], capsys: pytest.CaptureFixture[str]
) -> None:
    suffix = uuid.uuid4().hex[:6]
    admin_email, author_email, code = f"demo_admin_{suffix}@example.test", f"demo_pm_{suffix}@example.test", f"DEMO-{suffix.upper()}"
    main(["create-user", "--email", admin_email, "--name", "Demo Admin", "--admin"], settings=test_settings, read_password=lambda: DEFAULT_PASSWORD)
    other = make_team()
    args = ["seed-demo", "--admin-email", admin_email, "--author-email", author_email, "--code", code]

    first = main(args, settings=test_settings, read_password=lambda: DEFAULT_PASSWORD)
    second = main(args, settings=test_settings, read_password=lambda: DEFAULT_PASSWORD)  # safe to re-run

    out = capsys.readouterr().out
    assert (first, second) == (0, 0)
    assert f"Created demo project {code}" in out and f"Found demo project {code}" in out

    def inspect(s: Any) -> tuple[set[str], set[tuple[str, str]], set[str], list[Any], str | None]:
        admin = s.identity.actor_by_email(admin_email)
        project = next(p for p in s.projects.list_projects(admin) if p.code == code)
        members = {(m.email, m.role) for m in s.identity.list_members(admin, project.id)}
        briefs = [a for a in s.artifacts.list_artifacts(admin, project.id) if a.artifact_type == "project_brief"]
        return (
            set(s.identity.roles_for(admin, project.id)),
            members,
            set(s.identity.roles_for(admin, other.project.id)),
            briefs,
            s.workflow.phase_state(project.id, 7),
        )

    demo_roles, members, roles_elsewhere, briefs, phase_7 = run(inspect)
    assert demo_roles == {"owner", "reviewer", "customer_approver"}
    assert ("business_analyst@agents.agentra.local", "agent") in members
    assert (author_email, "project_manager") in members
    assert roles_elsewhere == set()  # the extra roles exist on the demo project only
    assert len(briefs) == 1 and briefs[0].current_version_no == 1  # not duplicated by the second run
    assert phase_7 == "in_progress"
    assert "Phase 7 is in progress" in out


def test_create_agent_and_verify_audit(test_settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    key = f"agent_{uuid.uuid4().hex[:8]}"  # not business_analyst: seed-demo may already have created that one

    assert main(["create-agent", "--key", key, "--name", "Test Agent"], settings=test_settings) == 0
    assert main(["verify-audit"], settings=test_settings) == 0

    out = capsys.readouterr().out
    assert f"Created agent account {key}" in out
    assert "Audit chain OK" in out
