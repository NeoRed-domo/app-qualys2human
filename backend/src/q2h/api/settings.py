"""App settings API — freshness thresholds, announcement banner, app status, session config, trends widgets."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.engine import get_db
from q2h.db.models import AppSettings, ImportJob
from q2h.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


class FreshnessSettings(BaseModel):
    stale_days: int
    hide_days: int


class BannerSettings(BaseModel):
    message: str = ""
    color: str = "info"        # info | warning | alert | other
    visibility: str = "none"   # all | admin | none


@router.get("/freshness", response_model=FreshnessSettings)
async def get_freshness(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stale = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "freshness_stale_days")
    )
    hide = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "freshness_hide_days")
    )
    return FreshnessSettings(
        stale_days=int(stale.scalar() or "7"),
        hide_days=int(hide.scalar() or "30"),
    )


@router.put("/freshness", response_model=FreshnessSettings)
async def update_freshness(
    body: FreshnessSettings,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    for key, val in [("freshness_stale_days", body.stale_days), ("freshness_hide_days", body.hide_days)]:
        existing = (await db.execute(select(AppSettings).where(AppSettings.key == key))).scalar_one_or_none()
        if existing:
            existing.value = str(val)
        else:
            db.add(AppSettings(key=key, value=str(val)))
    await db.commit()
    return body


# ── Application status (busy / idle) ────────────────────────────────

class OperationInfo(BaseModel):
    type: str          # "import" | "reclassify"
    progress: int      # 0-100
    detail: str = ""


class AppStatusResponse(BaseModel):
    busy: bool
    operations: list[OperationInfo]


@router.get("/status", response_model=AppStatusResponse)
async def app_status(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return global busy state: active imports and/or reclassification."""
    from q2h.api.layers import _reclassify
    from q2h.api.imports import _import_state

    ops: list[OperationInfo] = []

    # Check for active imports (DB jobs with status 'processing')
    active_imports = (
        await db.execute(
            select(ImportJob.id, ImportJob.progress)
            .where(ImportJob.status == "processing")
        )
    ).all()
    if active_imports:
        for job_id, progress in active_imports:
            ops.append(OperationInfo(type="import", progress=progress or 0, detail=f"Job #{job_id}"))
    elif _import_state.running:
        # In-memory flag covers the gap before the ImportJob row is created
        ops.append(OperationInfo(type="import", progress=0, detail=_import_state.filename))

    # Check reclassify state (in-memory)
    if _reclassify.running:
        ops.append(OperationInfo(
            type="reclassify",
            progress=_reclassify.progress,
            detail=f"{_reclassify.classified} classified",
        ))

    return AppStatusResponse(busy=len(ops) > 0, operations=ops)


# ── Announcement banner ─────────────────────────────────────────────

_BANNER_KEYS = {
    "message": "banner_message",
    "color": "banner_color",
    "visibility": "banner_visibility",
}
_BANNER_DEFAULTS = {"message": "", "color": "info", "visibility": "none"}


@router.get("/banner", response_model=BannerSettings)
async def get_banner(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    vals: dict[str, str] = {}
    for field, key in _BANNER_KEYS.items():
        row = await db.execute(select(AppSettings.value).where(AppSettings.key == key))
        vals[field] = row.scalar() or _BANNER_DEFAULTS[field]
    return BannerSettings(**vals)


@router.put("/banner", response_model=BannerSettings)
async def update_banner(
    body: BannerSettings,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    data = {"message": body.message, "color": body.color, "visibility": body.visibility}
    for field, key in _BANNER_KEYS.items():
        existing = (await db.execute(select(AppSettings).where(AppSettings.key == key))).scalar_one_or_none()
        if existing:
            existing.value = data[field]
        else:
            db.add(AppSettings(key=key, value=data[field]))
    await db.commit()
    return body


# ── Session timeout settings ──────────────────────────────────────

class SessionSettingsResponse(BaseModel):
    timeout_minutes: int
    warning_minutes: int


class SessionSettingsUpdate(BaseModel):
    timeout_minutes: int
    warning_minutes: int


@router.get("/session", response_model=SessionSettingsResponse)
async def get_session_settings(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    timeout = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "session_timeout_minutes")
    )
    warning = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "session_warning_minutes")
    )
    return SessionSettingsResponse(
        timeout_minutes=int(timeout.scalar() or "120"),
        warning_minutes=int(warning.scalar() or "5"),
    )


@router.put("/session", response_model=SessionSettingsResponse)
async def update_session_settings(
    body: SessionSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    if body.timeout_minutes < 5:
        raise HTTPException(400, "INVALID_TIMEOUT_VALUE")
    if body.warning_minutes < 1:
        raise HTTPException(400, "INVALID_WARNING_VALUE")
    if body.warning_minutes >= body.timeout_minutes:
        raise HTTPException(400, "WARNING_EXCEEDS_TIMEOUT")

    for key, val in [
        ("session_timeout_minutes", body.timeout_minutes),
        ("session_warning_minutes", body.warning_minutes),
    ]:
        existing = (await db.execute(select(AppSettings).where(AppSettings.key == key))).scalar_one_or_none()
        if existing:
            existing.value = str(val)
        else:
            db.add(AppSettings(key=key, value=str(val)))
    await db.commit()
    return SessionSettingsResponse(
        timeout_minutes=body.timeout_minutes,
        warning_minutes=body.warning_minutes,
    )


# ── Data retention settings ──────────────────────────────────────

class RetentionSettingsResponse(BaseModel):
    retention_months: int


class RetentionSettingsUpdate(BaseModel):
    retention_months: int


@router.get("/retention", response_model=RetentionSettingsResponse)
async def get_retention_settings(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    row = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "retention_months")
    )
    return RetentionSettingsResponse(retention_months=int(row.scalar() or "24"))


@router.put("/retention", response_model=RetentionSettingsResponse)
async def update_retention_settings(
    body: RetentionSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    if body.retention_months < 6 or body.retention_months > 120:
        raise HTTPException(400, "INVALID_RETENTION_VALUE")

    existing = (
        await db.execute(select(AppSettings).where(AppSettings.key == "retention_months"))
    ).scalar_one_or_none()
    if existing:
        existing.value = str(body.retention_months)
    else:
        db.add(AppSettings(key="retention_months", value=str(body.retention_months)))
    await db.commit()
    return RetentionSettingsResponse(retention_months=body.retention_months)


# ── Trends widget visibility (admin controls) ────────────────────

_TRENDS_WIDGETS_KEY = "trends_hidden_widgets"


class TrendsWidgetsResponse(BaseModel):
    hidden_widgets: list[str]


class TrendsWidgetsUpdate(BaseModel):
    hidden_widgets: list[str]


@router.get("/trends-widgets", response_model=TrendsWidgetsResponse)
async def get_trends_widgets(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get list of widget keys hidden from regular users."""
    row = await db.execute(
        select(AppSettings.value).where(AppSettings.key == _TRENDS_WIDGETS_KEY)
    )
    val = row.scalar()
    return TrendsWidgetsResponse(hidden_widgets=json.loads(val) if val else [])


@router.put("/trends-widgets", response_model=TrendsWidgetsResponse)
async def update_trends_widgets(
    body: TrendsWidgetsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Set which widgets are hidden from regular users (admin only)."""
    val = json.dumps(body.hidden_widgets)
    existing = (
        await db.execute(select(AppSettings).where(AppSettings.key == _TRENDS_WIDGETS_KEY))
    ).scalar_one_or_none()
    if existing:
        existing.value = val
    else:
        db.add(AppSettings(key=_TRENDS_WIDGETS_KEY, value=val))
    await db.commit()
    return body
