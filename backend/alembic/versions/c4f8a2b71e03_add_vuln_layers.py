"""add vuln layers classification

Revision ID: c4f8a2b71e03
Revises: a3e1f8c94d12
Create Date: 2026-02-22 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f8a2b71e03'
down_revision: Union[str, None] = 'a3e1f8c94d12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- vuln_layers table ---
    op.create_table(
        'vuln_layers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('color', sa.String(7), nullable=False, server_default='#1677ff'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
    )

    # --- vuln_layer_rules table ---
    op.create_table(
        'vuln_layer_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('layer_id', sa.Integer(), sa.ForeignKey('vuln_layers.id'), nullable=False),
        sa.Column('match_field', sa.String(20), nullable=False),
        sa.Column('pattern', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_vuln_layer_rules_layer_id', 'vuln_layer_rules', ['layer_id'])

    # --- Add layer_id to vulnerabilities ---
    op.add_column('vulnerabilities',
                  sa.Column('layer_id', sa.Integer(), sa.ForeignKey('vuln_layers.id'), nullable=True))
    op.create_index('ix_vulnerabilities_layer_id', 'vulnerabilities', ['layer_id'])

    # --- Add layers column to enterprise_presets and user_presets ---
    op.add_column('enterprise_presets',
                  sa.Column('layers', sa.ARRAY(sa.Integer()), nullable=True))
    op.add_column('user_presets',
                  sa.Column('layers', sa.ARRAY(sa.Integer()), nullable=True))

    # --- Seed default layers ---
    vuln_layers = sa.table(
        'vuln_layers',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('color', sa.String),
        sa.column('position', sa.Integer),
    )
    op.bulk_insert(vuln_layers, [
        {'id': 1, 'name': 'OS',          'color': '#f5222d', 'position': 0},
        {'id': 2, 'name': 'Middleware',   'color': '#fa8c16', 'position': 1},
        {'id': 3, 'name': 'Applicatif',  'color': '#1677ff', 'position': 2},
        {'id': 4, 'name': 'Réseau',      'color': '#52c41a', 'position': 3},
    ])

    # --- Seed default rules ---
    vuln_layer_rules = sa.table(
        'vuln_layer_rules',
        sa.column('layer_id', sa.Integer),
        sa.column('match_field', sa.String),
        sa.column('pattern', sa.Text),
        sa.column('priority', sa.Integer),
    )
    op.bulk_insert(vuln_layer_rules, [
        # OS rules
        {'layer_id': 1, 'match_field': 'category', 'pattern': 'windows',             'priority': 100},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'windows update',      'priority': 99},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'microsoft patch',     'priority': 98},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'kernel',              'priority': 97},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'linux',               'priority': 96},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'red hat enterprise',  'priority': 95},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'ubuntu',              'priority': 94},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'debian',              'priority': 93},
        # Middleware rules
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'jboss',               'priority': 80},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'tomcat',              'priority': 79},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'apache http',         'priority': 78},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'iis',                 'priority': 77},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'php',                 'priority': 76},
        {'layer_id': 2, 'match_field': 'title',    'pattern': '.net framework',      'priority': 75},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'java se',             'priority': 74},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'oracle java',         'priority': 73},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'openssl',             'priority': 72},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'nginx',               'priority': 71},
        # Applicatif rules
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'jira',                'priority': 60},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'confluence',          'priority': 59},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'sap',                 'priority': 58},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'prtg',                'priority': 57},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'oracle db',           'priority': 56},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'sql server',          'priority': 55},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'mysql',               'priority': 54},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'phpmyadmin',          'priority': 53},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'sharepoint',          'priority': 52},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'exchange',            'priority': 51},
        # Réseau rules
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'tcp/ip',              'priority': 40},
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'firewall',            'priority': 39},
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'snmp',                'priority': 38},
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'dns and bind',        'priority': 37},
    ])

    # Sync sequences after seeding with explicit IDs
    op.execute("SELECT setval('vuln_layers_id_seq', (SELECT MAX(id) FROM vuln_layers))")
    op.execute("SELECT setval('vuln_layer_rules_id_seq', (SELECT MAX(id) FROM vuln_layer_rules))")


def downgrade() -> None:
    op.drop_column('user_presets', 'layers')
    op.drop_column('enterprise_presets', 'layers')
    op.drop_index('ix_vulnerabilities_layer_id', table_name='vulnerabilities')
    op.drop_column('vulnerabilities', 'layer_id')
    op.drop_table('vuln_layer_rules')
    op.drop_table('vuln_layers')
