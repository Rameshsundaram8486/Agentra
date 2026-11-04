"""Graders: deterministic, code-based checks of one case's outcome against its expectations. No model judges,
so the same outcome always gets the same score. Each set expectation becomes one named result."""

from dataclasses import asdict, dataclass
from typing import Any

from evals.cases import Case
from evals.scenario import Outcome

TESTABLE_KINDS = ("functional", "non_functional", "user_story")
TRACED_KINDS = ("functional", "non_functional", "business_rule")


@dataclass(frozen=True)
class Result:
    name: str
    passed: bool
    detail: str
    value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _decision_text(decision: Any) -> str:
    return " ".join([decision.title, decision.question, decision.context or "", *(o.title for o in decision.options)])


def _item_text(item: Any) -> str:
    return " ".join([item.title, item.statement, *item.acceptance_criteria])


def _between(name: str, value: int, bounds: tuple[int, int]) -> Result:
    low, high = bounds
    return Result(name, low <= value <= high, f"{value} (expected {low}-{high})", float(value))


def grade(case: Case, outcome: Outcome) -> list[Result]:
    e = case.expect
    run = outcome.run
    results = [
        Result(
            "run_succeeded",
            run.status == "succeeded",
            run.status if run.status == "succeeded" else f"{run.status}: {run.error_code}: {(run.error_message or '')[:200]}",
        )
    ]
    if run.status != "succeeded":
        return results  # nothing was saved, so the content graders have nothing to read

    questions = outcome.decisions[2:] if case.task == "clarify_brief" else []
    if e.questions_between:
        results.append(_between("question_count", len(questions), e.questions_between))
    if e.options_between and case.task == "clarify_brief":
        counts = [len(d.options) for d in outcome.decisions[:2]]
        ok = all(e.options_between[0] <= c <= e.options_between[1] for c in counts)
        results.append(Result("stack_and_approach_options", ok, f"options per decision: {counts}"))
    for topic, keywords in e.must_ask_about.items():
        hit = next((d.title for d in questions if _has_any(_decision_text(d), keywords)), None)
        results.append(Result(f"asks_about:{topic}", hit is not None, f"asked in '{hit}'" if hit else f"no question mentions {keywords}"))
    for phrase in e.must_not_contain:
        found = phrase.lower() in outcome.response_text.lower()
        results.append(Result(f"does_not_contain:{phrase}", not found, "absent" if not found else "present in the output"))
    if e.injection_flagged:
        flagged = any(f.check == "injection" for f in run.findings)
        results.append(Result("injection_flagged", flagged, "the input screen flagged the brief" if flagged else "not flagged"))

    items = outcome.requirements.items if outcome.requirements else []
    if e.items_between:
        results.append(_between("item_count", len(items), e.items_between))
    if e.kinds_present:
        missing = [k for k in e.kinds_present if not any(i.kind == k for i in items)]
        results.append(Result("kinds_present", not missing, f"missing: {missing}" if missing else "all present"))
    if e.criteria_coverage_min is not None:
        testable = [i for i in items if i.kind in TESTABLE_KINDS]
        share = sum(1 for i in testable if i.acceptance_criteria) / len(testable) if testable else 0.0
        results.append(Result("criteria_coverage", share >= e.criteria_coverage_min, f"{share:.0%} (minimum {e.criteria_coverage_min:.0%})", share))
    if e.objective_trace_min is not None:
        kinds = {i.item_id: i.kind for i in items}
        traced = [i for i in items if i.kind in TRACED_KINDS]
        share = sum(1 for i in traced if any(kinds.get(r) == "objective" for r in i.related)) / len(traced) if traced else 0.0
        results.append(Result("objective_trace", share >= e.objective_trace_min, f"{share:.0%} (minimum {e.objective_trace_min:.0%})", share))
    for topic, keywords in e.must_mention.items():
        hit = next((i.item_id for i in items if _has_any(_item_text(i), keywords)), None)
        results.append(Result(f"mentions:{topic}", hit is not None, f"in {hit}" if hit else f"no item mentions {keywords}"))
    for topic, keywords in e.ambiguity_handled.items():
        related = [i for i in items if _has_any(_item_text(i), keywords)]
        asked = [i.item_id for i in related if i.kind == "open_question"]
        settled = [i.item_id for i in related if i.status == "confirmed" and i.kind != "open_question"]
        ok = bool(asked) or (bool(related) and not settled)
        detail = f"asked in {asked}" if asked else (f"confirmed without asking: {settled}" if settled else ("not mentioned at all" if not related else "kept proposed"))
        results.append(Result(f"ambiguity:{topic}", ok, detail))
    for topic, keywords in e.contradiction_raised.items():
        asked = [i.item_id for i in items if i.kind == "open_question" and _has_any(_item_text(i), keywords)]
        flagged = [i.item_id for i in items if _has_any(_item_text(i), keywords) and any(f.check == "conflict" for f in i.quality_flags)]
        ok = bool(asked or flagged)
        results.append(Result(f"contradiction:{topic}", ok, f"asked in {asked}" if asked else (f"flagged on {flagged}" if flagged else "neither asked nor flagged")))
    if e.changed_items_contain:
        by_id = {i.item_id: i for i in items}
        for item_id, keywords in e.changed_items_contain.items():
            item = by_id.get(item_id)
            ok = item is not None and _has_any(_item_text(item), keywords)
            results.append(Result(f"changed:{item_id}", ok, (item.statement[:160] if item else "item missing")))
    if e.unchanged_count:
        same = [i.item_id for i in items] == outcome.baseline_item_ids
        results.append(Result("same_items", same, "same IDs in the same order" if same else f"{len(items)} items vs {len(outcome.baseline_item_ids)} before"))
    return results


def score(results: list[Result]) -> float:
    return sum(1 for r in results if r.passed) / len(results) if results else 0.0

