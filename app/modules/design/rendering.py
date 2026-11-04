"""Renders a design set as the Solution design document (SAD / high-level design) stored as the design_baseline
version. Deterministic: the same items give byte-identical Markdown. Everything comes from stored records."""

from collections.abc import Sequence

from app.modules.design.schemas import KIND_TITLES, Coverage, DesignItemView, DesignSource, QualityFlag, RequirementException, ReviewResponse

_NOTE = (
    "Each design item is labelled fact (required by an approved requirement or decision), assumption, suggestion "
    "(the architect's proposal) or open question; its status is set by Agentra, not by the agent. Capabilities the "
    "inputs do not confirm are flagged for verification. Nothing in this document is approved until a reviewer "
    "approves this exact version, and it is valid only for the requirements version named below."
)


def _source(source: DesignSource) -> str:
    if source.type == "requirement":
        return f"Requirement {source.name}"
    if source.type == "decision":
        return f'Decision "{source.name}" ({"answered: " + source.answer if source.answer else "not answered yet"})'
    quote = " ".join(source.quote.split())
    return f'{source.name}: "{quote}"' if quote else source.name


def _flag(flag: QualityFlag) -> str:
    return f"{'Warning' if flag.severity == 'warning' else 'Note'} ({flag.check}): {flag.message}"


def _mermaid(title: str, diagram: str) -> list[str]:
    text = diagram.replace("```", "").strip()
    return [f"## {title}", "", "```mermaid", text, "```", ""] if text else []


def render_design(
    *,
    project_name: str,
    requirements_label: str,
    summary: str,
    component_diagram: str,
    data_flow_diagram: str,
    items: Sequence[DesignItemView],
    exceptions: Sequence[RequirementException],
    coverage: Coverage,
    set_flags: Sequence[QualityFlag],
    input_refs: Sequence[str],
    review_responses: Sequence[ReviewResponse] = (),
) -> str:
    lines = [f"# Solution design: {project_name}", "", f"Designed against {requirements_label}.", "", "Drafted by the Solution Architect Agent from:"]
    lines += [f"- {ref}" for ref in input_refs]
    lines += ["", f"> {_NOTE}", "", "## Summary", "", summary.strip(), ""]
    if review_responses:
        lines += ["## Changes in this version", "", "Responses to the review comments and findings on the previous version:", ""]
        for response in review_responses:
            heading = response.finding or "Review comment"
            lines += [f"- {heading}: \"{' '.join(response.comment.split())}\"", f"  Response: {response.response.strip()}"]
        lines.append("")
    lines += _mermaid("Component diagram", component_diagram)
    lines += _mermaid("Data flow diagram", data_flow_diagram)
    for kind, heading in KIND_TITLES.items():
        group = [item for item in items if item.kind == kind]
        if not group:
            continue
        lines += [f"## {heading}", ""]
        for item in group:
            lines += [f"### {item.item_id} {item.title}", "", item.description.strip(), ""]
            if item.rationale.strip():
                lines += [f"Rationale: {item.rationale.strip()}", ""]
            lines += [f"*Label: {item.label.replace('_', ' ')}. Status: {item.status}.*", ""]
            if item.satisfies:
                lines += [f"Satisfies: {', '.join(item.satisfies)}", ""]
            if item.related:
                lines += [f"Related: {', '.join(item.related)}", ""]
            if item.unverified_capabilities:
                lines += ["To verify:", *(f"- {capability}" for capability in item.unverified_capabilities), ""]
            lines += ["Sources:", *(f"- {_source(source)}" for source in item.sources), ""]
            if item.quality_flags:
                lines += [*(f"- {_flag(flag)}" for flag in item.quality_flags), ""]
    lines += [
        "## Requirement coverage",
        "",
        f"{coverage.covered} of {coverage.confirmed} confirmed requirements are covered by design items; "
        f"{coverage.excepted} have a documented exception; {len(coverage.gaps)} are not covered.",
        "",
        "| Requirement | Status | Design items | Exception |",
        "| --- | --- | --- | --- |",
    ]
    for row in coverage.rows:
        exception = (row.exception or "").replace("|", "\\|")
        lines.append(f"| {row.requirement_id} {row.title.replace('|', '/')} | {row.status} | {', '.join(row.design_items) or '-'} | {exception or '-'} |")
    lines.append("")
    if exceptions:
        lines += ["## Requirements not covered by this design", ""]
        lines += [f"- {e.requirement_id}: {e.reason}" for e in exceptions]
        lines.append("")
    lines += ["## Quality checks", "", f"- {len(items)} design items; {sum(1 for i in items if i.quality_flags)} with flags."]
    lines += [f"- {_flag(flag)}" for flag in set_flags]
    return "\n".join(lines).rstrip() + "\n"
