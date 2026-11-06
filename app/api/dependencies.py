"""Request dependencies: one unit of work per request, wired services and the authenticated actor.

Routers call `uow.commit()` explicitly after a successful change; anything not committed is rolled back.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine

from app.composition import Services
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.errors import AuthenticationError
from app.modules.identity.service import Actor

SESSION_COOKIE = "agentra_session"


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_uow(request: Request) -> Iterator[UnitOfWork]:
    with UnitOfWork(request.app.state.session_factory) as uow:
        yield uow


def get_services(request: Request, uow: Annotated[UnitOfWork, Depends(get_uow)]) -> Services:
    state = request.app.state
    return Services(uow.session, state.clock, state.policies, state.store, state.workspace)


def get_session_token(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AuthenticationError("Sign in required")
    return token


def get_actor(
    services: Annotated[Services, Depends(get_services)], token: Annotated[str, Depends(get_session_token)]
) -> Actor:
    return services.identity.actor_for_token(token)


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_uow)]
ServicesDep = Annotated[Services, Depends(get_services)]
ActorDep = Annotated[Actor, Depends(get_actor)]
SessionTokenDep = Annotated[str, Depends(get_session_token)]
