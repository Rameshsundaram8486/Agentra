"""The evals harness end to end against the test database, with recorded or scripted answers: no model calls."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.composition import Policies
from app.infrastructure.storage.local import LocalArtifactStore
from app.model_gateway.providers.fake import FakeProvider, fake_response
from evals.cases import load_cases
from evals.graders import grade, score
from evals.runner import main
from evals.scenario import Scenario
from tests.agent_support import BRIEF, ba_json, ba_output

CASE = """id: clarify_tiny
task: clarify_brief
description: The leave brief from the agent tests.
brief: {file: brief.md}
expect:
  questions_between: [2, 4]
  must_ask_about:
    approvals: [approv]
"""


@pytest.fixture
def evals_root(tmp_path: Path) -> Path:
    root = tmp_path / "evals"
    (root / "business_analyst" / "inputs").mkdir(parents=True)
    (root / "business_analyst" / "cases").mkdir()
    (root / "business_analyst" / "inputs" / "brief.md").write_text(BRIEF, encoding="utf-8")
    (root / "business_analyst" / "cases" / "clarify_tiny.yaml").write_text(CASE, encoding="utf-8")
    return root


def _record(root: Path, policies: Policies, text: str) -> None:
    path = root / "business_analyst" / "recordings" / "clarify_tiny.json"
    path.parent.mkdir(exist_ok=True)
    version = policies.agents.task("business_analyst", "clarify_brief").prompt.version  # type: ignore[union-attr]
    path.write_text(json.dumps({"case_id": "clarify_tiny", "prompt_version": version, "model": "claude-opus-5-5", "stop_reason": "end_turn",
                                "usage": {"input_tokens": 1000, "output_tokens": 500}, "text": text}), encoding="utf-8")


def _evals(root: Path, out: Path, database_url: str, *argv: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
    code = main(list(argv), database_url=database_url, root=root, out_dir=out, **kwargs)
    [report] = sorted(out.glob("*/results.json"))
    return code, json.loads(report.read_text(encoding="utf-8"))


def test_replay_sets_a_baseline_then_reports_a_regression(evals_root: Path, tmp_path: Path, test_database_url: str, policies: Policies) -> None:
    _record(evals_root, policies, ba_json())

    code, report = _evals(evals_root, tmp_path / "out1", test_database_url, "--update-baseline")

    [row] = report["cases"]
    assert code == 0 and report["spent_usd"] == "0"
    assert (row["status"], row["score"], row["regressions"]) == ("graded", 1.0, [])
    baseline = json.loads((evals_root / "business_analyst" / "baselines" / "clarify_tiny.json").read_text(encoding="utf-8"))
    assert baseline["results"] == {"run_succeeded": True, "question_count": True, "asks_about:approvals": True}

    # A worse answer: one question, and not about approvals.
    _record(evals_root, policies, ba_json(clarifying_questions=ba_output()["clarifying_questions"][1:]))
    code, report = _evals(evals_root, tmp_path / "out2", test_database_url)

    [row] = report["cases"]
    assert code == 1
    assert row["regressions"] == ["question_count", "asks_about:approvals"]
    assert "REGRESSION: question_count, asks_about:approvals" in next((tmp_path / "out2").glob("*/report.md")).read_text(encoding="utf-8")


def test_a_blocked_answer_fails_the_run_grader(evals_root: Path, tmp_path: Path, test_database_url: str, policies: Policies) -> None:
    _record(evals_root, policies, ba_json(brief_summary="The api_key is sk-ant-api03-" + "x" * 40))

    code, report = _evals(evals_root, tmp_path / "out", test_database_url)

    [row] = report["cases"]
    assert code == 0  # no baseline yet, so no regression
    assert [(r["name"], r["passed"]) for r in row["results"]] == [("run_succeeded", False)]


def test_replay_skips_a_case_without_a_recording(evals_root: Path, tmp_path: Path, test_database_url: str) -> None:
    code, report = _evals(evals_root, tmp_path / "out", test_database_url)

    assert code == 0
    assert report["cases"][0]["status"] == "skipped" and "no recording" in report["cases"][0]["reason"]


def test_live_mode_records_the_answer(evals_root: Path, tmp_path: Path, test_database_url: str) -> None:
    code, report = _evals(evals_root, tmp_path / "out", test_database_url, "--mode", "live",
                          live_provider=lambda: FakeProvider([fake_response(ba_json())]))

    assert code == 0 and report["cases"][0]["score"] == 1.0
    recording = json.loads((evals_root / "business_analyst" / "recordings" / "clarify_tiny.json").read_text(encoding="utf-8"))
    assert json.loads(recording["text"]) == ba_output()
    assert recording["prompt_version"] and recording["model"] and recording["recorded_at"]


def test_live_mode_stops_before_the_cap(evals_root: Path, tmp_path: Path, test_database_url: str) -> None:
    def no_calls() -> FakeProvider:
        raise AssertionError("no model call expected")

    code, report = _evals(evals_root, tmp_path / "out", test_database_url, "--mode", "live", "--cap", "0.01", live_provider=no_calls)

    assert code == 0
    assert report["cases"][0]["status"] == "skipped" and report["cases"][0]["reason"].startswith("cap:")
    assert not (evals_root / "business_analyst" / "recordings").exists()


def test_refuses_a_database_that_is_not_a_test_database(evals_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([], database_url="postgresql+psycopg://agentra@localhost/agentra_dev", root=evals_root, out_dir=tmp_path / "out")

    assert code == 2
    assert "_test" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# The committed cases: their scripted setup must work before a live run pays for the task under test.


def test_committed_apply_case_scripts_its_baseline_and_change_request(session_factory: Any, policies: Policies, store: LocalArtifactStore) -> None:
    [case] = load_cases(pattern="apply_cr_half_days")
    ids = ["OBJ-001", "STK-001", "REQ-F-001", "REQ-F-002", "REQ-F-003", "REQ-NF-001"]
    by_ref = dict(zip([item["ref"] for item in case.baseline_items or []], ids))
    items = [{**item, "ref": by_ref[item["ref"]], "related": [by_ref[r] for r in item["related"]]} for item in case.baseline_items or []]
    items[2]["statement"] = "Employees can request annual, sick, unpaid and compassionate leave online, in full or half days."
    answer = json.dumps({"summary": "Half-day leave applied.", "items": items, "process_flow_mermaid": "", "review_responses": []})

    outcome = Scenario(session_factory, policies, store).run(case, FakeProvider([fake_response(answer)]))

    assert outcome.baseline_item_ids == ids
    results = grade(case, outcome)
    assert score(results) == 1.0, [r for r in results if not r.passed]


@pytest.mark.parametrize("case", [c for c in load_cases() if c.task != "apply_change_request"], ids=lambda c: c.id)
def test_committed_case_sets_up_and_runs(case: Any, session_factory: Any, policies: Policies, store: LocalArtifactStore) -> None:
    # The scripted answer is not grounded in most of these briefs; the point is that setup and the run complete.
    outcome = Scenario(session_factory, policies, store).run(case, FakeProvider([fake_response(ba_json())]))

    assert outcome.run.status in ("succeeded", "failed", "blocked")
    assert grade(case, outcome)[0].name == "run_succeeded"
