"""add remediation index and recompute trend snapshots

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-03-14 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- Inline metric/dimension dicts (do NOT import from service module) ---

_METRICS = {
    "total_vulns": "COUNT(v.id)",
    "critical_count": "COUNT(v.id) FILTER (WHERE v.severity >= 4)",
    "host_count": "COUNT(DISTINCT v.host_id)",
    "avg_vulns_per_host": "COUNT(v.id)::float / NULLIF(COUNT(DISTINCT v.host_id), 0)",
}

_REMEDIATION_METRICS = {
    "avg_remediation_days": {
        "expr": (
            "AVG(EXTRACT(EPOCH FROM (v.date_last_fixed - v.first_detected)) / 86400)"
        ),
        "where": (
            "v.vuln_status = 'Fixed' "
            "AND v.date_last_fixed IS NOT NULL "
            "AND v.first_detected IS NOT NULL"
        ),
    },
    "remediation_rate": {
        "expr": (
            "COUNT(*) FILTER (WHERE v.vuln_status = 'Fixed') * 100.0 "
            "/ NULLIF(COUNT(*) FILTER (WHERE v.vuln_status IS NOT NULL), 0)"
        ),
        "where": None,
    },
    "avg_open_age_days": {
        "expr": (
            "AVG(GREATEST(0, EXTRACT(EPOCH FROM "
            "(COALESCE(sr.report_date, sr.imported_at) - v.first_detected)) / 86400))"
        ),
        "where": (
            "v.vuln_status IS DISTINCT FROM 'Fixed' "
            "AND v.first_detected IS NOT NULL"
        ),
    },
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
    # 1. Create covering index for remediation queries
    op.create_index(
        'ix_vuln_remediation',
        'vulnerabilities',
        ['scan_report_id', 'vuln_status', 'first_detected', 'date_last_fixed'],
    )

    # 2. Recompute all snapshots (includes new metrics)
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM trend_snapshots"))
    _populate_all(conn)


def _populate_all(conn):
    for gran in ("day", "week", "month"):
        date_expr = f"DATE_TRUNC('{gran}', COALESCE(sr.report_date, sr.imported_at))::date"

        # Standard metrics (simple aggregates)
        for metric_name, metric_expr in _METRICS.items():
            for dim_name, dim_expr in _DIMENSIONS.items():
                needs_host_join = (dim_name == "os_class")
                host_join = " JOIN hosts h ON h.id = v.host_id" if needs_host_join else ""

                if dim_name == "total":
                    sql = (
                        f"INSERT INTO trend_snapshots "
                        f"(period, granularity, metric, dimension, dimension_value, value, computed_at) "
                        f"SELECT {date_expr}, '{gran}', '{metric_name}', 'total', '__all__', "
                        f"{metric_expr}, now() "
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
                        f"SELECT {date_expr}, '{gran}', '{metric_name}', '{dim_name}', "
                        f"{dim_expr}, {metric_expr}, now() "
                        f"FROM vulnerabilities v "
                        f"JOIN scan_reports sr ON sr.id = v.scan_report_id "
                        f"{host_join} "
                        f"GROUP BY 1, {dim_expr} "
                        f"ON CONFLICT ON CONSTRAINT uq_trend_snapshot "
                        f"DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at"
                    )
                conn.execute(sa.text(sql))

        # Remediation metrics (filtered aggregates)
        for metric_name, meta in _REMEDIATION_METRICS.items():
            metric_expr = meta["expr"]
            extra_where = meta["where"]

            for dim_name, dim_expr in _DIMENSIONS.items():
                needs_host_join = (dim_name == "os_class")
                host_join = " JOIN hosts h ON h.id = v.host_id" if needs_host_join else ""
                full_where = f"WHERE {extra_where}" if extra_where else ""

                if dim_name == "total":
                    sql = (
                        f"INSERT INTO trend_snapshots "
                        f"(period, granularity, metric, dimension, dimension_value, value, computed_at) "
                        f"SELECT {date_expr}, '{gran}', '{metric_name}', 'total', '__all__', "
                        f"{metric_expr}, now() "
                        f"FROM vulnerabilities v "
                        f"JOIN scan_reports sr ON sr.id = v.scan_report_id "
                        f"{host_join} {full_where} "
                        f"GROUP BY 1 "
                        f"HAVING {metric_expr} IS NOT NULL "
                        f"ON CONFLICT ON CONSTRAINT uq_trend_snapshot "
                        f"DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at"
                    )
                else:
                    sql = (
                        f"INSERT INTO trend_snapshots "
                        f"(period, granularity, metric, dimension, dimension_value, value, computed_at) "
                        f"SELECT {date_expr}, '{gran}', '{metric_name}', '{dim_name}', "
                        f"{dim_expr}, {metric_expr}, now() "
                        f"FROM vulnerabilities v "
                        f"JOIN scan_reports sr ON sr.id = v.scan_report_id "
                        f"{host_join} {full_where} "
                        f"GROUP BY 1, {dim_expr} "
                        f"HAVING {metric_expr} IS NOT NULL "
                        f"ON CONFLICT ON CONSTRAINT uq_trend_snapshot "
                        f"DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at"
                    )
                conn.execute(sa.text(sql))


def downgrade() -> None:
    op.drop_index('ix_vuln_remediation', table_name='vulnerabilities')
    # Remove only the new metrics from snapshots
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM trend_snapshots WHERE metric IN "
        "('avg_remediation_days', 'remediation_rate', 'avg_open_age_days')"
    ))
