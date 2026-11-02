"""Liveness and readiness endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from app import __version__
from app.api.dependencies import get_engine
from app.infrastructure.db import ping

router = APIRouter(tags=["health"])


@router.get("/health")
def health(engine: Annotated[Engine, Depends(get_engine)]) -> JSONResponse:
    database_ok = ping(engine)
    body = {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "version": __version__,
    }
    return JSONResponse(body, status_code=200 if database_ok else 503)
