from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text

from app.infrastructure.db import make_session_factory
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture
def probe_table(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE uow_probe (id integer PRIMARY KEY)"))
    yield
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS uow_probe"))


def _row_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM uow_probe")).scalar_one()


def test_commit_persists_work(engine: Engine, probe_table: None) -> None:
    with UnitOfWork(make_session_factory(engine)) as uow:
        uow.session.execute(text("INSERT INTO uow_probe VALUES (1)"))
        uow.commit()

    assert _row_count(engine) == 1


def test_leaving_without_commit_rolls_back(engine: Engine, probe_table: None) -> None:
    with UnitOfWork(make_session_factory(engine)) as uow:
        uow.session.execute(text("INSERT INTO uow_probe VALUES (1)"))

    assert _row_count(engine) == 0


def test_exception_rolls_back_and_propagates(engine: Engine, probe_table: None) -> None:
    with pytest.raises(RuntimeError, match="side effect failed"):
        with UnitOfWork(make_session_factory(engine)) as uow:
            uow.session.execute(text("INSERT INTO uow_probe VALUES (1)"))
            raise RuntimeError("side effect failed")

    assert _row_count(engine) == 0


def test_session_is_unavailable_outside_the_block(engine: Engine) -> None:
    uow = UnitOfWork(make_session_factory(engine))

    with pytest.raises(RuntimeError, match="outside"):
        _ = uow.session
