"""Loads and validates config/workflows/*.yaml.

A phase file that contains only comments is a phase not yet defined (Phases 1-6, 12-13 in the MVP) and is skipped.
"""

from graphlib import CycleError, TopologicalSorter
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.modules.identity.service import PROJECT_ROLES, SYSTEM_ROLE

KNOWN_ROLES = frozenset(PROJECT_ROLES) | {SYSTEM_ROLE}


class WorkflowDefinitionError(ValueError):
    pass


class TransitionRule(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_states: tuple[str, ...] = Field(alias="from")
    to: str
    roles: frozenset[str]

    @field_validator("from_states", mode="before")
    @classmethod
    def _one_or_many(cls, value: object) -> object:
        return (value,) if isinstance(value, str) else value


class Lifecycle(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    version: int
    initial_state: str
    states: tuple[str, ...]
    terminal_states: frozenset[str]
    transitions: tuple[TransitionRule, ...]

    @model_validator(mode="after")
    def _consistent(self) -> "Lifecycle":
        states = set(self.states)
        if self.initial_state not in states:
            raise ValueError(f"initial_state '{self.initial_state}' is not a state")
        if not self.terminal_states <= states:
            raise ValueError(f"unknown terminal states: {sorted(self.terminal_states - states)}")
        seen: set[tuple[str, str]] = set()
        for rule in self.transitions:
            for source in rule.from_states:
                if source not in states or rule.to not in states:
                    raise ValueError(f"transition {source} -> {rule.to} uses an unknown state")
                if source in self.terminal_states:
                    raise ValueError(f"transition out of terminal state '{source}'")
                if (source, rule.to) in seen:
                    raise ValueError(f"transition {source} -> {rule.to} is defined twice")
                seen.add((source, rule.to))
            if not rule.roles:
                raise ValueError(f"transition to '{rule.to}' has no roles")
            if not rule.roles <= KNOWN_ROLES:
                raise ValueError(f"unknown roles: {sorted(rule.roles - KNOWN_ROLES)}")
        return self

    def rule_for(self, from_state: str, to_state: str) -> TransitionRule | None:
        for rule in self.transitions:
            if from_state in rule.from_states and rule.to == to_state:
                return rule
        return None

    def rules_from(self, from_state: str) -> list[TransitionRule]:
        return [rule for rule in self.transitions if from_state in rule.from_states]


class TaskDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    title: str
    agent: str | None = None
    depends_on: tuple[str, ...] = ()
    # Artifact types whose current versions must all be approved before the task can be completed.
    required_approvals: tuple[str, ...] = ()
    # The questions agent runs raised for this task must all be answered or deferred before it completes.
    requires_answered_questions: bool = False


class GeneratedTasks(BaseModel):
    """Tasks a phase gets from project data when it starts, one per subject (for example one per backlog work item).
    The source and the completion check are named here and provided by other modules (app/composition.py)."""

    model_config = ConfigDict(frozen=True)

    source: str  # yields (subject, title, subjects it depends on)
    key_prefix: str = Field(pattern=r"^[a-z][a-z0-9]{1,15}$")  # task key: <prefix>_<subject, lowercased>
    agent: str
    # Checked, with the task's subject, before a generated task can be completed.
    completion_check: str


class EntryRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    requires_completed_phases: tuple[int, ...] = ()


class ExitRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Artifact types (config/policies/approval_matrix.yaml) whose current versions must all be approved.
    required_approvals: tuple[str, ...] = ()
    # Named checks other modules provide (wired in app/composition.py), e.g. design_coverage.
    checks: tuple[str, ...] = ()


class PhaseDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    version: int
    phase: int = Field(ge=1, le=13)
    name: str
    primary_agent: str
    lifecycle: str
    task_lifecycle: str
    entry: EntryRule = EntryRule()
    exit: ExitRule = ExitRule()
    tasks: tuple[TaskDefinition, ...] = ()
    generated_tasks: GeneratedTasks | None = None

    @model_validator(mode="after")
    def _tasks_form_a_dag(self) -> "PhaseDefinition":
        keys = [task.key for task in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("task keys must be unique within a phase")
        for task in self.tasks:
            unknown = set(task.depends_on) - set(keys)
            if unknown:
                raise ValueError(f"task '{task.key}' depends on unknown tasks {sorted(unknown)}")
        try:
            tuple(TopologicalSorter({task.key: task.depends_on for task in self.tasks}).static_order())
        except CycleError as exc:
            raise ValueError(f"task dependencies form a cycle: {exc.args[1]}") from exc
        return self


class WorkflowCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    lifecycles: dict[str, Lifecycle]
    phases: dict[int, PhaseDefinition]

    @model_validator(mode="after")
    def _references_resolve(self) -> "WorkflowCatalog":
        for number, phase in self.phases.items():
            for key in (phase.lifecycle, phase.task_lifecycle):
                if key not in self.lifecycles:
                    raise ValueError(f"phase {number} uses unknown lifecycle '{key}'")
            for required in phase.entry.requires_completed_phases:
                if required not in self.phases or required >= number:
                    raise ValueError(f"phase {number} requires phase {required}, which is not an earlier defined phase")
        return self

    def phase(self, number: int) -> PhaseDefinition:
        return self.phases[number]

    def lifecycle(self, key: str) -> Lifecycle:
        return self.lifecycles[key]


def _read_yaml(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_catalog(workflows_dir: Path) -> WorkflowCatalog:
    try:
        lifecycles: dict[str, Lifecycle] = {}
        for path in sorted((workflows_dir / "lifecycles").glob("*.yaml")):
            lifecycle = Lifecycle.model_validate(_read_yaml(path))
            if lifecycle.key != path.stem:
                raise WorkflowDefinitionError(f"{path.name}: key '{lifecycle.key}' must match the file name")
            lifecycles[lifecycle.key] = lifecycle

        phases: dict[int, PhaseDefinition] = {}
        for path in sorted(workflows_dir.glob("phase_*.yaml")):
            data = _read_yaml(path)
            if data is None:
                continue
            phase = PhaseDefinition.model_validate(data)
            if phase.key != path.stem:
                raise WorkflowDefinitionError(f"{path.name}: key '{phase.key}' must match the file name")
            if phase.phase in phases:
                raise WorkflowDefinitionError(f"{path.name}: phase {phase.phase} is defined twice")
            phases[phase.phase] = phase

        return WorkflowCatalog(lifecycles=lifecycles, phases=phases)
    except ValidationError as exc:
        raise WorkflowDefinitionError(f"invalid workflow definition in {workflows_dir}: {exc}") from exc
