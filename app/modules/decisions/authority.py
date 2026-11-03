"""Who may decide what; separation of duties; no self-approval.

Loads config/policies/approval_matrix.yaml. Agents never approve or decide: any role list containing
"agent" is rejected when the policy loads, and every check also refuses non-human actors outright.
"""

import uuid
from collections.abc import Set
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.errors import PermissionDeniedError
from app.modules.identity.service import PROJECT_ROLES, Actor

_HUMAN_ROLES = frozenset(PROJECT_ROLES) - {"agent"}


class ArtifactTypePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    approver_roles: frozenset[str]
    independent_review: bool = True


class DecisionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    decider_roles: frozenset[str]


class ApprovalMatrix(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    artifact_types: dict[str, ArtifactTypePolicy]
    decisions: DecisionPolicy

    @model_validator(mode="after")
    def _humans_only(self) -> "ApprovalMatrix":
        for name, policy in self.artifact_types.items():
            if not policy.approver_roles:
                raise ValueError(f"artifact type '{name}' has no approver roles")
            if not policy.approver_roles <= _HUMAN_ROLES:
                raise ValueError(f"artifact type '{name}': approver roles must be human project roles")
        if not self.decisions.decider_roles or not self.decisions.decider_roles <= _HUMAN_ROLES:
            raise ValueError("decision decider roles must be human project roles")
        return self

    def artifact_type(self, name: str) -> ArtifactTypePolicy | None:
        return self.artifact_types.get(name)


def load_approval_matrix(path: Path) -> ApprovalMatrix:
    with path.open(encoding="utf-8") as handle:
        return ApprovalMatrix.model_validate(yaml.safe_load(handle))


def require_human(actor: Actor, what: str) -> None:
    if actor.kind != "human":
        raise PermissionDeniedError(f"Only people can {what}; agents and system accounts never can")


def check_can_approve(
    actor: Actor, roles: Set[str], policy: ArtifactTypePolicy, authors: Set[uuid.UUID]
) -> None:
    require_human(actor, "approve")
    if not roles & policy.approver_roles:
        raise PermissionDeniedError(
            f"Approving a {policy.title.lower()} needs one of these roles: {', '.join(sorted(policy.approver_roles))}"
        )
    if policy.independent_review and actor.id in authors:
        raise PermissionDeniedError(
            "You authored a version of this artifact, so an independent reviewer must approve it"
        )


def check_can_decide(actor: Actor, roles: Set[str], policy: DecisionPolicy) -> None:
    require_human(actor, "decide")
    if not roles & policy.decider_roles:
        raise PermissionDeniedError(
            f"Recording a decision needs one of these roles: {', '.join(sorted(policy.decider_roles))}"
        )
