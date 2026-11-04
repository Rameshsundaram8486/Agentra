"""Design completeness checks. Rule-based and deterministic. Flags inform the reviewer; the requirement coverage
gate (every confirmed requirement mapped or excepted) is enforced separately, at phase completion."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.design.schemas import QualityFlag

LINKED_KINDS = ("component", "data_flow", "interface", "entity", "security_control")


@dataclass(frozen=True)
class CheckedItem:
    item_id: str
    kind: str
    label: str
    rationale: str
    satisfies: Sequence[str]
    related: Sequence[str]
    unverified_capabilities: Sequence[str]


def check_items(items: Sequence[CheckedItem], gaps: Sequence[str]) -> tuple[dict[str, list[QualityFlag]], list[QualityFlag]]:
    flags: dict[str, list[QualityFlag]] = {item.item_id: [] for item in items}
    for item in items:
        for capability in item.unverified_capabilities:
            flags[item.item_id].append(
                QualityFlag(check="unverified", severity="warning", message=f"Relies on a capability the inputs do not confirm: {capability}")
            )
        if item.kind in LINKED_KINDS and not item.satisfies and not item.related:
            flags[item.item_id].append(QualityFlag(check="traceability", severity="warning", message="Not linked to any requirement or design item"))
        if item.kind == "decision" and not item.rationale.strip():
            flags[item.item_id].append(QualityFlag(check="completeness", severity="warning", message="An architecture decision without a rationale"))
        if item.label == "assumption":
            flags[item.item_id].append(QualityFlag(check="assumption", severity="info", message="Rests on an assumption to confirm"))

    kinds = {item.kind for item in items}
    set_flags = [
        QualityFlag(check="completeness", severity="warning", message=f"No {label} yet")
        for kind, label in (
            ("component", "components"),
            ("interface", "interfaces"),
            ("entity", "data entities"),
            ("security_control", "security controls"),
            ("environment", "environments"),
            ("decision", "architecture decisions"),
        )
        if kind not in kinds
    ]
    if gaps:
        set_flags.append(
            QualityFlag(check="coverage", severity="warning", message=f"{len(gaps)} confirmed requirement(s) not covered: {', '.join(gaps)}", related=list(gaps))
        )
    unverified = sum(1 for item in items if item.unverified_capabilities)
    if unverified:
        set_flags.append(QualityFlag(check="unverified", severity="warning", message=f"{unverified} item(s) rely on capabilities to verify"))
    return flags, set_flags
