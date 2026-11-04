"""Implementation backlog: epics and work items planned from the approved design, and the ID registry (append-only).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-04 15:03:37.282993
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("backlog_ids", "backlog_versions", "backlog_items")

revision: str = '0010'
down_revision: str | Sequence[str] | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('backlog_ids',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('first_artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['first_artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_backlog_ids_first_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_backlog_ids_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_backlog_ids')),
    sa.UniqueConstraint('project_id', 'item_id', name='uq_backlog_ids_project_item')
    )
    op.create_table('backlog_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=20), nullable=False),
    sa.Column('epic_id', sa.String(length=20), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('work_type', sa.String(length=16), nullable=False),
    sa.Column('design_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('acceptance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('estimate', sa.String(length=2), nullable=False),
    sa.Column('depends_on', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('wave', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_backlog_items_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_backlog_items_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_backlog_items')),
    sa.UniqueConstraint('artifact_version_id', 'item_id', name='uq_backlog_items_version_item')
    )
    op.create_table('backlog_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('design_version_id', sa.Uuid(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('epics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('review_responses', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_backlog_versions_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_backlog_versions_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['design_version_id'], ['artifact_versions.id'], name=op.f('fk_backlog_versions_design_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_backlog_versions_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_backlog_versions')),
    sa.UniqueConstraint('artifact_version_id', name=op.f('uq_backlog_versions_artifact_version_id'))
    )
    op.create_index(op.f('ix_backlog_versions_project_id'), 'backlog_versions', ['project_id'], unique=False)
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
    op.drop_index(op.f('ix_backlog_versions_project_id'), table_name='backlog_versions')
    op.drop_table('backlog_versions')
    op.drop_table('backlog_items')
    op.drop_table('backlog_ids')
