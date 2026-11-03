"""Requirement items, versions and stable IDs (append-only); agent runs linked to workflow tasks and their inputs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03 16:44:14.251475
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("requirement_ids", "requirement_versions", "requirement_items")

revision: str = '0005'
down_revision: str | Sequence[str] | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('requirement_ids',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('first_artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['first_artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_requirement_ids_first_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_requirement_ids_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_requirement_ids')),
    sa.UniqueConstraint('project_id', 'item_id', name='uq_requirement_ids_project_item')
    )
    op.create_table('requirement_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=20), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('statement', sa.Text(), nullable=False),
    sa.Column('label', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('priority', sa.String(length=16), nullable=False),
    sa.Column('acceptance_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('quality_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_requirement_items_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_requirement_items_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_requirement_items')),
    sa.UniqueConstraint('artifact_version_id', 'item_id', name='uq_requirement_items_version_item')
    )
    op.create_index('ix_requirement_items_project_item', 'requirement_items', ['project_id', 'item_id'], unique=False)
    op.create_table('requirement_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('previous_artifact_version_id', sa.Uuid(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('process_flow', sa.Text(), nullable=False),
    sa.Column('set_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('input_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_requirement_versions_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_requirement_versions_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['previous_artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_requirement_versions_previous_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_requirement_versions_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_requirement_versions')),
    sa.UniqueConstraint('artifact_version_id', name=op.f('uq_requirement_versions_artifact_version_id'))
    )
    op.create_index(op.f('ix_requirement_versions_project_id'), 'requirement_versions', ['project_id'], unique=False)
    # Existing runs read only their main input.
    op.add_column('agent_runs', sa.Column('input_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.alter_column('agent_runs', 'input_refs', server_default=None)
    op.add_column('agent_runs', sa.Column('task_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_agent_runs_task_id_tasks'), 'agent_runs', 'tasks', ['task_id'], ['id'])
    # Orders transitions recorded in the same instant (existing rows are numbered in storage order).
    op.add_column('state_transitions', sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False))
    op.create_unique_constraint(op.f('uq_state_transitions_seq'), 'state_transitions', ['seq'])
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
    op.drop_constraint(op.f('uq_state_transitions_seq'), 'state_transitions', type_='unique')
    op.drop_column('state_transitions', 'seq')
    op.drop_constraint(op.f('fk_agent_runs_task_id_tasks'), 'agent_runs', type_='foreignkey')
    op.drop_column('agent_runs', 'task_id')
    op.drop_column('agent_runs', 'input_refs')
    op.drop_index(op.f('ix_requirement_versions_project_id'), table_name='requirement_versions')
    op.drop_table('requirement_versions')
    op.drop_index('ix_requirement_items_project_item', table_name='requirement_items')
    op.drop_table('requirement_items')
    op.drop_table('requirement_ids')
