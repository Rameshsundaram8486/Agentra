"""Developer Agent, task review_feasibility: rates whether each design item of one design version can be built as
described (Phase 8). Code, configuration and unit tests in sandbox VMs (Phase 9) are not built yet.

The output becomes a version of the project's Feasibility review document with one finding per design item
(app/modules/design_reviews). A design version with an item rated not feasible cannot be approved; concerns go to
the Solution Architect's next draft. The shared prepare, check and apply steps are in app/agents/design_review.py.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.business_analyst.agent import _text
from app.agents.business_analyst.draft import ReviewReply
from app.agents.design_review import DesignReviewTask
from app.modules.design_reviews.service import FindingDraft


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeasibilityFindingOut(_Out):
    design_item: _text(20)
    verdict: Literal["feasible", "concerns", "not_feasible"]
    complexity: Literal["S", "M", "L"]
    assessment: _text(1200)
    recommendation: _text(1000, min_length=0)
    related_items: list[_text(20)] = Field(max_length=10)
    unverified_capabilities: list[_text(300)] = Field(max_length=5)


class ReviewFeasibilityOutput(_Out):
    summary: _text(2500)
    findings: list[FeasibilityFindingOut] = Field(min_length=1, max_length=200)
    review_responses: list[ReviewReply] = Field(max_length=30)


class ReviewFeasibility(DesignReviewTask):
    agent_key = "developer"
    task_key = "review_feasibility"
    output_model = ReviewFeasibilityOutput
    kind = "feasibility"
    instructions = "Rate every design item except open questions, as described in your instructions."

    def findings_of(self, output: ReviewFeasibilityOutput) -> list[FindingDraft]:  # type: ignore[override]
        return [
            FindingDraft(
                ref=f.design_item,
                verdict=f.verdict,
                complexity=f.complexity,
                assessment=f.assessment,
                recommendation=f.recommendation,
                design_items=list(f.related_items),
                unverified=list(f.unverified_capabilities),
            )
            for f in output.findings
        ]
