"""Phase 9 (Increment 5a): tasks per work item, the project repository, Developer change sets, sandbox runs as the
approval gate, reviewer approval and the merge into main."""

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.harness.runner import AgentRunner
from app.infrastructure.job_queue import ClaimedJob, Job
from app.model_gateway.providers.fake import FakeProvider, fake_response
from app.modules.decisions.service import ApprovalCreate
from app.modules.errors import InvalidTransitionError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.modules.executions.schemas import AgentRunCreate
from app.modules.implementation.git_repo import GitRepositories
from app.modules.workflow.service import TransitionRequest
from app.workers.implementation_jobs import ImplementationJobs
from tests.agent_support import cfile, change_set_json, implement, move_task, process
from tests.support import ScriptedSandbox, Team, TestUser

Run = Callable[..., Any]


def _view(run: Run, team: Team) -> Any:
    return run(lambda s: s.implementation.view(team.owner.actor, team.project.id))


def _item(run: Run, team: Team, work_item: str) -> Any:
    return next(i for i in _view(run, team).work_items if i.work_item_id == work_item)


def _draft(run: Run, team: Team, runner: AgentRunner, model: FakeProvider, work_item: str = "WI-001", output: str | None = None) -> Any:
    model.add(fake_response(output or change_set_json()))
    run_id = implement(run, team, work_item).run.id
    process(runner, run_id)
    return run(lambda s: s.executions.get_run(team.owner.actor, run_id))


def _sandbox(run: Run, team: Team, jobs: ImplementationJobs, work_item: str = "WI-001") -> Any:
    """What the worker does for the latest queued sandbox run of the work item's change set."""
    change_set = _item(run, team, work_item).change_set
    queued = next(r for r in change_set.sandbox_runs if r.status == "queued")
    jobs.handle_sandbox_run(ClaimedJob(uuid.uuid4(), "sandbox_run", {"sandbox_run_id": str(queued.id)}, "test", 1))
    return _item(run, team, work_item).change_set


def _approve(run: Run, user: TestUser, version_id: uuid.UUID, decision: str = "approved", comment: str | None = None) -> Any:
    return run(lambda s: s.decisions.record_approval(user.actor, version_id, ApprovalCreate(
        decision=decision, content_sha256=s.artifacts.version_record(version_id).content_sha256, comment=comment)))


def _merge(jobs: ImplementationJobs, version_id: uuid.UUID) -> None:
    jobs.handle_merge(ClaimedJob(uuid.uuid4(), "merge_change_set", {"change_set_version_id": str(version_id)}, "test", 1))


def _task(run: Run, team: Team, work_item: str) -> Any:
    return run(lambda s: s.workflow.task_by_subject(team.project.id, 9, work_item))


def _done(run: Run, team: Team, runner: AgentRunner, model: FakeProvider, jobs: ImplementationJobs, sandbox: ScriptedSandbox, work_item: str, output: str) -> Any:
    """Drafts, tests (passing), approves and merges a change set for one work item."""
    _draft(run, team, runner, model, work_item, output)
    sandbox.passes()
    change_set = _sandbox(run, team, jobs, work_item)
    _approve(run, team.reviewer, change_set.version_id)
    _merge(jobs, change_set.version_id)
    return _item(run, team, work_item)


def test_phase_9_start_creates_a_task_per_work_item_and_the_repository(phase9: Team, run: Run, repos: GitRepositories) -> None:
    team = phase9
    phase = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 9)
    tasks = {t.subject: t for t in phase.tasks}
    assert sorted(tasks) == ["WI-001", "WI-002", "WI-003", "WI-004", "WI-005"]
    assert tasks["WI-004"].key == "wi_wi_004" and sorted(tasks["WI-004"].depends_on) == ["wi_wi_002", "wi_wi_003"]
    assert {t.agent for t in tasks.values()} == {"developer"} and {t.state for t in tasks.values()} == {"not_started"}

    view = _view(run, team)
    assert view.repository_created and view.main_commit == repos.head(team.project.id)
    assert [f.path for f in repos.list_files(team.project.id, view.main_commit)] == ["README.md"]
    ready = {i.work_item_id: (i.ready, i.waiting_for) for i in view.work_items}
    assert ready["WI-001"] == (True, []) and ready["WI-002"] == (True, [])
    assert ready["WI-003"] == (False, ["WI-001"]) and ready["WI-004"] == (False, ["WI-003", "WI-002"])
    assert (view.sandbox_provider, view.sandbox_available) == ("scripted", True)

    # Resuming the phase adds nothing twice.
    run(lambda s: s.workflow.transition_phase_run(team.pm.actor, phase.id, TransitionRequest(to_state="blocked", reason="Waiting", expected_version=phase.version)))
    run(lambda s: s.workflow.transition_phase_run(team.pm.actor, phase.id, TransitionRequest(to_state="in_progress", reason="Resume", expected_version=phase.version + 1)))
    again = next(p for p in run(lambda s: s.workflow.list_phase_runs(team.owner.actor, team.project.id)) if p.phase == 9)
    assert len(again.tasks) == 5


def test_a_work_item_starts_only_after_its_dependencies_and_must_be_named(phase9: Team, run: Run) -> None:
    team = phase9
    with pytest.raises(InvalidTransitionError, match="Waiting for tasks: wi_wi_001"):
        implement(run, team, "WI-003")
    assert _task(run, team, "WI-003").state == "not_started"  # nothing of the refused request was kept
    with pytest.raises(NotFoundError, match="WI-099 is not a work item"):
        implement(run, team, "WI-099")
    backlog = run(lambda s: s.backlog.current_version_id(team.project.id))
    with pytest.raises(ValidationFailedError, match="Name the work item"):
        run(lambda s: s.executions.request_run(team.pm.actor, team.project.id, AgentRunCreate(agent_key="developer", task_key="implement_work_item", artifact_version_id=backlog)))


def test_a_change_set_becomes_a_commit_a_document_and_a_queued_sandbox_run(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, repos: GitRepositories
) -> None:
    team = phase9
    main = _view(run, team).main_commit
    detail = _draft(run, team, runner_for(), model)

    assert detail.status == "succeeded", detail.error_message
    assert detail.subject == "WI-001" and detail.output["change_set"]["branch"] == "wi/WI-001/v1"
    prompt = model.requests[-1].user
    assert "WI-001" in prompt and "README.md" in prompt and "ENV-001" in prompt
    assert _task(run, team, "WI-001").state == "waiting_for_review"

    change_set = _item(run, team, "WI-001").change_set
    assert (change_set.version_no, change_set.base_commit, change_set.approval_status, change_set.tested) == (1, main, "pending", False)
    assert [(f.path, f.action, f.test) for f in change_set.files] == [("deploy/environments.yaml", "add", False), ("tests/test_environments.py", "add", True)]
    assert [r.status for r in change_set.sandbox_runs] == ["queued"]
    assert repos.head(team.project.id) == main  # nothing reaches main before approval
    assert repos.head(team.project.id, "wi/WI-001/v1") == change_set.commit
    assert repos.read_file(team.project.id, change_set.commit, "deploy/environments.yaml").startswith(b"environments:")

    document = run(lambda s: s.artifacts.read_version(team.owner.actor, change_set.version_id))
    assert "+  - name: dev" in document.content and change_set.commit in document.content  # the diff is in what gets approved
    diff = run(lambda s: s.implementation.change_set(team.owner.actor, change_set.version_id)).diff
    assert "b/tests/test_environments.py" in diff
    jobs = run(lambda s: s.session.scalars(select(Job).where(Job.idempotency_key == f"sandbox_run:{change_set.sandbox_runs[0].id}")).all())
    assert len(jobs) == 1


def test_without_a_sandbox_run_nothing_can_be_approved(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, implementation_jobs: ImplementationJobs, sandbox: ScriptedSandbox
) -> None:
    team = phase9
    _draft(run, team, runner_for(), model)
    version_id = _item(run, team, "WI-001").change_set.version_id
    with pytest.raises(InvalidTransitionError, match="has not finished yet"):
        _approve(run, team.reviewer, version_id)

    change_set = _sandbox(run, team, implementation_jobs)  # nothing scripted: no sandbox VM
    run_view = change_set.sandbox_runs[0]
    assert (run_view.status, run_view.provider, change_set.tested) == ("not_run", "scripted", False)
    assert "No sandbox VM" in run_view.error
    assert sandbox.requests[0].commit == change_set.commit and sandbox.requests[0].command == "python -m pytest -q"
    with pytest.raises(InvalidTransitionError, match="did not happen .* approved only after a passing run in a sandbox VM"):
        _approve(run, team.reviewer, version_id)
    assert _approve(run, team.reviewer, version_id, "changes_requested", "Please add a staging environment.").decision == "changes_requested"


def test_a_failed_run_blocks_approval_until_a_rerun_passes(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, implementation_jobs: ImplementationJobs, sandbox: ScriptedSandbox
) -> None:
    team = phase9
    _draft(run, team, runner_for(), model)
    sandbox.fails(exit_code=2, output="FAILED tests/test_environments.py\nAPI_KEY=sk-ant-api03-" + "x" * 90)
    change_set = _sandbox(run, team, implementation_jobs)
    failed = change_set.sandbox_runs[0]
    assert (failed.status, failed.exit_code) == ("failed", 2)
    assert "sk-ant-api03" not in failed.output_excerpt and failed.output_sha256  # the stored excerpt is redacted
    with pytest.raises(InvalidTransitionError, match=r"failed \(exit code 2\)"):
        _approve(run, team.reviewer, change_set.version_id)

    with pytest.raises(PermissionDeniedError):
        run(lambda s: s.implementation.request_sandbox_run(team.reviewer.actor, change_set.version_id))  # reviewers do not start runs
    run(lambda s: s.implementation.request_sandbox_run(team.pm.actor, change_set.version_id))
    sandbox.passes()
    change_set = _sandbox(run, team, implementation_jobs)
    assert [r.status for r in change_set.sandbox_runs] == ["passed", "failed"] and change_set.tested
    assert _approve(run, team.reviewer, change_set.version_id).decision == "approved"


def test_after_a_passing_run_only_a_reviewer_approves_and_agentra_merges_into_main(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, implementation_jobs: ImplementationJobs,
    sandbox: ScriptedSandbox, repos: GitRepositories, developer_agent: TestUser,
) -> None:
    team = phase9
    _draft(run, team, runner_for(), model)
    sandbox.passes()
    change_set = _sandbox(run, team, implementation_jobs)
    for user in (team.pm, developer_agent, team.owner):
        with pytest.raises(PermissionDeniedError):
            _approve(run, user, change_set.version_id)  # only reviewers approve change sets; agents never do
    _approve(run, team.reviewer, change_set.version_id)
    merge_jobs = run(lambda s: s.session.scalars(select(Job).where(Job.idempotency_key == f"merge_change_set:{change_set.version_id}")).all())
    assert len(merge_jobs) == 1  # queued in the approval's own transaction
    assert _task(run, team, "WI-001").state == "waiting_for_review"  # nothing merged yet

    _merge(implementation_jobs, change_set.version_id)
    _merge(implementation_jobs, change_set.version_id)  # a repeated delivery changes nothing
    item = _item(run, team, "WI-001")
    assert item.task_state == "completed" and item.change_set.merge.status == "merged"
    assert repos.head(team.project.id) == change_set.commit == item.change_set.merge.main_after  # main had not moved: fast-forward
    history = run(lambda s: s.workflow.history(team.owner.actor, "task", item.task_id))
    assert history[-1].to_state == "completed" and "approved and merged into main" in history[-1].reason
    assert _item(run, team, "WI-003").ready  # its dependency is done


def test_review_comments_must_be_answered_and_only_the_latest_version_is_approvable(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, implementation_jobs: ImplementationJobs, sandbox: ScriptedSandbox
) -> None:
    team = phase9
    runner = runner_for()
    _draft(run, team, runner, model)
    first = _item(run, team, "WI-001").change_set
    _approve(run, team.reviewer, first.version_id, "changes_requested", "Add a staging environment.")

    unanswered = _draft(run, team, runner, model, output=change_set_json())
    assert unanswered.status == "failed" and unanswered.error_code == "guardrail_blocked"
    assert any("REV-1 needs exactly one response" in f.message for f in unanswered.findings)
    assert "Add a staging environment." in model.requests[-1].user

    files = [cfile("deploy/environments.yaml", "environments:\n  - name: dev\n  - name: test\n  - name: staging\n"), cfile("tests/test_environments.py", "def test_three():\n    assert True\n")]
    answered = _draft(run, team, runner, model, output=change_set_json(files, review_responses=[{"ref": "REV-1", "response": "Added staging."}]))
    assert answered.status == "succeeded", answered.error_message
    second = _item(run, team, "WI-001").change_set
    assert (second.version_no, second.branch, second.review_responses[0].comment) == (2, "wi/WI-001/v2", "Add a staging environment.")
    sandbox.passes()
    _sandbox(run, team, implementation_jobs)
    with pytest.raises(InvalidTransitionError, match="no longer the latest change set of WI-001"):
        _approve(run, team.reviewer, first.version_id)


@pytest.mark.parametrize(
    ("files", "design_items", "message"),
    [
        ([cfile(".github/workflows/ci.yml", "on: push\n")], ["ENV-001"], ".github/workflows/ci.yml is protected"),
        ([cfile("../outside.txt", "x\n")], ["ENV-001"], "is not a relative path inside the repository"),
        ([cfile("readme.md", "x\n")], ["ENV-001"], "readme.md already exists on main as README.md"),
        ([cfile("src/app.py", "x\n", "modify")], ["ENV-001"], "src/app.py does not exist on main"),
        ([cfile("deploy/env.yaml", "x\n")], ["CMP-001"], "CMP-001 is not one of WI-001's design items"),
    ],
)
def test_out_of_scope_or_unsafe_change_sets_are_refused_and_nothing_is_committed(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, repos: GitRepositories,
    files: list[dict[str, Any]], design_items: list[str], message: str,
) -> None:
    team = phase9
    detail = _draft(run, team, runner_for(), model, output=change_set_json(files, design_items=design_items))
    assert detail.status == "failed" and detail.error_code == "guardrail_blocked"
    assert any(message in f.message for f in detail.findings), [f.message for f in detail.findings]
    assert _item(run, team, "WI-001").change_set is None and repos.head(team.project.id, "wi/WI-001/v1") is None


def test_a_secret_in_a_file_is_refused(phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> None:
    team = phase9
    files = [cfile("deploy/settings.py", 'KEY = "sk-ant-api03-' + "a" * 90 + '"\n')]
    detail = _draft(run, team, runner_for(), model, output=change_set_json(files))
    assert detail.status == "failed" and any(f.check == "secret" for f in detail.findings)


def test_questions_leave_the_task_waiting_for_input(phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider) -> None:
    team = phase9
    question = {
        "title": "Hosting region", "question": "Which Azure region hosts the test environment?", "why_it_matters": "Data residency.",
        "suggested_answers": [{"key": "uae_north", "title": "UAE North", "description": ""}, {"key": "west_europe", "title": "West Europe", "description": ""}],
        "recommended_answer": "uae_north", "recommendation_rationale": "Customer data stays in the UAE.",
    }
    output = change_set_json([], design_items=[], outcome="questions", questions=[question], test_command="", summary="The region is not in the design.")
    detail = _draft(run, team, runner_for(), model, output=output)
    assert detail.status == "succeeded", detail.error_message
    assert _task(run, team, "WI-001").state == "waiting_for_input" and _item(run, team, "WI-001").change_set is None
    decision = run(lambda s: s.decisions.get_decision(team.owner.actor, detail.decision_ids[0]))
    assert decision.title == "WI-001: Hosting region" and decision.recommended_option == "uae_north"


def test_a_merge_conflict_changes_nothing_and_sends_the_task_back(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, implementation_jobs: ImplementationJobs,
    sandbox: ScriptedSandbox, repos: GitRepositories,
) -> None:
    team = phase9
    runner = runner_for()
    _draft(run, team, runner, model, "WI-001", change_set_json([cfile("README.md", "# Leave app\n\nEnvironments: dev, test.\n", "modify")]))
    _draft(run, team, runner, model, "WI-002", change_set_json([cfile("README.md", "# Leave app\n\nAccess: Entra ID groups.\n", "modify")], design_items=["SEC-001"]))
    for work_item in ("WI-001", "WI-002"):
        sandbox.passes()
        _sandbox(run, team, implementation_jobs, work_item)
    first, second = (_item(run, team, w).change_set for w in ("WI-001", "WI-002"))
    _approve(run, team.reviewer, first.version_id)
    _merge(implementation_jobs, first.version_id)
    main = repos.head(team.project.id)
    assert main == first.commit

    _approve(run, team.reviewer, second.version_id)
    _merge(implementation_jobs, second.version_id)
    item = _item(run, team, "WI-002")
    assert item.task_state == "changes_requested" and item.change_set.merge.status == "conflict"
    assert item.change_set.merge.conflicts == ["README.md"] and repos.head(team.project.id) == main
    assert run(lambda s: s.implementation.task_completion_problems(team.project.id, "WI-002")) == ["WI-002's change set v1 is not merged into main"]

    redo = _draft(run, team, runner, model, "WI-002", change_set_json([cfile("docs/access.md", "Access: Entra ID groups.\n")], design_items=["SEC-001"]))
    assert redo.status == "succeeded", redo.error_message
    assert "Merge conflict" in model.requests[-1].user and "README.md" in model.requests[-1].user
    assert _item(run, team, "WI-002").change_set.base_commit == main


def test_the_api_shows_progress_and_change_sets_and_reruns_checks(
    phase9: Team, run: Run, runner_for: Callable[..., AgentRunner], model: FakeProvider, client_for: Callable[..., TestClient]
) -> None:
    team = phase9
    _draft(run, team, runner_for(), model)
    pm = client_for(team.pm)
    view = pm.get(f"/api/projects/{team.project.id}/implementation")
    assert view.status_code == 200
    item = next(i for i in view.json()["work_items"] if i["work_item_id"] == "WI-001")
    version_id = item["change_set"]["version_id"]
    detail = pm.get(f"/api/change-sets/{version_id}")
    assert detail.status_code == 200 and "deploy/environments.yaml" in detail.json()["diff"]
    queued = pm.post(f"/api/change-sets/{version_id}/sandbox-runs")
    assert queued.status_code == 202 and queued.json()["status"] == "queued"  # the run still queued is returned, not a second one
    assert client_for(team.reviewer).post(f"/api/change-sets/{version_id}/sandbox-runs").status_code == 403
    assert client_for().get(f"/api/projects/{team.project.id}/implementation").status_code == 401
    body = {"agent_key": "developer", "task_key": "implement_work_item", "artifact_version_id": str(uuid.uuid4()), "subject": "WI-001; DROP"}
    assert pm.post(f"/api/projects/{team.project.id}/agent-runs", content=json.dumps(body), headers={"content-type": "application/json"}).status_code == 422
