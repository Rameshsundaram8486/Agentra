"""Workflow data accepted from and returned to callers."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TransitionRequest(BaseModel):
    to_state: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=3, max_length=2000)
    expected_version: int = Field(ge=1, description="The version the caller last saw; a mismatch is a conflict")


class TaskView(BaseModel):
    id: uuid.UUID
    phase_run_id: uuid.UUID
    key: str
    subject: str | None = None  # set on generated tasks, e.g. the work item WI-005
    title: str
    agent: str | None
    depends_on: list[str]
    state: str
    version: int
    updated_at: datetime
    available_transitions: list[str]


class GeneratedTask(BaseModel):
    """One task a source yields for a phase: its subject, its title and the subjects it depends on."""

    subject: str = Field(pattern=r"^[A-Z][A-Z0-9]{0,7}-\d{1,6}$")
    title: str = Field(min_length=1, max_length=200)
    depends_on: list[str] = []


class PhaseRunView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    phase: int
    name: str
    primary_agent: str
    definition_key: str
    definition_version: int
    state: str
    version: int
    updated_at: datetime
    available_transitions: list[str]
    required_approvals: list[str]
    tasks: list[TaskView]


class StateTransitionView(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    from_state: str
    to_state: str
    actor_id: uuid.UUID
    reason: str
    occurred_at: datetime
