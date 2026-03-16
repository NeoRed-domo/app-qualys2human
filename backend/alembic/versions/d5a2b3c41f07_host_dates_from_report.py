"""host first_seen/last_seen nullable, driven by report_date

Revision ID: d5a2b3c41f07
Revises: c4f8a2b71e03
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5a2b3c41f07'
down_revision: Union[str, None] = 'c4f8a2b71e03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('hosts', 'first_seen',
                    existing_type=sa.DateTime(),
                    nullable=True,
                    server_default=None)
    op.alter_column('hosts', 'last_seen',
                    existing_type=sa.DateTime(),
                    nullable=True,
                    server_default=None)


def downgrade() -> None:
    op.alter_column('hosts', 'first_seen',
                    existing_type=sa.DateTime(),
                    nullable=False,
                    server_default=sa.text('now()'))
    op.alter_column('hosts', 'last_seen',
                    existing_type=sa.DateTime(),
                    nullable=False,
                    server_default=sa.text('now()'))
