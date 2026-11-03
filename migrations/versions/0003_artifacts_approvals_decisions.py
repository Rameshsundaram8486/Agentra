"""Artifacts with immutable versions, version-bound approvals, decision requests and outcomes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03 12:10:53.318214
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("artifact_versions", "approvals", "decision_requests", "decision_outcomes")

revision: str = '0003'
down_revision: str | Sequence[str] | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('artifacts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_type', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('current_version_no', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_artifacts_created_by_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_artifacts_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_artifacts')),
    sa.UniqueConstraint('project_id', 'artifact_type', 'title', name='uq_artifacts_project_type_title')
    )
    op.create_index(op.f('ix_artifacts_project_id'), 'artifacts', ['project_id'], unique=False)
    op.create_table('artifact_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('media_type', sa.String(length=64), nullable=False),
    sa.Column('change_summary', sa.Text(), nullable=False),
    sa.Column('source_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_artifact_versions_sha256_hex')),
    sa.CheckConstraint('version_no >= 1', name=op.f('ck_artifact_versions_version_no_positive')),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_artifact_versions_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_artifact_versions_author_id_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_artifact_versions_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_artifact_versions')),
    sa.UniqueConstraint('artifact_id', 'version_no', name='uq_artifact_versions_artifact_version_no')
    )
    op.create_index(op.f('ix_artifact_versions_artifact_id'), 'artifact_versions', ['artifact_id'], unique=False)
    op.create_table('approvals',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_id', sa.Uuid(), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('decision', sa.String(length=24), nullable=False),
    sa.Column('approver_id', sa.Uuid(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_approvals_sha256_hex')),
    sa.CheckConstraint("decision IN ('approved', 'rejected', 'changes_requested')", name=op.f('ck_approvals_decision')),
    sa.ForeignKeyConstraint(['approver_id'], ['users.id'], name=op.f('fk_approvals_approver_id_users')),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_approvals_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_approvals_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_approvals_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_approvals')),
    sa.UniqueConstraint('seq', name=op.f('uq_approvals_seq'))
    )
    op.create_index(op.f('ix_approvals_artifact_id'), 'approvals', ['artifact_id'], unique=False)
    op.create_index(op.f('ix_approvals_artifact_version_id'), 'approvals', ['artifact_version_id'], unique=False)
    op.create_table('decision_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('context', sa.Text(), nullable=True),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('recommended_option', sa.String(length=64), nullable=True),
    sa.Column('recommendation_rationale', sa.Text(), nullable=False),
    sa.Column('assumptions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('risks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=True),
    sa.Column('raised_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_decision_requests_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_decision_requests_project_id_projects')),
    sa.ForeignKeyConstraint(['raised_by'], ['users.id'], name=op.f('fk_decision_requests_raised_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_decision_requests'))
    )
    op.create_index(op.f('ix_decision_requests_project_id'), 'decision_requests', ['project_id'], unique=False)
    op.create_table('decision_outcomes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('decision_request_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('outcome_no', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=16), nullable=False),
    sa.Column('selected_option', sa.String(length=64), nullable=True),
    sa.Column('custom_choice', sa.Text(), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('decided_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("action IN ('accept', 'select_option', 'other', 'modify', 'reject', 'defer')", name=op.f('ck_decision_outcomes_action')),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name=op.f('fk_decision_outcomes_decided_by_users')),
    sa.ForeignKeyConstraint(['decision_request_id'], ['decision_requests.id'], name=op.f('fk_decision_outcomes_decision_request_id_decision_requests')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_decision_outcomes_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_decision_outcomes')),
    sa.UniqueConstraint('decision_request_id', 'outcome_no', name='uq_decision_outcomes_request_outcome_no')
    )
    op.create_index(op.f('ix_decision_outcomes_decision_request_id'), 'decision_outcomes', ['decision_request_id'], unique=False)

    # Versions, approvals, recommendations and outcomes are evidence: never edited, never deleted.
    op.execute(
        """
        CREATE FUNCTION agentra_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only (% refused)', TG_TABLE_NAME, TG_OP;
        END
        $$
        """
    )
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
    op.drop_index(op.f('ix_decision_outcomes_decision_request_id'), table_name='decision_outcomes')
    op.drop_table('decision_outcomes')
    op.drop_index(op.f('ix_decision_requests_project_id'), table_name='decision_requests')
    op.drop_table('decision_requests')
    op.drop_index(op.f('ix_approvals_artifact_version_id'), table_name='approvals')
    op.drop_index(op.f('ix_approvals_artifact_id'), table_name='approvals')
    op.drop_table('approvals')
    op.drop_index(op.f('ix_artifact_versions_artifact_id'), table_name='artifact_versions')
    op.drop_table('artifact_versions')
    op.drop_index(op.f('ix_artifacts_project_id'), table_name='artifacts')
    op.drop_table('artifacts')
    op.execute("DROP FUNCTION agentra_append_only()")
