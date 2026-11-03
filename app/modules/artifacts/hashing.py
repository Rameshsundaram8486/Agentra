"""Content hashing used for version binding and evidence."""

from app.infrastructure.storage.base import SHA256_PATTERN, sha256_hex
from app.modules.errors import ValidationFailedError

__all__ = ["parse_sha256", "sha256_hex"]


def parse_sha256(value: str) -> str:
    """A hash claimed by a caller, normalised to lowercase hex."""
    normalised = value.strip().lower()
    if not SHA256_PATTERN.match(normalised):
        raise ValidationFailedError("content_sha256 must be 64 hexadecimal characters")
    return normalised
