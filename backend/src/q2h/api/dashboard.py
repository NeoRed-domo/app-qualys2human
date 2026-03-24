import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_data_access
from q2h.db.engine import get_db
from q2h.db.models import LatestVuln, Host, ReportCoherenceCheck, VulnLayer
from q2h.api._filters import get_freshness_thresholds, apply_freshness, os_class_case, os_type_case, os_class_filter_conditions

logger = logging.getLogger("q2h")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class SeverityCount(BaseModel):
    severity: int
    count: int


class TopVuln(BaseModel):
    qid: int
    title: str
    severity: int
    count: int
    layer_name: Optional[str] = None
    layer_color: Optional[str] = None


class TopHost(BaseModel):
    ip: str
    dns: Optional[str] = None
    os: Optional[str] = None
    host_count: int


class CoherenceItem(BaseModel):
    check_type: str
    entity: Optional[str] = None
    expected_value: str
    actual_value: str
    severity: str


class LayerCount(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    color: Optional[str] = None
    count: int


class OsClassCount(BaseModel):
    name: str
    count: int


class OsTypeCount(BaseModel):
    os_class: str
    os_type: str
    count: int


class OverviewResponse(BaseModel):
    total_vulns: int
    host_count: int
    critical_count: int
    severity_distribution: list[SeverityCount]
    top_vulns: list[TopVuln]
    top_hosts: list[TopHost]
    coherence_checks: list[CoherenceItem]
    layer_distribution: list[LayerCount]
    os_class_distribution: list[OsClassCount]
    os_type_distribution: list[OsTypeCount]
    freshness_stale_days: int = 7
    freshness_hide_days: int = 30


def _apply_filters(stmt, severities, date_from, date_to, report_id, types, layers=None, os_classes=None, host_joined=False):
    """Apply common filters to a LatestVuln query."""
    if severities:
        sev_list = [int(s.strip()) for s in severities.split(",")]
        stmt = stmt.where(LatestVuln.severity.in_(sev_list))
    if date_from:
        stmt = stmt.where(LatestVuln.first_detected >= date_from)
    if date_to:
        stmt = stmt.where(LatestVuln.last_detected <= date_to)
    if report_id:
        stmt = stmt.where(LatestVuln.scan_report_id == report_id)
    if types:
        type_list = [t.strip() for t in types.split(",")]
        stmt = stmt.where(LatestVuln.type.in_(type_list))
    if layers:
        layer_list = [int(l.strip()) for l in layers.split(",")]
        # 0 = "Autre" (unclassified, layer_id IS NULL)
        if 0 in layer_list:
            real_ids = [lid for lid in layer_list if lid != 0]
            if real_ids:
                stmt = stmt.where(or_(LatestVuln.layer_id.in_(real_ids), LatestVuln.layer_id.is_(None)))
            else:
                stmt = stmt.where(LatestVuln.layer_id.is_(None))
        else:
            stmt = stmt.where(LatestVuln.layer_id.in_(layer_list))
    if os_classes:
        cls_list = [c.strip().lower() for c in os_classes.split(",")]
        conditions = os_class_filter_conditions(Host.os, cls_list)
        if conditions:
            if not host_joined:
                stmt = stmt.join(Host, LatestVuln.host_id == Host.id, isouter=False)
            stmt = stmt.where(or_(*conditions))
    return stmt


@router.get("/overview", response_model=OverviewResponse)
async def dashboard_overview(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    severities: Optional[str] = Query(None, description="Comma-separated severity levels"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    report_id: Optional[int] = Query(None, description="Filter by scan report ID"),
    types: Optional[str] = Query(None, description="Comma-separated vuln types"),
    layers: Optional[str] = Query(None, description="Comma-separated layer IDs"),
    os_classes: Optional[str] = Query(None, description="Comma-separated OS classes: windows,nix"),
    freshness: Optional[str] = Query("active", description="Freshness: active, stale, all"),
):
    fargs = (severities, date_from, date_to, report_id, types, layers, os_classes)

    try:
        return await _build_overview(db, fargs, freshness)
    except Exception:
        logger.exception("Dashboard overview failed")
        raise HTTPException(status_code=500, detail="Dashboard query failed")


async def _build_overview(db, fargs, freshness):
    import asyncio
    severities, date_from, date_to, report_id, types, layers, os_classes = fargs
    thresholds = await get_freshness_thresholds(db)

    def _fresh(q):
        return apply_freshness(q, LatestVuln.last_detected, freshness or "active", thresholds)

    # --- Group 1: KPIs + severity distribution (single scan) ---
    async def _kpis_and_severity():
        sev_q = (
            select(LatestVuln.severity, func.count(LatestVuln.id).label("count"))
            .group_by(LatestVuln.severity)
            .order_by(LatestVuln.severity.desc())
        )
        sev_q = _fresh(_apply_filters(sev_q, *fargs))
        sev_rows = (await db.execute(sev_q)).all()

        total = sum(r.count for r in sev_rows)
        critical = sum(r.count for r in sev_rows if r.severity >= 4)
        sev_dist = [SeverityCount(severity=r.severity, count=r.count) for r in sev_rows]

        # Host count (separate — can't derive from severity grouping)
        host_q = select(func.count(func.distinct(LatestVuln.host_id)))
        host_q = _fresh(_apply_filters(host_q, *fargs))
        hosts = (await db.execute(host_q)).scalar() or 0

        return total, hosts, critical, sev_dist

    # --- Group 2: Top vulns ---
    async def _top_vulns():
        q = (
            select(
                LatestVuln.qid, LatestVuln.title, LatestVuln.severity,
                func.count(LatestVuln.id).label("count"),
                VulnLayer.name.label("layer_name"), VulnLayer.color.label("layer_color"),
            )
            .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
            .group_by(LatestVuln.qid, LatestVuln.title, LatestVuln.severity, VulnLayer.name, VulnLayer.color)
            .order_by(func.count(LatestVuln.id).desc())
            .limit(10)
        )
        q = _fresh(_apply_filters(q, *fargs))
        rows = (await db.execute(q)).all()
        return [TopVuln(qid=r.qid, title=r.title, severity=r.severity, count=r.count,
                        layer_name=r.layer_name, layer_color=r.layer_color) for r in rows]

    # --- Group 3: Top hosts ---
    async def _top_hosts():
        q = (
            select(Host.ip, Host.dns, Host.os, func.count(LatestVuln.id).label("host_count"))
            .join(LatestVuln, LatestVuln.host_id == Host.id)
            .group_by(Host.id, Host.ip, Host.dns, Host.os)
            .order_by(func.count(LatestVuln.id).desc())
            .limit(10)
        )
        q = _fresh(_apply_filters(q, *fargs, host_joined=True))
        rows = (await db.execute(q)).all()
        return [TopHost(ip=r.ip, dns=r.dns, os=r.os, host_count=r.host_count) for r in rows]

    # --- Group 4: Layer + OS distributions ---
    async def _distributions():
        os_class_label = os_class_case(Host.os).label("os_class")

        # Layer distribution
        layer_q = (
            select(VulnLayer.id.label("layer_id"), VulnLayer.name, VulnLayer.color,
                   func.count(LatestVuln.id).label("count"))
            .select_from(LatestVuln)
            .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
            .group_by(VulnLayer.id, VulnLayer.name, VulnLayer.color)
        )
        layer_q = _fresh(_apply_filters(layer_q, *fargs))

        # OS class distribution
        os_q = (
            select(os_class_label, func.count(func.distinct(Host.id)).label("count"))
            .select_from(LatestVuln)
            .join(Host, LatestVuln.host_id == Host.id)
            .group_by(os_class_label)
        )
        os_q = _fresh(_apply_filters(os_q, *fargs, host_joined=True))

        # OS type distribution
        os_type_label = os_type_case(Host.os).label("os_type")
        os_type_q = (
            select(os_class_label, os_type_label, func.count(func.distinct(Host.id)).label("count"))
            .select_from(LatestVuln)
            .join(Host, LatestVuln.host_id == Host.id)
            .group_by(os_class_label, os_type_label)
        )
        os_type_q = _fresh(_apply_filters(os_type_q, *fargs, host_joined=True))

        layer_rows, os_rows, os_type_rows = await asyncio.gather(
            db.execute(layer_q), db.execute(os_q), db.execute(os_type_q),
        )
        layer_rows = layer_rows.all()
        os_rows = os_rows.all()
        os_type_rows = os_type_rows.all()

        return (
            [LayerCount(id=r.layer_id, name=r.name, color=r.color, count=r.count) for r in layer_rows],
            [OsClassCount(name=r.os_class, count=r.count) for r in os_rows],
            [OsTypeCount(os_class=r.os_class, os_type=r.os_type, count=r.count) for r in os_type_rows],
        )

    # --- Coherence checks (lightweight, no LatestVuln scan) ---
    async def _coherence():
        coh_q = select(ReportCoherenceCheck)
        if report_id:
            coh_q = coh_q.where(ReportCoherenceCheck.scan_report_id == report_id)
        rows = (await db.execute(coh_q)).scalars().all()
        return [CoherenceItem(check_type=c.check_type, entity=c.entity,
                              expected_value=c.expected_value, actual_value=c.actual_value,
                              severity=c.severity) for c in rows]

    # Execute all groups in parallel
    (total_vulns, host_count, critical_count, severity_distribution), \
        top_vulns, top_hosts, (layer_distribution, os_class_distribution, os_type_distribution), \
        coherence_checks = await asyncio.gather(
            _kpis_and_severity(), _top_vulns(), _top_hosts(), _distributions(), _coherence(),
        )

    return OverviewResponse(
        total_vulns=total_vulns,
        host_count=host_count,
        critical_count=critical_count,
        severity_distribution=severity_distribution,
        top_vulns=top_vulns,
        top_hosts=top_hosts,
        coherence_checks=coherence_checks,
        layer_distribution=layer_distribution,
        os_class_distribution=os_class_distribution,
        os_type_distribution=os_type_distribution,
        freshness_stale_days=thresholds["stale_days"],
        freshness_hide_days=thresholds["hide_days"],
    )
