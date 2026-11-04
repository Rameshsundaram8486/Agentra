"""Report data accepted from and returned to callers."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    report_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")


class ReportView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    report_type: str
    title: str
    version_no: int
    customer_visible: bool
    generated_by: uuid.UUID
    generated_by_name: str | None
    generated_at: datetime
    data_as_of: datetime | None
    data_sha256: str
    content_sha256: str
    template_version: str
    sources: list[str]


class GenerateResult(BaseModel):
    report: ReportView
    created: bool = Field(description="False when nothing changed since the latest version, which is returned instead")


class ReportTypeView(BaseModel):
    key: str
    title: str
    customer_visible: bool
