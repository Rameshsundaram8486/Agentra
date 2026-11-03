"""Runs the input checkpoint (G1) before a model call and the output checkpoint (G4) after it.

G1: secrets are redacted from untrusted content and injection-like text is flagged; the content is then
wrapped as data. G4: the output must match the schema; every quoted passage (`source_quotes`, or the quote of
a {"ref", "quote"} entry in a `sources` list) must appear in the document it cites, and cited decisions must
be ones the agent was shown; no other text may claim approvals, decisions, passed tests or deployments;
nothing may contain a secret.
Tool-call checks (G3) arrive with the first agent that uses tools.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.guardrails.findings import Finding, blocking
from app.guardrails.input.injection_screen import screen
from app.guardrails.input.untrusted_content import wrap
from app.guardrails.output.forbidden_claims import find_claims
from app.guardrails.output.grounding import normalise, quote_found
from app.guardrails.output.schema_validation import parse_output
from app.guardrails.output.secret_scan import find_secrets, redact_secrets

QUOTE_FIELD = "source_quotes"
CITATIONS_FIELD = "sources"


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


@dataclass(frozen=True)
class Sources:
    """What an agent was shown, so its citations can be checked.

    documents: ref -> text exactly as the model saw it (after redaction). names: ref -> name for messages.
    decisions: refs of decision records it may cite. default: the document that bare `source_quotes` lists
    quote from (tasks with a single source document).
    """

    documents: Mapping[str, str]
    names: Mapping[str, str]
    decisions: frozenset[str] = frozenset()
    default: str | None = None


@dataclass(frozen=True)
class _Text:
    path: str
    text: str
    quote_ref: str | None = None  # set for quoted passages: the source they claim to come from
    is_quote: bool = False


def _strings(value: Any, path: str = "", default: str | None = None) -> list[_Text]:
    """Every string in parsed JSON. `source_quotes` lists quote the default document; `sources` lists hold
    {"ref", "quote"} citations; their refs and quotes are not prose."""
    if isinstance(value, str):
        return [_Text(path, value)]
    if isinstance(value, dict):
        found: list[_Text] = []
        for key, item in value.items():
            child = f"{path}.{key}" if path else key
            if key == QUOTE_FIELD and isinstance(item, list):
                found += [_Text(f"{child}[{i}]", quote, default, True) for i, quote in enumerate(item) if isinstance(quote, str)]
            elif key == CITATIONS_FIELD and isinstance(item, list) and all(isinstance(entry, dict) for entry in item):
                for i, entry in enumerate(item):
                    ref, quote = entry.get("ref"), entry.get("quote")
                    if isinstance(ref, str) and isinstance(quote, str):
                        found.append(_Text(f"{child}[{i}]", quote, ref.strip(), True))
            else:
                found += _strings(item, child, default)
        return found
    if isinstance(value, list):
        return [entry for i, item in enumerate(value) for entry in _strings(item, f"{path}[{i}]", default)]
    return []


def _citation_findings(quotes: list[_Text], sources: Sources) -> list[Finding]:
    normalised = {ref: normalise(text) for ref, text in sources.documents.items()}
    findings = []
    for entry in quotes:
        ref = entry.quote_ref
        if ref in sources.decisions:
            continue  # a decision is cited by reference; it exists, and its answer is read from the record
        if ref not in normalised:
            findings.append(Finding("grounding", "block", f"Cites a source that was not provided: {ref!r}", entry.path))
        elif not quote_found(entry.text, normalised[ref]):
            name = sources.names.get(ref, ref)
            findings.append(Finding("grounding", "block", f"Quoted text does not appear in the {name}: \"{entry.text[:120]}\"", entry.path))
    return findings


def check_output[T: BaseModel](raw: str, model: type[T], *, sources: Sources) -> OutputCheck[T]:
    value, data, findings = parse_output(raw, model)
    if data is not None:
        strings = _strings(data, default=sources.default)
        findings += [
            Finding("secret", "block", f"Output contains what looks like a secret ({', '.join(kinds)})", entry.path)
            for entry in strings
            if (kinds := find_secrets(entry.text))
        ]
        findings += find_claims([(entry.path, entry.text) for entry in strings if not entry.is_quote])
        findings += _citation_findings([entry for entry in strings if entry.is_quote], sources)
    return OutputCheck(value=None if blocking(findings) else value, findings=findings)
