"""Sign-in, sign-out and current-user endpoints. Sessions are HttpOnly, SameSite=Strict cookies."""

import uuid

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field

from app.api.dependencies import SESSION_COOKIE, ActorDep, ServicesDep, SessionTokenDep, UnitOfWorkDep
from app.modules.errors import AuthenticationError
from app.modules.identity.service import Actor

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class MeView(BaseModel):
    id: uuid.UUID
    display_name: str
    kind: str
    is_platform_admin: bool


def _me(actor: Actor) -> MeView:
    return MeView(id=actor.id, display_name=actor.display_name, kind=actor.kind, is_platform_admin=actor.is_platform_admin)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, uow: UnitOfWorkDep, services: ServicesDep) -> MeView:
    result = services.identity.login(body.email, body.password)
    uow.commit()  # failed attempts are audited too
    if result is None:
        raise AuthenticationError("Invalid email or password")
    response.set_cookie(
        SESSION_COOKIE,
        result.token,
        expires=result.expires_at,
        path="/",
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.agentra_env == "production",
    )
    return _me(services.identity.get_actor(result.actor_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, token: SessionTokenDep, uow: UnitOfWorkDep, services: ServicesDep) -> None:
    services.identity.logout(token)
    uow.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(actor: ActorDep) -> MeView:
    return _me(actor)
