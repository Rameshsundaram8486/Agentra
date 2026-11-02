from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

from app.infrastructure.db import Base
from app.modules.identity.service import SYSTEM_USER_ID
from tests.support import alembic_config as _alembic_config


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


def test_downgrade_removes_everything_and_upgrade_seeds_system_account(test_database_url: str, engine: Engine) -> None:
    config = _alembic_config(test_database_url)

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}

    command.upgrade(config, "head")
    with engine.connect() as connection:
        system_kind = connection.execute(
            text("SELECT kind FROM users WHERE id = :id"), {"id": SYSTEM_USER_ID}
        ).scalar_one()
        triggers = set(
            connection.execute(
                text("SELECT tgname FROM pg_trigger WHERE tgrelid = 'audit_events'::regclass AND NOT tgisinternal")
            ).scalars()
        )
    assert system_kind == "system"
    assert triggers == {"audit_events_no_update_delete", "audit_events_no_truncate"}


def test_models_match_migrations(test_database_url: str, engine: Engine) -> None:
    command.upgrade(_alembic_config(test_database_url), "head")

    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == [], f"Models and migrations differ; generate a migration: {differences}"
