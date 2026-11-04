"""Security Reviewer Agent, task review_security: answers the security checklist for one design version.

The output becomes a version of the project's Security review document with one finding per check
(app/modules/design_reviews). A person with the reviewer role signs it off by approving it; a design version can be
approved only with a signed-off security review of that exact version, and a review with a high-severity gap
cannot be signed off. The shared prepare, check and apply steps are in app/agents/design_review.py.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.business_analyst.agent import _text
from app.agents.business_analyst.draft import ReviewReply
from app.agents.design_review import DesignReviewTask
from app.modules.design_reviews.service import FindingDraft


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SecurityFindingOut(_Out):
    check: _text(10)
    verdict: Literal["addressed", "gap", "not_applicable"]
    severity: Literal["high", "medium", "low"] | None
    assessment: _text(1500)
    recommendation: _text(1000, min_length=0)
    design_items: list[_text(20)] = Field(max_length=15)
    requirements: list[_text(20)] = Field(max_length=15)
    unverified_capabilities: list[_text(300)] = Field(max_length=5)


class ReviewSecurityOutput(_Out):
    summary: _text(2500)
    findings: list[SecurityFindingOut] = Field(min_length=1, max_length=30)
    review_responses: list[ReviewReply] = Field(max_length=30)


class ReviewSecurity(DesignReviewTask):
    agent_key = "security_reviewer"
    task_key = "review_security"
    output_model = ReviewSecurityOutput
    kind = "security"
    instructions = "Answer every check in the security checklist for this design, as described in your instructions."

    def findings_of(self, output: ReviewSecurityOutput) -> list[FindingDraft]:  # type: ignore[override]
        return [
            FindingDraft(
                ref=f.check,
                verdict=f.verdict,
                severity=f.severity,
                assessment=f.assessment,
                recommendation=f.recommendation,
                design_items=list(f.design_items),
                requirements=list(f.requirements),
                unverified=list(f.unverified_capabilities),
            )
            for f in output.findings
        ]
