"""Entry and exit gates evaluated before a transition. Each returns the reasons it fails; empty means it passes."""

from collections.abc import Mapping

from app.modules.workflow.definitions import PhaseDefinition

COMPLETED = "completed"
CANCELLED = "cancelled"
IN_PROGRESS = "in_progress"


def phase_entry_failures(definition: PhaseDefinition, phase_states: Mapping[int, str]) -> list[str]:
    """Leaving the initial state needs every required earlier phase completed."""
    return [
        f"Phase {required} must be completed first (it is '{phase_states.get(required, 'missing')}')"
        for required in definition.entry.requires_completed_phases
        if phase_states.get(required) != COMPLETED
    ]


def phase_exit_failures(task_states: Mapping[str, str]) -> list[str]:
    """Completing a phase needs every task completed or cancelled."""
    open_tasks = sorted(key for key, state in task_states.items() if state not in (COMPLETED, CANCELLED))
    return [f"Tasks still open: {', '.join(open_tasks)}"] if open_tasks else []


def task_start_failures(phase_state: str, depends_on: tuple[str, ...], task_states: Mapping[str, str]) -> list[str]:
    """Starting a task needs its phase in progress and its dependencies completed."""
    failures = []
    if phase_state != IN_PROGRESS:
        failures.append(f"The phase must be in progress (it is '{phase_state}')")
    waiting = sorted(key for key in depends_on if task_states.get(key) != COMPLETED)
    if waiting:
        failures.append(f"Waiting for tasks: {', '.join(waiting)}")
    return failures
