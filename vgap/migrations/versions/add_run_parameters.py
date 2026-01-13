"""add_run_parameters

Revision ID: add_run_parameters
Revises: 
Create Date: 2026-01-12 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_run_parameters'
down_revision: Union[str, None] = '701f312207a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('run_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('runs', sa.Column('parameter_audit', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('runs', 'parameter_audit')
    op.drop_column('runs', 'run_parameters')
