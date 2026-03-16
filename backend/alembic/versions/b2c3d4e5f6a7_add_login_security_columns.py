"""add login security columns to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('refresh_token_jti', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('prev_refresh_token_jti', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('prev_refresh_token_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'prev_refresh_token_at')
    op.drop_column('users', 'prev_refresh_token_jti')
    op.drop_column('users', 'refresh_token_jti')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
