"""Solution design: design items, versions tied to the approved requirements, and the design ID registry (append-only).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-04 11:03:49.164911
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("design_ids", "design_versions", "design_items")

revision: str = '0008'
down_revision: str | Sequence[str] | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('design_ids',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('first_artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['first_artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_design_ids_first_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_design_ids_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_design_ids')),
    sa.UniqueConstraint('project_id', 'item_id', name='uq_design_ids_project_item')
    )
    op.create_table('design_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=20), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('label', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('satisfies', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('related', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('unverified_capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('quality_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_design_items_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_design_items_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_design_items')),
    sa.UniqueConstraint('artifact_version_id', 'item_id', name='uq_design_items_version_item')
    )
    op.create_index('ix_design_items_project_item', 'design_items', ['project_id', 'item_id'], unique=False)
    op.create_table('design_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('previous_artifact_version_id', sa.Uuid(), nullable=True),
    sa.Column('requirements_version_id', sa.Uuid(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('component_diagram', sa.Text(), nullable=False),
    sa.Column('data_flow_diagram', sa.Text(), nullable=False),
    sa.Column('exceptions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('set_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('input_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('review_responses', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_design_versions_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_design_versions_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['previous_artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_design_versions_previous_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_design_versions_project_id_projects')),
    sa.ForeignKeyConstraint(['requirements_version_id'], ['artifact_versions.id'], name=op.f('fk_design_versions_requirements_version_id_artifact_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_design_versions')),
    sa.UniqueConstraint('artifact_version_id', name=op.f('uq_design_versions_artifact_version_id'))
    )
    op.create_index(op.f('ix_design_versions_project_id'), 'design_versions', ['project_id'], unique=False)

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
    op.drop_index(op.f('ix_design_versions_project_id'), table_name='design_versions')
    op.drop_table('design_versions')
    op.drop_index('ix_design_items_project_item', table_name='design_items')
    op.drop_table('design_items')
    op.drop_table('design_ids')
