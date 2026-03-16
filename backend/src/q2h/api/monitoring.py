"""Monitoring API — system health, metrics, and proactive alerts."""

import os
import platform
import time

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_verified_user, require_admin
from q2h.db.engine import get_db
import q2h.db.engine as db_engine
from q2h.db.models import ImportJob, ScanReport, User

from fastapi import HTTPException

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

_start_time = time.time()


# --- Schemas ---

class ServiceStatus(BaseModel):
    name: str
    status: str  # ok / warning / error
    detail: str | None = None


class SystemMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: int
    memory_total_mb: int
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float


class DbPoolInfo(BaseModel):
    pool_size: int
    checked_out: int
    overflow: int
    checked_in: int


class ActivitySummary(BaseModel):
    total_reports: int
    total_users: int
    db_size_mb: float
    last_import_status: str | None
    purgeable_reports_count: int = 0


class AlertItem(BaseModel):
    level: str  # warning / error
    message: str


class MonitoringResponse(BaseModel):
    uptime_seconds: int
    platform: str
    python_version: str
    services: list[ServiceStatus]
    system: SystemMetrics
    db_pool: DbPoolInfo | None
    activity: ActivitySummary
    alerts: list[AlertItem]


# --- Thresholds ---

CPU_WARN = 80
CPU_ERROR = 95
MEM_WARN = 80
MEM_ERROR = 95
DISK_WARN = 80
DISK_ERROR = 95


@router.get("", response_model=MonitoringResponse)
async def get_monitoring(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_verified_user),
):
    uptime = int(time.time() - _start_time)
    alerts: list[AlertItem] = []

    # --- System metrics ---
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))

    system = SystemMetrics(
        cpu_percent=cpu,
        memory_percent=mem.percent,
        memory_used_mb=int(mem.used / 1024 / 1024),
        memory_total_mb=int(mem.total / 1024 / 1024),
        disk_percent=disk.percent,
        disk_used_gb=round(disk.used / 1024 / 1024 / 1024, 1),
        disk_total_gb=round(disk.total / 1024 / 1024 / 1024, 1),
    )

    # CPU alerts
    if cpu >= CPU_ERROR:
        alerts.append(AlertItem(level="error", message=f"CPU_CRITICAL:{cpu}%"))
    elif cpu >= CPU_WARN:
        alerts.append(AlertItem(level="warning", message=f"CPU_HIGH:{cpu}%"))

    # Memory alerts
    if mem.percent >= MEM_ERROR:
        alerts.append(AlertItem(level="error", message=f"MEMORY_CRITICAL:{mem.percent}%"))
    elif mem.percent >= MEM_WARN:
        alerts.append(AlertItem(level="warning", message=f"MEMORY_HIGH:{mem.percent}%"))

    # Disk alerts
    if disk.percent >= DISK_ERROR:
        alerts.append(AlertItem(level="error", message=f"DISK_CRITICAL:{disk.percent}%"))
    elif disk.percent >= DISK_WARN:
        alerts.append(AlertItem(level="warning", message=f"DISK_HIGH:{disk.percent}%"))

    # --- Service statuses ---
    services: list[ServiceStatus] = []

    # Database connectivity
    try:
        await db.execute(text("SELECT 1"))
        services.append(ServiceStatus(name="PostgreSQL", status="ok"))
    except Exception:
        services.append(ServiceStatus(name="PostgreSQL", status="error", detail="Connection failed"))
        alerts.append(AlertItem(level="error", message="DB_UNREACHABLE"))

    # App service
    services.append(ServiceStatus(name="API FastAPI", status="ok", detail=f"Uptime {uptime}s"))

    # --- DB pool info ---
    db_pool = None
    if db_engine.engine is not None:
        pool = db_engine.engine.pool
        db_pool = DbPoolInfo(
            pool_size=pool.size(),
            checked_out=pool.checkedout(),
            overflow=pool.overflow(),
            checked_in=pool.checkedin(),
        )

    # --- Activity summary ---
    total_reports = (await db.execute(select(func.count()).select_from(ScanReport))).scalar() or 0
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

    # Database size
    db_size_row = (await db.execute(text("SELECT pg_database_size(current_database())"))).scalar() or 0
    db_size_mb = round(db_size_row / 1024 / 1024, 1)

    last_import_q = (
        select(ImportJob.status)
        .order_by(ImportJob.id.desc())
        .limit(1)
    )
    last_import_status = (await db.execute(last_import_q)).scalar()

    # Purgeable reports count (admin-only)
    purgeable_count = 0
    if user.get("profile") == "admin":
        from q2h.services.retention import count_purgeable_reports
        retention_row = (await db.execute(
            text("SELECT value FROM app_settings WHERE key = 'retention_months'")
        )).scalar()
        retention_months = int(retention_row or "24")
        purgeable_count = await count_purgeable_reports(db, retention_months)

    activity = ActivitySummary(
        total_reports=total_reports,
        total_users=total_users,
        db_size_mb=db_size_mb,
        last_import_status=last_import_status,
        purgeable_reports_count=purgeable_count,
    )

    # Check for failed imports
    failed_q = select(func.count()).select_from(ImportJob).where(ImportJob.status == "error")
    failed_count = (await db.execute(failed_q)).scalar() or 0
    if failed_count > 0:
        alerts.append(AlertItem(
            level="warning",
            message=f"FAILED_IMPORTS:{failed_count}",
        ))

    return MonitoringResponse(
        uptime_seconds=uptime,
        platform=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        services=services,
        system=system,
        db_pool=db_pool,
        activity=activity,
        alerts=alerts,
    )


# ── Data purge ───────────────────────────────────────────────────

class PurgeResponse(BaseModel):
    reports_deleted: int
    vulns_deleted: int


class PurgePreviewItem(BaseModel):
    id: int
    report_date: str | None
    asset_group: str | None
    filename: str


@router.get("/purge/preview", response_model=list[PurgePreviewItem])
async def purge_preview(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """List reports that would be purged (for confirmation modal)."""
    from q2h.services.retention import get_purgeable_reports

    retention_row = (await db.execute(
        text("SELECT value FROM app_settings WHERE key = 'retention_months'")
    )).scalar()
    retention_months = int(retention_row or "24")
    return await get_purgeable_reports(db, retention_months)


@router.post("/purge", response_model=PurgeResponse)
async def purge_data(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Manually purge expired reports."""
    from q2h.api.imports import _import_state
    from q2h.services.retention import purge_expired_data

    # Concurrency guard
    if _import_state.running:
        raise HTTPException(409, "IMPORT_IN_PROGRESS")

    active_imports = (
        await db.execute(
            select(ImportJob.id).where(ImportJob.status == "processing")
        )
    ).first()
    if active_imports:
        raise HTTPException(409, "IMPORT_IN_PROGRESS")

    retention_row = (await db.execute(
        text("SELECT value FROM app_settings WHERE key = 'retention_months'")
    )).scalar()
    retention_months = int(retention_row or "24")

    reports_deleted, vulns_deleted = await purge_expired_data(
        db, retention_months, audit_username=admin.get("username", "admin")
    )
    return PurgeResponse(reports_deleted=reports_deleted, vulns_deleted=vulns_deleted)
