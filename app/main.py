"""FastAPI application factory: routers and middleware. Control Center and Portal are mounted from Increment 1a."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routers import health
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.logging import configure_logging
from app.infrastructure.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    engine = create_db_engine(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    show_docs = settings.agentra_env != "production"
    app = FastAPI(
        title="Agentra",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if show_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if show_docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.include_router(health.router)
    return app
