"""Rules for backlog content, shared by the Developer agent's check (before anything is saved) and the backlog
service (before a draft is recorded). Pure functions returning (path, message) problems."""

import re
from collections.abc import Mapping, Sequence

from app.modules.backlog.schemas import BUILDABLE_KINDS, EpicDraft, WorkItemDraft

_ID = re.compile(r"^(?P<prefix>EP|WI)-(?P<number>\d{3,})$")
_NEW = re.compile(r"^new-[a-z0-9-]{1,30}$")
_CRITERION = re.compile(r"^(?P<req>[A-Z]+(?:-[A-Z]+)?-\d{3,})\.AC(?P<n>\d+)$")

Problem = tuple[str, str]


def parse_id(value: str) -> tuple[str, int] | None:
    match = _ID.match(value)
    return (match["prefix"], int(match["number"])) if match else None


def _ref_problems(ref: str, prefix: str, known: set[str], path: str) -> list[Problem]:
    if ref in known:
        return []
    parsed = parse_id(ref)
    if parsed and parsed[0] == prefix:
        return [(path, f"{ref} is not an existing ID on this project; new entries need a new-... ref")]
    if not _NEW.match(ref):
        return [(path, f"{ref!r} is not an existing {prefix} ID or a new-... ref")]
    return []


def _cycle(edges: Mapping[str, list[str]]) -> list[str] | None:
    """One dependency cycle, if there is one."""
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in edges.get(node, []):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :] + [nxt]
            if state.get(nxt) is None and (found := visit(nxt)):
                return found
        stack.pop()
        state[node] = 2
        return None

    for node in edges:
        if state.get(node) is None and (found := visit(node)):
            return found
    return None


def backlog_problems(
    epics: Sequence[EpicDraft],
    items: Sequence[WorkItemDraft],
    *,
    design_items: Mapping[str, str],
    criteria: Mapping[str, int],
    known_epics: set[str],
    known_items: set[str],
) -> list[Problem]:
    """design_items: ID -> kind of the approved design version. criteria: requirement ID -> number of acceptance
    criteria, for every requirement of the version the design was drafted against."""
    problems: list[Problem] = []
    epic_refs = [e.ref for e in epics]
    item_refs = [i.ref for i in items]
    for refs, what in ((epic_refs, "epic"), (item_refs, "work item")):
        problems += [("items" if what == "work item" else "epics", f"{what.title()} ref {ref} is used more than once") for ref in sorted(set(refs)) if refs.count(ref) > 1]
    for index, epic in enumerate(epics):
        problems += _ref_problems(epic.ref, "EP", known_epics, f"epics[{index}].ref")
    for index, item in enumerate(items):
        path = f"items[{index}]"
        problems += _ref_problems(item.ref, "WI", known_items, f"{path}.ref")
        if item.epic not in epic_refs:
            problems.append((f"{path}.epic", f"{item.ref}: epic {item.epic!r} is not an epic in this backlog"))
        if not item.design_items:
            problems.append((f"{path}.design_items", f"{item.ref} names no design item it implements"))
        problems += [(f"{path}.design_items", f"{item.ref}: {ref!r} is not a design item in the approved design") for ref in item.design_items if ref not in design_items]
        problems += [(f"{path}.requirements", f"{item.ref}: {ref!r} is not a requirement in the approved requirements") for ref in item.requirements if ref not in criteria]
        for ref in item.acceptance:
            match = _CRITERION.match(ref)
            if not match or match["req"] not in criteria or not 1 <= int(match["n"]) <= criteria[match["req"]]:
                problems.append((f"{path}.acceptance", f"{item.ref}: {ref!r} is not an acceptance criterion of an approved requirement (REQ-F-001.AC1)"))
        for ref in item.depends_on:
            if ref == item.ref:
                problems.append((f"{path}.depends_on", f"{item.ref} depends on itself"))
            elif ref not in item_refs:
                problems.append((f"{path}.depends_on", f"{item.ref} depends on {ref!r}, which is not a work item in this backlog"))
    waves = {i.ref: i.wave for i in items}
    for index, item in enumerate(items):
        later = [ref for ref in item.depends_on if ref in waves and waves[ref] > item.wave]
        if later:
            problems.append((f"items[{index}].wave", f"{item.ref} (wave {item.wave}) depends on {', '.join(later)} in a later wave"))
    if cycle := _cycle({i.ref: [d for d in i.depends_on if d in waves and d != i.ref] for i in items}):
        problems.append(("items", f"Dependency cycle: {' -> '.join(cycle)}"))
    planned = {ref for item in items for ref in item.design_items}
    missing = [ref for ref, kind in design_items.items() if kind in BUILDABLE_KINDS and ref not in planned]
    if missing:
        problems.append(("items", f"No work item implements {', '.join(missing)}"))
    return problems
