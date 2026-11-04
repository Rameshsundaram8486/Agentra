"""Eval case files: the committed cases load, and malformed ones are rejected before anything runs."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.cases import load_cases


def _write_case(root: Path, name: str, body: str) -> None:
    cases = root / "business_analyst" / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    (cases / f"{name}.yaml").write_text(body, encoding="utf-8")


def test_committed_cases_load() -> None:
    cases = {case.id: case for case in load_cases()}

    assert {"clarify_leave", "clarify_injection", "draft_leave", "apply_cr_half_days"} <= set(cases)
    assert cases["draft_leave"].documents and all(d.content for d in cases["draft_leave"].documents)
    assert "PINEAPPLE" in cases["clarify_injection"].brief  # the brief file was read in


def test_pattern_selects_a_subset() -> None:
    assert {case.task for case in load_cases(pattern="clarify_*")} == {"clarify_brief"}


def test_file_references_are_read_from_inputs(tmp_path: Path) -> None:
    (tmp_path / "business_analyst" / "inputs").mkdir(parents=True)
    (tmp_path / "business_analyst" / "inputs" / "brief.md").write_text("# A synthetic brief", encoding="utf-8")
    _write_case(tmp_path, "clarify_one", "id: clarify_one\ntask: clarify_brief\ndescription: x\nbrief: {file: brief.md}\nexpect: {questions_between: [1, 3]}\n")

    [case] = load_cases(tmp_path)

    assert case.brief == "# A synthetic brief"
    assert case.expect.questions_between == (1, 3)


def test_id_must_match_the_file_name(tmp_path: Path) -> None:
    _write_case(tmp_path, "clarify_one", "id: clarify_two\ntask: clarify_brief\ndescription: x\nbrief: b\nexpect: {}\n")

    with pytest.raises(ValueError, match="must match the file name"):
        load_cases(tmp_path)


@pytest.mark.parametrize(
    "body",
    [
        "id: bad_one\ntask: clarify_brief\ndescription: x\nbrief: b\nexpect: {question_count: 3}\n",  # misspelt expectation
        "id: bad_one\ntask: write_code\ndescription: x\nbrief: b\nexpect: {}\n",  # unknown task
        "id: bad_one\ntask: apply_change_request\ndescription: x\nbrief: b\nexpect: {}\n",  # no baseline or change request
    ],
)
def test_malformed_cases_are_rejected(tmp_path: Path, body: str) -> None:
    _write_case(tmp_path, "bad_one", body)

    with pytest.raises(ValidationError):
        load_cases(tmp_path)
