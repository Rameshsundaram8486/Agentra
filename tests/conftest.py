"""Shared pytest fixtures: test PostgreSQL database and settings.

The fake model provider and fake sandbox fixtures arrive with the agent runtime (Increment 2).
"""

from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from app.infrastructure.db import create_db_engine
from app.infrastructure.settings import ENV_FILE, Settings


class _TestEnvironment(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_ignore_empty=True, extra="ignore")

    test_database_url: SecretStr | None = None


@pytest.fixture(scope="session")
def test_database_url() -> str:
    configured = _TestEnvironment().test_database_url
    if configured is None:
        pytest.fail("TEST_DATABASE_URL is not set; see docs/development-guide.md")
    url = configured.get_secret_value()
    # Guard: tests drop and recreate schema objects, so never point them at a real database.
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in '_test'")
    return url


@pytest.fixture(scope="session")
def test_settings(test_database_url: str) -> Settings:
    return Settings(database_url=test_database_url, agentra_env="test")


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Iterator[Engine]:
    engine = create_db_engine(test_database_url)
    yield engine
    engine.dispose()
