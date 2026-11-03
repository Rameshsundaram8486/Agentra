"""Content-addressed storage interface (sha256).

Content is stored under its own SHA-256, so identical bytes are stored once and every read can prove
the bytes are unchanged.
"""

import hashlib
import re
from typing import Protocol

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ContentIntegrityError(Exception):
    """Stored content is missing or no longer matches its hash."""


class ArtifactStore(Protocol):
    def put(self, content: bytes) -> str:
        """Stores content and returns its sha256."""
        ...

    def get(self, sha256: str) -> bytes:
        """Returns content after verifying it still hashes to sha256; raises ContentIntegrityError otherwise."""
        ...
