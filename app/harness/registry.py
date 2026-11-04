"""Loads and versions agent definitions from config/agents/<key>/agent.yaml, with their prompts and schemas.

Agent folders whose agent.yaml has no definition yet (the scaffolds for later phases) are skipped.
An invalid definition, or a missing prompt or schema file, fails startup.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.model_gateway.prompts import PromptFile, SchemaFile, load_prompt, load_schema


class AgentDefinitionError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskSpec(_Strict):
    title: str
    description: str
    phase: int
    workflow_task: str | None  # the phase task it works on (config/workflows/phase_*.yaml); None: no task moves
    phase_states: tuple[str, ...] = Field(min_length=1)
    input_artifact_types: tuple[str, ...] = Field(min_length=1)  # the main input, chosen by the person asking
    context_artifact_types: tuple[str, ...] = ()  # every current document of these types is included too
    context_decisions_from: tuple[str, ...] = ()  # decisions raised by this agent's earlier runs of these tasks
    context_reviews_of: tuple[str, ...] = ()  # review comments (changes requested, rejected) on current versions
    requires_change_request: bool = False  # the person asking names an approved change request to apply
    prompt: str
    output_schema: str
    max_attempts: int = Field(ge=1, le=5)


class AgentSpec(_Strict):
    version: int
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    name: str
    mission: str
    phases: tuple[int, ...]
    autonomy: Literal["supervised"]
    risk_class: Literal["low", "medium", "high"]
    tasks: dict[str, TaskSpec] = Field(min_length=1)


class TaskDefinition(_Strict):
    agent_key: str
    agent_name: str
    agent_version: int
    key: str
    spec: TaskSpec
    prompt: PromptFile
    schema_file: SchemaFile


class AgentRegistry(_Strict):
    agents: dict[str, AgentSpec]
    tasks: dict[tuple[str, str], TaskDefinition]

    def task(self, agent_key: str, task_key: str) -> TaskDefinition | None:
        return self.tasks.get((agent_key, task_key))


def load_registry(agents_dir: Path) -> AgentRegistry:
    agents: dict[str, AgentSpec] = {}
    tasks: dict[tuple[str, str], TaskDefinition] = {}
    for path in sorted(agents_dir.glob("*/agent.yaml")):
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        if raw is None:
            continue  # scaffold for an agent not built yet
        try:
            spec = AgentSpec.model_validate(raw)
        except ValidationError as exc:
            raise AgentDefinitionError(f"{path.parent.name}/agent.yaml: {exc}") from exc
        if spec.key != path.parent.name:
            raise AgentDefinitionError(f"{path.parent.name}/agent.yaml declares key '{spec.key}'")
        for task_key, task in spec.tasks.items():
            try:
                prompt = load_prompt(path.parent / task.prompt)
                schema = load_schema(path.parent / task.output_schema)
            except (OSError, ValueError) as exc:
                raise AgentDefinitionError(f"{spec.key}.{task_key}: {exc}") from exc
            tasks[(spec.key, task_key)] = TaskDefinition(
                agent_key=spec.key,
                agent_name=spec.name,
                agent_version=spec.version,
                key=task_key,
                spec=task,
                prompt=prompt,
                schema_file=schema,
            )
        agents[spec.key] = spec
    return AgentRegistry(agents=agents, tasks=tasks)
