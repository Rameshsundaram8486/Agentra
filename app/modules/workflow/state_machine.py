"""Allowed states and transitions for a lifecycle, and who may request each one. Pure functions, no I/O."""

from collections.abc import Set

from app.modules.errors import InvalidTransitionError, PermissionDeniedError
from app.modules.workflow.definitions import Lifecycle, TransitionRule


def check_transition(lifecycle: Lifecycle, from_state: str, to_state: str, roles: Set[str]) -> TransitionRule:
    if from_state in lifecycle.terminal_states:
        raise InvalidTransitionError(f"'{from_state}' is a final state; nothing can change it")
    rule = lifecycle.rule_for(from_state, to_state)
    if rule is None:
        raise InvalidTransitionError(f"Cannot move from '{from_state}' to '{to_state}'")
    if not rule.roles & roles:
        raise PermissionDeniedError(
            f"Moving from '{from_state}' to '{to_state}' needs one of these roles: {', '.join(sorted(rule.roles))}"
        )
    return rule


def allowed_targets(lifecycle: Lifecycle, from_state: str, roles: Set[str]) -> list[str]:
    return [rule.to for rule in lifecycle.rules_from(from_state) if rule.roles & roles]
