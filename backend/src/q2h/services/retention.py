"""Data retention — purge scan reports older than the configured threshold."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.models import (
    ScanReport, Vulnerability, ImportJob, ReportCoherenceCheck, AuditLog,
)

logger = logging.getLogger("q2h")


async def count_purgeable_reports(
    session: AsyncSession, retention_months: int
) -> int:
    """Count reports older than the retention threshold."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_months * 30)
    result = await session.execute(
        select(func.count()).select_from(ScanReport).where(
            ScanReport.report_date < cutoff
        )
    )
    return result.scalar() or 0


async def get_purgeable_reports(
    session: AsyncSession, retention_months: int
) -> list[dict]:
    """Return summary of purgeable reports (for confirmation UI)."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_months * 30)
    rows = (await session.execute(
        select(ScanReport.id, ScanReport.report_date, ScanReport.asset_group, ScanReport.filename)
        .where(ScanReport.report_date < cutoff)
        .order_by(ScanReport.report_date)
    )).all()
    return [
        {
            "id": r.id,
            "report_date": r.report_date.isoformat() if r.report_date else None,
            "asset_group": r.asset_group,
            "filename": r.filename,
        }
        for r in rows
    ]


async def purge_expired_data(
    session: AsyncSession,
    retention_months: int,
    audit_username: str = "system",
) -> tuple[int, int]:
    """Purge reports older than retention_months.

    Deletion order (mandatory — no DB-level CASCADE on FKs):
    1. ReportCoherenceCheck
    2. ImportJob
    3. Vulnerability
    4. ScanReport

    Returns (reports_deleted, vulns_deleted).
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_months * 30)

    # Collect expired report IDs before deletion (for snapshot recompute)
    expired_ids = [
        r[0]
        for r in (
            await session.execute(
                select(ScanReport.id).where(ScanReport.report_date < cutoff)
            )
        ).all()
    ]

    if not expired_ids:
        return 0, 0

    # Count vulns for logging
    vuln_count = (
        await session.execute(
            select(func.count()).select_from(Vulnerability).where(
                Vulnerability.scan_report_id.in_(expired_ids)
            )
        )
    ).scalar() or 0

    # Delete in FK-safe order
    await session.execute(
        delete(ReportCoherenceCheck).where(
            ReportCoherenceCheck.scan_report_id.in_(expired_ids)
        )
    )
    await session.execute(
        delete(ImportJob).where(ImportJob.scan_report_id.in_(expired_ids))
    )
    await session.execute(
        delete(Vulnerability).where(Vulnerability.scan_report_id.in_(expired_ids))
    )
    await session.execute(
        delete(ScanReport).where(ScanReport.id.in_(expired_ids))
    )
    await session.commit()

    # Refresh materialized view
    await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"))
    await session.commit()

    # Recompute trend snapshots for affected reports
    from q2h.services.trend_snapshots import recompute_snapshots_for_reports
    await recompute_snapshots_for_reports(session, expired_ids)

    # Audit log
    report_count = len(expired_ids)
    session.add(AuditLog(
        user_id=None,
        action="purge",
        detail=f"user={audit_username}, reports={report_count}, vulns={vuln_count}, retention={retention_months}mo",
    ))
    await session.commit()

    logger.info(
        "Purged %d reports (%d vulnerabilities) older than %d months",
        report_count, vuln_count, retention_months,
    )
    return report_count, vuln_count
