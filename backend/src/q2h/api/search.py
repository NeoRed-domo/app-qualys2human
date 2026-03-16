import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import require_data_access
from q2h.db.engine import get_db
from q2h.db.models import LatestVuln, Host, VulnLayer
from q2h.api._filters import escape_like

logger = logging.getLogger("q2h")

router = APIRouter(prefix="/api/search", tags=["search"])


class VulnSearchItem(BaseModel):
    qid: int
    title: str
    severity: int
    type: Optional[str] = None
    category: Optional[str] = None
    host_count: int
    layer_name: Optional[str] = None
    layer_color: Optional[str] = None


class HostSearchItem(BaseModel):
    ip: str
    dns: Optional[str] = None
    os: Optional[str] = None
    vuln_count: int


class SearchResponse(BaseModel):
    type: str
    items: list


@router.get("", response_model=SearchResponse)
async def search(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    q: str = Query(..., min_length=1, description="Search term"),
    type: str = Query(..., pattern="^(vuln|host)$", description="Search type: vuln or host"),
):
    try:
        return await _do_search(db, q, type)
    except Exception:
        logger.exception("Search failed (q=%s, type=%s)", q, type)
        raise HTTPException(status_code=500, detail="Search query failed")


async def _do_search(db, q, type):
    MAX_RESULTS = 200

    if type == "vuln":
        stmt = (
            select(
                LatestVuln.qid,
                func.min(LatestVuln.title).label("title"),
                func.min(LatestVuln.severity).label("severity"),
                func.min(LatestVuln.type).label("type"),
                func.min(LatestVuln.category).label("category"),
                func.count(func.distinct(LatestVuln.host_id)).label("host_count"),
                func.min(VulnLayer.name).label("layer_name"),
                func.min(VulnLayer.color).label("layer_color"),
            )
            .outerjoin(VulnLayer, LatestVuln.layer_id == VulnLayer.id)
            .group_by(LatestVuln.qid)
        )

        if q.strip().isdigit():
            stmt = stmt.having(LatestVuln.qid == int(q.strip()))
        else:
            stmt = stmt.where(LatestVuln.title.ilike(f"%{escape_like(q)}%"))

        stmt = stmt.order_by(func.count(LatestVuln.id).desc()).limit(MAX_RESULTS)
        rows = (await db.execute(stmt)).all()

        items = [
            VulnSearchItem(
                qid=r.qid, title=r.title, severity=r.severity,
                type=r.type, category=r.category,
                host_count=r.host_count,
                layer_name=r.layer_name, layer_color=r.layer_color,
            ).model_dump()
            for r in rows
        ]
        return SearchResponse(type="vuln", items=items)

    else:
        stmt = (
            select(
                Host.ip,
                Host.dns,
                Host.os,
                func.count(LatestVuln.id).label("vuln_count"),
            )
            .join(LatestVuln, LatestVuln.host_id == Host.id)
            .where(
                or_(
                    Host.ip.ilike(f"%{escape_like(q)}%"),
                    Host.dns.ilike(f"%{escape_like(q)}%"),
                    Host.netbios.ilike(f"%{escape_like(q)}%"),
                )
            )
            .group_by(Host.id, Host.ip, Host.dns, Host.os)
            .order_by(func.count(LatestVuln.id).desc())
            .limit(MAX_RESULTS)
        )
        rows = (await db.execute(stmt)).all()

        items = [
            HostSearchItem(
                ip=r.ip, dns=r.dns, os=r.os, vuln_count=r.vuln_count,
            ).model_dump()
            for r in rows
        ]
        return SearchResponse(type="host", items=items)
