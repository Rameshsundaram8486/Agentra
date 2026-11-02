"""Helpers shared by tests (importable as tests.support)."""

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass

from alembic.config import Config

from app.composition import Policies
from app.infrastructure.settings import ROOT_DIR
from app.modules.identity.service import Actor
from app.modules.projects.service import ProjectView
from app.modules.workflow.definitions import TaskDefinition, WorkflowCatalog

DEFAULT_PASSWORD = "correct-horse-battery-staple"


def alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def with_phase_tasks(policies: Policies, phase: int, tasks: Iterable[TaskDefinition]) -> Policies:
    """The real workflow config, with tasks added to one phase (real phase files define tasks in later increments)."""
    catalog = policies.catalog
    definition = catalog.phase(phase).model_copy(update={"tasks": tuple(tasks)})
    updated = WorkflowCatalog(lifecycles=catalog.lifecycles, phases={**catalog.phases, phase: definition})
    return dataclasses.replace(policies, catalog=updated)


@dataclass(frozen=True)
class TestUser:
    __test__ = False  # not a pytest test class

    actor: Actor
    email: str
    password: str | None


@dataclass(frozen=True)
class Team:
    project: ProjectView
    owner: TestUser
    pm: TestUser
    reviewer: TestUser
    agent: TestUser
