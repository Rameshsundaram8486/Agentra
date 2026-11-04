"""Design items: what callers hand in for a draft and what they get back."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal[
    "component", "data_flow", "interface", "entity", "security_control",
    "environment", "decision", "risk", "open_question",
]
Label = Literal["fact", "assumption", "suggestion", "open_question"]
Status = Literal["confirmed", "proposed", "open"]

# Stable IDs assigned by the server, per project, never reused.
PREFIXES: dict[str, str] = {
    "component": "CMP",
    "data_flow": "DF",
    "interface": "API",
    "entity": "ENT",
    "security_control": "SEC",
    "environment": "ENV",
    "decision": "ADR",
    "risk": "RSK",
    "open_question": "DQ",
}
KIND_TITLES: dict[str, str] = {
    "component": "Components",
    "data_flow": "Data flows",
    "interface": "Interfaces and integrations",
    "entity": "Data model",
    "security_control": "Security controls",
    "environment": "Environments and deployment",
    "decision": "Architecture decisions",
    "risk": "Technical risks",
    "open_question": "Open questions",
}


class DesignSource(BaseModel):
    """What a design item rests on: a requirement, a quote in a document version, or a decision record."""

    type: Literal["requirement", "document", "decision"]
    name: str
    artifact_version_id: uuid.UUID | None = None
    decision_id: uuid.UUID | None = None
    quote: str = ""
    answer: str | None = None


class QualityFlag(BaseModel):
    check: str
    severity: Literal["warning", "info"]
    message: str
    related: list[str] = Field(default_factory=list)


class DesignDraftItem(BaseModel):
    ref: str = Field(description="An existing design item ID to keep it, or any other key for a new item")
    kind: Kind
    title: str
    description: str
    rationale: str = ""
    label: Label
    satisfies: list[str] = Field(default_factory=list, description="Requirement IDs it satisfies")
    related: list[str] = Field(default_factory=list, description="Refs of other design items in the draft")
    unverified_capabilities: list[str] = Field(default_factory=list)
    sources: list[DesignSource] = Field(min_length=1)


class RequirementException(BaseModel):
    requirement_id: str
    reason: str


class ReviewResponse(BaseModel):
    """The architect's answer to a reviewer's comment (approval_id) or to a security or feasibility review finding."""

    approval_id: uuid.UUID | None = None
    finding: str | None = None  # e.g. "Security review v1: SC-03 (gap, high)"
    comment: str
    response: str


class DesignDraft(BaseModel):
    requirements_version_id: uuid.UUID = Field(description="The approved requirements version it was designed against")
    summary: str
    component_diagram: str
    data_flow_diagram: str
    items: list[DesignDraftItem] = Field(min_length=1)
    exceptions: list[RequirementException] = Field(default_factory=list)
    input_refs: list[str]
    change_summary: str
    review_responses: list[ReviewResponse] = Field(default_factory=list)


class DesignItemView(BaseModel):
    item_id: str
    kind: Kind
    title: str
    description: str
    rationale: str
    label: Label
    status: Status
    satisfies: list[str]
    related: list[str]
    unverified_capabilities: list[str]
    sources: list[DesignSource]
    quality_flags: list[QualityFlag]


class CoverageRow(BaseModel):
    requirement_id: str
    kind: str
    title: str
    status: str  # the requirement's status
    design_items: list[str]
    exception: str | None


class Coverage(BaseModel):
    confirmed: int = Field(description="Confirmed requirements that must be covered")
    covered: int
    excepted: int
    gaps: list[str] = Field(description="Confirmed requirement IDs neither mapped nor excepted")
    rows: list[CoverageRow]


class DesignView(BaseModel):
    artifact_id: uuid.UUID
    artifact_title: str
    version_id: uuid.UUID
    version_no: int
    approval_status: str
    locked: bool
    stale: bool
    stale_reason: str | None
    requirements_version_no: int
    summary: str
    component_diagram: str
    data_flow_diagram: str
    set_flags: list[QualityFlag]
    counts: dict[str, int]
    added: list[str]
    removed: list[str]
    review_responses: list[ReviewResponse]
    exceptions: list[RequirementException]
    coverage: Coverage
    items: list[DesignItemView]
    created_at: datetime


class DraftResult(BaseModel):
    view: DesignView
    ids: dict[str, str]
