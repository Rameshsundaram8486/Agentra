"""Loads and validates config/policies/change_sets.yaml."""

from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

WorkType = Literal["build", "configure", "integrate", "migrate", "deploy"]


class ChangeSetPolicyError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Limits(_Strict):
    max_files: int = Field(ge=1, le=200)
    max_file_bytes: int = Field(ge=1000, le=2_000_000)
    max_total_bytes: int = Field(ge=1000, le=10_000_000)
    context_bytes: int = Field(ge=1000, le=1_000_000)


class SandboxSettings(_Strict):
    timeout_seconds: int = Field(ge=30, le=7200)


class ChangeSetPolicy(_Strict):
    version: int
    limits: Limits
    protected_paths: tuple[str, ...]
    test_paths: tuple[str, ...] = Field(min_length=1)
    tests_required_for: tuple[WorkType, ...]
    sandbox: SandboxSettings

    def protected(self, path: str) -> bool:
        return _matches(path, self.protected_paths)

    def is_test(self, path: str) -> bool:
        return _matches(path, self.test_paths)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    parts = PurePosixPath(path).parts
    folders, name = [p.lower() for p in parts[:-1]], parts[-1] if parts else ""
    for pattern in patterns:
        if pattern.endswith("/"):
            if pattern[:-1].lower() in folders:
                return True
        elif fnmatchcase(name.lower(), pattern.lower()):
            return True
    return False


def load_change_set_policy(path: Path) -> ChangeSetPolicy:
    try:
        with path.open(encoding="utf-8") as handle:
            return ChangeSetPolicy.model_validate(yaml.safe_load(handle))
    except (OSError, ValidationError) as exc:
        raise ChangeSetPolicyError(f"invalid change set policy {path.name}: {exc}") from exc
