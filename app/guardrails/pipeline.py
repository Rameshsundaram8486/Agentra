"""Runs the input checkpoint (G1) before a model call and the output checkpoint (G4) after it.

G1: secrets are redacted from untrusted content and injection-like text is flagged; the content is then
wrapped as data. G4: the output must match the schema; every `source_quotes` entry must appear in the source;
no other text may claim approvals, decisions, passed tests or deployments; nothing may contain a secret.
Tool-call checks (G3) arrive with the first agent that uses tools.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.guardrails.findings import Finding, blocking
from app.guardrails.input.injection_screen import screen
from app.guardrails.input.untrusted_content import wrap
from app.guardrails.output.forbidden_claims import find_claims
from app.guardrails.output.grounding import check_quotes
from app.guardrails.output.schema_validation import parse_output
from app.guardrails.output.secret_scan import find_secrets, redact_secrets

QUOTE_FIELD = "source_quotes"


@dataclass(frozen=True)
class InputCheck:
    text: str  # redacted, not yet wrapped: grounding compares quotes against exactly what the model saw
    wrapped: str
    findings: list[Finding]


@dataclass(frozen=True)
class OutputCheck[T: BaseModel]:
    value: T | None  # None whenever a blocking finding exists
    findings: list[Finding]

    @property
    def blocked(self) -> bool:
        return bool(blocking(self.findings))


def check_input(content: str, *, tag: str, source: str, **attributes: str) -> InputCheck:
    text, secret_kinds = redact_secrets(content)
    findings = [
        Finding("secret_redacted", "warn", f"Removed from the {source} before sending to the model: {', '.join(secret_kinds)}")
    ] if secret_kinds else []
    findings += screen(text, source=source)
    return InputCheck(text=text, wrapped=wrap(tag, text, **attributes), findings=findings)


def _strings(value: Any, path: str = "") -> list[tuple[str, str, bool]]:
    """(path, text, is_quote) for every string in parsed JSON."""
    if isinstance(value, str):
        return [(path, value, False)]
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            child = f"{path}.{key}" if path else key
            if key == QUOTE_FIELD and isinstance(item, list):
                found += [(f"{child}[{i}]", quote, True) for i, quote in enumerate(item) if isinstance(quote, str)]
            else:
                found += _strings(item, child)
        return found
    if isinstance(value, list):
        return [entry for i, item in enumerate(value) for entry in _strings(item, f"{path}[{i}]")]
    return []


def check_output[T: BaseModel](raw: str, model: type[T], *, source_text: str, source_name: str) -> OutputCheck[T]:
    value, data, findings = parse_output(raw, model)
    if data is not None:
        strings = _strings(data)
        findings += [
            Finding("secret", "block", f"Output contains what looks like a secret ({', '.join(kinds)})", path)
            for path, text, _ in strings
            if (kinds := find_secrets(text))
        ]
        findings += find_claims([(path, text) for path, text, is_quote in strings if not is_quote])
        findings += check_quotes([(path, text) for path, text, is_quote in strings if is_quote], source_text, source_name=source_name)
    return OutputCheck(value=None if blocking(findings) else value, findings=findings)
