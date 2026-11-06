"""Change set rules shared by the Developer agent's output check and the implementation service. Pure functions.

A change set may only touch ordinary repository files (never .git, pipeline definitions or other protected paths),
must match what is on main (add only new files, modify or delete only existing ones, with no two paths differing
only in letter case, since the sandbox VMs run Windows), stays within the size limits, carries no secrets, adds or
changes a test where the work type needs one, and links only to its own work item's design items, requirements and
acceptance criteria.
"""

from collections.abc import Iterable, Sequence

from app.guardrails.output.secret_scan import find_secrets
from app.modules.implementation.git_repo import safe_path
from app.modules.implementation.policy import ChangeSetPolicy
from app.modules.implementation.schemas import FileDraft

Problem = tuple[str, str]  # (path in the draft, message)


def change_set_problems(
    files: Sequence[FileDraft],
    *,
    existing: Iterable[str],
    policy: ChangeSetPolicy,
    work_item: str,
    work_type: str,
    allowed_design_items: Sequence[str],
    allowed_requirements: Sequence[str],
    allowed_acceptance: Sequence[str],
    design_items: Sequence[str],
    requirements: Sequence[str],
    acceptance: Sequence[str],
    test_command: str,
) -> list[Problem]:
    problems: list[Problem] = []
    limits = policy.limits
    on_main = {path.lower(): path for path in existing}
    if not files:
        problems.append(("files", "A change set changes at least one file"))
    if len(files) > limits.max_files:
        problems.append(("files", f"{len(files)} files; a change set may change at most {limits.max_files}"))

    seen: dict[str, int] = {}
    total = 0
    for n, change in enumerate(files):
        where, path = f"files[{n}]", change.path
        if not safe_path(path):
            problems.append((f"{where}.path", f"{path!r} is not a relative path inside the repository"))
            continue
        if policy.protected(path):
            problems.append((f"{where}.path", f"{path} is protected: pipeline definitions, git settings and Agentra's own files are never changed by an agent"))
        key = path.lower()
        if key in seen:
            problems.append((f"{where}.path", f"{path} appears more than once (paths differing only in case count as the same file)"))
        seen[key] = n
        present = on_main.get(key)
        if change.action == "add" and present is not None:
            problems.append((f"{where}.action", f"{path} already exists on main{f' as {present}' if present != path else ''}; modify it instead"))
        if change.action in ("modify", "delete") and present != path:
            problems.append((f"{where}.action", f"{path} does not exist on main, so it cannot be {'modified' if change.action == 'modify' else 'deleted'}"))
        if change.action == "delete":
            if change.content is not None:
                problems.append((f"{where}.content", "A deleted file has no content"))
            continue
        if change.content is None:
            problems.append((f"{where}.content", f"{path}: give the whole new content of the file"))
            continue
        size = len(change.content.encode("utf-8"))
        total += size
        if size > limits.max_file_bytes:
            problems.append((f"{where}.content", f"{path} is {size} bytes; the limit is {limits.max_file_bytes}"))
        if "\x00" in change.content:
            problems.append((f"{where}.content", f"{path} looks binary; only text files can be changed"))
        if kinds := find_secrets(change.content):
            problems.append((f"{where}.content", f"{path} contains what looks like a secret ({', '.join(kinds)})"))
    if total > limits.max_total_bytes:
        problems.append(("files", f"{total} bytes of new content; the limit per change set is {limits.max_total_bytes}"))

    if work_type in policy.tests_required_for and not any(c.action != "delete" and policy.is_test(c.path) for c in files):
        problems.append(("files", f"A {work_type} work item adds or changes at least one test file (for example under tests/)"))

    if not design_items:
        problems.append(("design_items", f"Name the design items of {work_item} this change implements"))
    for field, given, allowed, label in (
        ("design_items", design_items, allowed_design_items, "design items"),
        ("requirements", requirements, allowed_requirements, "requirements"),
        ("acceptance_criteria", acceptance, allowed_acceptance, "acceptance criteria"),
    ):
        for ref in given:
            if ref not in allowed:
                shown = ", ".join(allowed) or "none"
                problems.append((field, f"{ref} is not one of {work_item}'s {label} ({shown})"))

    command = test_command.strip()
    if not command or "\n" in command or "\r" in command:
        problems.append(("test_command", "Give one command line that runs the tests"))
    return problems
