"""Design reviews: what callers hand in for a review and what they get back."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ReviewKind = Literal["security", "feasibility"]
SecurityVerdict = Literal["addressed", "gap", "not_applicable"]
FeasibilityVerdict = Literal["feasible", "concerns", "not_feasible"]
Severity = Literal["high", "medium", "low"]
Complexity = Literal["S", "M", "L"]

# Artifact type and document title per review kind.
REVIEW_TYPES: dict[str, tuple[str, str]] = {
    "security": ("security_review", "Security review"),
    "feasibility": ("feasibility_review", "Feasibility review"),
}
# Findings the Solution Architect must answer when it redrafts the design.
OPEN_VERDICTS: dict[str, tuple[str, ...]] = {"security": ("gap",), "feasibility": ("concerns", "not_feasible")}


class FindingDraft(BaseModel):
    ref: str = Field(description="A checklist ID (SC-01) for security, a design item ID for feasibility")
    verdict: str
    severity: Severity | None = None
    complexity: Complexity | None = None
    assessment: str
    recommendation: str = ""
    design_items: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)


class ReviewReply(BaseModel):
    approval_id: uuid.UUID
    comment: str
    response: str


class ReviewDraft(BaseModel):
    kind: ReviewKind
    design_version_id: uuid.UUID
    summary: str
    findings: list[FindingDraft] = Field(min_length=1)
    change_summary: str
    review_responses: list[ReviewReply] = Field(default_factory=list)


class FindingView(BaseModel):
    ref: str
    title: str
    verdict: str
    severity: Severity | None
    complexity: Complexity | None
    assessment: str
    recommendation: str
    design_items: list[str]
    requirements: list[str]
    unverified: list[str]


class ReviewView(BaseModel):
    kind: ReviewKind
    artifact_id: uuid.UUID
    artifact_title: str
    version_id: uuid.UUID
    version_no: int
    approval_status: str
    design_version_id: uuid.UUID
    design_version_no: int
    current: bool = Field(description="It reviews the current, non-stale design version")
    checklist: str | None
    summary: str
    counts: dict[str, int] = Field(description="Findings per verdict")
    blocking: list[str] = Field(description="Why this review stops the design from being approved, if it does")
    findings: list[FindingView]
    review_responses: list[ReviewReply]
    created_at: datetime


class OpenFinding(BaseModel):
    """A gap or concern the Solution Architect must answer in its next draft."""

    kind: ReviewKind
    review_version_no: int
    design_version_no: int
    ref: str
    title: str
    verdict: str
    severity: Severity | None
    assessment: str
    recommendation: str

    @property
    def label(self) -> str:
        detail = f"{self.verdict}, {self.severity}" if self.severity else self.verdict.replace("_", " ")
        return f"{self.kind.title()} review v{self.review_version_no}: {self.ref} ({detail})"


class DesignReviewsView(BaseModel):
    design_version_id: uuid.UUID | None
    design_version_no: int | None
    security: ReviewView | None
    feasibility: ReviewView | None
    gate: list[str] = Field(description="What still stops the current design version from being approved, as far as reviews go")
