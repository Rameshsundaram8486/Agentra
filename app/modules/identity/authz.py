"""Server-side authorisation: loads config/policies/permissions.yaml and resolves an actor's permissions."""

from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

from app.modules.identity.schemas import PROJECT_ROLES, Actor


class PermissionPolicy(BaseModel):
    version: int
    platform_admin: frozenset[str]
    roles: dict[str, frozenset[str]]

    @model_validator(mode="after")
    def _known_roles_only(self) -> "PermissionPolicy":
        unknown = set(self.roles) - set(PROJECT_ROLES)
        if unknown:
            raise ValueError(f"unknown roles in permission policy: {sorted(unknown)}")
        return self

    def permissions_for(self, actor: Actor, project_roles: Iterable[str]) -> frozenset[str]:
        granted: set[str] = set()
        for role in project_roles:
            granted |= self.roles.get(role, frozenset())
        if actor.is_platform_admin:
            granted |= self.platform_admin
        return frozenset(granted)


def load_permission_policy(path: Path) -> PermissionPolicy:
    with path.open(encoding="utf-8") as handle:
        return PermissionPolicy.model_validate(yaml.safe_load(handle))
