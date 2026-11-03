"""Binds approvals to artifact version id + content sha256.

An approval names the version and the hash of the content the reviewer saw. Both must match the stored
version, and that version must still be the artifact's current one.
"""

from app.modules.artifacts.hashing import parse_sha256
from app.modules.artifacts.service import VersionRecord
from app.modules.errors import ConflictError


def check_binding(version: VersionRecord, claimed_sha256: str) -> str:
    claimed = parse_sha256(claimed_sha256)
    if claimed != version.content_sha256:
        raise ConflictError(
            f"The content you reviewed (hash {claimed[:12]}...) is not version {version.version_no} "
            f"(hash {version.content_sha256[:12]}...); reload and review again"
        )
    if not version.is_current:
        raise ConflictError(f"Version {version.version_no} has been replaced by a newer version; review the current one")
    return claimed
