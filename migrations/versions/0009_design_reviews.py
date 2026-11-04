"""Design reviews: security and feasibility reviews of a design version and their findings (append-only).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-04 14:04:02.524556
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("design_reviews", "design_review_findings")

revision: str = '0009'
down_revision: str | Sequence[str] | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('design_review_findings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('review_version_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('ref', sa.String(length=20), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('verdict', sa.String(length=16), nullable=False),
    sa.Column('severity', sa.String(length=8), nullable=True),
    sa.Column('complexity', sa.String(length=2), nullable=True),
    sa.Column('assessment', sa.Text(), nullable=False),
    sa.Column('recommendation', sa.Text(), nullable=False),
    sa.Column('design_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('unverified', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['review_version_id'], ['artifact_versions.id'], name=op.f('fk_design_review_findings_review_version_id_artifact_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_design_review_findings')),
    sa.UniqueConstraint('review_version_id', 'ref', name='uq_design_review_findings_version_ref')
    )
    op.create_table('design_reviews',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('design_version_id', sa.Uuid(), nullable=False),
    sa.Column('checklist', sa.String(length=120), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('review_responses', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_design_reviews_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_design_reviews_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['design_version_id'], ['artifact_versions.id'], name=op.f('fk_design_reviews_design_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_design_reviews_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_design_reviews')),
    sa.UniqueConstraint('artifact_version_id', name=op.f('uq_design_reviews_artifact_version_id'))
    )
    op.create_index('ix_design_reviews_design_version', 'design_reviews', ['design_version_id', 'kind'], unique=False)
    op.create_index(op.f('ix_design_reviews_project_id'), 'design_reviews', ['project_id'], unique=False)
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
    op.drop_index(op.f('ix_design_reviews_project_id'), table_name='design_reviews')
    op.drop_index('ix_design_reviews_design_version', table_name='design_reviews')
    op.drop_table('design_reviews')
    op.drop_table('design_review_findings')
