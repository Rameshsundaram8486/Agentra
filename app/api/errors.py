"""Maps domain errors to HTTP responses: {"error": <code>, "message": <safe text>}."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    IntegrityFailureError,
    InvalidTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)

_RESPONSES: list[tuple[type[DomainError], int, str]] = [
    (AuthenticationError, 401, "authentication_required"),
    (PermissionDeniedError, 403, "permission_denied"),
    (NotFoundError, 404, "not_found"),
    (InvalidTransitionError, 409, "invalid_transition"),
    (ConflictError, 409, "conflict"),
    (ValidationFailedError, 422, "validation_failed"),
    (IntegrityFailureError, 500, "integrity_failure"),
]


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    for error_type, status, code in _RESPONSES:
        if isinstance(exc, error_type):
            return JSONResponse({"error": code, "message": str(exc)}, status_code=status)
    return JSONResponse({"error": "domain_error", "message": str(exc)}, status_code=400)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
