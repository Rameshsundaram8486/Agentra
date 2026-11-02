"""Core tables: identity, projects, workflow, audit (append-only), job queue, outbox.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-02 17:07:11.073395
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Fixed here rather than imported, so this migration never changes when application code does.
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

revision: str = '0002'
down_revision: str | Sequence[str] | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), nullable=False),
    sa.Column('locked_by', sa.String(length=64), nullable=True),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_jobs_idempotency_key'))
    )
    op.create_index('ix_jobs_claimable', 'jobs', ['status', 'kind', 'run_after'], unique=False)
    op.create_table('outbox_messages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_messages')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_outbox_messages_idempotency_key'))
    )
    op.create_index('ix_outbox_messages_pending', 'outbox_messages', ['status', 'kind', 'next_attempt_at'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('agent_key', sa.String(length=64), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('is_platform_admin', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(kind = 'agent') = (agent_key IS NOT NULL)", name=op.f('ck_users_agents_have_agent_key')),
    sa.CheckConstraint("kind = 'human' OR password_hash IS NULL", name=op.f('ck_users_only_humans_have_passwords')),
    sa.CheckConstraint("kind IN ('human', 'agent', 'system')", name=op.f('ck_users_kind')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('agent_key', name=op.f('uq_users_agent_key')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('projects',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('customer_name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_projects_created_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
    sa.UniqueConstraint('code', name=op.f('uq_projects_code'))
    )
    op.create_table('user_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_user_sessions_token_hash'))
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('prev_hash', sa.String(length=64), nullable=False),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_events_actor_id_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_audit_events_project_id_projects')),
    sa.PrimaryKeyConstraint('seq', name=op.f('pk_audit_events')),
    sa.UniqueConstraint('hash', name=op.f('uq_audit_events_hash'))
    )
    op.create_index('ix_audit_events_project_seq', 'audit_events', ['project_id', 'seq'], unique=False)
    op.create_table('phase_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('phase', sa.Integer(), nullable=False),
    sa.Column('definition_key', sa.String(length=100), nullable=False),
    sa.Column('definition_version', sa.Integer(), nullable=False),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_phase_runs_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_phase_runs')),
    sa.UniqueConstraint('project_id', 'phase', name='uq_phase_runs_project_phase')
    )
    op.create_index(op.f('ix_phase_runs_project_id'), 'phase_runs', ['project_id'], unique=False)
    op.create_table('project_memberships',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'project_manager', 'reviewer', 'customer_approver', 'agent')", name=op.f('ck_project_memberships_role')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_project_memberships_created_by_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_memberships_project_id_projects')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_project_memberships_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_memberships')),
    sa.UniqueConstraint('project_id', 'user_id', 'role', name='uq_project_memberships_project_user_role')
    )
    op.create_index(op.f('ix_project_memberships_project_id'), 'project_memberships', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_memberships_user_id'), 'project_memberships', ['user_id'], unique=False)
    op.create_table('state_transitions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('entity_type', sa.String(length=16), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('from_state', sa.String(length=32), nullable=False),
    sa.Column('to_state', sa.String(length=32), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("entity_type IN ('phase_run', 'task')", name=op.f('ck_state_transitions_entity_type')),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_state_transitions_actor_id_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_state_transitions_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_state_transitions'))
    )
    op.create_index('ix_state_transitions_entity', 'state_transitions', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_state_transitions_project_id', 'state_transitions', ['project_id'], unique=False)
    op.create_table('tasks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('phase_run_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('agent', sa.String(length=64), nullable=True),
    sa.Column('depends_on', postgresql.ARRAY(sa.String(length=64)), nullable=False),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['phase_run_id'], ['phase_runs.id'], name=op.f('fk_tasks_phase_run_id_phase_runs')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_tasks_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tasks')),
    sa.UniqueConstraint('phase_run_id', 'key', name='uq_tasks_phase_run_key')
    )
    op.create_index(op.f('ix_tasks_phase_run_id'), 'tasks', ['phase_run_id'], unique=False)
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)

    # Audit trail is append-only, enforced by the database as well as by code.
    op.execute(
        """
        CREATE FUNCTION audit_events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only (% refused)', TG_OP;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_no_update_delete BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only()"
    )

    # The system account: actor for Agentra's own workers and admin CLI commands. It cannot sign in.
    op.execute(
        f"""
        INSERT INTO users (id, email, display_name, kind, agent_key, password_hash, is_platform_admin, is_active, created_at)
        VALUES ('{SYSTEM_USER_ID}', 'system@agentra.local', 'Agentra system', 'system', NULL, NULL, true, true, now())
        """
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_phase_run_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index('ix_state_transitions_project_id', table_name='state_transitions')
    op.drop_index('ix_state_transitions_entity', table_name='state_transitions')
    op.drop_table('state_transitions')
    op.drop_index(op.f('ix_project_memberships_user_id'), table_name='project_memberships')
    op.drop_index(op.f('ix_project_memberships_project_id'), table_name='project_memberships')
    op.drop_table('project_memberships')
    op.drop_index(op.f('ix_phase_runs_project_id'), table_name='phase_runs')
    op.drop_table('phase_runs')
    op.drop_index('ix_audit_events_project_seq', table_name='audit_events')
    op.drop_table('audit_events')
    op.execute("DROP FUNCTION audit_events_append_only()")
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_index('ix_outbox_messages_pending', table_name='outbox_messages')
    op.drop_table('outbox_messages')
    op.drop_index('ix_jobs_claimable', table_name='jobs')
    op.drop_table('jobs')
