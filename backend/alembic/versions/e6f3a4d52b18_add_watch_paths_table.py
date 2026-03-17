"""add watch_paths table

Revision ID: e6f3a4d52b18
Revises: d5a2b3c41f07
Create Date: 2026-02-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f3a4d52b18'
down_revision: Union[str, None] = 'd5a2b3c41f07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'watch_paths',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('path', sa.Text(), nullable=False, unique=True),
        sa.Column('pattern', sa.String(100), nullable=False, server_default='*.csv'),
        sa.Column('recursive', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('watch_paths')
