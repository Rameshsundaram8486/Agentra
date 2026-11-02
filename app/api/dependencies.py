"""Request dependencies: current user, DB session, authorisation helpers.

Current user and authorisation helpers arrive with the identity module (Increment 1a).
"""

from fastapi import Request
from sqlalchemy import Engine


def get_engine(request: Request) -> Engine:
    return request.app.state.engine
