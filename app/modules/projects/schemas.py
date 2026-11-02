"""Project data accepted from and returned to callers."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,31}$", description="Short unique code, e.g. ACME-INTRANET")
    name: str = Field(min_length=1, max_length=200)
    customer_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class ProjectView(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    customer_name: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
