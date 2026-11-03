from pathlib import Path

import pytest

from app.infrastructure.storage.base import ContentIntegrityError, sha256_hex
from app.infrastructure.storage.local import LocalArtifactStore


def test_put_returns_the_sha256_and_get_returns_the_same_bytes(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    content = "# Requirements\n\nREQ-F-001: Staff can submit leave.\n".encode()

    digest = store.put(content)

    assert digest == sha256_hex(content)
    assert store.get(digest) == content
    assert (tmp_path / digest[:2] / digest).is_file()


def test_identical_content_is_stored_once(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    first, second = store.put(b"same"), store.put(b"same")

    assert first == second
    assert len(list(tmp_path.rglob("*"))) == 2  # one folder, one file


def test_content_changed_on_disk_is_detected(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    digest = store.put(b"approved text")
    (tmp_path / digest[:2] / digest).write_bytes(b"quietly changed text")

    with pytest.raises(ContentIntegrityError, match="no longer matches"):
        store.get(digest)


def test_missing_content_is_detected(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ContentIntegrityError, match="missing"):
        store.get("a" * 64)


@pytest.mark.parametrize("bad", ["../../etc/passwd", "A" * 64, "abc", "g" * 64])
def test_only_sha256_names_are_accepted(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        LocalArtifactStore(tmp_path).get(bad)
