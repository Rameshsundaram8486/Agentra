"""Solution Architect Agent, task compare_options: compares two to four solution options against weighted criteria
and raises one decision for the project team: which option the design builds on.

The agent scores; Agentra calculates the weighted totals, so a recommendation can be checked against them. If the
agent recommends an option that does not score highest, that is noted on the run and in the decision.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.base import ApplyResult, PreparedPrompt
from app.agents.business_analyst.agent import _text, _unique_keys, option_key
from app.agents.business_analyst.draft import Citation
from app.agents.solution_architect.inputs import gather
from app.composition import Services
from app.guardrails.findings import Finding
from app.harness.registry import TaskDefinition
from app.modules.decisions.schemas import DecisionOption, DecisionRequestCreate
from app.modules.executions.schemas import StartedRun

_FOOTER = "Raised by the Solution Architect Agent. This is a proposal for people to decide; nothing has been decided."


def _fit(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 40].rstrip() + " ... (full detail on the agent run)"


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Criterion(_Out):
    key: _text(40)
    title: _text(120)
    weight: int = Field(ge=1, le=5)
    description: _text(600)


class Score(_Out):
    criterion: _text(40)
    score: int = Field(ge=1, le=5)
    rationale: _text(300)


class Option(_Out):
    key: _text(40)
    title: _text(120)
    description: _text(1000)
    scores: list[Score] = Field(min_length=1, max_length=8)
    pros: list[_text(250)] = Field(max_length=5)
    cons: list[_text(250)] = Field(max_length=5)
    risks: list[_text(250)] = Field(max_length=5)


class CompareOptionsOutput(_Out):
    summary: _text(2000)
    criteria: list[Criterion] = Field(min_length=3, max_length=8)
    options: list[Option] = Field(min_length=2, max_length=4)
    recommended_option: _text(40)
    recommendation_rationale: _text(2500)
    assumptions: list[_text(400)] = Field(max_length=10)
    unverified_capabilities: list[_text(400)] = Field(max_length=10)
    sources: list[Citation] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _complete(self) -> "CompareOptionsOutput":
        _unique_keys([c.key for c in self.criteria], "criterion")
        _unique_keys([o.key for o in self.options], "option")
        criteria = {option_key(c.key) for c in self.criteria}
        for option in self.options:
            scored = [option_key(s.criterion) for s in option.scores]
            if sorted(scored) != sorted(criteria):
                raise ValueError(f"option {option.key} must score every criterion exactly once")
        if option_key(self.recommended_option) not in {option_key(o.key) for o in self.options}:
            raise ValueError("recommended_option must be one of the option keys")
        return self


def weighted_totals(output: CompareOptionsOutput) -> dict[str, int]:
    """Option key -> weighted score as a percentage of the maximum, calculated by Agentra."""
    weights = {option_key(c.key): c.weight for c in output.criteria}
    maximum = 5 * sum(weights.values())
    return {
        option_key(o.key): round(100 * sum(weights[option_key(s.criterion)] * s.score for s in o.scores) / maximum)
        for o in output.options
    }


class CompareOptions:
    agent_key = "solution_architect"
    task_key = "compare_options"
    output_model = CompareOptionsOutput

    def prepare(self, services: Services, run: StartedRun, definition: TaskDefinition) -> PreparedPrompt:
        gathered = gather(services, run, definition, design=False)
        return PreparedPrompt(
            user=gathered.text,
            sources=gathered.sources,
            input_findings=gathered.findings,
            extras={"decisions": gathered.decisions, "document_names": gathered.document_names},
        )

    def check(self, output: CompareOptionsOutput, prepared: PreparedPrompt) -> list[Finding]:  # type: ignore[override]
        totals = weighted_totals(output)
        best = max(totals.values())
        recommended = option_key(output.recommended_option)
        if totals[recommended] < best:
            leader = next(key for key, total in totals.items() if total == best)
            return [Finding("scoring", "warn", f"Recommends {recommended} ({totals[recommended]}%) although {leader} scores higher ({best}%)", "recommended_option")]
        return []

    def apply(self, services: Services, run: StartedRun, output: CompareOptionsOutput, prepared: PreparedPrompt) -> ApplyResult:  # type: ignore[override]
        totals = weighted_totals(output)
        titles = {option_key(c.key): f"{c.title} (weight {c.weight})" for c in output.criteria}
        names = prepared.extras["document_names"]
        decisions = prepared.extras["decisions"]

        def cite(c: Citation) -> str:
            if c.ref in decisions:
                return f"Decision: {decisions[c.ref][1]}"
            if c.ref in names:
                return f'{names[c.ref]}: "{c.quote}"'
            return f"Requirement {c.ref}"

        options = []
        for option in output.options:
            key = option_key(option.key)
            scores = "\n".join(f"- {titles[option_key(s.criterion)]}: {s.score}/5. {s.rationale}" for s in option.scores)
            parts = [
                option.description,
                f"Weighted score (calculated by Agentra): {totals[key]}%",
                f"Scores:\n{scores}",
                *(f"{label}:\n" + "\n".join(f"- {text}" for text in items) for label, items in (("Pros", option.pros), ("Cons", option.cons), ("Risks", option.risks)) if items),
            ]
            options.append(DecisionOption(key=key, title=option.title, description=_fit("\n\n".join(parts), 4000)))

        ranking = ", ".join(f"{o.title} {totals[option_key(o.key)]}%" for o in sorted(output.options, key=lambda o: -totals[option_key(o.key)]))
        context = "\n\n".join(
            part
            for part in (
                output.summary,
                "Criteria: " + "; ".join(f"{c.title} (weight {c.weight}): {c.description}" for c in output.criteria),
                f"Weighted scores, calculated by Agentra from the agent's scores: {ranking}.",
                ("Capabilities to verify: " + "; ".join(output.unverified_capabilities)) if output.unverified_capabilities else "",
                "Based on: " + "; ".join(cite(c) for c in output.sources),
                _FOOTER,
            )
            if part
        )
        request = DecisionRequestCreate(
            title="Architecture option",
            question="Which solution option should the design build on?",
            context=_fit(context, 10000),
            options=options,
            recommended_option=option_key(output.recommended_option),
            recommendation_rationale=output.recommendation_rationale,
            assumptions=output.assumptions,
            risks=[f"To verify: {c}" for c in output.unverified_capabilities][:20],
            artifact_version_id=run.input_artifact_version_id,
        )
        decision = services.decisions.raise_decision(run.agent, run.project_id, request)
        return ApplyResult(decision_ids=[decision.id], task_state="waiting_for_input", records={"weighted_scores": totals})

