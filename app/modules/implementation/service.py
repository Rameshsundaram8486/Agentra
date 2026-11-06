"""Business rules for Phase 9 implementation; the only entry point for other modules.

When Phase 9 starts, the workflow asks this module for its tasks (generated_tasks, source work_items): one per work
item of the approved implementation backlog. The project's git repository is created then too (git_repo.py).
A draft from the Developer agent becomes a version of the work item's Change set document and a commit on a
branch of that repository, and queues a build and test run in a sandbox VM. Rules enforced here, not by the agent:
- The draft implements a work item of the current approved backlog, whose task is in progress, against main as it
  is now; its files and links pass the change set rules (rules.py, config/policies/change_sets.yaml).
- A change set version can be approved only while it is the work item's latest version, its task waits for review,
  and the latest sandbox run of that exact version passed. Without sandbox VMs (until Increment 5b) no run can
  pass, so nothing is approved untested.
- Approval queues a merge into main (a background job, after the approval commits). A merge that conflicts
  changes nothing and sends the task back; a merge that succeeds completes the task (completion check
  change_set_merged).
"""

import hashlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.guardrails.output.secret_scan import redact_secrets
from app.harness.sandbox.provider import SandboxProvider, SandboxRequest, SandboxResult, UnavailableSandbox
from app.infrastructure.clock import Clock
from app.infrastructure.job_queue import JobQueue
from app.modules.artifacts.service import ArtifactCreate, ArtifactsService, VersionCreate, VersionRecord
from app.modules.audit.service import AuditService
from app.modules.backlog.schemas import WorkItemView
from app.modules.backlog.service import BacklogService
from app.modules.decisions.service import DecisionsService
from app.modules.errors import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.modules.identity.service import SYSTEM_ACTOR, Actor, IdentityService
from app.modules.implementation import repository
from app.modules.implementation.git_repo import MAIN, FileChange, GitRepositories, Signature
from app.modules.implementation.models import ChangeSet, Merge, ProjectRepository, SandboxRun
from app.modules.implementation.policy import ChangeSetPolicy
from app.modules.implementation.rendering import render_change_set
from app.modules.implementation.rules import change_set_problems
from app.modules.implementation.schemas import (
    ChangeSetDetail,
    ChangeSetDraft,
    ChangeSetReply,
    ChangeSetView,
    FileDraft,
    FileRecord,
    ImplementationView,
    MergeView,
    SandboxRunView,
    WorkItemProgress,
    WorkTarget,
)
from app.modules.projects.service import ProjectsService
from app.modules.workflow.service import GeneratedTask, TransitionRequest, WorkflowService

__all__ = [
    "CHANGE_SET_TYPE",
    "MERGE_JOB",
    "SANDBOX_RUN_JOB",
    "ChangeSetDraft",
    "ChangeSetReply",
    "ChangeSetView",
    "FileDraft",
    "ImplementationService",
    "ImplementationView",
    "WorkTarget",
]

PHASE = 9
CHANGE_SET_TYPE = "change_set"
SANDBOX_RUN_JOB = "sandbox_run"
MERGE_JOB = "merge_change_set"
_AGENTRA = "agentra@agentra.local"
_EXCERPT_CHARS = 6000
_OPEN = ("queued", "running")
_DONE = ("completed", "cancelled")


def change_set_title(work_item_id: str) -> str:
    return f"Change set {work_item_id}"


class ImplementationService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        identity: IdentityService,
        artifacts: ArtifactsService,
        decisions: DecisionsService,
        projects: ProjectsService,
        backlog: BacklogService,
        workflow: WorkflowService,
        repos: GitRepositories,
        policy: ChangeSetPolicy,
        sandbox: SandboxProvider | None = None,
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._identity = identity
        self._artifacts = artifacts
        self._decisions = decisions
        self._projects = projects
        self._backlog = backlog
        self._workflow = workflow
        self._repos = repos
        self._policy = policy
        self._sandbox = sandbox or UnavailableSandbox()

    @property
    def policy(self) -> ChangeSetPolicy:
        return self._policy

    @property
    def sandbox(self) -> SandboxProvider:
        return self._sandbox

    # Hooks for the workflow, executions and decisions modules -------------------------------------

    def generated_tasks(self, project_id: uuid.UUID) -> list[GeneratedTask]:
        """Task source work_items: one task per work item of the approved backlog. Creates the project repository
        (once; creating it again finds the existing one)."""
        if failures := self._backlog.gate_failures(project_id):
            raise InvalidTransitionError("Phase 9 starts from an approved backlog of the current design: " + "; ".join(failures))
        _, items = self._backlog.current_items(project_id)
        self._ensure_repository(project_id)
        return [GeneratedTask(subject=i.item_id, title=f"{i.item_id} {i.title}"[:200], depends_on=list(i.depends_on)) for i in items]

    def run_context(self, project_id: uuid.UUID, work_item_id: str) -> dict[str, Any]:
        """What a run on one work item works from besides the backlog: review comments on its latest change set (to
        answer), main as it is now, and a merge conflict to resolve. A change in any of them makes asking again a new run."""
        self._work_item(project_id, work_item_id)
        latest = self._latest(project_id, work_item_id)
        reviews: list[str] = []
        conflict = None
        if latest is not None:
            history = self._decisions.artifact_approvals(SYSTEM_ACTOR, latest.artifact_id).history
            reviews = [str(a.id) for a in sorted(history, key=lambda a: a.created_at) if a.artifact_version_id == latest.artifact_version_id and a.decision != "approved"]
            merge = next(iter(repository.merges_for(self._session, [latest.artifact_version_id])), None)
            conflict = str(merge.id) if merge is not None and merge.status == "conflict" else None
        return {"reviews": reviews, "main": self._repos.head(project_id), "conflict": conflict}

    def task_completion_problems(self, project_id: uuid.UUID, work_item_id: str) -> list[str]:
        """Completion check change_set_merged: the work item's latest change set is approved and merged into main."""
        latest = self._latest(project_id, work_item_id)
        if latest is None:
            return [f"{work_item_id} has no change set yet"]
        number = self._artifacts.version_record(latest.artifact_version_id).version_no
        merge = next(iter(repository.merges_for(self._session, [latest.artifact_version_id])), None)
        if merge is None or merge.status != "merged":
            return [f"{work_item_id}'s change set v{number} is not merged into main"]
        return []

    def approval_problems(self, version_id: uuid.UUID) -> list[str]:
        """Checked before a change set version is approved."""
        row = repository.change_set(self._session, version_id)
        if row is None:
            return ["Only a change set drafted by the Developer agent can be approved"]
        record = self._artifacts.version_record(version_id)
        problems = []
        latest = self._latest(row.project_id, row.work_item_id)
        if latest is None or latest.artifact_version_id != version_id:
            problems.append(f"v{record.version_no} is no longer the latest change set of {row.work_item_id}")
        task = self._workflow.task_by_subject(row.project_id, PHASE, row.work_item_id)
        if task is None or task.state != "waiting_for_review":
            state = task.state.replace("_", " ") if task else "missing"
            problems.append(f"The {row.work_item_id} task is {state}; a change set is approved while its task waits for review")
        problems += self._backlog.gate_failures(row.project_id)
        runs = repository.sandbox_runs_for(self._session, [version_id])
        latest_run = runs[0] if runs else None
        if latest_run is None:
            problems.append("This version has no build and test run yet")
        elif latest_run.status in _OPEN:
            problems.append("Its build and test run has not finished yet")
        elif latest_run.status == "not_run":
            problems.append(f"Its build and test run did not happen ({latest_run.error}); a change set is approved only after a passing run in a sandbox VM")
        elif latest_run.status == "failed":
            problems.append(f"Its build and test run failed (exit code {latest_run.exit_code})")
        elif latest_run.status == "error":
            problems.append(f"Its build and test run could not complete ({latest_run.error})")
        return problems

    def on_approved(self, version_id: uuid.UUID) -> None:
        """After a change set version is approved: queue its merge into main, once."""
        JobQueue(self._session, self._clock).enqueue(MERGE_JOB, {"change_set_version_id": str(version_id)}, f"{MERGE_JOB}:{version_id}", max_attempts=5)

    # For the Developer agent ---------------------------------------------------------------------

    def work_target(self, project_id: uuid.UUID, backlog_version_id: uuid.UUID, work_item_id: str) -> WorkTarget:
        current = self._current_backlog(project_id)
        if backlog_version_id != current:
            raise InvalidTransitionError("This is not the current approved implementation backlog; work from the current one")
        item = self._work_item(project_id, work_item_id)
        main = self._repos.head(project_id)
        if main is None:
            raise InvalidTransitionError("The project repository does not exist yet; it is created when Phase 9 starts")
        files = [(f.path, f.size) for f in self._repos.list_files(project_id, main)]
        latest = self._latest(project_id, work_item_id)
        previous = self._view(latest) if latest else None
        conflict = previous.merge if previous and previous.merge and previous.merge.status == "conflict" else None
        design_version_id = self._backlog.planned_design(current)
        assert design_version_id is not None
        return WorkTarget(
            work_item_id=item.item_id,
            title=item.title,
            description=item.description,
            work_type=item.work_type,
            design_items=item.design_items,
            requirements=item.requirements,
            acceptance=item.acceptance,
            depends_on=item.depends_on,
            backlog_version_id=current,
            design_version_id=design_version_id,
            main_commit=main,
            files=files,
            contents=self._context_files(project_id, main, files, item.depends_on, previous),
            previous=previous,
            conflict=conflict,
        )

    def record_draft(self, actor: Actor, project_id: uuid.UUID, draft: ChangeSetDraft) -> ChangeSetView:
        self._identity.require_project(actor, project_id, "artifact.author")
        draft = ChangeSetDraft.model_validate(draft)
        current = self._current_backlog(project_id)
        if draft.backlog_version_id != current:
            raise InvalidTransitionError("This is not the current approved implementation backlog; work from the current one")
        item = self._work_item(project_id, draft.work_item_id)
        task = self._workflow.task_by_subject(project_id, PHASE, item.item_id)
        if task is None or task.state != "in_progress":
            state = task.state.replace("_", " ") if task else "missing"
            raise InvalidTransitionError(f"The {item.item_id} task is {state}; a change set is drafted while it is in progress")
        main = self._repos.head(project_id)
        if main is None:
            raise InvalidTransitionError("The project repository does not exist yet; it is created when Phase 9 starts")
        if draft.base_commit != main:
            raise InvalidTransitionError("main changed while the change set was being written; ask the Developer agent again")
        existing = [f.path for f in self._repos.list_files(project_id, main)]
        problems = change_set_problems(
            draft.files,
            existing=existing,
            policy=self._policy,
            work_item=item.item_id,
            work_type=item.work_type,
            allowed_design_items=item.design_items,
            allowed_requirements=item.requirements,
            allowed_acceptance=item.acceptance,
            design_items=draft.design_items,
            requirements=draft.requirements,
            acceptance=draft.acceptance,
            test_command=draft.test_command,
        )
        if problems:
            raise ValidationFailedError("; ".join(f"{path}: {message}" for path, message in problems[:20]))

        number = len(repository.change_sets_for(self._session, project_id, item.item_id)) + 1
        branch = f"wi/{item.item_id}/v{number}"
        now = self._clock.now()
        author = Signature(actor.display_name, _AGENTRA, now)
        changes = [FileChange(f.path, f.action, f.content) for f in draft.files]
        commit = self._repos.commit_changes(project_id, main, changes, f"{item.item_id}: {item.title}\n\n{draft.summary.strip()}\n", author, branch)
        diff = self._repos.diff(project_id, main, commit)
        records = [
            FileRecord(
                path=f.path,
                action=f.action,
                bytes=len((f.content or "").encode("utf-8")),
                sha256=hashlib.sha256(f.content.encode("utf-8")).hexdigest() if f.content is not None else None,
                test=f.action != "delete" and self._policy.is_test(f.path),
            )
            for f in draft.files
        ]
        project = self._projects.get_project(actor, project_id)
        backlog_record = self._artifacts.version_record(current)
        content = render_change_set(
            project_name=project.name,
            work_item_label=f"{item.item_id} {item.title}",
            backlog_label=f"{backlog_record.artifact_title} v{backlog_record.version_no} (sha256 {backlog_record.content_sha256[:12]})",
            summary=draft.summary,
            base_commit=main,
            commit=commit,
            branch=branch,
            files=records,
            design_items=draft.design_items,
            requirements=draft.requirements,
            acceptance=draft.acceptance,
            test_command=draft.test_command,
            limitations=draft.limitations,
            review_responses=draft.review_responses,
            diff=diff,
        )
        source_refs = [f"{backlog_record.artifact_title} v{backlog_record.version_no}", f"{item.item_id}", f"main {main[:12]}"]
        previous = self._record(project_id, item.item_id)
        if previous is None:
            detail = self._artifacts.create_artifact(
                actor,
                project_id,
                ArtifactCreate(artifact_type=CHANGE_SET_TYPE, title=change_set_title(item.item_id), content=content, change_summary=draft.change_summary, source_refs=source_refs),
            )
        else:
            detail = self._artifacts.add_version(
                actor,
                previous.artifact_id,
                VersionCreate(content=content, change_summary=draft.change_summary, source_refs=source_refs, expected_current_version=previous.version_no),
            )
        version = detail.current_version
        repository.add(
            self._session,
            ChangeSet(
                project_id=project_id,
                work_item_id=item.item_id,
                artifact_id=detail.id,
                artifact_version_id=version.id,
                backlog_version_id=current,
                base_commit=main,
                commit=commit,
                branch=branch,
                summary=draft.summary.strip(),
                files=[r.model_dump() for r in records],
                design_items=list(dict.fromkeys(draft.design_items)),
                requirements=list(dict.fromkeys(draft.requirements)),
                acceptance=list(dict.fromkeys(draft.acceptance)),
                test_command=draft.test_command.strip(),
                limitations=[x.strip() for x in draft.limitations],
                review_responses=[r.model_dump(mode="json") for r in draft.review_responses],
                created_at=now,
            ),
        )
        self._queue_sandbox_run(actor, project_id, version.id, commit, draft.test_command.strip())
        view = self._view(repository.change_set(self._session, version.id))  # type: ignore[arg-type]
        self._audit.record(
            actor_id=actor.id,
            action="change_set.draft",
            entity_type="artifact_version",
            entity_id=version.id,
            project_id=project_id,
            after={"work_item": item.item_id, "version_no": view.version_no, "commit": commit, "base": main, "files": len(records)},
        )
        return view

    # Sandbox runs ------------------------------------------------------------------------------------

    def request_sandbox_run(self, actor: Actor, version_id: uuid.UUID) -> SandboxRunView:
        """Runs the build and tests of a change set version again (the latest version only)."""
        row = repository.change_set(self._session, version_id)
        if row is None:
            raise NotFoundError("Change set not found")
        self._identity.require_project(actor, row.project_id, "agent.run")
        latest = self._latest(row.project_id, row.work_item_id)
        if latest is None or latest.artifact_version_id != version_id:
            raise InvalidTransitionError("Only the latest change set version of a work item is built and tested")
        runs = repository.sandbox_runs_for(self._session, [version_id])
        if runs and runs[0].status in _OPEN:
            return self._run_views(runs[:1])[0]
        run = self._queue_sandbox_run(actor, row.project_id, version_id, row.commit, row.test_command)
        return self._run_views([run])[0]

    def start_sandbox_run(self, run_id: uuid.UUID) -> SandboxRequest | None:
        """Worker side: marks a queued run as running. None when it already started or finished."""
        run = repository.sandbox_run(self._session, run_id, for_update=True)
        if run is None:
            raise NotFoundError("Sandbox run not found")
        if run.status != "queued":
            return None
        run.status, run.started_at = "running", self._clock.now()
        self._session.flush()
        return SandboxRequest(
            project_id=run.project_id,
            repository=self._repos.path(run.project_id),
            commit=run.commit,
            command=run.command,
            timeout_seconds=self._policy.sandbox.timeout_seconds,
        )

    def finish_sandbox_run(self, run_id: uuid.UUID, *, result: SandboxResult | None = None, not_run: str | None = None, error: str | None = None) -> None:
        """Worker side: records what happened. not_run: no sandbox could run it. error: the run broke down."""
        run = repository.sandbox_run(self._session, run_id, for_update=True)
        if run is None:
            raise NotFoundError("Sandbox run not found")
        if run.status != "running":
            return  # the first outcome stands
        run.finished_at = self._clock.now()
        run.provider = result.provider if result else self._sandbox.name
        if result is not None:
            run.status = result.status
            run.exit_code = result.exit_code
            run.image = result.image[:100]
            run.duration_ms = result.duration_ms
            run.output_sha256 = hashlib.sha256(result.output.encode("utf-8")).hexdigest()
            run.output_excerpt = redact_secrets(result.output)[0][-_EXCERPT_CHARS:]
        elif not_run is not None:
            run.status, run.error = "not_run", not_run[:2000]
        else:
            run.status, run.error = "error", (error or "unknown error")[:2000]
        self._session.flush()
        self._audit.record(
            actor_id=SYSTEM_ACTOR.id,
            action="sandbox_run.finish",
            entity_type="sandbox_run",
            entity_id=run.id,
            project_id=run.project_id,
            reason=run.error,
            after={"status": run.status, "exit_code": run.exit_code, "provider": run.provider, "image": run.image, "commit": run.commit},
        )

    # Merges --------------------------------------------------------------------------------------------

    def merge(self, version_id: uuid.UUID) -> None:
        """Worker side: merges an approved change set version into main, once. On a conflict nothing changes and the
        task goes back to the Developer; on success the task completes."""
        if repository.merges_for(self._session, [version_id]):
            return
        row = repository.change_set(self._session, version_id)
        if row is None:
            raise NotFoundError("Change set not found")
        if self._decisions.approval_statuses([version_id])[version_id] != "approved":
            return  # a later decision replaced the approval before the merge ran
        record = self._artifacts.version_record(version_id)
        main = self._repos.head(row.project_id)
        assert main is not None
        outcome = self._repos.merge(
            row.project_id, row.commit, f"Merge {row.work_item_id} change set v{record.version_no}\n", Signature("Agentra", _AGENTRA, self._clock.now())
        )
        status = "conflict" if outcome.status == "conflict" else "merged"
        repository.add(
            self._session,
            Merge(
                project_id=row.project_id,
                change_set_version_id=version_id,
                status=status,
                main_before=main,
                main_after=outcome.commit if status == "merged" else None,
                conflicts=list(outcome.conflicts),
                created_at=self._clock.now(),
            ),
        )
        self._audit.record(
            actor_id=SYSTEM_ACTOR.id,
            action="change_set.merge",
            entity_type="artifact_version",
            entity_id=version_id,
            project_id=row.project_id,
            after={"work_item": row.work_item_id, "status": status, "main_before": main, "main_after": outcome.commit, "conflicts": list(outcome.conflicts)},
        )
        task = self._workflow.task_by_subject(row.project_id, PHASE, row.work_item_id)
        if task is None or task.state != "waiting_for_review":
            return
        if status == "merged":
            target, reason = "completed", f"Change set v{record.version_no} was approved and merged into main ({(outcome.commit or '')[:12]})"
        else:
            target = "changes_requested"
            reason = f"Change set v{record.version_no} conflicts with main in {', '.join(outcome.conflicts)}; nothing was merged. Ask the Developer agent to redo it on the current main"
        self._workflow.transition_task(SYSTEM_ACTOR, task.id, TransitionRequest(to_state=target, reason=reason[:2000], expected_version=task.version))

    # Reads -------------------------------------------------------------------------------------------

    def view(self, actor: Actor, project_id: uuid.UUID) -> ImplementationView:
        self._identity.require_project(actor, project_id, "artifact.view")
        phase_state = self._workflow.phase_state(project_id, PHASE)
        version_id = self._backlog.current_version_id(project_id)
        _, items = self._backlog.current_items(project_id)
        tasks = {i.item_id: self._workflow.task_by_subject(project_id, PHASE, i.item_id) for i in items}
        states = {key: task.state for key, task in tasks.items() if task is not None}
        progress = []
        for item in items:
            task = tasks[item.item_id]
            latest = self._latest(project_id, item.item_id)
            waiting = [d for d in item.depends_on if states.get(d) != "completed"]
            progress.append(
                WorkItemProgress(
                    work_item_id=item.item_id,
                    title=item.title,
                    epic_id=item.epic_id,
                    work_type=item.work_type,
                    wave=item.wave,
                    estimate=item.estimate,
                    depends_on=item.depends_on,
                    design_items=item.design_items,
                    task_id=task.id if task else None,
                    task_state=task.state if task else None,
                    ready=task is not None and task.state not in _DONE and phase_state == "in_progress" and not waiting,
                    waiting_for=waiting,
                    change_set=self._view(latest) if latest else None,
                )
            )
        counts: dict[str, int] = {}
        for state in states.values():
            counts[state] = counts.get(state, 0) + 1
        return ImplementationView(
            phase_state=phase_state,
            backlog_version_id=version_id,
            backlog_version_no=self._artifacts.version_record(version_id).version_no if version_id else None,
            repository_created=repository.project_repository(self._session, project_id) is not None,
            main_commit=self._repos.head(project_id),
            sandbox_provider=self._sandbox.name,
            sandbox_available=not isinstance(self._sandbox, UnavailableSandbox),
            work_items=sorted(progress, key=lambda p: (p.wave, p.work_item_id)),
            counts=counts,
        )

    def change_set(self, actor: Actor, version_id: uuid.UUID) -> ChangeSetDetail:
        row = repository.change_set(self._session, version_id)
        if row is None:
            raise NotFoundError("Change set not found")
        self._identity.require_project(actor, row.project_id, "artifact.view")
        return ChangeSetDetail(**self._view(row).model_dump(), diff=self._repos.diff(row.project_id, row.base_commit, row.commit))

    # Helpers -----------------------------------------------------------------------------------------

    def _ensure_repository(self, project_id: uuid.UUID) -> None:
        if repository.project_repository(self._session, project_id) is not None and self._repos.exists(project_id):
            return
        project = self._projects.get_project(SYSTEM_ACTOR, project_id)
        readme = (
            f"# {project.name}\n\n{project.customer_name} project {project.code}. Source code for Phase 9, Development and Implementation.\n\n"
            "Changes arrive as change sets from the Developer Agent; each is built and tested in a sandbox VM and approved by a "
            "reviewer before Agentra merges it into main.\n"
        )
        head = self._repos.ensure(project_id, readme, Signature("Agentra", _AGENTRA, self._clock.now()))
        if repository.project_repository(self._session, project_id) is None:
            repository.add(self._session, ProjectRepository(project_id=project_id, initial_commit=head, created_at=self._clock.now()))
            self._audit.record(
                actor_id=SYSTEM_ACTOR.id,
                action="repository.create",
                entity_type="project",
                entity_id=project_id,
                project_id=project_id,
                after={"branch": MAIN, "initial_commit": head},
            )

    def _current_backlog(self, project_id: uuid.UUID) -> uuid.UUID:
        if failures := self._backlog.gate_failures(project_id):
            raise InvalidTransitionError("; ".join(failures))
        version_id = self._backlog.current_version_id(project_id)
        assert version_id is not None
        return version_id

    def _work_item(self, project_id: uuid.UUID, work_item_id: str) -> WorkItemView:
        _, items = self._backlog.current_items(project_id)
        item = next((i for i in items if i.item_id == work_item_id), None)
        if item is None:
            raise NotFoundError(f"{work_item_id} is not a work item of the current implementation backlog")
        return item

    def _record(self, project_id: uuid.UUID, work_item_id: str) -> VersionRecord | None:
        title = change_set_title(work_item_id)
        return next((r for r in self._artifacts.current_records_of_type(project_id, CHANGE_SET_TYPE) if r.artifact_title == title), None)

    def _latest(self, project_id: uuid.UUID, work_item_id: str) -> ChangeSet | None:
        record = self._record(project_id, work_item_id)
        return repository.change_set(self._session, record.id) if record else None

    def _queue_sandbox_run(self, actor: Actor, project_id: uuid.UUID, version_id: uuid.UUID, commit: str, command: str) -> SandboxRun:
        run = SandboxRun(
            project_id=project_id,
            change_set_version_id=version_id,
            commit=commit,
            command=command,
            status="queued",
            requested_by=actor.id,
            created_at=self._clock.now(),
        )
        repository.add(self._session, run)
        JobQueue(self._session, self._clock).enqueue(SANDBOX_RUN_JOB, {"sandbox_run_id": str(run.id)}, f"{SANDBOX_RUN_JOB}:{run.id}", max_attempts=3)
        return run

    def _context_files(
        self, project_id: uuid.UUID, main: str, files: list[tuple[str, int]], depends_on: list[str], previous: ChangeSetView | None
    ) -> dict[str, str]:
        """The files the agent sees in full: all of them when the repository is small, otherwise the files its
        dependencies and its own previous version changed, within the context budget."""
        budget = self._policy.limits.context_bytes
        sizes = dict(files)
        if sum(sizes.values()) <= budget:
            wanted = list(sizes)
        else:
            wanted = []
            for dependency in depends_on:
                if (change := self._latest(project_id, dependency)) is not None:
                    wanted += [f["path"] for f in change.files if f["action"] != "delete"]
            if previous is not None:
                wanted += [f.path for f in previous.files if f.action != "delete"]
            wanted = ["README.md", *wanted]
        contents: dict[str, str] = {}
        used = 0
        for path in dict.fromkeys(wanted):
            size = sizes.get(path)
            if size is None or size > self._policy.limits.max_file_bytes or used + size > budget:
                continue
            try:
                contents[path] = self._repos.read_file(project_id, main, path).decode("utf-8")
            except UnicodeDecodeError:
                continue
            used += size
        return contents

    def _run_views(self, runs: list[SandboxRun]) -> list[SandboxRunView]:
        names = self._identity.display_names({r.requested_by for r in runs})
        return [
            SandboxRunView(
                id=r.id,
                status=r.status,  # type: ignore[arg-type]
                commit=r.commit,
                command=r.command,
                provider=r.provider,
                image=r.image,
                exit_code=r.exit_code,
                output_excerpt=r.output_excerpt,
                output_sha256=r.output_sha256,
                duration_ms=r.duration_ms,
                error=r.error,
                requested_by_name=names.get(r.requested_by),
                created_at=r.created_at,
                finished_at=r.finished_at,
            )
            for r in runs
        ]

    def _view(self, row: ChangeSet) -> ChangeSetView:
        record = self._artifacts.version_record(row.artifact_version_id)
        runs = self._run_views(repository.sandbox_runs_for(self._session, [row.artifact_version_id]))
        merge = next(iter(repository.merges_for(self._session, [row.artifact_version_id])), None)
        latest = self._record(row.project_id, row.work_item_id)
        return ChangeSetView(
            artifact_id=row.artifact_id,
            version_id=row.artifact_version_id,
            version_no=record.version_no,
            work_item_id=row.work_item_id,
            approval_status=self._decisions.approval_statuses([row.artifact_version_id])[row.artifact_version_id],
            current=latest is not None and latest.id == row.artifact_version_id,
            base_commit=row.base_commit,
            commit=row.commit,
            branch=row.branch,
            summary=row.summary,
            files=[FileRecord.model_validate(f) for f in row.files],
            design_items=row.design_items,
            requirements=row.requirements,
            acceptance=row.acceptance,
            test_command=row.test_command,
            limitations=row.limitations,
            review_responses=[ChangeSetReply.model_validate(r) for r in row.review_responses],
            sandbox_runs=runs,
            tested=bool(runs) and runs[0].status == "passed",
            merge=MergeView(
                status=merge.status, main_before=merge.main_before, main_after=merge.main_after, conflicts=merge.conflicts, created_at=merge.created_at  # type: ignore[arg-type]
            )
            if merge
            else None,
            created_at=row.created_at,
        )
