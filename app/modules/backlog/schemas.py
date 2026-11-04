"""Implementation backlog: what callers hand in for a draft and what they get back."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WorkType = Literal["build", "configure", "integrate", "migrate", "deploy"]
Estimate = Literal["S", "M", "L"]
EPIC_PREFIX = "EP"
ITEM_PREFIX = "WI"
# Design items a backlog must plan work for; decisions, risks and open questions shape the work but are not built.
BUILDABLE_KINDS = ("component", "data_flow", "interface", "entity", "security_control", "environment")


class EpicDraft(BaseModel):
    ref: str = Field(description="An existing epic ID (EP-001) to keep it, or a new-... ref")
    title: str
    description: str


class WorkItemDraft(BaseModel):
    ref: str = Field(description="An existing work item ID (WI-001) to keep it, or a new-... ref")
    epic: str = Field(description="Ref of its epic in the same draft")
    title: str
    description: str
    work_type: WorkType
    design_items: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list, description="Acceptance criteria refs such as REQ-F-001.AC1")
    estimate: Estimate
    depends_on: list[str] = Field(default_factory=list, description="Refs of work items in the same draft")
    wave: int = Field(ge=1, le=12)


class BacklogReply(BaseModel):
    approval_id: uuid.UUID
    comment: str
    response: str


class BacklogDraft(BaseModel):
    design_version_id: uuid.UUID
    summary: str
    epics: list[EpicDraft] = Field(min_length=1)
    items: list[WorkItemDraft] = Field(min_length=1)
    change_summary: str
    review_responses: list[BacklogReply] = Field(default_factory=list)


class EpicView(BaseModel):
    epic_id: str
    title: str
    description: str


class WorkItemView(BaseModel):
    item_id: str
    epic_id: str
    title: str
    description: str
    work_type: WorkType
    design_items: list[str]
    requirements: list[str]
    acceptance: list[str]
    estimate: Estimate
    depends_on: list[str]
    wave: int


class BacklogView(BaseModel):
    artifact_id: uuid.UUID
    artifact_title: str
    version_id: uuid.UUID
    version_no: int
    approval_status: str
    design_version_id: uuid.UUID
    design_version_no: int
    stale: bool
    stale_reason: str | None
    summary: str
    epics: list[EpicView]
    items: list[WorkItemView]
    estimates: dict[str, int] = Field(description="Work items per size")
    waves: dict[int, int] = Field(description="Work items per wave")
    review_responses: list[BacklogReply]
    created_at: datetime


class BacklogResult(BaseModel):
    view: BacklogView
    ids: dict[str, str]
