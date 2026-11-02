"""Domain errors shared by modules. Messages are safe to show to the caller; app/api/errors.py maps them to HTTP."""


class DomainError(Exception):
    """Base class for expected, user-facing failures."""


class AuthenticationError(DomainError):
    """No valid identity: missing, expired or revoked session, or bad credentials."""


class PermissionDeniedError(DomainError):
    """Identity is known but not allowed to do this."""


class NotFoundError(DomainError):
    """Missing, or not visible to this identity (existence is not revealed)."""


class InvalidTransitionError(DomainError):
    """The requested state change is not allowed from the current state or its gates are not met."""


class ConflictError(DomainError):
    """The record changed since it was read, or a unique value is already taken."""


class ValidationFailedError(DomainError):
    """Input is well-formed but breaks a business rule."""
