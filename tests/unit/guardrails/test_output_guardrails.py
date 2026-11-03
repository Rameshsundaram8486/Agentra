import json

import pytest

from app.agents.business_analyst.agent import ClarifyBriefOutput
from app.guardrails.output.forbidden_claims import find_claims
from app.guardrails.output.grounding import check_quotes, normalise, quote_found
from app.guardrails.pipeline import Sources, check_output
from tests.agent_support import BRIEF, ba_json, ba_output


def _sources(text: str = BRIEF) -> Sources:
    return Sources(documents={"BRIEF": text}, names={"BRIEF": "brief"}, default="BRIEF")


def _check(raw: str):  # noqa: ANN202
    return check_output(raw, ClarifyBriefOutput, sources=_sources())


def test_valid_grounded_output_passes() -> None:
    result = _check(ba_json())

    assert not result.blocked
    assert result.findings == []
    assert isinstance(result.value, ClarifyBriefOutput)


@pytest.mark.parametrize(
    "quote",
    [
        "The company already uses Microsoft 365.",
        "the company ALREADY uses   microsoft 365",  # case and spacing
        "Customer: Example Trading LLC",  # Markdown emphasis in the source
        "Managers lose requests, and HR spends two days each month",  # line break in the source
        "Leave requests are made by email ... shared Excel sheet",  # ellipsis joins parts in order
        "Leave Management – project brief",  # en dash in the quote, hyphen in the source
    ],
)
def test_faithful_quotes_are_found(quote: str) -> None:
    assert quote_found(quote, normalise(BRIEF))


@pytest.mark.parametrize(
    "quote",
    [
        "Employees work four days a week.",  # invented
        "shared Excel sheet ... Leave requests are made by email",  # parts out of order
        "HR",  # too short to mean anything
        "",
    ],
)
def test_invented_or_meaningless_quotes_are_not_found(quote: str) -> None:
    assert not quote_found(quote, normalise(BRIEF))


def test_ungrounded_quote_blocks_with_its_path() -> None:
    output = ba_output()
    output["clarifying_questions"][1]["source_quotes"] = ["Balances are kept in SAP."]

    result = _check(json.dumps(output))

    assert result.blocked and result.value is None
    assert [(f.check, f.path) for f in result.findings] == [("grounding", "clarifying_questions[1].source_quotes[0]")]


@pytest.mark.parametrize(
    "claim",
    [
        "The customer has approved Power Platform.",
        "This stack has been approved by the sponsor.",
        "The requirements have been baselined.",
        "The approach has already been decided.",
        "I have approved the recommendation.",
        "All tests have passed.",
        "The release has been deployed to production.",
    ],
)
def test_status_claims_are_blocked(claim: str) -> None:
    findings = find_claims([("x", claim)])

    assert [f.check for f in findings] == ["forbidden_claim"]
    assert findings[0].severity == "block"


@pytest.mark.parametrize(
    "text",
    [
        "Who approves leave for line managers?",
        "Approved leave is deducted from the employee's balance.",
        "Once the scope has been approved by the sponsor, build starts.",
        "The design should not be finalised until the customer has decided on integrations.",
        "Nothing has been decided yet.",
        "Confirm whether the customer has approved the budget.",
    ],
)
def test_domain_language_conditions_and_questions_are_allowed(text: str) -> None:
    assert find_claims([("x", text)]) == []


def test_a_claim_in_agent_prose_blocks_but_the_same_words_in_a_quote_do_not() -> None:
    brief = BRIEF + "\nThe sponsor has approved the budget.\n"
    output = ba_output()
    output["technology_stack"]["source_quotes"] = ["The sponsor has approved the budget."]
    assert not check_output(json.dumps(output), ClarifyBriefOutput, sources=_sources(brief)).blocked

    output["technology_stack"]["context"] = "The sponsor has approved the budget, so cost is settled."
    result = check_output(json.dumps(output), ClarifyBriefOutput, sources=_sources(brief))
    assert [(f.check, f.path) for f in result.findings] == [("forbidden_claim", "technology_stack.context")]


def test_secret_in_output_blocks() -> None:
    result = _check(ba_json(brief_summary="Use key sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123 for testing."))

    assert result.blocked
    assert [(f.check, f.path) for f in result.findings] == [("secret", "brief_summary")]


@pytest.mark.parametrize(
    ("raw", "expected_path"),
    [
        ("not json", None),
        (json.dumps({"brief_summary": "x"}), "technology_stack"),
    ],
)
def test_malformed_output_blocks(raw: str, expected_path: str | None) -> None:
    result = _check(raw)

    assert result.blocked
    assert result.findings[0].check == "schema"
    if expected_path:
        assert expected_path in {f.path for f in result.findings}


def test_cross_field_rules_are_enforced_in_code() -> None:
    output = ba_output()
    output["technology_stack"]["recommended_option"] = "not_an_option"
    output["delivery_approach"]["options"] = output["delivery_approach"]["options"][:1]
    output["clarifying_questions"][1]["recommendation_rationale"] = ""

    result = _check(json.dumps(output))

    assert result.blocked
    assert {f.path for f in result.findings} >= {"technology_stack", "delivery_approach.options", "clarifying_questions[1]"}


def test_check_quotes_reports_every_bad_quote() -> None:
    findings = check_quotes([("a", "The company already uses Microsoft 365."), ("b", "made up"), ("c", "also made up")], BRIEF, source_name="brief")

    assert [f.path for f in findings] == ["b", "c"]
