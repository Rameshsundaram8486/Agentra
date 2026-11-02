import pytest

from app.infrastructure.settings import Settings


def test_secrets_are_hidden_in_repr() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://agentra:db-password-123@localhost/agentra_dev",
        anthropic_api_key="sk-ant-test-key-123",
    )

    text = repr(settings) + str(settings.model_dump())

    assert "db-password-123" not in text
    assert "sk-ant-test-key-123" not in text


def test_secret_values_include_the_database_password_on_its_own() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://agentra:db-password-123@localhost/agentra_dev",
    )

    assert "db-password-123" in settings.secret_values()


def test_empty_environment_values_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AZURE_KEY_VAULT_URL", "")

    settings = Settings(_env_file=None, database_url="postgresql+psycopg://u:p@h/db")

    assert settings.anthropic_api_key is None
    assert settings.azure_key_vault_url is None


@pytest.mark.parametrize(("env", "minimum"), [("development", 8), ("test", 12), ("production", 12)])
def test_short_passwords_are_allowed_only_in_development(env: str, minimum: int) -> None:
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://u:p@h/db", agentra_env=env)

    assert settings.min_password_length == minimum


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="database_url"):
        Settings(_env_file=None)
