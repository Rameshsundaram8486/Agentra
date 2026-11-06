"""Phase 9: generated tasks name their subject; project repositories, change sets, sandbox runs and merges.
Repositories, change sets and merges are append-only; a sandbox run's status changes as it runs.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-06 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("project_repositories", "change_sets", "change_set_merges")

revision: str = '0012'
down_revision: str | Sequence[str] | None = '0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('subject', sa.String(length=64), nullable=True))
    op.create_table('project_repositories',
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('initial_commit', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_repositories_project_id_projects')),
    sa.PrimaryKeyConstraint('project_id', name=op.f('pk_project_repositories'))
    )
    op.create_table('change_sets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('work_item_id', sa.String(length=20), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('backlog_version_id', sa.Uuid(), nullable=False),
    sa.Column('base_commit', sa.String(length=40), nullable=False),
    sa.Column('commit', sa.String(length=40), nullable=False),
    sa.Column('branch', sa.String(length=100), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('files', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('design_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('acceptance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('test_command', sa.String(length=300), nullable=False),
    sa.Column('limitations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('review_responses', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_change_sets_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_change_sets_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['backlog_version_id'], ['artifact_versions.id'], name=op.f('fk_change_sets_backlog_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_change_sets_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_change_sets')),
    sa.UniqueConstraint('artifact_version_id', name=op.f('uq_change_sets_artifact_version_id'))
    )
    op.create_index('ix_change_sets_project_work_item', 'change_sets', ['project_id', 'work_item_id'], unique=False)
    op.create_table('sandbox_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('change_set_version_id', sa.Uuid(), nullable=False),
    sa.Column('commit', sa.String(length=40), nullable=False),
    sa.Column('command', sa.String(length=300), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=True),
    sa.Column('image', sa.String(length=100), nullable=True),
    sa.Column('exit_code', sa.Integer(), nullable=True),
    sa.Column('output_excerpt', sa.Text(), nullable=True),
    sa.Column('output_sha256', sa.String(length=64), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('requested_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued', 'running', 'passed', 'failed', 'not_run', 'error')", name=op.f('ck_sandbox_runs_status')),
    sa.ForeignKeyConstraint(['change_set_version_id'], ['artifact_versions.id'], name=op.f('fk_sandbox_runs_change_set_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_sandbox_runs_project_id_projects')),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], name=op.f('fk_sandbox_runs_requested_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sandbox_runs')),
    sa.UniqueConstraint('seq', name=op.f('uq_sandbox_runs_seq'))
    )
    op.create_index(op.f('ix_sandbox_runs_change_set_version_id'), 'sandbox_runs', ['change_set_version_id'], unique=False)
    op.create_table('change_set_merges',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('change_set_version_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('main_before', sa.String(length=40), nullable=False),
    sa.Column('main_after', sa.String(length=40), nullable=True),
    sa.Column('conflicts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('merged', 'conflict')", name=op.f('ck_change_set_merges_status')),
    sa.ForeignKeyConstraint(['change_set_version_id'], ['artifact_versions.id'], name=op.f('fk_change_set_merges_change_set_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_change_set_merges_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_change_set_merges')),
    sa.UniqueConstraint('change_set_version_id', name=op.f('uq_change_set_merges_change_set_version_id'))
    )
    op.create_index(op.f('ix_change_set_merges_project_id'), 'change_set_merges', ['project_id'], unique=False)
    # agentra_append_only() is created by migration 0003.
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION agentra_append_only()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION agentra_append_only()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER {table}_no_truncate ON {table}")
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.drop_index(op.f('ix_change_set_merges_project_id'), table_name='change_set_merges')
    op.drop_table('change_set_merges')
    op.drop_index(op.f('ix_sandbox_runs_change_set_version_id'), table_name='sandbox_runs')
    op.drop_table('sandbox_runs')
    op.drop_index('ix_change_sets_project_work_item', table_name='change_sets')
    op.drop_table('change_sets')
    op.drop_table('project_repositories')
    op.drop_column('tasks', 'subject')
