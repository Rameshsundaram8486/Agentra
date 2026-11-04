"""Incident data accepted from and returned to callers."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]
IncidentStatus = Literal["open", "resolved", "closed"]
CauseCertainty = Literal["confirmed", "probable", "unknown"]


class RcaCreate(BaseModel):
    """A root-cause analysis. Facts come from the recorded evidence; what people add is labelled by certainty."""

    cause: str = Field(min_length=3, max_length=4000)
    cause_certainty: CauseCertainty = Field(description="confirmed by evidence, probable, or unknown (then list the evidence needed)")
    contributing_factors: str = Field(default="", max_length=4000)
    containment: str = Field(min_length=3, max_length=4000, description="What was done to limit the impact")
    corrective_action: str = Field(min_length=3, max_length=4000)
    action_owner_email: str = Field(max_length=320, description="A person on the project who owns the corrective action")
    target_date: date
    verification_criteria: str = Field(min_length=3, max_length=4000, description="How we will know the fix works")


class IncidentClose(BaseModel):
    verification_evidence: str = Field(min_length=10, max_length=4000, description="What showed the corrective action works")


class IncidentEventView(BaseModel):
    event: Literal["recurrence", "resolved", "closed"]
    actor_id: uuid.UUID
    actor_name: str | None
    data: dict[str, Any]
    created_at: datetime


class RcaView(BaseModel):
    cause: str
    cause_certainty: CauseCertainty
    contributing_factors: str
    containment: str
    corrective_action: str
    action_owner_name: str | None
    target_date: date
    verification_criteria: str
    resolved_by: uuid.UUID
    resolved_by_name: str | None
    resolved_at: datetime


class IncidentView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    incident_id: str  # INC-001
    title: str
    category: str
    severity: Severity
    status: IncidentStatus
    source_type: str
    source_id: uuid.UUID
    task_id: uuid.UUID | None
    task_key: str | None
    evidence: dict[str, Any] = Field(description="Observed facts captured when the incident opened")
    occurrences: int
    rca: RcaView | None
    closed_by_name: str | None
    verification_evidence: str | None
    events: list[IncidentEventView]
    opened_at: datetime
