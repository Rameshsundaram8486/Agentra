"""Design change requests: change requests name the baseline they change and their computed impact; a design
version records the change request it applies. Existing change requests are requirements change requests.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-04 16:02:01.979183
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0011'
down_revision: str | Sequence[str] | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('change_requests', sa.Column('baseline_type', sa.String(length=32), server_default='requirements_baseline', nullable=False))
    op.add_column('change_requests', sa.Column('impacted_requirements', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('change_requests', sa.Column('impacted_work_items', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('design_versions', sa.Column('change_request_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_design_versions_change_request_id_change_requests'), 'design_versions', 'change_requests', ['change_request_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(op.f('fk_design_versions_change_request_id_change_requests'), 'design_versions', type_='foreignkey')
    op.drop_column('design_versions', 'change_request_id')
    op.drop_column('change_requests', 'impacted_work_items')
    op.drop_column('change_requests', 'impacted_requirements')
    op.drop_column('change_requests', 'baseline_type')
