"""Stable identifier generation."""

import uuid


def new_id() -> uuid.UUID:
    return uuid.uuid4()
