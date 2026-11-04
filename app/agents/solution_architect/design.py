"""Solution Architect Agent, task draft_design: drafts the solution design on the chosen option.

The output becomes a new version of the project's design baseline document with a record per design item, tied to
the approved requirements version (app/modules/design). IDs, statuses and requirement coverage are computed by
the server. Open questions are raised as decisions; the workflow task then waits for input, otherwise for review.
"""

import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.base import ApplyResult, PreparedPrompt
from app.agents.business_analyst.agent import Answer, _text, _unique_keys, option_key
from app.agents.business_analyst.draft import Citation, ReviewReply
from app.agents.solution_architect.inputs import gather
from app.composition import Services
from app.guardrails.findings import Finding
from app.harness.registry import TaskDefinition
from app.modules.decisions.schemas import DecisionOption, DecisionRequestCreate
from app.modules.design.schemas import Kind, Label
from app.modules.design.service import DesignDraft, DesignDraftItem, DesignSource, RequirementException, ReviewResponse, parse_item_id
from app.modules.errors import ValidationFailedError
from app.modules.executions.schemas import StartedRun

_NEW_REF = re.compile(r"^new-\d+$")


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DesignItemOut(_Out):
    ref: _text(40)
    kind: Kind
    title: _text(150)
    description: _text(2500)
    rationale: _text(1500, min_length=0)
    label: Label
    satisfies: list[_text(20)] = Field(max_length=40)
    related: list[_text(40)] = Field(max_length=20)
    unverified_capabilities: list[_text(300)] = Field(max_length=6)
    sources: list[Citation] = Field(min_length=1, max_length=6)
    suggested_answers: list[Answer] = Field(max_length=4)
    recommended_answer: _text(64) | None
    recommendation_rationale: _text(1500, min_length=0)

    @model_validator(mode="after")
    def _consistent(self) -> "DesignItemOut":
        if self.kind == "open_question":
            if self.label != "open_question":
                raise ValueError("an open_question item must be labelled open_question")
            if len(self.suggested_answers) < 2:
                raise ValueError("an open question needs at least two suggested answers")
            _unique_keys([a.key for a in self.suggested_answers], "answer")
            if self.recommended_answer is not None:
                if option_key(self.recommended_answer) not in {option_key(a.key) for a in self.suggested_answers}:
                    raise ValueError("recommended_answer must be one of the suggested answer keys")
                if not self.recommendation_rationale:
                    raise ValueError("a recommended answer needs a rationale")
        elif self.suggested_answers or self.recommended_answer is not None:
            raise ValueError("only open_question items have suggested answers")
        return self


class ExceptionOut(_Out):
    requirement_id: _text(20)
    reason: _text(800)


class DraftDesignOutput(_Out):
    summary: _text(3000)
    component_diagram: _text(6000, min_length=0)
    data_flow_diagram: _text(6000, min_length=0)
    items: list[DesignItemOut] = Field(min_length=3, max_length=200)
    exceptions: list[ExceptionOut] = Field(max_length=150)
    review_responses: list[ReviewReply] = Field(max_length=50)


class DraftDesign:
    agent_key = "solution_architect"
    task_key = "draft_design"
    output_model = DraftDesignOutput

    def prepare(self, services: Services, run: StartedRun, definition: TaskDefinition) -> PreparedPrompt:
        if problem := services.design.baseline_problem(run.project_id):
            raise ValidationFailedError(problem)
        gathered = gather(services, run, definition, design=True)
        return PreparedPrompt(
            user=gathered.text,
            sources=gathered.sources,
            input_findings=gathered.findings,
            extras={
                "requirements_version_id": gathered.requirements.id,
                "requirement_ids": gathered.requirement_ids,
                "document_ids": gathered.document_ids,
                "document_names": gathered.document_names,
                "decisions": gathered.decisions,
                "reviews": gathered.reviews,
                "findings": gathered.review_findings,
                "known_ids": {item.item_id: item.kind for item in gathered.current_design},
            },
        )

    def check(self, output: DraftDesignOutput, prepared: PreparedPrompt) -> list[Finding]:  # type: ignore[override]
        """IDs are the server's; links stay inside the output; requirement IDs must exist in the approved version;
        every review comment and review finding gets exactly one response."""
        known: dict[str, str] = prepared.extras["known_ids"]
        requirement_ids: set[str] = prepared.extras["requirement_ids"]
        findings, seen = [], set()
        for index, item in enumerate(output.items):
            path = f"items[{index}]"
            if item.ref in seen:
                findings.append(Finding("item_ref", "block", f"Ref {item.ref} is used by more than one item", f"{path}.ref"))
            seen.add(item.ref)
            if item.ref in known:
                if known[item.ref] != item.kind:
                    findings.append(Finding("item_ref", "block", f"{item.ref} is a {known[item.ref]} item; it cannot become {item.kind}", f"{path}.ref"))
            elif parse_item_id(item.ref) or not _NEW_REF.match(item.ref):
                findings.append(Finding("item_ref", "block", f"{item.ref!r} is not an existing design item ID or a new-n ref", f"{path}.ref"))
            for rid in item.satisfies:
                if rid not in requirement_ids:
                    findings.append(Finding("requirement_ref", "block", f"Satisfies {rid!r}, which is not an approved requirement ID", f"{path}.satisfies"))
        for index, item in enumerate(output.items):
            for ref in item.related:
                if ref not in seen:
                    findings.append(Finding("item_ref", "block", f"Links to {ref!r}, which is not an item in this output", f"items[{index}].related"))
        for index, exception in enumerate(output.exceptions):
            if exception.requirement_id not in requirement_ids:
                findings.append(Finding("requirement_ref", "block", f"Exception for {exception.requirement_id!r}, which is not an approved requirement ID", f"exceptions[{index}]"))
        to_answer = [*prepared.extras["reviews"], *prepared.extras["findings"]]
        answered = [reply.ref for reply in output.review_responses]
        for ref in to_answer:
            if answered.count(ref) != 1:
                what = "Review finding" if ref.startswith("FND-") else "Review comment"
                findings.append(Finding("review", "block", f"{what} {ref} needs exactly one response (it has {answered.count(ref)})", "review_responses"))
        for ref in sorted(set(answered) - set(to_answer)):
            findings.append(Finding("review", "block", f"Responds to {ref}, which is not a review comment or finding it was given", "review_responses"))
        return findings

    def apply(self, services: Services, run: StartedRun, output: DraftDesignOutput, prepared: PreparedPrompt) -> ApplyResult:  # type: ignore[override]
        extras = prepared.extras
        decisions: dict[str, tuple[uuid.UUID, str, str | None]] = extras["decisions"]
        reviews: dict[str, tuple[uuid.UUID, str]] = extras["reviews"]
        review_findings = extras["findings"]

        def response(ref: str, text: str) -> ReviewResponse:
            if ref in reviews:
                return ReviewResponse(approval_id=reviews[ref][0], comment=reviews[ref][1], response=text)
            finding = review_findings[ref]
            return ReviewResponse(finding=finding.label, comment=f"{finding.title}: {finding.assessment}", response=text)

        def source(c: Citation) -> DesignSource:
            if c.ref in decisions:
                decision_id, title, answer = decisions[c.ref]
                return DesignSource(type="decision", name=title, decision_id=decision_id, answer=answer)
            if c.ref in extras["document_ids"]:
                return DesignSource(type="document", name=extras["document_names"][c.ref], artifact_version_id=extras["document_ids"][c.ref], quote=c.quote)
            return DesignSource(type="requirement", name=c.ref)

        draft = DesignDraft(
            requirements_version_id=extras["requirements_version_id"],
            summary=output.summary,
            component_diagram=output.component_diagram,
            data_flow_diagram=output.data_flow_diagram,
            items=[
                DesignDraftItem(
                    ref=i.ref,
                    kind=i.kind,
                    title=i.title,
                    description=i.description,
                    rationale=i.rationale,
                    label=i.label,
                    satisfies=list(i.satisfies),
                    related=list(i.related),
                    unverified_capabilities=list(i.unverified_capabilities),
                    sources=[source(c) for c in i.sources],
                )
                for i in output.items
            ],
            exceptions=[RequirementException(requirement_id=e.requirement_id, reason=e.reason) for e in output.exceptions],
            input_refs=[f"{ref}: {name}" for ref, name in extras["document_names"].items()]
            + [f"{ref}: decision '{title}' ({answer or 'not answered yet'})" for ref, (_, title, answer) in decisions.items()],
            change_summary=(
                f"{'Revised' if extras['known_ids'] else 'Drafted'} by the Solution Architect Agent against the approved requirements, "
                f"{len(decisions)} decision(s), {len(reviews)} review comment(s) and {len(review_findings)} review finding(s)"
            ),
            review_responses=[response(r.ref, r.response) for r in output.review_responses],
        )
        result = services.design.record_draft(run.agent, run.project_id, draft)
        version = result.view
        decision_ids = []
        for item in output.items:
            if item.kind != "open_question":
                continue
            item_id = result.ids[item.ref]
            recommended = option_key(item.recommended_answer) if item.recommended_answer else None
            request = DecisionRequestCreate(
                title=f"{item_id}: {item.title}"[:200],
                question=item.description[:4000],
                context=(
                    f"Open question {item_id} in the solution design v{version.version_no}. Raised by the Solution Architect Agent; "
                    "nothing has been decided. If none of the suggested answers fits, choose Other and write your own."
                ),
                options=[DecisionOption(key=option_key(a.key), title=a.title, description=a.description) for a in item.suggested_answers],
                recommended_option=recommended,
                recommendation_rationale=item.recommendation_rationale if recommended else "",
                artifact_version_id=version.version_id,
            )
            decision_ids.append(services.decisions.raise_decision(run.agent, run.project_id, request).id)
        return ApplyResult(
            decision_ids=decision_ids,
            task_state="waiting_for_input" if decision_ids else "waiting_for_review",
            records={
                "design": {
                    "version_id": str(version.version_id),
                    "version_no": version.version_no,
                    "coverage": {"confirmed": version.coverage.confirmed, "covered": version.coverage.covered, "gaps": version.coverage.gaps},
                    "ids": result.ids,
                }
            },
        )
