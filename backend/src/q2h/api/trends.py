import logging
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, text, cast, Date, Float, or_, String
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_admin, require_data_access
from q2h.db.engine import get_db
from q2h.db.models import TrendConfig, TrendTemplate, TrendSnapshot, Vulnerability, ScanReport, Host, AppSettings
from q2h.api._filters import get_freshness_thresholds, apply_freshness, os_class_filter_conditions

logger = logging.getLogger("q2h")

router = APIRouter(prefix="/api/trends", tags=["trends"])


# --- Schemas ---

class TrendConfigResponse(BaseModel):
    max_window_days: int
    query_timeout_seconds: int


class TrendConfigUpdate(BaseModel):
    max_window_days: int
    query_timeout_seconds: int


class TrendTemplateResponse(BaseModel):
    id: int
    name: str
    metric: str
    group_by: Optional[str] = None
    filters: dict


class TrendTemplateCreate(BaseModel):
    name: str
    metric: str
    group_by: Optional[str] = None
    filters: dict = {}


class TrendQueryRequest(BaseModel):
    metrics: list[str] = []           # batch: ["avg_vulns_per_host", "host_count"]
    metric: Optional[str] = None      # backward compat: single metric
    group_by: Optional[str] = None    # severity, category, type, layer (forces live query)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    severities: Optional[list[int]] = None
    types: Optional[list[str]] = None
    layers: Optional[list[int]] = None
    os_classes: Optional[list[str]] = None
    freshness: Literal["all", "active", "stale"] = "all"
    granularity: Literal["day", "week", "month"] = "week"


class TrendDataPoint(BaseModel):
    date: str
    value: float
    group: Optional[str] = None


class TrendQueryResponse(BaseModel):
    results: dict[str, list[TrendDataPoint]]


# --- Helpers ---



def _apply_trend_filters(stmt, body: TrendQueryRequest):
    """Apply severities, types, layers, os_classes filters to a Vulnerability-based query.

    Returns (stmt, host_joined) tuple.
    """
    host_joined = False

    if body.severities:
        stmt = stmt.where(Vulnerability.severity.in_(body.severities))
    if body.types:
        stmt = stmt.where(Vulnerability.type.in_(body.types))
    if body.layers:
        # 0 = "Autre" (unclassified, layer_id IS NULL)
        if 0 in body.layers:
            real_ids = [lid for lid in body.layers if lid != 0]
            if real_ids:
                stmt = stmt.where(or_(Vulnerability.layer_id.in_(real_ids), Vulnerability.layer_id.is_(None)))
            else:
                stmt = stmt.where(Vulnerability.layer_id.is_(None))
        else:
            stmt = stmt.where(Vulnerability.layer_id.in_(body.layers))
    if body.os_classes:
        cls_list = [c.lower() for c in body.os_classes]
        conditions = os_class_filter_conditions(Host.os, cls_list)
        if conditions:
            stmt = stmt.join(Host, Vulnerability.host_id == Host.id, isouter=False)
            host_joined = True
            stmt = stmt.where(or_(*conditions))

    return stmt, host_joined




# --- Config ---

@router.get("/config", response_model=TrendConfigResponse)
async def get_trend_config(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    result = await db.execute(select(TrendConfig).limit(1))
    cfg = result.scalar_one_or_none()
    if not cfg:
        return TrendConfigResponse(max_window_days=365, query_timeout_seconds=30)
    return TrendConfigResponse(
        max_window_days=cfg.max_window_days,
        query_timeout_seconds=cfg.query_timeout_seconds,
    )


@router.get("/default-granularity")
async def get_default_granularity(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    """Return the enterprise default granularity for trends charts."""
    result = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "trend_granularity")
    )
    val = result.scalar() or "week"
    return {"granularity": val}


@router.put("/config", response_model=TrendConfigResponse)
async def update_trend_config(
    body: TrendConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(select(TrendConfig).limit(1))
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.max_window_days = body.max_window_days
        cfg.query_timeout_seconds = body.query_timeout_seconds
    else:
        cfg = TrendConfig(
            max_window_days=body.max_window_days,
            query_timeout_seconds=body.query_timeout_seconds,
        )
        db.add(cfg)
    await db.commit()
    return TrendConfigResponse(
        max_window_days=cfg.max_window_days,
        query_timeout_seconds=cfg.query_timeout_seconds,
    )


# --- Templates ---

@router.get("/templates", response_model=list[TrendTemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    result = await db.execute(select(TrendTemplate))
    templates = result.scalars().all()
    return [
        TrendTemplateResponse(
            id=t.id, name=t.name, metric=t.metric,
            group_by=t.group_by, filters=t.filters or {},
        )
        for t in templates
    ]


@router.post("/templates", response_model=TrendTemplateResponse, status_code=201)
async def create_template(
    body: TrendTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    tmpl = TrendTemplate(
        name=body.name,
        metric=body.metric,
        group_by=body.group_by,
        filters=body.filters,
        created_by=int(user["sub"]),
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return TrendTemplateResponse(
        id=tmpl.id, name=tmpl.name, metric=tmpl.metric,
        group_by=tmpl.group_by, filters=tmpl.filters or {},
    )


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    result = await db.execute(select(TrendTemplate).where(TrendTemplate.id == template_id))
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    await db.delete(tmpl)
    await db.commit()


# --- Query ---

VALID_METRICS = {
    "total_vulns", "critical_count", "host_count", "avg_vulns_per_host",
    "avg_remediation_days", "remediation_rate", "avg_open_age_days",
}


def _has_filters(body: TrendQueryRequest) -> bool:
    """Check if any global filter is active (forces live query path)."""
    return bool(
        body.severities or body.types or body.layers or body.os_classes
        or body.freshness != "all"
    )


async def _read_from_snapshots(
    db: AsyncSession, metrics: list[str], body: TrendQueryRequest,
) -> dict[str, list[TrendDataPoint]]:
    """Read pre-aggregated data from trend_snapshots table (fast path)."""
    results: dict[str, list[TrendDataPoint]] = {}
    for metric in metrics:
        q = (
            select(TrendSnapshot.period, TrendSnapshot.value)
            .where(
                TrendSnapshot.granularity == body.granularity,
                TrendSnapshot.metric == metric,
                TrendSnapshot.dimension == "total",
                TrendSnapshot.dimension_value == "__all__",
            )
            .order_by(TrendSnapshot.period)
        )
        if body.date_from:
            q = q.where(TrendSnapshot.period >= body.date_from)
        if body.date_to:
            q = q.where(TrendSnapshot.period < body.date_to + timedelta(days=1))
        rows = (await db.execute(q)).all()
        results[metric] = [
            TrendDataPoint(date=str(row.period), value=float(row.value))
            for row in rows if row.value is not None
        ]
    return results


async def _live_query_metric(
    db: AsyncSession, metric: str, body: TrendQueryRequest,
) -> list[TrendDataPoint]:
    """Execute a live query on the vulnerabilities table for one metric (slow path)."""
    effective_date = func.coalesce(ScanReport.report_date, ScanReport.imported_at)
    date_col = func.date_trunc(body.granularity, effective_date).cast(Date).label("period")

    if metric == "avg_vulns_per_host":
        value_expr = (
            cast(func.count(Vulnerability.id), Float)
            / func.nullif(func.count(func.distinct(Vulnerability.host_id)), 0)
        )
    elif metric == "total_vulns":
        value_expr = func.count(Vulnerability.id)
    elif metric == "critical_count":
        value_expr = func.count(Vulnerability.id).filter(Vulnerability.severity >= 4)
    elif metric == "host_count":
        value_expr = func.count(func.distinct(Vulnerability.host_id))
    elif metric == "avg_remediation_days":
        value_expr = func.avg(
            func.extract('epoch', Vulnerability.date_last_fixed - Vulnerability.first_detected) / 86400
        )
    elif metric == "remediation_rate":
        value_expr = (
            func.count(Vulnerability.id).filter(Vulnerability.vuln_status == 'Fixed') * 100.0
            / func.nullif(
                func.count(Vulnerability.id).filter(Vulnerability.vuln_status.isnot(None)), 0
            )
        )
    elif metric == "avg_open_age_days":
        # effective_date defined at top of function
        value_expr = func.avg(
            func.greatest(
                0,
                func.extract('epoch', effective_date - Vulnerability.first_detected) / 86400,
            )
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}")

    # Handle group_by (backward compat)
    group_col = None
    if body.group_by == "severity":
        group_col = cast(Vulnerability.severity, String).label("grp")
    elif body.group_by == "category":
        group_col = Vulnerability.category.label("grp")
    elif body.group_by == "type":
        group_col = Vulnerability.type.label("grp")
    elif body.group_by == "layer":
        group_col = func.coalesce(cast(Vulnerability.layer_id, String), "unclassified").label("grp")

    cols = [date_col, value_expr.label("value")]
    group_by_cols = [date_col]
    if group_col is not None:
        cols.insert(1, group_col)
        group_by_cols.append(group_col)

    q = (
        select(*cols)
        .select_from(Vulnerability)
        .join(ScanReport, Vulnerability.scan_report_id == ScanReport.id)
        .group_by(*group_by_cols)
        .order_by(date_col)
    )

    if body.date_from:
        q = q.where(effective_date >= body.date_from)
    if body.date_to:
        q = q.where(effective_date < body.date_to + timedelta(days=1))

    q, _ = _apply_trend_filters(q, body)

    # Metric-specific filters
    if metric == "avg_remediation_days":
        q = q.where(
            Vulnerability.vuln_status == 'Fixed',
            Vulnerability.date_last_fixed.isnot(None),
            Vulnerability.first_detected.isnot(None),
        )
    elif metric == "avg_open_age_days":
        q = q.where(
            Vulnerability.vuln_status.is_distinct_from('Fixed'),
            Vulnerability.first_detected.isnot(None),
        )

    thresholds = await get_freshness_thresholds(db)
    q = apply_freshness(q, Vulnerability.last_detected, body.freshness, thresholds)

    rows = (await db.execute(q)).all()
    return [
        TrendDataPoint(
            date=str(row.period),
            value=float(row.value),
            group=str(row[1]) if group_col is not None else None,
        )
        for row in rows if row.value is not None
    ]


@router.post("/query", response_model=TrendQueryResponse)
async def execute_trend_query(
    body: TrendQueryRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
):
    try:
        return await _execute_trend_query(body, db)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Trend query failed (metrics=%s)", body.metrics or body.metric)
        raise HTTPException(status_code=500, detail="Trend query failed")


async def _execute_trend_query(body: TrendQueryRequest, db: AsyncSession):
    # Resolve metrics list (backward compat: singular metric → list)
    metrics = body.metrics if body.metrics else ([body.metric] if body.metric else [])
    if not metrics:
        raise HTTPException(status_code=400, detail="No metrics specified")
    for m in metrics:
        if m not in VALID_METRICS:
            raise HTTPException(status_code=400, detail=f"Unknown metric: {m}")

    # Set statement timeout
    cfg_result = await db.execute(select(TrendConfig).limit(1))
    cfg = cfg_result.scalar_one_or_none()
    timeout_sec = max(1, min(300, int(cfg.query_timeout_seconds) if cfg else 30))
    # SET does not support bind parameters — int() cast + clamp ensures safety
    await db.execute(text(f"SET LOCAL statement_timeout = '{timeout_sec}s'"))

    # Fast path: no filters and no group_by → read from pre-aggregated snapshots
    if not _has_filters(body) and not body.group_by:
        return TrendQueryResponse(
            results=await _read_from_snapshots(db, metrics, body)
        )

    # Slow path: filters active or group_by → live query on vulnerabilities table
    results: dict[str, list[TrendDataPoint]] = {}
    for metric in metrics:
        results[metric] = await _live_query_metric(db, metric, body)
    return TrendQueryResponse(results=results)
