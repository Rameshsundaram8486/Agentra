"""Agent runs and model calls (with reserved and actual cost for the monthly cap).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03 14:52:27.276124
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | Sequence[str] | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('agent_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('agent_key', sa.String(length=64), nullable=False),
    sa.Column('task_key', sa.String(length=64), nullable=False),
    sa.Column('agent_user_id', sa.Uuid(), nullable=False),
    sa.Column('agent_version', sa.Integer(), nullable=False),
    sa.Column('prompt_version', sa.String(length=100), nullable=False),
    sa.Column('schema_version', sa.String(length=100), nullable=False),
    sa.Column('input_artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('requested_by', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('output', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
    sa.Column('findings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('cost_usd', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'blocked')", name=op.f('ck_agent_runs_status')),
    sa.ForeignKeyConstraint(['agent_user_id'], ['users.id'], name=op.f('fk_agent_runs_agent_user_id_users')),
    sa.ForeignKeyConstraint(['input_artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_agent_runs_input_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_agent_runs_project_id_projects')),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], name=op.f('fk_agent_runs_requested_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_agent_runs_idempotency_key'))
    )
    op.create_index('ix_agent_runs_input', 'agent_runs', ['agent_key', 'task_key', 'input_artifact_version_id'], unique=False)
    op.create_index(op.f('ix_agent_runs_project_id'), 'agent_runs', ['project_id'], unique=False)
    op.create_table('model_calls',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('agent_run_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('agent_key', sa.String(length=64), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('requested_model', sa.String(length=100), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('effort', sa.String(length=16), nullable=False),
    sa.Column('max_tokens', sa.Integer(), nullable=False),
    sa.Column('prompt_version', sa.String(length=100), nullable=False),
    sa.Column('schema_version', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('stop_reason', sa.String(length=32), nullable=True),
    sa.Column('refusal_category', sa.String(length=64), nullable=True),
    sa.Column('fallback_used', sa.Boolean(), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_creation_input_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_read_input_tokens', sa.Integer(), nullable=False),
    sa.Column('reserved_usd', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('cost_exact', sa.Boolean(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('request_id', sa.String(length=100), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending', 'completed', 'refused', 'truncated', 'failed', 'abandoned')", name=op.f('ck_model_calls_status')),
    sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], name=op.f('fk_model_calls_agent_run_id_agent_runs')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_model_calls_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_calls'))
    )
    op.create_index(op.f('ix_model_calls_agent_run_id'), 'model_calls', ['agent_run_id'], unique=False)
    op.create_index(op.f('ix_model_calls_created_at'), 'model_calls', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_model_calls_created_at'), table_name='model_calls')
    op.drop_index(op.f('ix_model_calls_agent_run_id'), table_name='model_calls')
    op.drop_table('model_calls')
    op.drop_index(op.f('ix_agent_runs_project_id'), table_name='agent_runs')
    op.drop_index('ix_agent_runs_input', table_name='agent_runs')
    op.drop_table('agent_runs')
