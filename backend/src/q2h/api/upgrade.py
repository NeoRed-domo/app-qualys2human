# backend/src/q2h/api/upgrade.py
"""Upgrade management API -- upload, validate, schedule, history, settings."""

import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.engine import get_db
from q2h.db.models import AppSettings, AuditLog, UpgradeSchedule, UpgradeHistory, User
from q2h.auth.dependencies import get_current_user, require_admin
from q2h.upgrade import APP_VERSION

logger = logging.getLogger("q2h.upgrade")

router = APIRouter(prefix="/api/upgrade", tags=["upgrade"])


# -- Pydantic models --

class UploadStatusResponse(BaseModel):
    upload_id: str
    total_chunks: int
    received_chunks: list[int]
    complete: bool
    filename: str


class ValidationResult(BaseModel):
    valid: bool
    target_version: str | None = None
    current_version: str
    signature_ok: bool
    version_ok: bool
    error: str | None = None


class ScheduleRequest(BaseModel):
    scheduled_at: str  # ISO 8601 UTC datetime
    notification_thresholds: list[dict] | None = None


class ScheduleResponse(BaseModel):
    id: int
    source_version: str
    target_version: str
    scheduled_at: str
    notification_thresholds: list[dict]
    status: str
    created_at: str
    scheduled_by_username: str | None = None


class HistoryEntry(BaseModel):
    id: int
    source_version: str
    target_version: str
    scheduled_at: str | None
    started_at: str
    completed_at: str | None
    duration_seconds: int | None
    status: str
    error_message: str | None
    initiated_by_username: str | None


class NotificationSettingsResponse(BaseModel):
    default_thresholds: list[dict]


def _persist_package(tmp_zip_path: str) -> str:
    """Copy package from temp upload dir to a stable location.

    Prevents the scheduler from failing because the temp dir was cleaned up.
    Returns the stable path.
    """
    src = Path(tmp_zip_path)
    if not src.exists():
        raise HTTPException(400, "PACKAGE_NOT_FOUND")

    config_path_env = os.environ.get("Q2H_CONFIG")
    if config_path_env:
        install_dir = Path(config_path_env).parent
    else:
        install_dir = Path(__file__).parent.parent.parent.parent

    stable_dir = install_dir / "upgrades"
    stable_dir.mkdir(parents=True, exist_ok=True)
    dest = stable_dir / src.name

    # Skip if already in the stable location
    if src.resolve() == dest.resolve():
        return str(dest)

    shutil.copy2(str(src), str(dest))

    # Also copy .sig if present
    sig_src = src.with_suffix(src.suffix + ".sig")
    if sig_src.exists():
        shutil.copy2(str(sig_src), str(dest.with_suffix(dest.suffix + ".sig")))

    logger.info("Persisted package to %s", dest)
    return str(dest)


# -- Upload endpoints --

@router.post("/upload")
async def upload_chunk(
    request: Request,
    file: UploadFile,
    x_upload_id: str = Header(...),
    x_chunk_index: int = Header(...),
    x_chunk_total: int = Header(...),
    x_checksum: str = Header(...),
    x_filename: str = Header("package.zip"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Receive a single chunk of the upgrade package."""
    from q2h.upgrade.chunked_upload import (
        start_upload, receive_chunk, get_upload_status,
        check_disk_space,
    )

    # Validate upload_id (must be UUID format — prevent directory traversal)
    if not re.match(r'^[a-f0-9\-]{36}$', x_upload_id):
        raise HTTPException(400, "INVALID_UPLOAD_ID")

    # Sanitize filename (prevent path traversal — same fix as CSV upload)
    safe_filename = os.path.basename(x_filename)
    if not safe_filename.endswith(".zip"):
        safe_filename = "package.zip"

    # Pre-flight: reject if upgrade is running
    active = (await db.execute(
        select(UpgradeSchedule).where(UpgradeSchedule.status.in_(["running"]))
    )).scalar_one_or_none()
    if active:
        raise HTTPException(409, "UPGRADE_IN_PROGRESS")

    # First chunk: start upload
    if x_chunk_index == 0:
        chunk_data = await file.read()
        estimated_size = len(chunk_data) * x_chunk_total
        ok, required, available = check_disk_space(estimated_size)
        if not ok:
            raise HTTPException(
                507,
                f"INSUFFICIENT_DISK_SPACE: need {required // (1024*1024)} MB, "
                f"available {available // (1024*1024)} MB",
            )
        start_upload(x_upload_id, x_chunk_total, safe_filename)
        try:
            receive_chunk(x_upload_id, x_chunk_index, chunk_data, x_checksum)
        except ValueError as e:
            raise HTTPException(400, str(e))

        db.add(AuditLog(
            user_id=int(admin["sub"]),
            action="upgrade_upload",
            detail=f"Upload started: {safe_filename} ({x_chunk_total} chunks)",
            ip_address=request.client.host if request.client else None,
        ))
        await db.commit()
    else:
        chunk_data = await file.read()
        try:
            receive_chunk(x_upload_id, x_chunk_index, chunk_data, x_checksum)
        except ValueError as e:
            raise HTTPException(400, str(e))

    status = get_upload_status(x_upload_id)
    return status


@router.post("/upload-sig/{upload_id}")
async def upload_signature(
    upload_id: str,
    file: UploadFile,
    admin: dict = Depends(require_admin),
):
    """Upload the detached .sig file for a package."""
    from q2h.upgrade.chunked_upload import get_active_upload_dir

    upload_dir = get_active_upload_dir()
    if upload_dir is None or upload_dir.name != upload_id:
        raise HTTPException(410, "UPLOAD_EXPIRED_OR_NOT_FOUND")

    sig_data = await file.read()
    if len(sig_data) != 64:
        raise HTTPException(400, "INVALID_SIGNATURE_SIZE")

    # Find the assembled zip or save next to future assembled zip
    zip_files = list(upload_dir.glob("*.zip"))
    if zip_files:
        sig_path = zip_files[0].with_suffix(zip_files[0].suffix + ".sig")
    else:
        sig_path = upload_dir / "package.zip.sig"

    sig_path.write_bytes(sig_data)
    return {"status": "ok"}


@router.get("/upload/{upload_id}/status", response_model=UploadStatusResponse)
async def upload_status(
    upload_id: str,
    admin: dict = Depends(require_admin),
):
    """Get status of a chunked upload."""
    from q2h.upgrade.chunked_upload import get_upload_status

    status = get_upload_status(upload_id)
    if status is None:
        raise HTTPException(410, "UPLOAD_EXPIRED_OR_NOT_FOUND")
    return status


@router.delete("/upload/{upload_id}")
async def cancel_upload_endpoint(
    upload_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Cancel and delete an in-progress upload."""
    from q2h.upgrade.chunked_upload import cancel_upload

    cancel_upload(upload_id)

    db.add(AuditLog(
        user_id=int(admin["sub"]),
        action="upgrade_upload_cancel",
        detail=f"Upload cancelled: {upload_id}",
        ip_address=request.client.host if request.client else None,
    ))
    await db.commit()

    return {"status": "cancelled"}


# -- Validation endpoint --

@router.post("/validate/{upload_id}", response_model=ValidationResult)
async def validate_package(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Assemble chunks, verify signature and version."""
    from q2h.upgrade.chunked_upload import assemble_chunks, get_upload_status, cancel_upload
    from q2h.upgrade.signature import verify_signature
    from q2h.upgrade.version import is_newer

    status = get_upload_status(upload_id)
    if status is None:
        raise HTTPException(410, "UPLOAD_EXPIRED_OR_NOT_FOUND")
    if not status["complete"]:
        raise HTTPException(400, "UPLOAD_INCOMPLETE")

    try:
        zip_path = assemble_chunks(upload_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Step 1: Check zip integrity
    if not zipfile.is_zipfile(zip_path):
        cancel_upload(upload_id)
        return ValidationResult(
            valid=False, current_version=APP_VERSION,
            signature_ok=False, version_ok=False,
            error="INVALID_ZIP_FILE",
        )

    # Step 2: Verify Ed25519 signature
    sig_path = zip_path.with_suffix(zip_path.suffix + ".sig")
    if not sig_path.exists():
        # Also check upload dir root for pre-uploaded sig
        upload_dir = zip_path.parent
        alt_sig = upload_dir / "package.zip.sig"
        if alt_sig.exists():
            sig_path = alt_sig
        else:
            cancel_upload(upload_id)
            return ValidationResult(
                valid=False, current_version=APP_VERSION,
                signature_ok=False, version_ok=False,
                error="SIGNATURE_FILE_MISSING",
            )

    signature_ok = verify_signature(zip_path, sig_path)
    if not signature_ok:
        cancel_upload(upload_id)
        return ValidationResult(
            valid=False, current_version=APP_VERSION,
            signature_ok=False, version_ok=False,
            error="INVALID_SIGNATURE",
        )

    # Step 3: Extract VERSION file and check
    target_version = None
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            version_files = [n for n in zf.namelist() if n.endswith("/VERSION")]
            if not version_files:
                cancel_upload(upload_id)
                return ValidationResult(
                    valid=False, current_version=APP_VERSION,
                    signature_ok=True, version_ok=False,
                    error="VERSION_FILE_MISSING",
                )
            target_version = zf.read(version_files[0]).decode().strip()
    except Exception as e:
        cancel_upload(upload_id)
        return ValidationResult(
            valid=False, current_version=APP_VERSION,
            signature_ok=True, version_ok=False,
            error=f"VERSION_READ_ERROR: {e}",
        )

    version_ok = is_newer(target_version, APP_VERSION)
    if not version_ok:
        cancel_upload(upload_id)
        return ValidationResult(
            valid=False, current_version=APP_VERSION,
            target_version=target_version,
            signature_ok=True, version_ok=False,
            error="VERSION_NOT_NEWER",
        )

    db.add(AuditLog(
        user_id=int(admin["sub"]),
        action="upgrade_validate",
        detail=f"Package validated: {target_version} (sig=OK, version=OK)",
    ))
    await db.commit()

    return ValidationResult(
        valid=True,
        current_version=APP_VERSION,
        target_version=target_version,
        signature_ok=True,
        version_ok=True,
    )


# -- Schedule endpoints --

@router.post("/schedule", response_model=ScheduleResponse)
async def schedule_upgrade(
    body: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Schedule an upgrade at a specific time."""
    from q2h.upgrade.chunked_upload import get_active_upload_dir

    upload_dir = get_active_upload_dir()
    if not upload_dir:
        raise HTTPException(400, "NO_PACKAGE_UPLOADED")

    zip_files = list(upload_dir.glob("*.zip"))
    if not zip_files:
        raise HTTPException(400, "PACKAGE_NOT_VALIDATED")
    package_path = _persist_package(str(zip_files[0]))

    # Parse scheduled time
    try:
        scheduled_at = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        scheduled_at = scheduled_at.replace(tzinfo=None)
    except ValueError:
        raise HTTPException(400, "INVALID_DATETIME_FORMAT")

    # Must be at least 15 minutes in the future (per spec)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    min_time = now + timedelta(minutes=15)
    if scheduled_at < min_time:
        raise HTTPException(400, "SCHEDULED_TIME_TOO_SOON")

    # Extract target version
    with zipfile.ZipFile(zip_files[0], "r") as zf:
        version_files = [n for n in zf.namelist() if n.endswith("/VERSION")]
        target_version = zf.read(version_files[0]).decode().strip()

    # Check for existing active schedule
    existing = (await db.execute(
        select(UpgradeSchedule).where(UpgradeSchedule.status.in_(["pending", "running"]))
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "UPGRADE_ALREADY_SCHEDULED")

    thresholds = body.notification_thresholds or [
        {"minutes_before": 2880, "level": "info"},
        {"minutes_before": 120, "level": "warning"},
        {"minutes_before": 15, "level": "danger"},
    ]

    # Validate thresholds format (same rules as PUT /settings)
    for t in thresholds:
        if "minutes_before" not in t or "level" not in t:
            raise HTTPException(400, "INVALID_THRESHOLD_FORMAT")
        if t["level"] not in ("info", "warning", "danger"):
            raise HTTPException(400, "INVALID_THRESHOLD_LEVEL")
        if not isinstance(t["minutes_before"], int) or t["minutes_before"] < 1:
            raise HTTPException(400, "INVALID_THRESHOLD_MINUTES")

    schedule = UpgradeSchedule(
        package_path=package_path,
        source_version=APP_VERSION,
        target_version=target_version,
        scheduled_at=scheduled_at,
        notification_thresholds=thresholds,
        status="pending",
        scheduled_by=int(admin["sub"]),
        created_at=now,
    )
    db.add(schedule)

    db.add(AuditLog(
        user_id=int(admin["sub"]),
        action="upgrade_schedule",
        detail=f"Upgrade {APP_VERSION} -> {target_version} scheduled for {scheduled_at.isoformat()}",
    ))

    await db.commit()
    await db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        source_version=schedule.source_version,
        target_version=schedule.target_version,
        scheduled_at=schedule.scheduled_at.isoformat() + "Z",
        notification_thresholds=schedule.notification_thresholds,
        status=schedule.status,
        created_at=schedule.created_at.isoformat() + "Z",
        scheduled_by_username=admin.get("username"),
    )


@router.delete("/schedule")
async def cancel_schedule(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Cancel a pending scheduled upgrade."""
    schedule = (await db.execute(
        select(UpgradeSchedule).where(UpgradeSchedule.status == "pending")
    )).scalar_one_or_none()

    if not schedule:
        raise HTTPException(404, "NO_PENDING_UPGRADE")

    schedule.status = "cancelled"
    schedule.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.add(AuditLog(
        user_id=int(admin["sub"]),
        action="upgrade_cancel",
        detail=f"Cancelled upgrade to {schedule.target_version}",
    ))

    await db.commit()
    return {"status": "cancelled"}


@router.post("/launch-now")
async def launch_now(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Launch upgrade immediately (in 60 seconds)."""
    from q2h.upgrade.chunked_upload import get_active_upload_dir

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    scheduled_at = now + timedelta(seconds=60)

    # Cancel any existing pending schedule (and reuse its package_path as fallback)
    existing = (await db.execute(
        select(UpgradeSchedule).where(UpgradeSchedule.status == "pending")
    )).scalar_one_or_none()

    package_path: str | None = None

    # Try in-memory upload first
    upload_dir = get_active_upload_dir()
    if upload_dir:
        zip_files = list(upload_dir.glob("*.zip"))
        if zip_files:
            package_path = str(zip_files[0])

    # Fallback: reuse package from existing pending schedule
    if not package_path and existing:
        existing_path = Path(existing.package_path)
        if existing_path.exists():
            package_path = existing.package_path

    if not package_path:
        raise HTTPException(400, "NO_PACKAGE_UPLOADED")

    # Copy to stable location so temp cleanup can't break the schedule
    package_path = _persist_package(package_path)

    with zipfile.ZipFile(package_path, "r") as zf:
        version_files = [n for n in zf.namelist() if n.endswith("/VERSION")]
        target_version = zf.read(version_files[0]).decode().strip()

    if existing:
        existing.status = "cancelled"
        existing.completed_at = now

    schedule = UpgradeSchedule(
        package_path=package_path,
        source_version=APP_VERSION,
        target_version=target_version,
        scheduled_at=scheduled_at,
        notification_thresholds=[{"minutes_before": 1, "level": "danger"}],
        status="pending",
        scheduled_by=int(admin["sub"]),
        created_at=now,
    )
    db.add(schedule)

    db.add(AuditLog(
        user_id=int(admin["sub"]),
        action="upgrade_schedule",
        detail=f"Immediate upgrade {APP_VERSION} -> {target_version} (in 60s)",
    ))

    await db.commit()
    await db.refresh(schedule)

    return {
        "status": "scheduled",
        "scheduled_at": scheduled_at.isoformat() + "Z",
        "target_version": target_version,
    }


@router.get("/schedule")
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get active upgrade schedule (for banner display). Accessible to all authenticated users."""
    schedule = (await db.execute(
        select(UpgradeSchedule).where(UpgradeSchedule.status.in_(["pending", "running"]))
    )).scalar_one_or_none()

    if not schedule:
        # Check for recent failure (last 1h) — but only if no more recent success
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        most_recent = (await db.execute(
            select(UpgradeSchedule)
            .where(UpgradeSchedule.status.in_(["failed", "completed"]))
            .where(UpgradeSchedule.completed_at >= now_utc - timedelta(hours=1))
            .order_by(UpgradeSchedule.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if most_recent and most_recent.status == "failed":
            return {
                "scheduled": False,
                "recent_failure": {
                    "target_version": most_recent.target_version,
                    "error": most_recent.error_message,
                    "failed_at": most_recent.completed_at.isoformat() + "Z",
                },
            }
        return {"scheduled": False}

    return {
        "scheduled": True,
        "id": schedule.id,
        "target_version": schedule.target_version,
        "scheduled_at": schedule.scheduled_at.isoformat() + "Z",
        "notification_thresholds": schedule.notification_thresholds,
        "status": schedule.status,
    }


# -- History endpoint --

@router.get("/history", response_model=list[HistoryEntry])
async def get_history(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Get upgrade history (most recent first)."""
    rows = (await db.execute(
        select(UpgradeHistory, User.username)
        .outerjoin(User, UpgradeHistory.initiated_by == User.id)
        .order_by(UpgradeHistory.started_at.desc())
        .limit(50)
    )).all()

    return [
        HistoryEntry(
            id=h.id,
            source_version=h.source_version,
            target_version=h.target_version,
            scheduled_at=(h.scheduled_at.isoformat() + "Z") if h.scheduled_at else None,
            started_at=h.started_at.isoformat() + "Z",
            completed_at=(h.completed_at.isoformat() + "Z") if h.completed_at else None,
            duration_seconds=h.duration_seconds,
            status=h.status,
            error_message=h.error_message,
            initiated_by_username=username,
        )
        for h, username in rows
    ]


# -- Notification settings endpoints --

_DEFAULT_THRESHOLDS = [
    {"minutes_before": 2880, "level": "info"},
    {"minutes_before": 120, "level": "warning"},
    {"minutes_before": 15, "level": "danger"},
]


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_upgrade_settings(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Get default notification thresholds."""
    import json
    row = await db.execute(
        select(AppSettings.value).where(AppSettings.key == "upgrade_notification_thresholds")
    )
    val = row.scalar()
    thresholds = json.loads(val) if val else _DEFAULT_THRESHOLDS
    return NotificationSettingsResponse(default_thresholds=thresholds)


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_upgrade_settings(
    body: NotificationSettingsResponse,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Update default notification thresholds."""
    import json

    for t in body.default_thresholds:
        if "minutes_before" not in t or "level" not in t:
            raise HTTPException(400, "INVALID_THRESHOLD_FORMAT")
        if t["level"] not in ("info", "warning", "danger"):
            raise HTTPException(400, "INVALID_THRESHOLD_LEVEL")
        if not isinstance(t["minutes_before"], int) or t["minutes_before"] < 1:
            raise HTTPException(400, "INVALID_THRESHOLD_MINUTES")

    val = json.dumps(body.default_thresholds)
    existing = (await db.execute(
        select(AppSettings).where(AppSettings.key == "upgrade_notification_thresholds")
    )).scalar_one_or_none()
    if existing:
        existing.value = val
    else:
        db.add(AppSettings(key="upgrade_notification_thresholds", value=val))
    await db.commit()

    return body
