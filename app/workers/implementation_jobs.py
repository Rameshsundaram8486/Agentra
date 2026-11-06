"""Phase 9 background jobs, run by the agent worker (app/workers/workflow_worker.py):

- sandbox_run: builds and tests one change set version in a sandbox VM. The run is marked running and committed
  before the VM is asked, and the outcome is recorded in a new transaction. No sandbox (until Increment 5b) records
  the run as not run; it never counts as passed.
- merge_change_set: merges an approved change set version into main and completes or returns its task. Safe to
  repeat: a version merges once, and a merge that already reached main is only recorded.
"""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.composition import Policies, Services, Workspace
from app.harness.sandbox.provider import SandboxUnavailable
from app.infrastructure.clock import Clock
from app.infrastructure.job_queue import ClaimedJob
from app.infrastructure.logging import redact
from app.infrastructure.storage.base import ArtifactStore
from app.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class ImplementationJobs:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock, policies: Policies, store: ArtifactStore, workspace: Workspace) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._policies = policies
        self._store = store
        self._workspace = workspace

    @contextmanager
    def _transaction(self) -> Iterator[Services]:
        with UnitOfWork(self._session_factory) as uow:
            yield Services(uow.session, self._clock, self._policies, self._store, self._workspace)
            uow.commit()

    def handle_sandbox_run(self, job: ClaimedJob) -> None:
        run_id = uuid.UUID(job.payload["sandbox_run_id"])
        with self._transaction() as services:
            request = services.implementation.start_sandbox_run(run_id)
        if request is None:
            return  # already started or finished
        try:
            result = self._workspace.sandbox.run_checks(request)
        except SandboxUnavailable as exc:
            with self._transaction() as services:
                services.implementation.finish_sandbox_run(run_id, not_run=str(exc))
            logger.info("sandbox run not run", extra={"sandbox_run_id": str(run_id)})
            return
        except Exception as exc:  # recorded, not retried: a broken run is asked for again by a person
            logger.exception("sandbox run failed", extra={"sandbox_run_id": str(run_id)})
            with self._transaction() as services:
                services.implementation.finish_sandbox_run(run_id, error=redact(f"{type(exc).__name__}: {exc}"))
            return
        with self._transaction() as services:
            services.implementation.finish_sandbox_run(run_id, result=result)
        logger.info("sandbox run finished", extra={"sandbox_run_id": str(run_id), "status": result.status})

    def handle_merge(self, job: ClaimedJob) -> None:
        with self._transaction() as services:
            services.implementation.merge(uuid.UUID(job.payload["change_set_version_id"]))
