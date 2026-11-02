"""Transaction boundary: persist state before side effects.

Work is committed only by an explicit `commit()`. Leaving the block without committing,
or because of an exception, rolls everything back.
"""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker


class UnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("UnitOfWork used outside its 'with' block")
        return self._session

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.session.rollback()
        finally:
            self.session.close()
            self._session = None

    def commit(self) -> None:
        self.session.commit()
