"""Renders a backlog as the Implementation backlog document stored as the implementation_backlog version.
Deterministic: the same epics and work items give byte-identical Markdown. Everything comes from stored records."""

from collections.abc import Sequence

from app.modules.backlog.schemas import BacklogReply, EpicView, WorkItemView

_NOTE = (
    "Drafted by the Developer Agent from the approved design version named below. Work item IDs, coverage of the "
    "design and the dependency checks are Agentra's, not the agent's. Sizes are relative (S, M, L), not commitments. "
    "Nothing here is approved until a person approves this exact version, and it is valid only for that design version."
)


def render_backlog(
    *,
    project_name: str,
    design_label: str,
    summary: str,
    epics: Sequence[EpicView],
    items: Sequence[WorkItemView],
    review_responses: Sequence[BacklogReply] = (),
) -> str:
    lines = [f"# Implementation backlog: {project_name}", "", f"Plans {design_label}.", "", f"> {_NOTE}", "", "## Summary", "", summary.strip(), ""]
    sizes = {size: sum(1 for i in items if i.estimate == size) for size in ("S", "M", "L")}
    waves = sorted({i.wave for i in items})
    lines += [f"{len(epics)} epic(s), {len(items)} work item(s): {sizes['S']} S, {sizes['M']} M, {sizes['L']} L, in {len(waves)} wave(s).", ""]
    if review_responses:
        lines += ["## Changes in this version", "", "Responses to the review comments on the previous version:", ""]
        for response in review_responses:
            lines += [f"- Review comment: \"{' '.join(response.comment.split())}\"", f"  Response: {response.response.strip()}"]
        lines.append("")
    for epic in epics:
        lines += [f"## {epic.epic_id} {epic.title}", "", epic.description.strip(), ""]
        for item in (i for i in items if i.epic_id == epic.epic_id):
            lines += [f"### {item.item_id} {item.title}", "", item.description.strip(), ""]
            lines += [f"*{item.work_type.title()}, size {item.estimate}, wave {item.wave}.*", ""]
            lines += [f"Implements: {', '.join(item.design_items)}", ""]
            if item.requirements:
                lines += [f"Requirements: {', '.join(item.requirements)}", ""]
            if item.acceptance:
                lines += [f"Acceptance criteria: {', '.join(item.acceptance)}", ""]
            if item.depends_on:
                lines += [f"Depends on: {', '.join(item.depends_on)}", ""]
    lines += ["## Delivery waves", ""]
    for wave in waves:
        lines.append(f"- Wave {wave}: {', '.join(i.item_id for i in items if i.wave == wave)}")
    return "\n".join(lines).rstrip() + "\n"
