"""Requirements traceability matrix: objective <- requirement -> user stories -> acceptance criteria -> design
items -> backlog work items, with the sources behind each requirement. The design and backlog columns come from
Phase 8, tests from Phase 10.
Built only from stored items; the same items always give the same rows and the same CSV.
"""

import csv
import io
from collections.abc import Mapping, Sequence

from app.modules.requirements.schemas import RequirementItemView, TraceRow, TraceabilityView

TRACED_KINDS = ("functional", "non_functional", "business_rule")
NOT_YET_DESIGN = "Not yet (Phase 8)"
NOT_YET_BACKLOG = "Not yet (backlog)"
NOT_YET_TESTS = "Not yet (Phase 10)"


def _source(item: RequirementItemView) -> list[str]:
    out = []
    for source in item.sources:
        if source.type == "decision":
            out.append(f"Decision: {source.name} ({source.answer or 'not answered'})")
        else:
            out.append(f"{source.name}: \"{' '.join(source.quote.split())}\"")
    return out


def build_rows(
    items: Sequence[RequirementItemView], design: Mapping[str, list[str]] | None = None, backlog: Mapping[str, list[str]] | None = None
) -> tuple[list[TraceRow], list[str]]:
    """design: requirement ID -> design item IDs (or an exception note) for the current design; backlog: requirement
    ID -> work item IDs of the current backlog. None before there is one."""
    by_id = {item.item_id: item for item in items}
    objectives = [item for item in items if item.kind == "objective"]
    stories = [item for item in items if item.kind == "user_story"]
    traced = [item for item in items if item.kind in TRACED_KINDS]

    rows = []
    for item in traced:
        linked_objectives = [ref for ref in item.related if by_id.get(ref) and by_id[ref].kind == "objective"]
        linked_stories = sorted(story.item_id for story in stories if item.item_id in story.related)
        gaps = []
        if not linked_objectives:
            gaps.append("No objective")
        if item.kind != "business_rule" and not item.acceptance_criteria:
            gaps.append("No acceptance criteria")
        rows.append(
            TraceRow(
                item_id=item.item_id,
                kind=item.kind,
                title=item.title,
                status=item.status,
                objectives=linked_objectives,
                user_stories=linked_stories,
                acceptance_criteria=[f"{item.item_id}.AC{n} {text}" for n, text in enumerate(item.acceptance_criteria, start=1)],
                sources=_source(item),
                design=NOT_YET_DESIGN if design is None else (", ".join(design.get(item.item_id, [])) or "Not covered"),
                backlog=NOT_YET_BACKLOG if backlog is None else (", ".join(backlog.get(item.item_id, [])) or "No work item"),
                tests=NOT_YET_TESTS,
                gaps=gaps,
            )
        )

    covered_objectives = {ref for row in rows for ref in row.objectives}
    set_gaps = [f"{o.item_id} has no requirement tracing to it" for o in objectives if o.item_id not in covered_objectives]
    set_gaps += [
        f"{s.item_id} does not trace to any requirement"
        for s in stories
        if not any(by_id.get(ref) and by_id[ref].kind in TRACED_KINDS for ref in s.related)
    ]
    return rows, set_gaps


def to_csv(view: TraceabilityView) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Requirement", "Kind", "Title", "Status", "Objectives", "User stories", "Acceptance criteria", "Sources", "Design", "Backlog", "Tests", "Gaps"])
    for row in view.rows:
        writer.writerow(
            [
                row.item_id,
                row.kind,
                row.title,
                row.status,
                "; ".join(row.objectives),
                "; ".join(row.user_stories),
                " | ".join(row.acceptance_criteria),
                " | ".join(row.sources),
                row.design,
                row.backlog,
                row.tests,
                "; ".join(row.gaps),
            ]
        )
    return buffer.getvalue()
