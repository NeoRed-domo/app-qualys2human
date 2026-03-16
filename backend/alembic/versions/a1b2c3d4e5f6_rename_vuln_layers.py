"""rename vuln layers to OS / Middleware-OS / Middleware-Application / Application

Revision ID: a1b2c3d4e5f6
Revises: f7b4c5d63a29
Create Date: 2026-02-24 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f7b4c5d63a29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Single atomic UPDATE avoids UNIQUE constraint violations between statements.
    # Idempotent: only renames rows that don't already have the target name.
    conn.execute(text("""
        UPDATE vuln_layers
        SET name = CASE id
                WHEN 2 THEN 'Middleware - OS'
                WHEN 3 THEN 'Middleware - Application'
                WHEN 4 THEN 'Application'
            END,
            color = CASE id
                WHEN 4 THEN '#1677ff'
                ELSE color
            END
        WHERE id IN (2, 3, 4)
          AND name NOT IN ('Middleware - OS', 'Middleware - Application', 'Application')
    """))

    # Ensure color is correct for id=4 even if name was already set
    conn.execute(text("UPDATE vuln_layers SET color = '#1677ff' WHERE id = 4"))

    # Delete all old rules and re-seed with new layer assignments
    conn.execute(text("DELETE FROM vuln_layer_rules"))

    vuln_layer_rules = sa.table(
        'vuln_layer_rules',
        sa.column('layer_id', sa.Integer),
        sa.column('match_field', sa.String),
        sa.column('pattern', sa.Text),
        sa.column('priority', sa.Integer),
    )
    op.bulk_insert(vuln_layer_rules, [
        # --- OS (layer 1) — unchanged ---
        {'layer_id': 1, 'match_field': 'category', 'pattern': 'windows',             'priority': 100},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'windows update',      'priority': 99},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'microsoft patch',     'priority': 98},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'kernel',              'priority': 97},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'linux',               'priority': 96},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'red hat enterprise',  'priority': 95},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'ubuntu',              'priority': 94},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'debian',              'priority': 93},

        # --- Middleware - OS (layer 2): runtimes, crypto libs, network services ---
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'openssl',             'priority': 80},
        {'layer_id': 2, 'match_field': 'title',    'pattern': '.net framework',      'priority': 79},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'java se',             'priority': 78},
        {'layer_id': 2, 'match_field': 'title',    'pattern': 'oracle java',         'priority': 77},
        {'layer_id': 2, 'match_field': 'category', 'pattern': 'tcp/ip',              'priority': 76},
        {'layer_id': 2, 'match_field': 'category', 'pattern': 'firewall',            'priority': 75},
        {'layer_id': 2, 'match_field': 'category', 'pattern': 'snmp',               'priority': 74},
        {'layer_id': 2, 'match_field': 'category', 'pattern': 'dns and bind',        'priority': 73},

        # --- Middleware - Application (layer 3): web/app servers ---
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'jboss',               'priority': 60},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'tomcat',              'priority': 59},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'apache http',         'priority': 58},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'iis',                 'priority': 57},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'php',                 'priority': 56},
        {'layer_id': 3, 'match_field': 'title',    'pattern': 'nginx',               'priority': 55},

        # --- Application (layer 4): end-user apps ---
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'jira',                'priority': 50},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'confluence',          'priority': 49},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'sap',                 'priority': 48},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'prtg',                'priority': 47},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'oracle db',           'priority': 46},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'sql server',          'priority': 45},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'mysql',               'priority': 44},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'phpmyadmin',          'priority': 43},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'sharepoint',          'priority': 42},
        {'layer_id': 4, 'match_field': 'title',    'pattern': 'exchange',            'priority': 41},
    ])

    # Reset sequence — protect against empty table (COALESCE)
    conn.execute(text(
        "SELECT setval('vuln_layer_rules_id_seq', COALESCE((SELECT MAX(id) FROM vuln_layer_rules), 1))"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    # Single atomic UPDATE for downgrade too
    conn.execute(text("""
        UPDATE vuln_layers
        SET name = CASE id
                WHEN 2 THEN 'Middleware'
                WHEN 3 THEN 'Applicatif'
                WHEN 4 THEN 'Réseau'
            END,
            color = CASE id
                WHEN 4 THEN '#52c41a'
                ELSE color
            END
        WHERE id IN (2, 3, 4)
          AND name NOT IN ('Middleware', 'Applicatif', 'Réseau')
    """))
    conn.execute(text("UPDATE vuln_layers SET color = '#52c41a' WHERE id = 4"))

    # Delete new rules and re-seed original ones
    conn.execute(text("DELETE FROM vuln_layer_rules"))
    vuln_layer_rules = sa.table(
        'vuln_layer_rules',
        sa.column('layer_id', sa.Integer),
        sa.column('match_field', sa.String),
        sa.column('pattern', sa.Text),
        sa.column('priority', sa.Integer),
    )
    op.bulk_insert(vuln_layer_rules, [
        {'layer_id': 1, 'match_field': 'category', 'pattern': 'windows',             'priority': 100},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'windows update',      'priority': 99},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'microsoft patch',     'priority': 98},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'kernel',              'priority': 97},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'linux',               'priority': 96},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'red hat enterprise',  'priority': 95},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'ubuntu',              'priority': 94},
        {'layer_id': 1, 'match_field': 'title',    'pattern': 'debian',              'priority': 93},
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
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'tcp/ip',              'priority': 40},
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'firewall',            'priority': 39},
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'snmp',                'priority': 38},
        {'layer_id': 4, 'match_field': 'category', 'pattern': 'dns and bind',        'priority': 37},
    ])
    conn.execute(text(
        "SELECT setval('vuln_layer_rules_id_seq', COALESCE((SELECT MAX(id) FROM vuln_layer_rules), 1))"
    ))
