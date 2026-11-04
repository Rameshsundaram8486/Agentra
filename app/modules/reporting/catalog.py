"""Loads config/policies/report_visibility.yaml: the report types and which ones customer approvers may see."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReportType(_Frozen):
    title: str
    phase: int
    customer_visible: bool


class ReportCatalog(_Frozen):
    version: int
    report_types: dict[str, ReportType]

    def get(self, key: str) -> ReportType | None:
        return self.report_types.get(key)


def load_report_catalog(path: Path) -> ReportCatalog:
    with path.open(encoding="utf-8") as handle:
        return ReportCatalog.model_validate(yaml.safe_load(handle))
