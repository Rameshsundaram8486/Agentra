"""Business rules for identity and authorisation; the only entry point for other modules."""

import hashlib
import re
import secrets
import uuid
from datetime import timedelta
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.clock import Clock
from app.modules.audit.service import AuditService
from app.modules.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.modules.identity import repository
from app.modules.identity.authz import PermissionPolicy
from app.modules.identity.models import ProjectMembership, User, UserSession
from app.modules.identity.schemas import (
    PROJECT_ROLES,
    SYSTEM_ACTOR,
    SYSTEM_ROLE,
    SYSTEM_USER_ID,
    Actor,
    LoginResult,
    MemberView,
    ProjectRole,
    UserKind,
    UserView,
)

__all__ = [
    "PROJECT_ROLES",
    "SYSTEM_ACTOR",
    "SYSTEM_ROLE",
    "SYSTEM_USER_ID",
    "Actor",
    "IdentityService",
    "LoginResult",
    "MemberView",
    "ProjectRole",
    "UserView",
]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_AGENT_KEY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_hasher = PasswordHasher()


@cache
def _dummy_hash() -> str:
    """Verified against when the user is unknown, so response time does not reveal which emails exist."""
    return _hasher.hash(secrets.token_urlsafe(16))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalise_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise ValidationFailedError("Enter a valid email address")
    return email


def _to_view(user: User) -> UserView:
    return UserView.model_validate(user, from_attributes=True)


def _to_actor(user: User) -> Actor:
    return Actor(
        id=user.id,
        kind=user.kind,  # type: ignore[arg-type]
        display_name=user.display_name,
        is_platform_admin=user.is_platform_admin,
    )


class IdentityService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        audit: AuditService,
        policy: PermissionPolicy,
        session_ttl: timedelta = timedelta(hours=12),
        min_password_length: int = 12,
    ) -> None:
        self._session = session
        self._clock = clock
        self._audit = audit
        self._policy = policy
        self._session_ttl = session_ttl
        self._min_password_length = min_password_length

    # Users ----------------------------------------------------------------------------------

    def create_user(
        self,
        actor: Actor,
        *,
        email: str,
        display_name: str,
        kind: UserKind = "human",
        password: str | None = None,
        is_platform_admin: bool = False,
        agent_key: str | None = None,
    ) -> UserView:
        self.require_platform(actor, "user.manage")
        email = _normalise_email(email)
        display_name = display_name.strip()
        if not display_name:
            raise ValidationFailedError("Display name is required")
        if kind == "human":
            if password is None or len(password) < self._min_password_length:
                raise ValidationFailedError(f"Password must be at least {self._min_password_length} characters")
            if agent_key is not None:
                raise ValidationFailedError("Only agent accounts have an agent key")
        elif kind == "agent":
            if password is not None:
                raise ValidationFailedError("Agent accounts cannot have a password; they never sign in")
            if agent_key is None or not _AGENT_KEY.match(agent_key):
                raise ValidationFailedError("Agent key must be lower_snake_case")
            if is_platform_admin:
                raise ValidationFailedError("Agent accounts cannot be platform administrators")
        else:
            raise ValidationFailedError("The system account already exists")

        if repository.get_user_by_email(self._session, email) is not None:
            raise ConflictError("A user with this email already exists")
        if agent_key is not None and self._session.scalar(select(User.id).where(User.agent_key == agent_key)):
            raise ConflictError("An agent account with this key already exists")

        user = User(
            email=email,
            display_name=display_name,
            kind=kind,
            agent_key=agent_key,
            password_hash=_hasher.hash(password) if password is not None else None,
            is_platform_admin=is_platform_admin,
            is_active=True,
            created_at=self._clock.now(),
        )
        repository.add(self._session, user)
        self._audit.record(
            actor_id=actor.id,
            action="user.create",
            entity_type="user",
            entity_id=user.id,
            after={
                "email": email,
                "display_name": display_name,
                "kind": kind,
                "agent_key": agent_key,
                "is_platform_admin": is_platform_admin,
            },
        )
        return _to_view(user)

    def get_actor(self, user_id: uuid.UUID) -> Actor:
        user = repository.get_user(self._session, user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User not found")
        return _to_actor(user)

    def actor_by_email(self, email: str) -> Actor:
        """For admin tooling (CLI); API requests always get their actor from the session."""
        user = repository.get_user_by_email(self._session, _normalise_email(email))
        if user is None or not user.is_active:
            raise NotFoundError(f"No active user {email}")
        return _to_actor(user)

    def agent_by_key(self, agent_key: str) -> Actor | None:
        user = self._session.scalar(select(User).where(User.agent_key == agent_key, User.is_active.is_(True)))
        return _to_actor(user) if user else None

    def agent_key_of(self, actor: Actor) -> str | None:
        if actor.kind != "agent":
            return None
        return self._session.scalar(select(User.agent_key).where(User.id == actor.id))

    def display_names(self, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        rows = self._session.execute(select(User.id, User.display_name).where(User.id.in_(user_ids)))
        return {user_id: name for user_id, name in rows}

    # Sessions -------------------------------------------------------------------------------

    def login(self, email: str, password: str) -> LoginResult | None:
        """None means the credentials were rejected. The caller commits either way, so failures stay audited."""
        try:
            email = _normalise_email(email)
        except ValidationFailedError:
            return None
        user = repository.get_user_by_email(self._session, email)
        if user is None or user.kind != "human" or not user.is_active or user.password_hash is None:
            try:
                _hasher.verify(_dummy_hash(), password)
            except VerificationError:
                pass
            if user is not None:
                self._audit.record(
                    actor_id=user.id, action="auth.login_failed", entity_type="user", entity_id=user.id
                )
            return None
        try:
            _hasher.verify(user.password_hash, password)
        except (VerificationError, InvalidHashError):
            self._audit.record(actor_id=user.id, action="auth.login_failed", entity_type="user", entity_id=user.id)
            return None

        if _hasher.check_needs_rehash(user.password_hash):
            user.password_hash = _hasher.hash(password)
        now = self._clock.now()
        token = secrets.token_urlsafe(32)
        user_session = UserSession(
            user_id=user.id, token_hash=_token_hash(token), created_at=now, expires_at=now + self._session_ttl
        )
        repository.add(self._session, user_session)
        self._audit.record(actor_id=user.id, action="auth.login", entity_type="user", entity_id=user.id)
        return LoginResult(actor_id=user.id, token=token, expires_at=user_session.expires_at)

    def actor_for_token(self, token: str) -> Actor:
        user_session = repository.get_active_session(self._session, _token_hash(token), self._clock.now())
        if user_session is None:
            raise AuthenticationError("Sign in required")
        user = repository.get_user(self._session, user_session.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Sign in required")
        return _to_actor(user)

    def logout(self, token: str) -> None:
        actor = self.actor_for_token(token)
        repository.revoke_session(self._session, _token_hash(token), self._clock.now())
        self._audit.record(actor_id=actor.id, action="auth.logout", entity_type="user", entity_id=actor.id)

    # Authorisation --------------------------------------------------------------------------

    def roles_for(self, actor: Actor, project_id: uuid.UUID) -> frozenset[str]:
        if actor.kind == "system":
            return frozenset({SYSTEM_ROLE})
        return frozenset(repository.roles_for(self._session, actor.id, project_id))

    def permissions_for(self, actor: Actor, project_id: uuid.UUID) -> frozenset[str]:
        return self._policy.permissions_for(actor, self.roles_for(actor, project_id))

    def require_project(self, actor: Actor, project_id: uuid.UUID, permission: str) -> None:
        """Raises NotFound if the actor cannot see the project at all, so its existence is not revealed."""
        granted = self.permissions_for(actor, project_id)
        if "project.view" not in granted:
            raise NotFoundError("Project not found")
        if permission not in granted:
            raise PermissionDeniedError(f"Your role on this project does not allow '{permission}'")

    def require_platform(self, actor: Actor, permission: str) -> None:
        if permission not in self._policy.permissions_for(actor, ()):
            raise PermissionDeniedError(f"Only platform administrators may do '{permission}'")

    def visible_project_ids(self, actor: Actor) -> list[uuid.UUID] | None:
        """None means every project."""
        if "project.view" in self._policy.permissions_for(actor, ()):
            return None
        return repository.project_ids_for(self._session, actor.id)

    # Memberships ----------------------------------------------------------------------------

    def add_initial_owner(self, actor: Actor, project_id: uuid.UUID) -> None:
        """Called by the projects service right after it creates a project; works only while it has no members."""
        if actor.kind != "human":
            raise ValidationFailedError("A project owner must be a person")
        if self._session.scalar(select(ProjectMembership.id).where(ProjectMembership.project_id == project_id)):
            raise ConflictError("This project already has members")
        self._add_membership(actor, project_id, actor.id, "owner")

    def add_member(self, actor: Actor, project_id: uuid.UUID, email: str, role: str) -> MemberView:
        self.require_project(actor, project_id, "project.manage_members")
        if role not in PROJECT_ROLES:
            raise ValidationFailedError(f"Unknown role '{role}'")
        user = repository.get_user_by_email(self._session, _normalise_email(email))
        if user is None or not user.is_active or user.kind == "system":
            raise NotFoundError("No active user with that email")
        if role == "agent" and user.kind != "agent":
            raise ValidationFailedError("Only agent accounts can hold the agent role")
        if role != "agent" and user.kind != "human":
            raise ValidationFailedError("Agent accounts can only hold the agent role")
        if repository.membership_exists(self._session, project_id, user.id, role):
            raise ConflictError("This user already has that role on the project")
        self._add_membership(actor, project_id, user.id, role)
        return MemberView(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            kind=user.kind,  # type: ignore[arg-type]
            role=role,  # type: ignore[arg-type]
        )

    def list_members(self, actor: Actor, project_id: uuid.UUID) -> list[MemberView]:
        self.require_project(actor, project_id, "project.view")
        return [
            MemberView(
                user_id=user.id,
                display_name=user.display_name,
                email=user.email,
                kind=user.kind,  # type: ignore[arg-type]
                role=membership.role,  # type: ignore[arg-type]
            )
            for membership, user in repository.list_members(self._session, project_id)
        ]

    def _add_membership(self, actor: Actor, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        membership = ProjectMembership(
            project_id=project_id, user_id=user_id, role=role, created_by=actor.id, created_at=self._clock.now()
        )
        repository.add(self._session, membership)
        self._audit.record(
            actor_id=actor.id,
            action="membership.add",
            entity_type="project_membership",
            entity_id=membership.id,
            project_id=project_id,
            after={"user_id": str(user_id), "role": role},
        )
