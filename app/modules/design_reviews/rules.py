"""Rules for review content, shared by the agent tasks (before anything is saved) and the service (before a
review is recorded). Pure functions: each returns (path, message) problems."""

import re
from collections.abc import Iterable, Mapping, Sequence

from app.modules.design_reviews.schemas import FindingDraft

SECURITY_VERDICTS = ("addressed", "gap", "not_applicable")
FEASIBILITY_VERDICTS = ("feasible", "concerns", "not_feasible")
NOT_REVIEWED_KINDS = ("open_question",)  # feasibility covers every other design item

Problem = tuple[str, str]


def _refs(finding: FindingDraft, path: str, design_ids: set[str], requirement_ids: set[str]) -> list[Problem]:
    problems = [(f"{path}.design_items", f"{ref!r} is not a design item in the reviewed version") for ref in finding.design_items if ref not in design_ids]
    problems += [(f"{path}.requirements", f"{ref!r} is not a requirement in the approved version") for ref in finding.requirements if ref not in requirement_ids]
    return problems


def _once(refs: list[str], expected: Iterable[str], what: str) -> list[Problem]:
    problems = [("findings", f"{ref} is answered {refs.count(ref)} times") for ref in sorted(set(refs)) if refs.count(ref) > 1]
    missing = [ref for ref in expected if ref not in refs]
    if missing:
        problems.append(("findings", f"No answer for {what} {', '.join(missing)}"))
    return problems


def security_problems(findings: Sequence[FindingDraft], checks: Mapping[str, str], design_ids: set[str], requirement_ids: set[str]) -> list[Problem]:
    """checks: check ID -> title. Every check answered once; addressed cites design items; a gap has a severity
    and a fix; not applicable says why."""
    problems = _once([f.ref for f in findings], checks, "check")
    for index, finding in enumerate(findings):
        path = f"findings[{index}]"
        if finding.ref not in checks:
            problems.append((f"{path}.ref", f"{finding.ref!r} is not a check in the security checklist"))
        if finding.verdict not in SECURITY_VERDICTS:
            problems.append((f"{path}.verdict", f"{finding.verdict!r} is not one of {', '.join(SECURITY_VERDICTS)}"))
        if finding.verdict == "addressed" and not finding.design_items:
            problems.append((f"{path}.design_items", f"{finding.ref} is marked addressed but cites no design item"))
        if finding.verdict == "gap":
            if finding.severity is None:
                problems.append((f"{path}.severity", f"{finding.ref} is a gap without a severity"))
            if not finding.recommendation.strip():
                problems.append((f"{path}.recommendation", f"{finding.ref} is a gap without a recommended fix"))
        elif finding.severity is not None:
            problems.append((f"{path}.severity", f"{finding.ref}: only gaps have a severity"))
        if not finding.assessment.strip():
            problems.append((f"{path}.assessment", f"{finding.ref} needs an assessment (for not applicable: why)"))
        if finding.complexity is not None:
            problems.append((f"{path}.complexity", "Security findings have no complexity"))
        problems += _refs(finding, path, design_ids, requirement_ids)
    return problems


def feasibility_problems(findings: Sequence[FindingDraft], items: Mapping[str, str], requirement_ids: set[str]) -> list[Problem]:
    """items: design item ID -> kind, for the reviewed version. Every item but open questions is rated once, with
    a complexity; concerns and not feasible say what would resolve them."""
    reviewed = [item_id for item_id, kind in items.items() if kind not in NOT_REVIEWED_KINDS]
    problems = _once([f.ref for f in findings], reviewed, "design item")
    for index, finding in enumerate(findings):
        path = f"findings[{index}]"
        if finding.ref not in reviewed:
            problems.append((f"{path}.ref", f"{finding.ref!r} is not a reviewable design item in this version"))
        if finding.verdict not in FEASIBILITY_VERDICTS:
            problems.append((f"{path}.verdict", f"{finding.verdict!r} is not one of {', '.join(FEASIBILITY_VERDICTS)}"))
        if finding.complexity is None:
            problems.append((f"{path}.complexity", f"{finding.ref} needs a complexity (S, M or L)"))
        if finding.severity is not None:
            problems.append((f"{path}.severity", "Feasibility findings have no severity"))
        if not finding.assessment.strip():
            problems.append((f"{path}.assessment", f"{finding.ref} needs an assessment"))
        if finding.verdict in ("concerns", "not_feasible") and not finding.recommendation.strip():
            problems.append((f"{path}.recommendation", f"{finding.ref} is rated {finding.verdict.replace('_', ' ')} without saying what would resolve it"))
        problems += _refs(finding, path, set(items), requirement_ids)
    return problems


# "The design is secure" is a conclusion only people reach, through the checklist and a sign-off. Conditions and
# negations are fine: "would be secure once ...", "is not yet compliant".
_ASSURANCE = re.compile(
    r"\b(?:is|are)\s+(?:now\s+|fully\s+|completely\s+|entirely\s+|already\s+)?(?:secure|compliant|risk[- ]free)\b"
    r"|\bmeets\s+all\s+(?:the\s+)?(?:security|compliance)\s+requirements\b"
    r"|\bno\s+(?:security\s+)?(?:risks?|vulnerabilit(?:y|ies)|weaknesses)\s+(?:exist|remain|were\s+found)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(r"\b(?:if|once|until|unless|when|whether|after|before|not|never|yet|would|could|should|must)\b[^.;:!?\n]*$", re.IGNORECASE)


def assurance_claims(texts: Iterable[tuple[str, str]]) -> list[Problem]:
    """(path, text) pairs -> unhedged claims that something is secure or compliant (at most one per text)."""
    problems = []
    for path, text in texts:
        for match in _ASSURANCE.finditer(text):
            if not _HEDGE.search(text[max(0, match.start() - 60) : match.start()]):
                problems.append((path, f'Claims assurance only a person can give: "{" ".join(match.group(0).split())}"'))
                break
    return problems
