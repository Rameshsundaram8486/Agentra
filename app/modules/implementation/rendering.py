"""Renders a change set as the Change set document stored as the change_set version, diff included, so an approval
binds to the exact code. Deterministic: the same change set and diff give byte-identical Markdown."""

import re
from collections.abc import Sequence

from app.modules.implementation.schemas import ChangeSetReply, FileRecord

_NOTE = (
    "Drafted by the Developer Agent for one work item of the approved implementation backlog. The commit, the diff "
    "and the links are recorded by Agentra. Nothing here has been built or tested until a sandbox run of this exact "
    "version passes, and it is not approved until a reviewer approves this exact version; then Agentra merges it into main."
)


def _fence(text: str) -> str:
    """A code fence longer than any run of backticks in the text."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render_change_set(
    *,
    project_name: str,
    work_item_label: str,
    backlog_label: str,
    summary: str,
    base_commit: str,
    commit: str,
    branch: str,
    files: Sequence[FileRecord],
    design_items: Sequence[str],
    requirements: Sequence[str],
    acceptance: Sequence[str],
    test_command: str,
    limitations: Sequence[str],
    review_responses: Sequence[ChangeSetReply],
    diff: str,
) -> str:
    lines = [f"# Change set {work_item_label}: {project_name}", "", f"Implements {work_item_label} of {backlog_label}.", "", f"> {_NOTE}", ""]
    lines += ["## Summary", "", summary.strip(), ""]
    lines += [f"Commit {commit} on branch {branch}, based on main at {base_commit}.", ""]
    lines += [f"Design items: {', '.join(design_items)}", ""]
    if requirements:
        lines += [f"Requirements: {', '.join(requirements)}", ""]
    if acceptance:
        lines += [f"Acceptance criteria: {', '.join(acceptance)}", ""]
    lines += ["## Files", ""]
    for record in files:
        size = "" if record.action == "delete" else f", {record.bytes} bytes"
        lines.append(f"- {record.action} `{record.path}`{size}{' (test)' if record.test else ''}")
    lines += ["", "## How to run the tests", "", f"    {test_command.strip()}", ""]
    if limitations:
        lines += ["## Known limitations", ""] + [f"- {item.strip()}" for item in limitations] + [""]
    if review_responses:
        lines += ["## Changes in this version", "", "Responses to the review comments on the previous version:", ""]
        for response in review_responses:
            lines += [f"- Review comment: \"{' '.join(response.comment.split())}\"", f"  Response: {response.response.strip()}"]
        lines.append("")
    fence = _fence(diff)
    lines += ["## Diff", "", f"{fence}diff", diff.rstrip("\n"), fence]
    return "\n".join(lines).rstrip() + "\n"
