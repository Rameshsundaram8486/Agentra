"""What an applied change request may change. Pure and deterministic, so the agent task (before anything is
saved) and the requirements service (as the last line) apply exactly the same rule:

- an item the change request does not list must come back unchanged: same kind, title, statement, label,
  priority and acceptance criteria (sources may be re-quoted);
- only listed items may be removed or reworded;
- new items are allowed only if the change request allows them.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ComparableItem:
    ref: str  # an item ID, or a new-n ref for an added item
    kind: str
    title: str
    statement: str
    label: str
    priority: str
    acceptance_criteria: Sequence[str]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _same(a: ComparableItem, b: ComparableItem) -> bool:
    return (
        a.kind == b.kind
        and _norm(a.title) == _norm(b.title)
        and _norm(a.statement) == _norm(b.statement)
        and a.label == b.label
        and a.priority == b.priority
        and [_norm(c) for c in a.acceptance_criteria] == [_norm(c) for c in b.acceptance_criteria]
    )


def change_violations(
    baseline: Sequence[ComparableItem], draft: Sequence[ComparableItem], *, affected: Collection[str], allows_new_items: bool
) -> list[tuple[str, str]]:
    """(ref, problem) for each change the change request does not authorise."""
    drafted = {item.ref: item for item in draft}
    known = {item.ref for item in baseline}
    problems = []
    for item in baseline:
        if item.ref in affected:
            continue
        if item.ref not in drafted:
            problems.append((item.ref, f"{item.ref} was removed, but the change request does not list it"))
        elif not _same(item, drafted[item.ref]):
            problems.append((item.ref, f"{item.ref} was changed, but the change request does not list it"))
    if not allows_new_items:
        problems += [(item.ref, "The change request does not allow new items") for item in draft if item.ref not in known]
    return problems
