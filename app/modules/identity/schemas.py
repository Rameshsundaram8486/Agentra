"""Identity data shared with callers: the authenticated actor, roles and views."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

UserKind = Literal["human", "agent", "system"]
ProjectRole = Literal["owner", "project_manager", "reviewer", "customer_approver", "agent"]
PROJECT_ROLES: tuple[str, ...] = ("owner", "project_manager", "reviewer", "customer_approver", "agent")
SYSTEM_ROLE = "system"


@dataclass(frozen=True)
class Actor:
    """Who is acting. Built only from an authenticated session, a verified agent run or the system account."""

    id: uuid.UUID
    kind: UserKind
    display_name: str
    is_platform_admin: bool


SYSTEM_ACTOR = Actor(id=SYSTEM_USER_ID, kind="system", display_name="Agentra system", is_platform_admin=True)


class UserView(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    kind: UserKind
    agent_key: str | None
    is_platform_admin: bool
    is_active: bool


class MemberView(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    kind: UserKind
    role: ProjectRole


class LoginResult(BaseModel):
    actor_id: uuid.UUID
    token: str
    expires_at: datetime
