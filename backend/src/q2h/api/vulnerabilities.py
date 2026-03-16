from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_data_access
from q2h.db.engine import get_db
from q2h.db.models import LatestVuln, Host, VulnLayer
from q2h.api._filters import get_freshness_thresholds, apply_freshness

router = APIRouter(prefix="/api/vulnerabilities", tags=["vulnerabilities"])


class VulnListItem(BaseModel):
    qid: int
    title: str
    severity: int
    type: Optional[str] = None
    category: Optional[str] = None
    host_count: int
    occurrence_count: int
    layer_name: Optional[str] = None
    layer_color: Optional[str] = None


class VulnListResponse(BaseModel):
    items: list[VulnListItem]
    total: int


class VulnDetailResponse(BaseModel):
    qid: int
    title: str
    severity: int
    type: Optional[str] = None
    category: Optional[str] = None
    cvss_base: Optional[str] = None
    cvss_temporal: Optional[str] = None
    cvss3_base: Optional[str] = None
    cvss3_temporal: Optional[str] = None
    bugtraq_id: Optional[str] = None
    threat: Optional[str] = None
    impact: Optional[str] = None
    solution: Optional[str] = None
    vendor_reference: Optional[str] = None
    cve_ids: Optional[list[str]] = None
    affected_host_count: int
    total_occurrences: int
    layer_id: Optional[int] = None
    layer_name: Optional[str] = None


class VulnHostItem(BaseModel):
    ip: str
    dns: Optional[str] = None
    os: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    vuln_status: Optional[str] = None
    first_detected: Optional[str] = None
    last_detected: Optional[str] = None


class PaginatedHosts(BaseModel):
    items: list[VulnHostItem]
    total: int
    page: int
    page_size: int




@router.get("", response_model=VulnListResponse)
async def list_vulnerabilities(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    severity: Optional[int] = Query(None, description="Filter by severity level"),
    layer: Optional[int] = Query(None, description="Filter by layer ID (0 = unclassified)"),
    freshness: Optional[str] = Query("active", description="Freshness: active, stale, all"),
):
    thresholds = await get_freshness_thresholds(db)

    q = (
        select(
            LatestVuln.qid,
            func.min(LatestVuln.title).label("title"),
            func.min(LatestVuln.severity).label("severity"),
            func.min(LatestVuln.type).label("type"),
            func.min(LatestVuln.category).label("category"),
            func.count(func.distinct(LatestVuln.host_id)).label("host_count"),
            func.count(LatestVuln.id).label("occurrence_count"),
            func.min(VulnLayer.name).label("layer_name"),
            func.min(VulnLayer.color).label("layer_color"),
        )
        .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
        .group_by(LatestVuln.qid)
    )

    if severity is not None:
        q = q.where(LatestVuln.severity == severity)

    if layer is not None:
        if layer == 0:
            q = q.where(LatestVuln.layer_id.is_(None))
        else:
            q = q.where(LatestVuln.layer_id == layer)

    q = apply_freshness(q, LatestVuln.last_detected, freshness or "active", thresholds)
    q = q.order_by(func.count(LatestVuln.id).desc())

    rows = (await db.execute(q)).all()

    items = [
        VulnListItem(
            qid=r.qid, title=r.title, severity=r.severity,
            type=r.type, category=r.category,
            host_count=r.host_count, occurrence_count=r.occurrence_count,
            layer_name=r.layer_name, layer_color=r.layer_color,
        )
        for r in rows
    ]
    return VulnListResponse(items=items, total=len(items))


@router.get("/{qid}", response_model=VulnDetailResponse)
async def vulnerability_detail(
    qid: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    # Get one representative row for the QID info, with layer name
    result = await db.execute(
        select(LatestVuln, VulnLayer.name.label("layer_name"))
        .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
        .where(LatestVuln.qid == qid)
        .limit(1)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QID not found")
    vuln = row[0]
    layer_name = row[1]

    # Count affected hosts and total occurrences
    host_count_q = select(func.count(func.distinct(LatestVuln.host_id))).where(
        LatestVuln.qid == qid
    )
    affected_host_count = (await db.execute(host_count_q)).scalar() or 0

    total_q = select(func.count(LatestVuln.id)).where(LatestVuln.qid == qid)
    total_occurrences = (await db.execute(total_q)).scalar() or 0

    return VulnDetailResponse(
        qid=vuln.qid,
        title=vuln.title,
        severity=vuln.severity,
        type=vuln.type,
        category=vuln.category,
        cvss_base=vuln.cvss_base,
        cvss_temporal=vuln.cvss_temporal,
        cvss3_base=vuln.cvss3_base,
        cvss3_temporal=vuln.cvss3_temporal,
        bugtraq_id=vuln.bugtraq_id,
        threat=vuln.threat,
        impact=vuln.impact,
        solution=vuln.solution,
        vendor_reference=vuln.vendor_reference,
        cve_ids=vuln.cve_ids,
        affected_host_count=affected_host_count,
        total_occurrences=total_occurrences,
        layer_id=vuln.layer_id,
        layer_name=layer_name,
    )


@router.get("/{qid}/hosts", response_model=PaginatedHosts)
async def vulnerability_hosts(
    qid: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    # Total count
    total_q = select(func.count(LatestVuln.id)).where(LatestVuln.qid == qid)
    total = (await db.execute(total_q)).scalar() or 0

    # Paginated host list
    offset = (page - 1) * page_size
    rows_q = (
        select(
            Host.ip, Host.dns, Host.os,
            LatestVuln.port, LatestVuln.protocol,
            LatestVuln.vuln_status,
            LatestVuln.first_detected, LatestVuln.last_detected,
        )
        .join(LatestVuln, LatestVuln.host_id == Host.id)
        .where(LatestVuln.qid == qid)
        .order_by(Host.ip)
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(rows_q)).all()

    items = [
        VulnHostItem(
            ip=r.ip,
            dns=r.dns,
            os=r.os,
            port=r.port,
            protocol=r.protocol,
            vuln_status=r.vuln_status,
            first_detected=r.first_detected.isoformat() if r.first_detected else None,
            last_detected=r.last_detected.isoformat() if r.last_detected else None,
        )
        for r in rows
    ]

    return PaginatedHosts(items=items, total=total, page=page, page_size=page_size)
