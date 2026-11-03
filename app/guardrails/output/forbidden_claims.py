"""Blocks unevidenced status claims: that something was approved, signed off, decided, tested or deployed.

Agents propose; only people approve and decide, and those facts live in approval and decision records, never
in agent prose. The patterns target completed-status claims, not domain vocabulary or conditions:
"an approved leave request", "who approves overtime?" and "once the scope has been approved by the sponsor"
are fine; "the customer has approved the scope" and "the stack has been decided" are not.
Quoted source passages are checked by grounding instead, since a brief may itself report an approval.
"""

import re

from app.guardrails.findings import Finding

_SUBJECTS = r"(?:customer|client|sponsor|stakeholders?|owner|reviewer|management|board)"
_STATUS = r"(?:approved|signed[ -]off|decided(?: on)?|finali[sz]ed|baselined)"
_ITEMS = r"(?:decision|stack|approach|recommendation|requirements?|baseline|scope|design|plan|option|proposal)"
_PERFECT = r"(?:has|have|had)\s+(?:already\s+|now\s+|formally\s+)?"

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("a person or party approved or decided", re.compile(rf"\b{_SUBJECTS}\s+{_PERFECT}{_STATUS}\b", re.IGNORECASE)),
    ("something was approved by someone", re.compile(rf"\b(?:{_PERFECT}been|was|were)\s+(?:already\s+|formally\s+)?{_STATUS}\s+by\b", re.IGNORECASE)),
    ("a project item is already settled", re.compile(rf"\b{_ITEMS}\s+{_PERFECT}been\s+{_STATUS}\b", re.IGNORECASE)),
    ("tests passed", re.compile(r"\b(?:tests?|uat|test cases?)\s+(?:has|have|had)\s+(?:all\s+)?passed\b", re.IGNORECASE)),
    ("deployed to production", re.compile(r"\b(?:has|have|had)\s+been\s+(?:deployed|released)\s+(?:to|in|into)\s+production\b", re.IGNORECASE)),
    ("the agent approved or decided", re.compile(r"\bI\s+(?:have\s+)?(?:approved|signed off|decided)\b")),
]

# A claim inside a condition or a negation is not a claim: "until the scope has been approved by ...".
_HEDGE = re.compile(
    r"\b(?:until|once|before|after|if|when|whether|unless|not|never|yet|pending|need|needs|must|should|will|would|"
    r"can|could|may|might)\b[^.;:!?\n]*$",
    re.IGNORECASE,
)
_HEDGE_WINDOW = 60


def _hedged(text: str, start: int) -> bool:
    return bool(_HEDGE.search(text[max(0, start - _HEDGE_WINDOW) : start]))


def _first_claim(text: str) -> tuple[str, str] | None:
    for label, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            if not _hedged(text, match.start()):
                return label, " ".join(match.group(0).split())
    return None


def find_claims(texts: list[tuple[str, str]]) -> list[Finding]:
    """texts: (path, text) pairs. At most one finding per text."""
    findings = []
    for path, text in texts:
        if claim := _first_claim(text):
            label, words = claim
            findings.append(Finding("forbidden_claim", "block", f'Claims {label}: "{words}"', path))
    return findings
