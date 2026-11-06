"""Phase 9 data accepted from and returned to callers: change set drafts and views, sandbox runs, merges and the
implementation view of a project."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FileAction = Literal["add", "modify", "delete"]
SandboxStatus = Literal["queued", "running", "passed", "failed", "not_run", "error"]


class FileDraft(BaseModel):
    path: str = Field(min_length=1, max_length=300)
    action: FileAction
    content: str | None = None  # the whole new file for add and modify; None for delete


class ChangeSetReply(BaseModel):
    """The developer's answer to one review comment on the previous change set version."""

    approval_id: uuid.UUID
    comment: str
    response: str


class ChangeSetDraft(BaseModel):
    work_item_id: str = Field(pattern=r"^WI-\d{3,}$")
    backlog_version_id: uuid.UUID
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")  # the main the draft was written against
    summary: str = Field(min_length=1, max_length=4000)
    files: list[FileDraft]
    design_items: list[str]
    requirements: list[str]
    acceptance: list[str]
    test_command: str = Field(min_length=1, max_length=300)
    limitations: list[str] = []
    review_responses: list[ChangeSetReply] = []
    change_summary: str = Field(min_length=3, max_length=500)


class FileRecord(BaseModel):
    path: str
    action: FileAction
    bytes: int
    sha256: str | None  # of the new content; None for a delete
    test: bool


class SandboxRunView(BaseModel):
    id: uuid.UUID
    status: SandboxStatus
    commit: str
    command: str
    provider: str | None
    image: str | None
    exit_code: int | None
    output_excerpt: str | None
    output_sha256: str | None
    duration_ms: int | None
    error: str | None
    requested_by_name: str | None
    created_at: datetime
    finished_at: datetime | None


class MergeView(BaseModel):
    status: Literal["merged", "conflict"]
    main_before: str
    main_after: str | None
    conflicts: list[str]
    created_at: datetime


class ChangeSetView(BaseModel):
    artifact_id: uuid.UUID
    version_id: uuid.UUID
    version_no: int
    work_item_id: str
    approval_status: str
    current: bool  # the latest version of this work item's change set
    base_commit: str
    commit: str
    branch: str
    summary: str
    files: list[FileRecord]
    design_items: list[str]
    requirements: list[str]
    acceptance: list[str]
    test_command: str
    limitations: list[str]
    review_responses: list[ChangeSetReply]
    sandbox_runs: list[SandboxRunView]  # newest first
    tested: bool  # the latest run of this version passed
    merge: MergeView | None
    created_at: datetime


class ChangeSetDetail(ChangeSetView):
    diff: str


class WorkItemProgress(BaseModel):
    work_item_id: str
    title: str
    epic_id: str
    work_type: str
    wave: int
    estimate: str
    depends_on: list[str]
    design_items: list[str]
    task_id: uuid.UUID | None
    task_state: str | None
    ready: bool  # its task can start: the phase is in progress and every dependency is completed
    waiting_for: list[str]  # dependencies not completed yet
    change_set: ChangeSetView | None


class ImplementationView(BaseModel):
    phase_state: str | None
    backlog_version_id: uuid.UUID | None
    backlog_version_no: int | None
    repository_created: bool
    main_commit: str | None
    sandbox_provider: str
    sandbox_available: bool
    work_items: list[WorkItemProgress]
    counts: dict[str, int]  # task state -> number of work items


class WorkTarget(BaseModel):
    """What the Developer agent works from for one work item (read by app/agents/developer/implement.py)."""

    work_item_id: str
    title: str
    description: str
    work_type: str
    design_items: list[str]
    requirements: list[str]
    acceptance: list[str]
    depends_on: list[str]
    backlog_version_id: uuid.UUID
    design_version_id: uuid.UUID
    main_commit: str
    files: list[tuple[str, int]]  # every file on main: (path, bytes)
    contents: dict[str, str]  # path -> text of the files the agent is shown in full
    previous: ChangeSetView | None  # the latest change set version of this work item
    conflict: MergeView | None  # the latest merge of that version, when it conflicted
