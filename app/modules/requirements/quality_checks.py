"""Completeness, consistency, duplication and testability checks. Rule-based and deterministic: the same items
always give the same flags. Flags inform the reviewer; they do not change an item's status.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations

from app.modules.requirements.schemas import QualityFlag

TESTABLE_KINDS = ("functional", "non_functional", "user_story")
COMPARABLE_KINDS = ("functional", "non_functional", "user_story", "business_rule")
DUPLICATE_RATIO = 0.88
CONFLICT_RATIO = 0.85
SUBJECT_OVERLAP = 0.6

VAGUE_TERMS = (
    "fast", "quick", "quickly", "user-friendly", "user friendly", "easy", "easily", "simple", "intuitive",
    "efficient", "efficiently", "robust", "flexible", "seamless", "seamlessly", "appropriate", "appropriately",
    "as needed", "adequate", "reasonable", "modern", "optimal", "minimal", "as soon as possible", "etc",
    "and/or", "high performance", "scalable", "short period", "timely", "regularly",
)
_VAGUE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(term) for term in VAGUE_TERMS) + r")(?![\w-])", re.IGNORECASE)
_NEGATION = re.compile(r"\b(must not|shall not|should not|cannot|can not|may not|will not|won't|never|no longer|not)\b", re.IGNORECASE)
_MODAL = re.compile(r"\b(must|shall|should|can|may|will|is able to|are able to)\b", re.IGNORECASE)
_MEASURE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|[a-z]+)", re.IGNORECASE)
_WORD = re.compile(r"[a-z][a-z'-]+")
_STOP = frozenset(
    "a an the and or of to in on for by with within at from be is are was were it its this that these those "
    "must shall should can may will not no than per each every all any user users system".split()
)
_UNITS = {"second": "s", "seconds": "s", "sec": "s", "secs": "s", "s": "s", "minute": "min", "minutes": "min",
          "min": "min", "mins": "min", "hour": "h", "hours": "h", "h": "h", "day": "day", "days": "day", "%": "%"}


@dataclass(frozen=True)
class CheckedItem:
    item_id: str
    kind: str
    title: str
    statement: str
    acceptance_criteria: Sequence[str]
    cites_open_decision: bool = False


def _text(item: CheckedItem) -> str:
    return " ".join([item.statement, *item.acceptance_criteria])


def _normalise(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def _without_modality(text: str) -> str:
    return " ".join(_MODAL.sub(" ", _NEGATION.sub(" ", text.lower())).split())


def _measures(text: str) -> set[tuple[str, str]]:
    found = set()
    for number, unit in _MEASURE.findall(text):
        unit = unit.lower()
        found.add((number.replace(",", "."), _UNITS.get(unit, unit.rstrip("s"))))
    return found


def _subject(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if word not in _STOP}


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _pair_problem(a: CheckedItem, b: CheckedItem) -> tuple[str, str] | None:
    """Conflicts first: two statements that differ only by a "not" or by a number look like duplicates too."""
    if bool(_NEGATION.search(a.statement)) != bool(_NEGATION.search(b.statement)):
        if SequenceMatcher(None, _without_modality(a.statement), _without_modality(b.statement)).ratio() >= CONFLICT_RATIO:
            return "conflict", "Says the opposite of {other}"
    measures_a, measures_b = _measures(a.statement), _measures(b.statement)
    shared_units = {unit for _, unit in measures_a} & {unit for _, unit in measures_b}
    if shared_units and _overlap(_subject(a.statement), _subject(b.statement)) >= SUBJECT_OVERLAP:
        if any({n for n, u in measures_a if u == unit} != {n for n, u in measures_b if u == unit} for unit in shared_units):
            return "conflict", "Gives a different value than {other} for what looks like the same measure"
    if a.kind == b.kind and SequenceMatcher(None, _normalise(a.statement), _normalise(b.statement)).ratio() >= DUPLICATE_RATIO:
        return "duplicate", "Looks like a duplicate of {other}"
    return None


def check_items(items: Sequence[CheckedItem]) -> tuple[dict[str, list[QualityFlag]], list[QualityFlag]]:
    """Returns (flags per item ID, flags about the set as a whole)."""
    flags: dict[str, list[QualityFlag]] = {item.item_id: [] for item in items}

    for item in items:
        text = _text(item)
        if item.kind in TESTABLE_KINDS and not item.acceptance_criteria:
            flags[item.item_id].append(QualityFlag(check="completeness", severity="warning", message="No acceptance criteria"))
        if item.kind in TESTABLE_KINDS and (vague := sorted({m.lower() for m in _VAGUE.findall(text)})) and not re.search(r"\d", text):
            flags[item.item_id].append(
                QualityFlag(check="testability", severity="warning", message=f"Vague wording with no measurable criterion: {', '.join(vague)}")
            )
        if item.kind == "non_functional" and not re.search(r"\d", text):
            flags[item.item_id].append(
                QualityFlag(check="testability", severity="warning", message="Non-functional requirement without a number or unit to test against")
            )
        if item.cites_open_decision:
            flags[item.item_id].append(
                QualityFlag(check="open_decision", severity="info", message="Cites a decision nobody has answered yet, so it stays proposed")
            )

    comparable = [item for item in items if item.kind in COMPARABLE_KINDS]
    for a, b in combinations(comparable, 2):
        found = _pair_problem(a, b)
        if found is not None:
            check, message = found
            for this, other in ((a, b), (b, a)):
                flags[this.item_id].append(
                    QualityFlag(check=check, severity="warning", message=message.format(other=other.item_id), related=[other.item_id])
                )

    kinds = {item.kind for item in items}
    set_flags = [
        QualityFlag(check="completeness", severity="warning", message=f"No {label} yet")
        for kind, label in (("objective", "objectives"), ("stakeholder", "stakeholders"), ("functional", "functional requirements"))
        if kind not in kinds
    ]
    open_count = sum(1 for item in items if item.kind == "open_question")
    if open_count:
        set_flags.append(QualityFlag(check="open_questions", severity="info", message=f"{open_count} open question(s) to answer"))
    return flags, set_flags
