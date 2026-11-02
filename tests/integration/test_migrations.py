from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from app.infrastructure.db import Base
from app.infrastructure.settings import ROOT_DIR


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_migrations_upgrade_and_downgrade_cleanly(test_database_url: str, engine: Engine) -> None:
    config = _alembic_config(test_database_url)
    head = ScriptDirectory.from_config(config).get_current_head()

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert _current_revision(engine) == head

    command.downgrade(config, "base")
    assert _current_revision(engine) is None

    command.upgrade(config, "head")
    assert _current_revision(engine) == head


def test_models_match_migrations(test_database_url: str, engine: Engine) -> None:
    command.upgrade(_alembic_config(test_database_url), "head")

    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == [], f"Models and migrations differ; generate a migration: {differences}"
