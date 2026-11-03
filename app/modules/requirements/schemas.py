"""Requirement items: what callers hand in for a draft and what they get back."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal[
    "objective", "stakeholder", "functional", "non_functional", "user_story",
    "business_rule", "assumption", "dependency", "open_question",
]
Label = Literal["fact", "assumption", "suggestion", "open_question"]
Status = Literal["confirmed", "proposed", "open"]
Priority = Literal["must", "should", "could", "not_set"]

# Stable item IDs are assigned by the server: prefix plus a per-project number, never reused.
PREFIXES: dict[str, str] = {
    "objective": "OBJ",
    "stakeholder": "STK",
    "functional": "REQ-F",
    "non_functional": "REQ-NF",
    "user_story": "US",
    "business_rule": "BR",
    "assumption": "ASM",
    "dependency": "DEP",
    "open_question": "Q",
}
KIND_TITLES: dict[str, str] = {
    "objective": "Objectives",
    "stakeholder": "Stakeholders and roles",
    "functional": "Functional requirements",
    "non_functional": "Non-functional requirements",
    "user_story": "User stories",
    "business_rule": "Business rules",
    "assumption": "Assumptions",
    "dependency": "Dependencies",
    "open_question": "Open questions",
}


class SourceRef(BaseModel):
    """Where an item comes from: a quote in a document version, or a decision record."""

    type: Literal["document", "decision"]
    artifact_version_id: uuid.UUID | None = None
    decision_id: uuid.UUID | None = None
    name: str = Field(description="Document title and version, or decision title")
    quote: str = ""
    answer: str | None = Field(default=None, description="For a decision: what was chosen, or None if not answered")


class QualityFlag(BaseModel):
    check: str
    severity: Literal["warning", "info"]
    message: str
    related: list[str] = Field(default_factory=list)


class DraftItem(BaseModel):
    ref: str = Field(description="An existing item ID to keep it, or any other key for a new item")
    kind: Kind
    title: str
    statement: str
    label: Label
    priority: Priority
    acceptance_criteria: list[str]
    sources: list[SourceRef] = Field(min_length=1)


class RequirementsDraft(BaseModel):
    summary: str
    process_flow_mermaid: str
    items: list[DraftItem] = Field(min_length=1)
    input_refs: list[str] = Field(description="The inputs it was drafted from, recorded on the document version")
    change_summary: str


class RequirementItemView(BaseModel):
    item_id: str
    kind: Kind
    title: str
    statement: str
    label: Label
    status: Status
    priority: Priority
    acceptance_criteria: list[str]
    sources: list[SourceRef]
    quality_flags: list[QualityFlag]


class RequirementsView(BaseModel):
    artifact_id: uuid.UUID
    artifact_title: str
    version_id: uuid.UUID
    version_no: int
    approval_status: str
    summary: str
    process_flow_mermaid: str
    set_flags: list[QualityFlag]
    counts: dict[str, int] = Field(description="Items per status")
    added: list[str] = Field(description="Item IDs new in this version")
    removed: list[str] = Field(description="Item IDs in the previous version but not this one")
    items: list[RequirementItemView]
    created_at: datetime


class DraftResult(BaseModel):
    view: RequirementsView
    ids: dict[str, str] = Field(description="Draft ref -> assigned item ID")
