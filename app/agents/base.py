"""Common agent task contract. The harness runner owns the flow; a task supplies only the task-specific parts:

1. prepare: read the inputs through the agent's own permissions, pass them through the input guardrails and
   build the user message. Read-only. Raises MissingInput when there is not enough to work from, so no
   model call is paid for.
2. output_model: the pydantic model the output must match (with the size limits and cross-field rules).
3. check: task-specific output checks that need the prepared inputs (for example, that kept IDs exist).
4. apply: turn validated output into records through module services, acting as the agent account. Only
   called after every output check has passed. Says which state the workflow task moves to.
"""

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel

from app.guardrails.findings import Finding
from app.guardrails.pipeline import Sources
from app.modules.executions.schemas import StartedRun

if TYPE_CHECKING:
    from app.composition import Services
    from app.harness.registry import TaskDefinition


class MissingInput(Exception):
    """The inputs are not enough to work from. The run ends without a model call; the task waits for input."""


@dataclass(frozen=True)
class PreparedPrompt:
    user: str
    sources: Sources
    input_findings: list[Finding] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)  # task-specific context for check and apply


@dataclass(frozen=True)
class ApplyResult:
    decision_ids: list[uuid.UUID]
    task_state: Literal["waiting_for_input", "waiting_for_review"]
    records: dict[str, Any] = field(default_factory=dict)  # what else was created, for the run's output


class AgentTask(Protocol):
    agent_key: str
    task_key: str
    output_model: type[BaseModel]

    def prepare(self, services: "Services", run: StartedRun, definition: "TaskDefinition") -> PreparedPrompt: ...

    def check(self, output: BaseModel, prepared: PreparedPrompt) -> list[Finding]: ...

    def apply(self, services: "Services", run: StartedRun, output: BaseModel, prepared: PreparedPrompt) -> ApplyResult: ...
