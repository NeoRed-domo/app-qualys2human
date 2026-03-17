"""add trend_snapshots table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-11 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_METRICS = {
    "total_vulns": "COUNT(v.id)",
    "critical_count": "COUNT(v.id) FILTER (WHERE v.severity >= 4)",
    "host_count": "COUNT(DISTINCT v.host_id)",
    "avg_vulns_per_host": "COUNT(v.id)::float / NULLIF(COUNT(DISTINCT v.host_id), 0)",
}

_DIMENSIONS = {
    "total": None,
    "severity": "v.severity::text",
    "layer": "COALESCE(v.layer_id::text, 'unclassified')",
    "os_class": (
        "CASE WHEN h.os ILIKE '%%windows%%' THEN 'windows' "
        "WHEN h.os ILIKE '%%linux%%' OR h.os ILIKE '%%unix%%' OR h.os ILIKE '%%ubuntu%%' "
        "OR h.os ILIKE '%%debian%%' OR h.os ILIKE '%%centos%%' OR h.os ILIKE '%%red hat%%' "
        "OR h.os ILIKE '%%rhel%%' OR h.os ILIKE '%%suse%%' OR h.os ILIKE '%%fedora%%' "
        "OR h.os ILIKE '%%aix%%' OR h.os ILIKE '%%solaris%%' OR h.os ILIKE '%%freebsd%%' "
        "THEN 'nix' ELSE 'autre' END"
    ),
    "type": "COALESCE(v.type, 'unknown')",
}


def upgrade() -> None:
    op.create_table(
        'trend_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('period', sa.DateTime(), nullable=False),
        sa.Column('granularity', sa.String(10), nullable=False),
        sa.Column('metric', sa.String(50), nullable=False),
        sa.Column('dimension', sa.String(20), nullable=False),
        sa.Column('dimension_value', sa.String(100), nullable=True),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        'uq_trend_snapshot',
        'trend_snapshots',
        ['period', 'granularity', 'metric', 'dimension', 'dimension_value'],
    )
    op.create_index(
        'ix_trend_snapshots_lookup',
        'trend_snapshots',
        ['granularity', 'metric', 'dimension', 'period'],
    )

    # Initial population from existing data
    conn = op.get_bind()
    _populate_all(conn)


def _populate_all(conn):
    """Compute snapshots for all existing data across all granularities."""
    for gran in ("day", "week", "month"):
        for metric_name, metric_expr in _METRICS.items():
            for dim_name, dim_expr in _DIMENSIONS.items():
                needs_host_join = (dim_name == "os_class")
                host_join = " JOIN hosts h ON h.id = v.host_id" if needs_host_join else ""

                if dim_name == "total":
                    sql = (
                        f"INSERT INTO trend_snapshots "
                        f"(period, granularity, metric, dimension, dimension_value, value, computed_at) "
                        f"SELECT DATE_TRUNC('{gran}', COALESCE(sr.report_date, sr.imported_at))::date, "
                        f"'{gran}', '{metric_name}', 'total', '__all__', {metric_expr}, now() "
                        f"FROM vulnerabilities v "
                        f"JOIN scan_reports sr ON sr.id = v.scan_report_id "
                        f"{host_join} "
                        f"GROUP BY 1 "
                        f"ON CONFLICT ON CONSTRAINT uq_trend_snapshot "
                        f"DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at"
                    )
                else:
                    sql = (
                        f"INSERT INTO trend_snapshots "
                        f"(period, granularity, metric, dimension, dimension_value, value, computed_at) "
                        f"SELECT DATE_TRUNC('{gran}', COALESCE(sr.report_date, sr.imported_at))::date, "
                        f"'{gran}', '{metric_name}', '{dim_name}', {dim_expr}, {metric_expr}, now() "
                        f"FROM vulnerabilities v "
                        f"JOIN scan_reports sr ON sr.id = v.scan_report_id "
                        f"{host_join} "
                        f"GROUP BY 1, {dim_expr} "
                        f"ON CONFLICT ON CONSTRAINT uq_trend_snapshot "
                        f"DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at"
                    )
                conn.execute(sa.text(sql))


def downgrade() -> None:
    op.drop_table('trend_snapshots')
