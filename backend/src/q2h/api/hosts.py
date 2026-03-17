from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_data_access
from q2h.db.engine import get_db
from q2h.db.models import LatestVuln, Host, VulnLayer

router = APIRouter(prefix="/api/hosts", tags=["hosts"])


class HostDetailResponse(BaseModel):
    ip: str
    dns: Optional[str] = None
    netbios: Optional[str] = None
    os: Optional[str] = None
    os_cpe: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    vuln_count: int


class HostVulnItem(BaseModel):
    qid: int
    title: str
    severity: int
    type: Optional[str] = None
    category: Optional[str] = None
    vuln_status: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    first_detected: Optional[str] = None
    last_detected: Optional[str] = None
    tracking_method: Optional[str] = None
    layer_name: Optional[str] = None
    layer_color: Optional[str] = None


class PaginatedVulns(BaseModel):
    items: list[HostVulnItem]
    total: int
    page: int
    page_size: int


class FullDetailResponse(BaseModel):
    ip: str
    dns: Optional[str] = None
    os: Optional[str] = None
    qid: int
    title: str
    severity: int
    type: Optional[str] = None
    category: Optional[str] = None
    vuln_status: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    fqdn: Optional[str] = None
    ssl: Optional[bool] = None
    first_detected: Optional[str] = None
    last_detected: Optional[str] = None
    times_detected: Optional[int] = None
    date_last_fixed: Optional[str] = None
    cve_ids: Optional[list[str]] = None
    vendor_reference: Optional[str] = None
    bugtraq_id: Optional[str] = None
    cvss_base: Optional[str] = None
    cvss_temporal: Optional[str] = None
    cvss3_base: Optional[str] = None
    cvss3_temporal: Optional[str] = None
    threat: Optional[str] = None
    impact: Optional[str] = None
    solution: Optional[str] = None
    results: Optional[str] = None
    pci_vuln: Optional[bool] = None
    ticket_state: Optional[str] = None
    tracking_method: Optional[str] = None
    layer_id: Optional[int] = None
    layer_name: Optional[str] = None
    affected_host_count: int = 0
    total_occurrences: int = 0


class HostListItem(BaseModel):
    ip: str
    dns: Optional[str] = None
    os: Optional[str] = None
    vuln_count: int


class HostListResponse(BaseModel):
    items: list[HostListItem]
    total: int


NIX_PATTERNS = [
    "%linux%", "%unix%", "%ubuntu%", "%debian%", "%centos%",
    "%red hat%", "%rhel%", "%suse%", "%fedora%", "%aix%",
    "%solaris%", "%freebsd%",
]


@router.get("", response_model=HostListResponse)
async def list_hosts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    os_class: Optional[str] = Query(None, description="OS class: windows, nix, autre"),
):
    q = (
        select(
            Host.ip,
            Host.dns,
            Host.os,
            func.count(LatestVuln.id).label("vuln_count"),
        )
        .join(LatestVuln, LatestVuln.host_id == Host.id)
        .group_by(Host.id, Host.ip, Host.dns, Host.os)
        .order_by(func.count(LatestVuln.id).desc())
    )

    if os_class:
        cls = os_class.strip().lower()
        if cls == "windows":
            q = q.where(Host.os.ilike("%windows%"))
        elif cls == "nix":
            q = q.where(or_(*(Host.os.ilike(p) for p in NIX_PATTERNS)))
        elif cls == "autre":
            q = q.where(
                ~Host.os.ilike("%windows%"),
                ~or_(*(Host.os.ilike(p) for p in NIX_PATTERNS)),
            )

    rows = (await db.execute(q)).all()
    items = [
        HostListItem(ip=r.ip, dns=r.dns, os=r.os, vuln_count=r.vuln_count)
        for r in rows
    ]
    return HostListResponse(items=items, total=len(items))


@router.get("/{ip}", response_model=HostDetailResponse)
async def host_detail(
    ip: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    result = await db.execute(select(Host).where(Host.ip == ip))
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")

    vuln_count_q = select(func.count(LatestVuln.id)).where(
        LatestVuln.host_id == host.id
    )
    vuln_count = (await db.execute(vuln_count_q)).scalar() or 0

    return HostDetailResponse(
        ip=host.ip,
        dns=host.dns,
        netbios=host.netbios,
        os=host.os,
        os_cpe=host.os_cpe,
        first_seen=host.first_seen.isoformat() if host.first_seen else None,
        last_seen=host.last_seen.isoformat() if host.last_seen else None,
        vuln_count=vuln_count,
    )


@router.get("/{ip}/vulnerabilities", response_model=PaginatedVulns)
async def host_vulnerabilities(
    ip: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    result = await db.execute(select(Host).where(Host.ip == ip))
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")

    # Total count
    total_q = select(func.count(LatestVuln.id)).where(
        LatestVuln.host_id == host.id
    )
    total = (await db.execute(total_q)).scalar() or 0

    # Paginated vuln list with layer info
    offset = (page - 1) * page_size
    rows_q = (
        select(LatestVuln, VulnLayer.name.label("layer_name"), VulnLayer.color.label("layer_color"))
        .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
        .where(LatestVuln.host_id == host.id)
        .order_by(LatestVuln.severity.desc(), LatestVuln.qid)
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(rows_q)).all()

    items = [
        HostVulnItem(
            qid=v.qid,
            title=v.title,
            severity=v.severity,
            type=v.type,
            category=v.category,
            vuln_status=v.vuln_status,
            port=v.port,
            protocol=v.protocol,
            first_detected=v.first_detected.isoformat() if v.first_detected else None,
            last_detected=v.last_detected.isoformat() if v.last_detected else None,
            tracking_method=v.tracking_method,
            layer_name=layer_name,
            layer_color=layer_color,
        )
        for v, layer_name, layer_color in rows
    ]

    return PaginatedVulns(items=items, total=total, page=page, page_size=page_size)


@router.get("/{ip}/vulnerabilities/{qid}", response_model=FullDetailResponse)
async def full_detail(
    ip: str,
    qid: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    result = await db.execute(select(Host).where(Host.ip == ip))
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")

    vuln_q = (
        select(LatestVuln, VulnLayer.name.label("layer_name"))
        .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
        .where(LatestVuln.host_id == host.id, LatestVuln.qid == qid)
    )
    row = (await db.execute(vuln_q)).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vulnerability not found on this host"
        )
    vuln = row[0]
    layer_name = row[1]

    # Count affected hosts and total occurrences (same as vulnerability_detail)
    host_count_q = select(func.count(func.distinct(LatestVuln.host_id))).where(
        LatestVuln.qid == qid
    )
    affected_host_count = (await db.execute(host_count_q)).scalar() or 0

    total_q = select(func.count(LatestVuln.id)).where(LatestVuln.qid == qid)
    total_occurrences = (await db.execute(total_q)).scalar() or 0

    return FullDetailResponse(
        ip=host.ip,
        dns=host.dns,
        os=host.os,
        qid=vuln.qid,
        title=vuln.title,
        severity=vuln.severity,
        type=vuln.type,
        category=vuln.category,
        vuln_status=vuln.vuln_status,
        port=vuln.port,
        protocol=vuln.protocol,
        fqdn=vuln.fqdn,
        ssl=vuln.ssl,
        first_detected=vuln.first_detected.isoformat() if vuln.first_detected else None,
        last_detected=vuln.last_detected.isoformat() if vuln.last_detected else None,
        times_detected=vuln.times_detected,
        date_last_fixed=vuln.date_last_fixed.isoformat() if vuln.date_last_fixed else None,
        cve_ids=vuln.cve_ids,
        vendor_reference=vuln.vendor_reference,
        bugtraq_id=vuln.bugtraq_id,
        cvss_base=vuln.cvss_base,
        cvss_temporal=vuln.cvss_temporal,
        cvss3_base=vuln.cvss3_base,
        cvss3_temporal=vuln.cvss3_temporal,
        threat=vuln.threat,
        impact=vuln.impact,
        solution=vuln.solution,
        results=vuln.results,
        pci_vuln=vuln.pci_vuln,
        ticket_state=vuln.ticket_state,
        tracking_method=vuln.tracking_method,
        layer_id=vuln.layer_id,
        layer_name=layer_name,
        affected_host_count=affected_host_count,
        total_occurrences=total_occurrences,
    )
