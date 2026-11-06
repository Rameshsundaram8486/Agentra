"""Picks queued agent runs and runs them through the harness, and Phase 9's sandbox runs and merges
(app/workers/implementation_jobs.py). A separate process from the API:

    uv run python -m app.workers.workflow_worker          # keeps polling; Ctrl+C to stop
    uv run python -m app.workers.workflow_worker --once   # runs at most one job, then exits

Several workers can run at once; the job queue's row locks and leases keep each job to one worker.
"""

import argparse
import logging
import socket
import sys
import time
import uuid
from collections.abc import Sequence
from datetime import timedelta

from app.composition import Policies, Workspace, load_policies
from app.harness.runner import AgentRunner
from app.infrastructure.clock import SystemClock
from app.infrastructure.db import create_db_engine, make_session_factory
from app.infrastructure.job_queue import run_one_job
from app.infrastructure.logging import configure_logging
from app.infrastructure.settings import Settings, get_settings
from app.infrastructure.storage.local import LocalArtifactStore
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.providers.anthropic_provider import AnthropicProvider
from app.model_gateway.providers.base import Provider
from app.modules.executions.service import AGENT_RUN_JOB
from app.modules.implementation.service import MERGE_JOB, SANDBOX_RUN_JOB
from app.workers.implementation_jobs import ImplementationJobs

logger = logging.getLogger(__name__)


def build_runner(settings: Settings, policies: Policies, provider: Provider | None = None) -> AgentRunner:
    engine = create_db_engine(settings.database_url.get_secret_value())
    if provider is None:
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        provider = AnthropicProvider(key)
    return AgentRunner(
        make_session_factory(engine),
        SystemClock(),
        policies,
        LocalArtifactStore(settings.artifact_root),
        ModelGateway(policies.models, provider),
        Workspace.default(settings.repository_root),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.workers.workflow_worker", description="Agentra agent worker")
    parser.add_argument("--once", action="store_true", help="Run at most one job, then exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    policies = load_policies(timedelta(hours=settings.session_ttl_hours), settings.min_password_length)
    runner = build_runner(settings, policies)
    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    if settings.anthropic_api_key is None:
        logger.warning("ANTHROPIC_API_KEY is not set: agent runs will fail with provider_not_configured")
    logger.info("worker started", extra={"worker_id": worker_id, "lease_seconds": runner.lease.total_seconds()})

    workspace = Workspace.default(settings.repository_root)
    jobs = ImplementationJobs(runner.session_factory, runner.clock, policies, LocalArtifactStore(settings.artifact_root), workspace)
    handlers = {AGENT_RUN_JOB: runner.handle, SANDBOX_RUN_JOB: jobs.handle_sandbox_run, MERGE_JOB: jobs.handle_merge}
    try:
        while True:
            worked = run_one_job(runner.session_factory, runner.clock, worker_id, handlers, runner.lease)
            if args.once:
                return 0
            if not worked:
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        logger.info("worker stopped", extra={"worker_id": worker_id})
        return 0


if __name__ == "__main__":
    sys.exit(main())
