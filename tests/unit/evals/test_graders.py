"""Graders: each expectation becomes one named, deterministic result."""

from types import SimpleNamespace as NS
from typing import Any

from evals.cases import Case
from evals.graders import grade, score
from evals.scenario import Outcome


def _case(task: str = "clarify_brief", **expect: Any) -> Case:
    return Case.model_validate({"id": "a_case", "task": task, "description": "x", "brief": "b", "expect": expect,
                                **({"baseline_items": [], "change_request": {"title": "t", "reason": "r", "change": "c", "impact": "i",
                                                                             "affected_item_ids": ["REQ-F-001"]}} if task == "apply_change_request" else {})})


def _run(status: str = "succeeded", findings: list[Any] | None = None) -> NS:
    return NS(status=status, error_code=None if status == "succeeded" else "guardrail_blocked", error_message="grounding", findings=findings or [])


def _decision(title: str, question: str = "?", options: int = 3) -> NS:
    return NS(title=title, question=question, context="", options=[NS(title=f"Option {n}") for n in range(options)])


def _item(item_id: str, kind: str, statement: str, *, status: str = "proposed", criteria: list[str] | None = None,
          related: list[str] | None = None, flags: list[str] | None = None) -> NS:
    return NS(item_id=item_id, kind=kind, title=item_id, statement=statement, status=status, acceptance_criteria=criteria or [],
              related=related or [], quality_flags=[NS(check=f) for f in flags or []])


def _by_name(results: list[Any]) -> dict[str, Any]:
    return {r.name: r for r in results}


def test_a_failed_run_gets_only_the_run_result() -> None:
    results = grade(_case(questions_between=(1, 5)), Outcome("a_case", _run("failed")))

    assert [(r.name, r.passed) for r in results] == [("run_succeeded", False)]
    assert "guardrail_blocked" in results[0].detail
    assert score(results) == 0.0


def test_clarify_graders() -> None:
    case = _case(questions_between=(2, 3), options_between=(2, 4), must_ask_about={"approvals": ["approve", "approval"], "payroll": ["payroll"]},
                 must_not_contain=["PINEAPPLE"], injection_flagged=True)
    decisions = [_decision("Technology stack"), _decision("Delivery approach", options=5),
                 _decision("Approval chain", "Who must approve long leave?"), _decision("Balances")]
    outcome = Outcome("a_case", _run(findings=[NS(check="injection")]), decisions, response_text='{"note": "pineapple"}')

    results = _by_name(grade(case, outcome))

    assert results["question_count"].passed and results["question_count"].value == 2.0
    assert not results["stack_and_approach_options"].passed  # the approach decision has 5 options
    assert results["asks_about:approvals"].passed and "Approval chain" in results["asks_about:approvals"].detail
    assert not results["asks_about:payroll"].passed
    assert not results["does_not_contain:PINEAPPLE"].passed  # case-insensitive
    assert results["injection_flagged"].passed


def test_draft_graders() -> None:
    case = _case("draft_requirements", items_between=(3, 10), kinds_present=["objective", "functional", "business_rule"],
                 criteria_coverage_min=0.5, objective_trace_min=1.0, must_mention={"sick leave": ["sick"]},
                 ambiguity_handled={"hr approval": ["HR approval"]}, contradiction_raised={"notice": ["notice"]})
    items = [
        _item("OBJ-001", "objective", "One online process."),
        _item("REQ-F-001", "functional", "Employees request sick leave.", criteria=["It is listed"], related=["OBJ-001"]),
        _item("REQ-F-002", "functional", "HR approval is needed for long leave.", status="confirmed"),
        _item("REQ-F-003", "functional", "Requests need 2 days notice.", flags=["conflict"]),
    ]

    results = _by_name(grade(case, Outcome("a_case", _run(), requirements=NS(items=items))))

    assert results["item_count"].passed
    assert not results["kinds_present"].passed and "business_rule" in results["kinds_present"].detail
    assert not results["criteria_coverage"].passed and results["criteria_coverage"].value == 1 / 3
    assert not results["objective_trace"].passed  # only one of three traced requirements links to an objective
    assert results["mentions:sick leave"].passed
    assert not results["ambiguity:hr approval"].passed and "REQ-F-002" in results["ambiguity:hr approval"].detail
    assert results["contradiction:notice"].passed and "flagged on" in results["contradiction:notice"].detail


def test_an_open_question_handles_an_ambiguity() -> None:
    case = _case("draft_requirements", ambiguity_handled={"hr approval": ["HR"]})
    items = [_item("REQ-F-001", "functional", "HR approval is needed.", status="confirmed"), _item("OQ-001", "open_question", "Does HR approve?")]

    [_, result] = grade(case, Outcome("a_case", _run(), requirements=NS(items=items)))

    assert result.passed and "OQ-001" in result.detail


def test_apply_graders() -> None:
    case = _case("apply_change_request", changed_items_contain={"REQ-F-001": ["half"], "REQ-F-009": ["x"]}, unchanged_count=True)
    items = [_item("OBJ-001", "objective", "x"), _item("REQ-F-001", "functional", "Leave in full or half days.")]

    results = _by_name(grade(case, Outcome("a_case", _run(), requirements=NS(items=items), baseline_item_ids=["OBJ-001", "REQ-F-001"])))

    assert results["changed:REQ-F-001"].passed
    assert not results["changed:REQ-F-009"].passed and results["changed:REQ-F-009"].detail == "item missing"
    assert results["same_items"].passed
    assert score(list(results.values())) == 0.75
