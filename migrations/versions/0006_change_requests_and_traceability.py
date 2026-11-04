"""Change requests and their events (append-only); item links and review responses on requirement versions.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03 17:19:03.792468
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("change_requests", "change_request_events")
EMPTY_LIST = sa.text("'[]'::jsonb")

revision: str = '0006'
down_revision: str | Sequence[str] | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('change_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('baseline_artifact_id', sa.Uuid(), nullable=False),
    sa.Column('baseline_version_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('change', sa.Text(), nullable=False),
    sa.Column('impact', sa.Text(), nullable=False),
    sa.Column('affected_item_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('allows_new_items', sa.Boolean(), nullable=False),
    sa.Column('raised_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['baseline_artifact_id'], ['artifacts.id'], name=op.f('fk_change_requests_baseline_artifact_id_artifacts')),
    sa.ForeignKeyConstraint(['baseline_version_id'], ['artifact_versions.id'], name=op.f('fk_change_requests_baseline_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_change_requests_project_id_projects')),
    sa.ForeignKeyConstraint(['raised_by'], ['users.id'], name=op.f('fk_change_requests_raised_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_change_requests')),
    sa.UniqueConstraint('project_id', 'number', name='uq_change_requests_project_number')
    )
    op.create_index(op.f('ix_change_requests_project_id'), 'change_requests', ['project_id'], unique=False)
    op.create_table('change_request_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('change_request_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('event', sa.String(length=16), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=True),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('artifact_version_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("event IN ('approved', 'rejected', 'applied')", name=op.f('ck_change_request_events_event')),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_change_request_events_actor_id_users')),
    sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name=op.f('fk_change_request_events_artifact_version_id_artifact_versions')),
    sa.ForeignKeyConstraint(['change_request_id'], ['change_requests.id'], name=op.f('fk_change_request_events_change_request_id_change_requests')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_change_request_events_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_change_request_events')),
    sa.UniqueConstraint('seq', name=op.f('uq_change_request_events_seq'))
    )
    op.create_index(op.f('ix_change_request_events_change_request_id'), 'change_request_events', ['change_request_id'], unique=False)
    op.create_index('uq_change_request_events_applied', 'change_request_events', ['change_request_id'], unique=True, postgresql_where=sa.text("event = 'applied'"))
    op.create_index('uq_change_request_events_role', 'change_request_events', ['change_request_id', 'role'], unique=True, postgresql_where=sa.text('role IS NOT NULL'))
    op.add_column('requirement_items', sa.Column('related', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=EMPTY_LIST))
    op.alter_column('requirement_items', 'related', server_default=None)
    op.add_column('requirement_versions', sa.Column('review_responses', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=EMPTY_LIST))
    op.alter_column('requirement_versions', 'review_responses', server_default=None)
    op.add_column('requirement_versions', sa.Column('change_request_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_requirement_versions_change_request_id_change_requests'), 'requirement_versions', 'change_requests', ['change_request_id'], ['id'])

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
    op.drop_constraint(op.f('fk_requirement_versions_change_request_id_change_requests'), 'requirement_versions', type_='foreignkey')
    op.drop_column('requirement_versions', 'change_request_id')
    op.drop_column('requirement_versions', 'review_responses')
    op.drop_column('requirement_items', 'related')
    op.drop_index('uq_change_request_events_role', table_name='change_request_events', postgresql_where=sa.text('role IS NOT NULL'))
    op.drop_index('uq_change_request_events_applied', table_name='change_request_events', postgresql_where=sa.text("event = 'applied'"))
    op.drop_index(op.f('ix_change_request_events_change_request_id'), table_name='change_request_events')
    op.drop_table('change_request_events')
    op.drop_index(op.f('ix_change_requests_project_id'), table_name='change_requests')
    op.drop_table('change_requests')
