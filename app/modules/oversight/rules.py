"""Loads config/policies/incident_rules.yaml: which failures open an incident and how severe they are."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.modules.oversight.schemas import Severity


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CodeRule(_Frozen):
    open: bool
    severity: Severity


class ClosingRule(_Frozen):
    independent_verification: bool = True


class IncidentRules(_Frozen):
    version: int
    default: CodeRule
    codes: dict[str, CodeRule]
    closing: ClosingRule = ClosingRule()

    def for_code(self, code: str | None) -> CodeRule:
        return self.codes.get(code or "", self.default)


def load_incident_rules(path: Path) -> IncidentRules:
    with path.open(encoding="utf-8") as handle:
        return IncidentRules.model_validate(yaml.safe_load(handle))
