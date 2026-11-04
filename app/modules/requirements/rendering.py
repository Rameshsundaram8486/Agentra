"""Renders a requirements set as the readable BRD stored as the requirements_baseline document version.

Deterministic: the same items give byte-identical Markdown, so the version hash identifies the content.
Everything comes from the stored items; nothing here is written by a model except the item text itself.
"""

from collections.abc import Sequence

from app.modules.requirements.schemas import KIND_TITLES, QualityFlag, RequirementItemView, ReviewResponse, SourceRef

_STATUS_NOTE = (
    "Each item is labelled fact, assumption, suggestion or open question. Its status is set by Agentra, not "
    "by the agent: confirmed only for facts backed by a source document or an answered decision; proposed for "
    "assumptions, suggestions and anything resting on an unanswered decision; open for questions. Nothing in "
    "this document is approved until a reviewer approves this exact version."
)


def _source(source: SourceRef) -> str:
    if source.type == "decision":
        return f'Decision "{source.name}" ({"answered: " + source.answer if source.answer else "not answered yet"})'
    quote = " ".join(source.quote.split())
    return f'{source.name}: "{quote}"' if quote else source.name


def _flag(flag: QualityFlag) -> str:
    prefix = "Warning" if flag.severity == "warning" else "Note"
    return f"{prefix} ({flag.check}): {flag.message}"


def render_brd(
    *,
    project_name: str,
    summary: str,
    items: Sequence[RequirementItemView],
    set_flags: Sequence[QualityFlag],
    process_flow_mermaid: str,
    input_refs: Sequence[str],
    review_responses: Sequence[ReviewResponse] = (),
    change_request: str | None = None,
) -> str:
    lines = [f"# Business requirements: {project_name}", ""]
    if change_request:
        lines += [f"This version applies the approved change request {change_request}.", ""]
    lines += ["Drafted by the Business Analyst Agent from:"]
    lines += [f"- {ref}" for ref in input_refs]
    lines += ["", f"> {_STATUS_NOTE}", "", "## Summary", "", summary.strip(), ""]
    if review_responses:
        lines += ["## Changes in this version", "", "Responses to the review comments on the previous version:", ""]
        for response in review_responses:
            lines += [f"- Review comment: \"{' '.join(response.comment.split())}\"", f"  Response: {response.response.strip()}"]
        lines.append("")
    for kind, heading in KIND_TITLES.items():
        group = [item for item in items if item.kind == kind]
        if not group:
            continue
        lines += [f"## {heading}", ""]
        for item in group:
            lines += [f"### {item.item_id} {item.title}", "", item.statement.strip(), ""]
            meta = f"Label: {item.label.replace('_', ' ')}. Status: {item.status}."
            if item.priority != "not_set":
                meta += f" Priority: {item.priority}."
            lines += [f"*{meta}*", ""]
            if item.acceptance_criteria:
                lines += ["Acceptance criteria:"]
                lines += [f"- {item.item_id}.AC{n}: {criterion}" for n, criterion in enumerate(item.acceptance_criteria, start=1)]
                lines.append("")
            if item.related:
                lines += [f"Traces to: {', '.join(item.related)}", ""]
            lines += ["Sources:", *(f"- {_source(source)}" for source in item.sources), ""]
            if item.quality_flags:
                lines += [*(f"- {_flag(flag)}" for flag in item.quality_flags), ""]
    flow = process_flow_mermaid.replace("```", "").strip()
    if flow:
        lines += ["## Process flow", "", "```mermaid", flow, "```", ""]
    lines += ["## Quality checks", ""]
    flagged = sum(1 for item in items if item.quality_flags)
    lines += [f"- {len(items)} items; {flagged} with flags."]
    lines += [f"- {_flag(flag)}" for flag in set_flags]
    return "\n".join(lines).rstrip() + "\n"
