"""fix snapshot NULL dimension_value → __all__ sentinel

NULL values in dimension_value break the UNIQUE constraint (NULL != NULL
in PostgreSQL < 15 default). Replace NULL with '__all__' for the 'total'
dimension so that ON CONFLICT upserts work correctly.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-11 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Replace NULL → '__all__' for existing rows
    op.execute(
        sa.text(
            "UPDATE trend_snapshots SET dimension_value = '__all__' "
            "WHERE dimension_value IS NULL"
        )
    )

    # Make column NOT NULL now that we use a sentinel
    op.alter_column('trend_snapshots', 'dimension_value',
                     nullable=False, server_default='__all__')


def downgrade() -> None:
    op.alter_column('trend_snapshots', 'dimension_value',
                     nullable=True, server_default=None)
    op.execute(
        sa.text(
            "UPDATE trend_snapshots SET dimension_value = NULL "
            "WHERE dimension_value = '__all__'"
        )
    )
