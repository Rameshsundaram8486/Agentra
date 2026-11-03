"""Screens untrusted content for prompt-injection patterns.

A match is recorded as a warning on the run; it does not stop the run. The content is always sent wrapped as
untrusted data, and what the model returns still has to pass the output guardrails, so a successful injection
cannot approve, decide or leak anything on its own. The screen gives reviewers visibility.
"""

import re

from app.guardrails.findings import Finding

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override previous instructions", re.compile(r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|system|all)\b[^.\n]{0,20}\b(?:instructions?|prompts?|rules|guidelines)\b", re.IGNORECASE)),
    ("role reassignment", re.compile(r"\byou are (?:now|no longer)\b|\bfrom now on,? you\b|\bact as (?:an?|the) (?:ai|assistant|system|admin)", re.IGNORECASE)),
    ("prompt extraction", re.compile(r"\b(?:reveal|print|show|repeat|output)\b[^.\n]{0,30}\b(?:system prompt|your instructions|hidden instructions)\b", re.IGNORECASE)),
    ("chat role markup", re.compile(r"</?\s*(?:system|assistant|user|instructions?)\s*>|^\s*(?:system|assistant)\s*:", re.IGNORECASE | re.MULTILINE)),
    ("approval request to the agent", re.compile(r"\b(?:mark|record|treat|consider)\b[^.\n]{0,40}\bas (?:approved|signed[ -]off|accepted|decided)\b", re.IGNORECASE)),
]


def screen(text: str, *, source: str) -> list[Finding]:
    findings = []
    for label, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            excerpt = " ".join(match.group(0).split())[:80]
            findings.append(
                Finding("injection", "warn", f"{source} contains text that looks like {label}: \"{excerpt}\"")
            )
    return findings
