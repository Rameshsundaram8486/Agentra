"""FastAPI application factory: routers, error handling, security headers and the static Control Center."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.errors import register_error_handlers
from app.api.routers import artifacts, audit, auth, decisions, health, projects, workflow
from app.composition import Policies, load_policies
from app.infrastructure.clock import Clock, SystemClock
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.logging import configure_logging
from app.infrastructure.settings import ROOT_DIR, Settings, get_settings
from app.infrastructure.storage.base import ArtifactStore
from app.infrastructure.storage.local import LocalArtifactStore

# Pages are plain files with no inline script or style, so the policy can be strict.
_PAGE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


async def _security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/app/"):
        response.headers.setdefault("Content-Security-Policy", _PAGE_CSP)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    policies: Policies | None = None,
    store: ArtifactStore | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    policies = policies or load_policies(timedelta(hours=settings.session_ttl_hours), settings.min_password_length)
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
    app.state.clock = clock or SystemClock()
    app.state.policies = policies
    app.state.store = store or LocalArtifactStore(settings.artifact_root)

    register_error_handlers(app)
    app.middleware("http")(_security_headers)
    for router in (
        health.router,
        auth.router,
        projects.router,
        workflow.router,
        artifacts.router,
        decisions.router,
        audit.router,
    ):
        app.include_router(router)

    app.mount("/app", StaticFiles(directory=ROOT_DIR / "web"), name="web")

    @app.get("/", include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse("/app/control-center/projects.html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(ROOT_DIR / "web" / "assets" / "img" / "favicon.svg", media_type="image/svg+xml")

    return app
