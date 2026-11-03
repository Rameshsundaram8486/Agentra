"""Versions, approvals, recommendations and outcomes cannot be edited or deleted, even with direct SQL."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.modules.artifacts.service import ArtifactCreate
from app.modules.decisions.service import ApprovalCreate, DecisionOutcomeCreate, DecisionRequestCreate
from tests.support import Team

Run = Callable[..., Any]


@pytest.fixture
def evidence(run: Run, team: Team) -> dict[str, Any]:
    artifact = run(
        lambda s: s.artifacts.create_artifact(
            team.agent.actor, team.project.id, ArtifactCreate(artifact_type="requirements_baseline", title="BRD", content="# BRD\n")
        )
    )
    version = artifact.current_version
    approval = run(
        lambda s: s.decisions.record_approval(
            team.reviewer.actor, version.id, ApprovalCreate(decision="approved", content_sha256=version.content_sha256)
        )
    )
    decision = run(
        lambda s: s.decisions.raise_decision(
            team.agent.actor,
            team.project.id,
            DecisionRequestCreate(
                title="Q",
                question="Which?",
                options=[{"key": "a", "title": "A"}, {"key": "b", "title": "B"}],
                recommended_option="a",
                recommendation_rationale="Because",
            ),
        )
    )
    run(lambda s: s.decisions.record_outcome(team.owner.actor, decision.id, DecisionOutcomeCreate(action="accept")))
    return {
        "artifact_versions": ("id", version.id, "content_sha256 = repeat('0', 64)"),
        "approvals": ("id", approval.id, "decision = 'rejected'"),
        "decision_requests": ("id", decision.id, "recommended_option = 'b'"),
        "decision_outcomes": ("decision_request_id", decision.id, "action = 'reject'"),
    }


@pytest.mark.parametrize("table", ["artifact_versions", "approvals", "decision_requests", "decision_outcomes"])
@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_evidence_tables_refuse_changes(engine: Engine, evidence: dict[str, Any], table: str, operation: str) -> None:
    key_column, key, change = evidence[table]
    statement = {
        "update": f"UPDATE {table} SET {change} WHERE {key_column} = :key",
        "delete": f"DELETE FROM {table} WHERE {key_column} = :key",
        "truncate": f"TRUNCATE {table} CASCADE",
    }[operation]

    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text(statement), {"key": key} if ":key" in statement else {})
