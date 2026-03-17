"""add covering index for trend live queries

The vulnerabilities table is ~20 GB due to TEXT columns (solution, results,
threat, impact). Trend aggregation queries only need scan_report_id, severity,
host_id, layer_id, and type. This covering index lets PostgreSQL do an
index-only scan on ~500 MB instead of a full table scan on 20 GB.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-12 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_vuln_trends',
        'vulnerabilities',
        ['scan_report_id', 'severity', 'host_id', 'layer_id', 'type'],
    )


def downgrade() -> None:
    op.drop_index('ix_vuln_trends', table_name='vulnerabilities')
