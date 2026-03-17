"""add os_classes and freshness to enterprise_presets and user_presets

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('enterprise_presets', sa.Column('os_classes', ARRAY(sa.String()), nullable=True))
    op.add_column('enterprise_presets', sa.Column('freshness', sa.String(20), nullable=True))
    op.add_column('user_presets', sa.Column('os_classes', ARRAY(sa.String()), nullable=True))
    op.add_column('user_presets', sa.Column('freshness', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('user_presets', 'freshness')
    op.drop_column('user_presets', 'os_classes')
    op.drop_column('enterprise_presets', 'freshness')
    op.drop_column('enterprise_presets', 'os_classes')
