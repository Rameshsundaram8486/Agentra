"""Review content rules and the security checklist config: pure functions, no database."""

from pathlib import Path

import pytest

from app.composition import CONFIG_DIR
from app.modules.design_reviews.checklist import load_security_checklist
from app.modules.design_reviews.rules import assurance_claims, feasibility_problems, security_problems
from app.modules.design_reviews.schemas import FindingDraft

CHECKS = {"SC-01": "Sign-in", "SC-02": "Access"}
ITEMS = {"CMP-001": "component", "SEC-001": "security_control", "DQ-001": "open_question"}


def _s(ref: str, verdict: str = "addressed", **changes: object) -> FindingDraft:
    data = {"ref": ref, "verdict": verdict, "assessment": "Handled.", "design_items": ["SEC-001"] if verdict == "addressed" else []}
    data.update(changes)
    return FindingDraft.model_validate(data)


def _f(ref: str, verdict: str = "feasible", **changes: object) -> FindingDraft:
    data = {"ref": ref, "verdict": verdict, "complexity": "M", "assessment": "Buildable.", "recommendation": "" if verdict == "feasible" else "Spike first."}
    data.update(changes)
    return FindingDraft.model_validate(data)


def _messages(problems: list[tuple[str, str]]) -> list[str]:
    return [message for _, message in problems]


def test_a_complete_security_review_has_no_problems() -> None:
    findings = [_s("SC-01"), _s("SC-02", "gap", severity="medium", recommendation="Add SEC-002.")]
    assert security_problems(findings, CHECKS, set(ITEMS), {"REQ-F-001"}) == []


@pytest.mark.parametrize(
    ("findings", "expected"),
    [
        ([_s("SC-01")], "No answer for check SC-02"),
        ([_s("SC-01"), _s("SC-01"), _s("SC-02")], "SC-01 is answered 2 times"),
        ([_s("SC-01", design_items=[]), _s("SC-02")], "SC-01 is marked addressed but cites no design item"),
        ([_s("SC-01", "gap", recommendation="Fix"), _s("SC-02")], "SC-01 is a gap without a severity"),
        ([_s("SC-01", "gap", severity="low"), _s("SC-02")], "SC-01 is a gap without a recommended fix"),
        ([_s("SC-01", severity="high"), _s("SC-02")], "SC-01: only gaps have a severity"),
        ([_s("SC-01", "not_applicable", assessment=" "), _s("SC-02")], "SC-01 needs an assessment (for not applicable: why)"),
        ([_s("SC-01", design_items=["CMP-404"]), _s("SC-02")], "'CMP-404' is not a design item in the reviewed version"),
        ([_s("SC-01", requirements=["REQ-F-404"]), _s("SC-02")], "'REQ-F-404' is not a requirement in the approved version"),
        ([_s("SC-01"), _s("SC-02"), _s("SC-03")], "'SC-03' is not a check in the security checklist"),
        ([_s("SC-01", "maybe"), _s("SC-02")], "'maybe' is not one of addressed, gap, not_applicable"),
    ],
)
def test_security_review_problems(findings: list[FindingDraft], expected: str) -> None:
    assert expected in _messages(security_problems(findings, CHECKS, set(ITEMS), {"REQ-F-001"}))


def test_a_complete_feasibility_review_skips_open_questions() -> None:
    assert feasibility_problems([_f("CMP-001"), _f("SEC-001", "concerns")], ITEMS, set()) == []


@pytest.mark.parametrize(
    ("findings", "expected"),
    [
        ([_f("CMP-001")], "No answer for design item SEC-001"),
        ([_f("CMP-001"), _f("SEC-001"), _f("DQ-001")], "'DQ-001' is not a reviewable design item in this version"),
        ([_f("CMP-001", complexity=None), _f("SEC-001")], "CMP-001 needs a complexity (S, M or L)"),
        ([_f("CMP-001", "not_feasible", recommendation=""), _f("SEC-001")], "CMP-001 is rated not feasible without saying what would resolve it"),
        ([_f("CMP-001", severity="high"), _f("SEC-001")], "Feasibility findings have no severity"),
        ([_f("CMP-001", design_items=["API-404"]), _f("SEC-001")], "'API-404' is not a design item in the reviewed version"),
    ],
)
def test_feasibility_review_problems(findings: list[FindingDraft], expected: str) -> None:
    assert expected in _messages(feasibility_problems(findings, ITEMS, set()))


@pytest.mark.parametrize(
    "text",
    [
        "The design is secure.",
        "Overall the solution is fully compliant with UAE data protection law.",
        "It meets all security requirements.",
        "No security risks remain.",
        "The integrations are risk-free.",
    ],
)
def test_assurance_claims_are_found(text: str) -> None:
    assert _messages(assurance_claims([("summary", text)]))[0].startswith("Claims assurance only a person can give")


@pytest.mark.parametrize(
    "text",
    [
        "The sign-in would be secure once conditional access is licensed.",
        "The retention design is not yet compliant with the six-year rule.",
        "Data must be secure in transit; SEC-001 covers this with TLS 1.2.",
        "A secure channel is used for the HR integration.",
        "If the vendor confirms the certificate, the link is secure.",
    ],
)
def test_hedged_and_descriptive_wording_is_allowed(text: str) -> None:
    assert assurance_claims([("summary", text)]) == []


def test_the_committed_checklist_loads_with_its_hash() -> None:
    checklist = load_security_checklist(CONFIG_DIR / "policies" / "security_checklist.yaml")

    assert list(checklist.checks) == [f"SC-{n:02d}" for n in range(1, 11)]
    assert len(checklist.sha256) == 64 and checklist.label.startswith("security_checklist v1 (sha256 ")


def test_checklist_ids_must_look_like_sc_numbers(tmp_path: Path) -> None:
    path = tmp_path / "checklist.yaml"
    path.write_text("version: 1\nchecks:\n  AUTH: {title: Sign-in, question: \"How do people sign in here?\"}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="check IDs look like SC-01"):
        load_security_checklist(path)
