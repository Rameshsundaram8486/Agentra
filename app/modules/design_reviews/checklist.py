"""Loads config/policies/security_checklist.yaml: the checks every security review of a design answers."""

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Check(_Frozen):
    title: str = Field(min_length=3)
    question: str = Field(min_length=10)


class SecurityChecklist(_Frozen):
    version: int
    checks: dict[str, Check] = Field(min_length=1)
    sha256: str = ""  # of the file, recorded on every review

    @property
    def label(self) -> str:
        return f"security_checklist v{self.version} (sha256 {self.sha256[:12]})"


def load_security_checklist(path: Path) -> SecurityChecklist:
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    for key in (data or {}).get("checks", {}):
        if not (isinstance(key, str) and key.startswith("SC-") and key[3:].isdigit()):
            raise ValueError(f"{path.name}: check IDs look like SC-01, not {key!r}")
    return SecurityChecklist.model_validate({**data, "sha256": hashlib.sha256(raw).hexdigest()})
