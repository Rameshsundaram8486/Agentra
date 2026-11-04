"""Incidents and their events, and generated report versions (all append-only).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04 09:32:17.231810
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

APPEND_ONLY_TABLES = ("incidents", "incident_events", "reports")

revision: str = '0007'
down_revision: str | Sequence[str] | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('reports',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('report_type', sa.String(length=64), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('data_sha256', sa.String(length=64), nullable=False),
    sa.Column('template_version', sa.String(length=32), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('data_as_of', sa.DateTime(timezone=True), nullable=True),
    sa.Column('generated_by', sa.Uuid(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['generated_by'], ['users.id'], name=op.f('fk_reports_generated_by_users')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_reports_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reports')),
    sa.UniqueConstraint('project_id', 'report_type', 'version_no', name='uq_reports_project_type_version')
    )
    op.create_index(op.f('ix_reports_project_id'), 'reports', ['project_id'], unique=False)
    op.create_table('incidents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('source_type', sa.String(length=32), nullable=False),
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('task_id', sa.Uuid(), nullable=True),
    sa.Column('task_key', sa.String(length=64), nullable=True),
    sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("severity IN ('low', 'medium', 'high')", name=op.f('ck_incidents_severity')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_incidents_project_id_projects')),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('fk_incidents_task_id_tasks')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_incidents')),
    sa.UniqueConstraint('project_id', 'number', name='uq_incidents_project_number'),
    sa.UniqueConstraint('source_type', 'source_id', name='uq_incidents_source')
    )
    op.create_index(op.f('ix_incidents_project_id'), 'incidents', ['project_id'], unique=False)
    op.create_table('incident_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('incident_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('event', sa.String(length=16), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("event IN ('recurrence', 'resolved', 'closed')", name=op.f('ck_incident_events_event')),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_incident_events_actor_id_users')),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name=op.f('fk_incident_events_incident_id_incidents')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_incident_events_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_incident_events')),
    sa.UniqueConstraint('seq', name=op.f('uq_incident_events_seq'))
    )
    op.create_index(op.f('ix_incident_events_incident_id'), 'incident_events', ['incident_id'], unique=False)

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
    op.drop_index(op.f('ix_incident_events_incident_id'), table_name='incident_events')
    op.drop_table('incident_events')
    op.drop_index(op.f('ix_incidents_project_id'), table_name='incidents')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_reports_project_id'), table_name='reports')
    op.drop_table('reports')
