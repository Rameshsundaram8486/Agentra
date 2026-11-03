"""Local filesystem storage for development: <root>/<first two hex chars>/<sha256>."""

import os
import uuid
from pathlib import Path

from app.infrastructure.storage.base import SHA256_PATTERN, ContentIntegrityError, sha256_hex


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha256: str) -> Path:
        # Also stops path traversal: only 64 lowercase hex characters are ever used as a file name.
        if not SHA256_PATTERN.match(sha256):
            raise ValueError("not a sha256 hex digest")
        return self._root / sha256[:2] / sha256

    def put(self, content: bytes) -> str:
        digest = sha256_hex(content)
        path = self._path(digest)
        if path.exists():
            return digest
        path.parent.mkdir(exist_ok=True)
        temporary = path.with_name(f"{digest}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)  # atomic: readers never see a half-written file
        return digest

    def get(self, sha256: str) -> bytes:
        try:
            content = self._path(sha256).read_bytes()
        except FileNotFoundError as exc:
            raise ContentIntegrityError(f"content {sha256[:12]} is missing from the store") from exc
        if sha256_hex(content) != sha256:
            raise ContentIntegrityError(f"content {sha256[:12]} no longer matches its hash")
        return content
