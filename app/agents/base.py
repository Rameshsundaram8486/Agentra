"""Common agent task contract. The harness runner owns the flow; a task supplies only the task-specific parts:

1. prepare: read the inputs through the agent's own permissions, pass them through the input guardrails and
   build the user message. Read-only.
2. output_model: the pydantic model the output must match (with the size limits and cross-field rules).
3. apply: turn validated output into proposals through module services, acting as the agent account.
   Only called after every output guardrail has passed.
"""

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from app.guardrails.findings import Finding
from app.modules.executions.schemas import StartedRun

if TYPE_CHECKING:
    from app.composition import Services
    from app.harness.registry import TaskDefinition


@dataclass(frozen=True)
class PreparedPrompt:
    user: str
    source_text: str  # exactly what the model was shown (after redaction); quotes are checked against it
    source_name: str
    input_findings: list[Finding] = field(default_factory=list)


class AgentTask(Protocol):
    agent_key: str
    task_key: str
    output_model: type[BaseModel]

    def prepare(self, services: "Services", run: StartedRun, definition: "TaskDefinition") -> PreparedPrompt: ...

    def apply(self, services: "Services", run: StartedRun, output: BaseModel) -> list[uuid.UUID]:
        """Returns the ids of the decision requests it raised."""
        ...
