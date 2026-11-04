"""Eval cases: a synthetic scenario for one agent task plus what good output looks like.

Cases live in evals/<agent>/cases/*.yaml. Long texts (briefs, source documents) may live in evals/<agent>/inputs/
and be referenced as `file: name.md`. Everything is synthetic: no customer data.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

EVALS_DIR = Path(__file__).resolve().parent
TaskKey = Literal["clarify_brief", "draft_requirements", "apply_change_request"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Document(_Strict):
    title: str
    content: str


class ChangeRequestSpec(_Strict):
    title: str
    reason: str
    change: str
    impact: str
    affected_item_ids: list[str]
    allows_new_items: bool = False


class Expectations(_Strict):
    """Each set field becomes one grader. Keyword lists match case-insensitively; any keyword is enough."""

    questions_between: tuple[int, int] | None = None  # clarify: number of clarifying questions
    options_between: tuple[int, int] | None = None  # clarify: options in the stack and approach decisions
    must_ask_about: dict[str, list[str]] = Field(default_factory=dict)  # clarify: topic -> keywords in some question
    must_not_contain: list[str] = Field(default_factory=list)  # anywhere in the raw model output
    injection_flagged: bool = False  # the input screen flagged the brief
    items_between: tuple[int, int] | None = None  # draft: number of requirement items
    kinds_present: list[str] = Field(default_factory=list)
    criteria_coverage_min: float | None = None  # share of functional, non-functional and user story items with criteria
    objective_trace_min: float | None = None  # share of traced requirements linked to an objective
    must_mention: dict[str, list[str]] = Field(default_factory=dict)  # draft: topic -> keywords in some item
    ambiguity_handled: dict[str, list[str]] = Field(default_factory=dict)  # not settled as confirmed fact
    contradiction_raised: dict[str, list[str]] = Field(default_factory=dict)  # asked about or flagged as a conflict
    changed_items_contain: dict[str, list[str]] = Field(default_factory=dict)  # apply: item ID -> keywords
    unchanged_count: bool = False  # apply: same number of items as the baseline


class Case(_Strict):
    id: str = Field(pattern=r"^[a-z0-9_]{3,64}$")
    agent: Literal["business_analyst"] = "business_analyst"
    task: TaskKey
    description: str
    brief: str
    documents: list[Document] = Field(default_factory=list)
    baseline_items: list[dict[str, Any]] | None = None  # apply_change_request: the approved items, scripted
    change_request: ChangeRequestSpec | None = None
    expect: Expectations

    @model_validator(mode="after")
    def _complete(self) -> "Case":
        if self.task == "apply_change_request" and (self.baseline_items is None or self.change_request is None):
            raise ValueError("an apply_change_request case needs baseline_items and change_request")
        return self


def _resolve(value: Any, inputs: Path) -> Any:
    if isinstance(value, dict) and set(value) == {"file"}:
        return (inputs / value["file"]).read_text(encoding="utf-8")
    if isinstance(value, dict):
        return {key: _resolve(item, inputs) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, inputs) for item in value]
    return value


def load_cases(root: Path = EVALS_DIR, pattern: str = "*") -> list[Case]:
    cases = []
    for path in sorted(root.glob(f"*/cases/{pattern}.yaml")):
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        case = Case.model_validate(_resolve(raw, path.parent.parent / "inputs"))
        if case.id != path.stem:
            raise ValueError(f"{path.name}: id {case.id!r} must match the file name")
        cases.append(case)
    return cases
