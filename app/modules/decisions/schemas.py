"""Approval and decision data accepted from and returned to callers."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ApprovalDecision = Literal["approved", "rejected", "changes_requested"]
ApprovalStatus = Literal["approved", "rejected", "changes_requested", "pending"]
OutcomeAction = Literal["accept", "select_option", "other", "modify", "reject", "defer"]
DecisionStatus = Literal["open", "deferred", "decided"]


class ApprovalCreate(BaseModel):
    decision: ApprovalDecision
    content_sha256: str = Field(description="Hash of the content the approver actually reviewed")
    comment: str | None = Field(default=None, max_length=4000)


class ApprovalView(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    artifact_version_id: uuid.UUID
    version_no: int
    content_sha256: str
    decision: ApprovalDecision
    approver_id: uuid.UUID
    approver_name: str | None
    comment: str | None
    created_at: datetime


class VersionApprovalState(BaseModel):
    version_id: uuid.UUID
    version_no: int
    status: ApprovalStatus
    latest: ApprovalView | None


class ArtifactApprovals(BaseModel):
    current: VersionApprovalState
    history: list[ApprovalView]


class DecisionOption(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class DecisionRequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=10000)
    options: list[DecisionOption] = Field(min_length=2, max_length=10)
    recommended_option: str | None = None
    recommendation_rationale: str = Field(default="", max_length=10000)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=20)
    artifact_version_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "DecisionRequestCreate":
        keys = [option.key for option in self.options]
        if len(keys) != len(set(keys)):
            raise ValueError("option keys must be unique")
        if self.recommended_option is not None:
            if self.recommended_option not in keys:
                raise ValueError("recommended_option must be one of the option keys")
            if not self.recommendation_rationale.strip():
                raise ValueError("a recommendation needs a rationale")
        return self


class DecisionOutcomeCreate(BaseModel):
    action: OutcomeAction
    selected_option: str | None = None
    custom_choice: str | None = Field(default=None, max_length=4000)
    comment: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _fields_match_action(self) -> "DecisionOutcomeCreate":
        def blank(value: str | None) -> bool:
            return value is None or not value.strip()

        if (self.action == "select_option") == (self.selected_option is None):
            raise ValueError("selected_option is required for select_option and not allowed otherwise")
        if (self.action == "other") == blank(self.custom_choice):
            raise ValueError("custom_choice is required for other and not allowed otherwise")
        if self.action in ("modify", "reject", "defer") and blank(self.comment):
            raise ValueError(f"a comment is required to {self.action}")
        return self


class DecisionOutcomeView(BaseModel):
    outcome_no: int
    action: OutcomeAction
    selected_option: str | None
    custom_choice: str | None
    comment: str | None
    decided_by: uuid.UUID
    decided_by_name: str | None
    created_at: datetime


class DecisionView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    question: str
    context: str | None
    options: list[DecisionOption]
    recommended_option: str | None
    recommendation_rationale: str
    assumptions: list[str]
    risks: list[str]
    artifact_version_id: uuid.UUID | None
    raised_by: uuid.UUID
    raised_by_name: str | None
    created_at: datetime
    status: DecisionStatus
    final_choice: str | None = Field(description="What was chosen, in words; None while open or if rejected")
    outcomes: list[DecisionOutcomeView]
