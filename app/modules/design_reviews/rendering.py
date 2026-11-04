"""Renders a review as the Security review or Feasibility review document stored as that review's version.
Deterministic: the same findings give byte-identical Markdown. Everything comes from stored records."""

from collections.abc import Sequence

from app.modules.design_reviews.schemas import FindingView, ReviewReply

_NOTES = {
    "security": (
        "Each check in the security checklist is answered by the Security Reviewer Agent as addressed (with the design "
        "items that address it), gap (with a severity and a recommended fix) or not applicable (with the reason). "
        "This is an assessment, not an assurance: nothing here is signed off until a reviewer approves this exact "
        "version. A design version can be approved only with an approved security review of that version, and a "
        "review with a high-severity gap cannot be approved."
    ),
    "feasibility": (
        "Each design item is rated by the Developer Agent as feasible, feasible with concerns, or not feasible as "
        "described, with a complexity estimate (S, M or L). A design version with an item rated not feasible cannot "
        "be approved; concerns are answered by the Solution Architect in the next draft."
    ),
}
_VERDICTS = {
    "addressed": "Addressed",
    "gap": "Gap",
    "not_applicable": "Not applicable",
    "feasible": "Feasible",
    "concerns": "Feasible with concerns",
    "not_feasible": "Not feasible",
}


def _finding(finding: FindingView) -> list[str]:
    verdict = _VERDICTS.get(finding.verdict, finding.verdict)
    detail = [f"severity {finding.severity}"] if finding.severity else []
    detail += [f"complexity {finding.complexity}"] if finding.complexity else []
    lines = [f"### {finding.ref} {finding.title}", "", f"**{verdict}**" + (f" ({', '.join(detail)})" if detail else ""), "", finding.assessment.strip(), ""]
    if finding.recommendation.strip():
        lines += [f"Recommendation: {finding.recommendation.strip()}", ""]
    if finding.design_items:
        lines += [f"Design items: {', '.join(finding.design_items)}", ""]
    if finding.requirements:
        lines += [f"Requirements: {', '.join(finding.requirements)}", ""]
    if finding.unverified:
        lines += ["To verify:", *(f"- {item}" for item in finding.unverified), ""]
    return lines


def render_review(
    *,
    kind: str,
    project_name: str,
    design_label: str,
    checklist: str | None,
    summary: str,
    findings: Sequence[FindingView],
    review_responses: Sequence[ReviewReply] = (),
) -> str:
    title = "Security review" if kind == "security" else "Feasibility review"
    reviewer = "Security Reviewer Agent" if kind == "security" else "Developer Agent"
    lines = [f"# {title}: {project_name}", "", f"Reviews {design_label}.", "", f"Drafted by the {reviewer}" + (f" against {checklist}." if checklist else ".")]
    lines += ["", f"> {_NOTES[kind]}", "", "## Summary", "", summary.strip(), ""]
    counts = {verdict: sum(1 for f in findings if f.verdict == verdict) for verdict in dict.fromkeys(f.verdict for f in findings)}
    lines += ["Findings: " + ", ".join(f"{count} {_VERDICTS.get(verdict, verdict).lower()}" for verdict, count in counts.items()) + ".", ""]
    if review_responses:
        lines += ["## Changes in this version", "", "Responses to the review comments on the previous version:", ""]
        for response in review_responses:
            lines += [f"- Review comment: \"{' '.join(response.comment.split())}\"", f"  Response: {response.response.strip()}"]
        lines.append("")
    gaps = [f for f in findings if f.verdict in ("gap", "not_feasible", "concerns")]
    if gaps:
        lines += ["## To resolve", ""]
        lines += [f"- {f.ref} {f.title}: {_VERDICTS[f.verdict].lower()}" + (f" ({f.severity})" if f.severity else "") for f in gaps]
        lines.append("")
    lines += ["## Findings", ""]
    for finding in findings:
        lines += _finding(finding)
    return "\n".join(lines).rstrip() + "\n"
