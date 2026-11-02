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


def test_create_agent_and_verify_audit(test_settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    key = f"agent_{uuid.uuid4().hex[:8]}"

    assert main(["create-agent", "--key", key, "--name", "Test Agent"], settings=test_settings) == 0
    assert main(["verify-audit"], settings=test_settings) == 0

    out = capsys.readouterr().out
    assert f"Created agent account {key}" in out
    assert "Audit chain OK" in out
