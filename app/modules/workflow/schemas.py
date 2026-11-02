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
    title: str
    agent: str | None
    depends_on: list[str]
    state: str
    version: int
    updated_at: datetime
    available_transitions: list[str]


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
    tasks: list[TaskView]


class StateTransitionView(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    from_state: str
    to_state: str
    actor_id: uuid.UUID
    reason: str
    occurred_at: datetime
