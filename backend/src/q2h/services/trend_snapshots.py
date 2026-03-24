"""Compute and store pre-aggregated trend snapshots.

Called after every data mutation (import, reclassify, delete_layer,
delete_report, reset_all, assign_layer).

Safety note on SQL construction:
  All interpolated values come from hardcoded dictionaries (_METRICS,
  _DIMENSIONS, _GRANULARITIES) or are explicitly int()-cast (report_ids).
  No user-controlled input ever reaches the SQL strings.
  PostgreSQL SET / DATE_TRUNC / dynamic column selection do not support
  bind parameters, so f-string assembly is required here.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("q2h")

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

_GRANULARITIES = ("day", "week", "month")

# Metrics that require filtered aggregates — computed in separate SQL blocks
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
        "where": None,  # no extra WHERE — uses all rows
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


async def recompute_all_snapshots(db: AsyncSession) -> None:
    """Full recompute of all snapshots. Used after reset-all or when
    dimensions may have changed globally (delete_layer)."""
    logger.info("Recomputing ALL trend snapshots...")
    await db.execute(text("DELETE FROM trend_snapshots"))
    for gran in _GRANULARITIES:
        await _compute_granularity(db, gran, period_filter=None)
    await db.commit()
    logger.info("Trend snapshots fully recomputed")


async def recompute_layer_snapshots(db: AsyncSession) -> None:
    """Recompute only layer-dimension snapshots. Used after reclassify
    where only layer_id changed — severity, os_class, type, total are unaffected.

    ~80% faster than recompute_all_snapshots.
    """
    logger.info("Recomputing layer-dimension trend snapshots...")

    # Delete only layer-dimension snapshots
    await db.execute(text("DELETE FROM trend_snapshots WHERE dimension = 'layer'"))

    # Recompute only the layer dimension for all metrics and granularities
    for gran in _GRANULARITIES:
        await _compute_granularity_for_dimension(db, gran, "layer")

    await db.commit()
    logger.info("Layer-dimension trend snapshots recomputed")


async def recompute_snapshots_for_reports(db: AsyncSession, report_ids: list[int]) -> None:
    """Recompute snapshots for the periods covered by given report IDs.
    Used after import or delete-report."""
    if not report_ids:
        return
    logger.info("Recomputing trend snapshots for %d report(s)...", len(report_ids))

    ids_str = ",".join(str(int(rid)) for rid in report_ids)
    for gran in _GRANULARITIES:
        # Find affected periods
        periods_q = (
            f"SELECT DISTINCT DATE_TRUNC('{gran}', COALESCE(report_date, imported_at))::date "
            f"FROM scan_reports WHERE id IN ({ids_str})"
        )
        rows = (await db.execute(text(periods_q))).all()
        periods = [row[0] for row in rows if row[0] is not None]
        if not periods:
            continue

        # Delete existing snapshots for these periods + granularity
        placeholders = ",".join(f"'{p}'" for p in periods)
        await db.execute(text(
            f"DELETE FROM trend_snapshots "
            f"WHERE granularity = '{gran}' AND period IN ({placeholders})"
        ))

        # Recompute for these periods only
        period_filter = (
            f"DATE_TRUNC('{gran}', COALESCE(sr.report_date, sr.imported_at))::date "
            f"IN ({placeholders})"
        )
        await _compute_granularity(db, gran, period_filter=period_filter)

    await db.commit()
    logger.info("Trend snapshots updated for reports %s", report_ids)


async def _compute_granularity_for_dimension(
    db: AsyncSession, gran: str, dim_name: str
) -> None:
    """Compute all metrics for a single dimension and granularity.

    Used by recompute_layer_snapshots to avoid recomputing unaffected dimensions.
    """
    date_expr = f"DATE_TRUNC('{gran}', COALESCE(sr.report_date, sr.imported_at))::date"
    dim_expr = _DIMENSIONS[dim_name]
    needs_host_join = (dim_name == "os_class")
    host_join = "JOIN hosts h ON h.id = v.host_id" if needs_host_join else ""

    # Standard metrics
    for metric_name, metric_expr in _METRICS.items():
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
        await db.execute(text(sql))

    # Remediation metrics
    for metric_name, meta in _REMEDIATION_METRICS.items():
        metric_expr = meta["expr"]
        extra_where = meta["where"]
        full_where = f"WHERE {extra_where}" if extra_where else ""

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
        await db.execute(text(sql))


async def _compute_granularity(db: AsyncSession, gran: str, period_filter: str | None) -> None:
    """Compute all metrics x all dimensions for one granularity."""
    date_expr = f"DATE_TRUNC('{gran}', COALESCE(sr.report_date, sr.imported_at))::date"
    where_clause = f"WHERE {period_filter}" if period_filter else ""

    for metric_name, metric_expr in _METRICS.items():
        for dim_name, dim_expr in _DIMENSIONS.items():
            needs_host_join = (dim_name == "os_class")
            host_join = "JOIN hosts h ON h.id = v.host_id" if needs_host_join else ""

            if dim_name == "total":
                sql = (
                    f"INSERT INTO trend_snapshots "
                    f"(period, granularity, metric, dimension, dimension_value, value, computed_at) "
                    f"SELECT {date_expr}, '{gran}', '{metric_name}', 'total', '__all__', "
                    f"{metric_expr}, now() "
                    f"FROM vulnerabilities v "
                    f"JOIN scan_reports sr ON sr.id = v.scan_report_id "
                    f"{host_join} {where_clause} "
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
                    f"{host_join} {where_clause} "
                    f"GROUP BY 1, {dim_expr} "
                    f"ON CONFLICT ON CONSTRAINT uq_trend_snapshot "
                    f"DO UPDATE SET value = EXCLUDED.value, computed_at = EXCLUDED.computed_at"
                )
            await db.execute(text(sql))

    # --- Remediation metrics (filtered aggregates, separate SQL blocks) ---
    for metric_name, meta in _REMEDIATION_METRICS.items():
        metric_expr = meta["expr"]
        extra_where = meta["where"]

        for dim_name, dim_expr in _DIMENSIONS.items():
            needs_host_join = (dim_name == "os_class")
            host_join = "JOIN hosts h ON h.id = v.host_id" if needs_host_join else ""

            # Build WHERE clause
            where_parts = []
            if period_filter:
                where_parts.append(period_filter)
            if extra_where:
                where_parts.append(extra_where)
            full_where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

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
            await db.execute(text(sql))
