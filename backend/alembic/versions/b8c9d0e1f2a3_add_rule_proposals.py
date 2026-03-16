"""add created_at to vuln_layer_rules and create rule_proposals table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-13 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Add created_at to vuln_layer_rules (nullable first for backfill) ---
    op.add_column(
        'vuln_layer_rules',
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # Backfill: higher priority → newer timestamp
    op.execute(
        """
        UPDATE vuln_layer_rules
        SET created_at = NOW() - interval '1 second'
            * ((SELECT MAX(priority) FROM vuln_layer_rules) - priority)
        """
    )

    # Handle empty table edge case: set remaining NULLs to NOW()
    op.execute(
        """
        UPDATE vuln_layer_rules
        SET created_at = NOW()
        WHERE created_at IS NULL
        """
    )

    # Make NOT NULL + set server default for future inserts
    op.alter_column(
        'vuln_layer_rules',
        'created_at',
        nullable=False,
        server_default=sa.text('NOW()'),
    )

    # --- 2. Create rule_proposals table ---
    op.create_table(
        'rule_proposals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'user_id', sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'layer_id', sa.Integer(),
            sa.ForeignKey('vuln_layers.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('pattern', sa.Text(), nullable=False),
        sa.Column('match_field', sa.String(20), nullable=False),
        sa.Column(
            'status', sa.String(20), nullable=False,
            server_default='pending',
        ),
        sa.Column('admin_comment', sa.Text(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.text('NOW()'),
        ),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'reviewed_by', sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'applied_rule_id', sa.Integer(),
            sa.ForeignKey('vuln_layer_rules.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.CheckConstraint(
            "match_field IN ('title', 'category')",
            name='ck_rule_proposals_match_field',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name='ck_rule_proposals_status',
        ),
    )

    op.create_index('ix_rule_proposals_status', 'rule_proposals', ['status'])
    op.create_index('ix_rule_proposals_user_id', 'rule_proposals', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_rule_proposals_user_id', table_name='rule_proposals')
    op.drop_index('ix_rule_proposals_status', table_name='rule_proposals')
    op.drop_table('rule_proposals')
    op.drop_column('vuln_layer_rules', 'created_at')
