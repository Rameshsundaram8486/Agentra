"""A guardrail finding. `block` stops the output from being used; `warn` is recorded and the run continues."""

from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["block", "warn"]


@dataclass(frozen=True)
class Finding:
    check: str  # e.g. schema, grounding, forbidden_claim, secret, injection, secret_redacted
    severity: Severity
    message: str
    path: str | None = None  # where in the output, e.g. clarifying_questions[2].source_quotes[0]

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def blocking(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.severity == "block"]
