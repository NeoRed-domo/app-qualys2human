"""add upgrade_schedules and upgrade_history tables

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-03-13 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_THRESHOLDS = '[{"minutes_before": 2880, "level": "info"}, {"minutes_before": 120, "level": "warning"}, {"minutes_before": 15, "level": "danger"}]'


def upgrade() -> None:
    # --- upgrade_schedules ---
    op.create_table(
        'upgrade_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('package_path', sa.Text(), nullable=False),
        sa.Column('source_version', sa.String(50), nullable=False),
        sa.Column('target_version', sa.String(50), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column(
            'notification_thresholds', JSONB(), nullable=False,
            server_default=sa.text(f"'{_DEFAULT_THRESHOLDS}'::jsonb"),
        ),
        sa.Column(
            'status', sa.String(20), nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'scheduled_by', sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.text('NOW()'),
        ),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name='ck_upgrade_schedules_status',
        ),
    )

    # Only one active (pending/running) schedule at a time
    op.execute(
        """
        CREATE UNIQUE INDEX uix_upgrade_schedules_active
        ON upgrade_schedules ((1))
        WHERE status IN ('pending', 'running')
        """
    )

    # --- upgrade_history ---
    op.create_table(
        'upgrade_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_version', sa.String(50), nullable=False),
        sa.Column('target_version', sa.String(50), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column(
            'status', sa.String(20), nullable=False,
        ),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column(
            'initiated_by', sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('backup_path', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('completed', 'failed', 'rolled_back')",
            name='ck_upgrade_history_status',
        ),
    )


def downgrade() -> None:
    op.drop_table('upgrade_history')
    op.execute('DROP INDEX IF EXISTS uix_upgrade_schedules_active')
    op.drop_table('upgrade_schedules')
