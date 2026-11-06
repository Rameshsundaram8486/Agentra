"""Change set rules (app/modules/implementation/rules.py) against the real policy file."""

from typing import Any

import pytest

from app.composition import CONFIG_DIR
from app.modules.implementation.policy import load_change_set_policy
from app.modules.implementation.rules import change_set_problems
from app.modules.implementation.schemas import FileDraft

POLICY = load_change_set_policy(CONFIG_DIR / "policies" / "change_sets.yaml")
TEST = FileDraft(path="tests/test_leave.py", action="add", content="def test_x():\n    assert True\n")


def _problems(files: list[FileDraft], **changes: Any) -> list[str]:
    arguments: dict[str, Any] = {
        "existing": ["README.md", "src/leave.py"],
        "policy": POLICY,
        "work_item": "WI-003",
        "work_type": "build",
        "allowed_design_items": ["ENT-001"],
        "allowed_requirements": ["REQ-F-001"],
        "allowed_acceptance": ["REQ-F-001.AC1"],
        "design_items": ["ENT-001"],
        "requirements": ["REQ-F-001"],
        "acceptance": ["REQ-F-001.AC1"],
        "test_command": "python -m pytest -q",
    }
    arguments.update(changes)
    return [message for _, message in change_set_problems(files, **arguments)]


def test_a_well_formed_change_set_has_no_problems() -> None:
    files = [FileDraft(path="src/leave.py", action="modify", content="x = 1\n"), FileDraft(path="src/old.py", action="add", content="y = 2\n"), TEST]
    assert _problems(files) == []
    assert _problems([FileDraft(path="README.md", action="delete"), TEST]) == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (FileDraft(path="/etc/passwd", action="add", content="x"), "is not a relative path"),
        (FileDraft(path="src\\leave.py", action="add", content="x"), "is not a relative path"),
        (FileDraft(path="src/../../x.py", action="add", content="x"), "is not a relative path"),
        (FileDraft(path=".git/hooks/pre-commit", action="add", content="x"), "is not a relative path"),
        (FileDraft(path="C:/x.py", action="add", content="x"), "is not a relative path"),
        (FileDraft(path=".github/workflows/ci.yml", action="add", content="x"), "is protected"),
        (FileDraft(path="build/azure-pipelines.yml", action="add", content="x"), "is protected"),
        (FileDraft(path=".gitattributes", action="add", content="x"), "is protected"),
        (FileDraft(path="Readme.md", action="add", content="x"), "already exists on main as README.md"),
        (FileDraft(path="src/missing.py", action="modify", content="x"), "does not exist on main, so it cannot be modified"),
        (FileDraft(path="src/missing.py", action="delete"), "does not exist on main, so it cannot be deleted"),
        (FileDraft(path="src/new.py", action="add"), "give the whole new content"),
        (FileDraft(path="README.md", action="delete", content="x"), "A deleted file has no content"),
        (FileDraft(path="src/blob.bin", action="add", content="a\x00b"), "looks binary"),
        (FileDraft(path="src/big.py", action="add", content="x" * 200_001), "the limit is 200000"),
        (FileDraft(path="src/config.py", action="add", content='KEY = "sk-ant-api03-' + "a" * 90 + '"'), "looks like a secret"),
    ],
)
def test_unsafe_or_inconsistent_files_are_refused(change: FileDraft, message: str) -> None:
    assert any(message in problem for problem in _problems([change, TEST])), _problems([change, TEST])


def test_limits_on_the_whole_change_set() -> None:
    assert "A change set changes at least one file" in _problems([], work_type="configure")
    many = [FileDraft(path=f"src/m{n}.py", action="add", content="x") for n in range(31)]
    assert any("at most 30" in p for p in _problems(many))
    twice = [FileDraft(path="src/a.py", action="add", content="x"), FileDraft(path="SRC/A.py", action="add", content="y"), TEST]
    assert any("appears more than once" in p for p in _problems(twice))
    heavy = [FileDraft(path=f"src/h{n}.py", action="add", content="x" * 199_000) for n in range(6)]
    assert any("limit per change set is 1000000" in p for p in _problems(heavy))


def test_build_integrate_and_migrate_work_needs_a_test_file() -> None:
    code_only = [FileDraft(path="src/leave.py", action="modify", content="x = 1\n")]
    for work_type in ("build", "integrate", "migrate"):
        assert any("adds or changes at least one test file" in p for p in _problems(code_only, work_type=work_type))
    for work_type in ("configure", "deploy"):
        assert _problems(code_only, work_type=work_type) == []
    deleted_test = [*code_only, FileDraft(path="tests/test_old.py", action="delete")]
    assert any("at least one test file" in p for p in _problems(deleted_test, existing=["src/leave.py", "tests/test_old.py"]))
    for path in ("src/LeaveTests.cs", "web/leave.spec.ts", "pkg/leave_test.go", "src/__tests__/leave.js"):
        assert _problems([*code_only, FileDraft(path=path, action="add", content="x")]) == [], path


def test_links_stay_within_the_work_item_and_the_test_command_is_one_line() -> None:
    problems = _problems([TEST], design_items=["CMP-001"], requirements=["REQ-F-009"], acceptance=["REQ-F-001.AC2"])
    assert "CMP-001 is not one of WI-003's design items (ENT-001)" in problems
    assert "REQ-F-009 is not one of WI-003's requirements (REQ-F-001)" in problems
    assert "REQ-F-001.AC2 is not one of WI-003's acceptance criteria (REQ-F-001.AC1)" in problems
    assert "Name the design items of WI-003 this change implements" in _problems([TEST], design_items=[])
    assert "Give one command line that runs the tests" in _problems([TEST], test_command="pytest\nrm -rf /")
    assert "Give one command line that runs the tests" in _problems([TEST], test_command="  ")
