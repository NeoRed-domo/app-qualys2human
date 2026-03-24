# backend/src/q2h/upgrade/scheduler.py
"""Background scheduler: checks every 30s if a scheduled upgrade should trigger.

Handles:
- Pre-flight checks (no import running, disk space)
- Writing HMAC-signed upgrade-request.json
- Starting Q2H-Updater service
- Shutting down Q2H
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.models import AuditLog, ImportJob, UpgradeSchedule

logger = logging.getLogger("q2h.upgrade")


async def _check_preflight(db: AsyncSession, package_path: str) -> tuple[bool, str]:
    """Run pre-flight checks before starting upgrade.

    Checks: no import running, no reclassification running, sufficient disk space.
    Returns (ok, reason).
    """
    from q2h.api.imports import _import_state
    from q2h.api.layers import _reclassify
    from q2h.upgrade.chunked_upload import check_disk_space

    # Check import in progress
    if _import_state.running:
        return False, "Import in progress"

    active_imports = (await db.execute(
        select(ImportJob.id).where(ImportJob.status == "processing")
    )).first()
    if active_imports:
        return False, f"Import job #{active_imports[0]} in progress"

    # Check reclassification in progress
    if _reclassify.running:
        return False, "Reclassification in progress"

    # Check disk space (3x package size)
    try:
        package_size = Path(package_path).stat().st_size
        space_ok, required, available = check_disk_space(package_size)
        if not space_ok:
            return False, (
                f"Insufficient disk space: need {required // (1024*1024)} MB, "
                f"available {available // (1024*1024)} MB"
            )
    except FileNotFoundError:
        return False, f"Package file not found: {package_path}"

    return True, ""


def _read_jwt_secret(install_dir: Path) -> str:
    """Read JWT_SECRET from .env file (same source as the Updater).

    Falls back to env var, then default.
    """
    env_file = install_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("JWT_SECRET="):
                return line.partition("=")[2].strip()
    return os.environ.get("JWT_SECRET", "dev-secret-change-in-prod")


def _write_upgrade_request(
    install_dir: Path,
    config_path: Path,
    package_path: str,
    backup_dir: Path,
) -> Path:
    """Write HMAC-signed upgrade-request.json."""
    jwt_secret = _read_jwt_secret(install_dir)

    payload = {
        "install_dir": str(install_dir),
        "config_path": str(config_path),
        "package_path": package_path,
        "backup_dir": str(backup_dir),
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }

    payload_json = json.dumps(payload, sort_keys=True)
    mac = hmac.new(jwt_secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()

    request_data = {
        "payload": payload,
        "hmac": mac,
    }

    request_path = install_dir / "upgrade-request.json"
    request_path.write_text(json.dumps(request_data, indent=2))
    logger.info("Wrote upgrade-request.json to %s", request_path)
    return request_path


_UPDATER_XML_TEMPLATE = """\
<service>
  <id>{service_id}</id>
  <name>{service_name}</name>
  <description>Qualys2Human upgrade orchestration service</description>
  <executable>{python_exe}</executable>
  <arguments>-m q2h_updater</arguments>
  <workingdirectory>{working_dir}</workingdirectory>
  <startmode>Manual</startmode>
  <onfailure action="none" />
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>5</keepFiles>
    <logpath>{log_dir}</logpath>
  </log>
  <env name="Q2H_INSTALL_DIR" value="{install_dir}" />
</service>
"""


_UPDATER_SERVICE = "Qualys2Human-Updater"


def _refresh_updater_runtime(install_dir: Path):
    """Refresh tmp/python_updater/ with current Python runtime + ._pth patch."""
    tmp_python = install_dir / "tmp" / "python_updater"
    python_src = install_dir / "python"

    if not python_src.exists():
        logger.error("Python source not found at %s", python_src)
        return

    if tmp_python.exists():
        shutil.rmtree(tmp_python)
    shutil.copytree(str(python_src), str(tmp_python))

    # Patch ._pth so embedded Python can find updater/ package
    pth_files = list(tmp_python.glob("python*._pth"))
    if pth_files:
        pth = pth_files[0]
        content = pth.read_text(encoding="utf-8")
        updater_rel = "..\\..\\updater"
        if updater_rel not in content:
            content = updater_rel + "\n" + content
            pth.write_text(content, encoding="utf-8")

    logger.info("Refreshed runtime isolation: %s (._pth patched)", tmp_python)


def _is_service_installed(service_name: str) -> bool:
    """Check if a Windows service is registered."""
    try:
        r = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def ensure_updater_service_installed(install_dir: Path):
    """Ensure the Updater Windows service is installed. Idempotent — safe to call every startup.

    Steps:
    1. Check if service already exists → skip if yes
    2. Verify WinSW exe exists (copy from Qualys2Human.exe if needed)
    3. Prepare runtime isolation (tmp/python_updater/)
    4. Generate XML config
    5. Register service via WinSW
    """
    service_name = _UPDATER_SERVICE

    # 1. Already installed?
    if _is_service_installed(service_name):
        logger.debug("Updater service already installed")
        return

    logger.info("Updater service not found — installing...")

    # 2. WinSW exe
    main_exe = install_dir / "Qualys2Human.exe"
    updater_exe = install_dir / f"{service_name}.exe"
    if not updater_exe.exists():
        if not main_exe.exists():
            logger.error("Cannot install Updater: WinSW exe not found at %s", main_exe)
            return
        shutil.copy2(str(main_exe), str(updater_exe))
        logger.info("  Copied WinSW -> %s", updater_exe.name)

    # 3. Prepare runtime isolation (tmp/python_updater/)
    tmp_python = install_dir / "tmp" / "python_updater"
    python_src = install_dir / "python"
    if not tmp_python.exists() and python_src.exists():
        shutil.copytree(str(python_src), str(tmp_python))
        # Patch ._pth
        pth_files = list(tmp_python.glob("python*._pth"))
        if pth_files:
            pth = pth_files[0]
            content = pth.read_text(encoding="utf-8")
            updater_rel = "..\\..\\updater"
            if updater_rel not in content:
                content = updater_rel + "\n" + content
                pth.write_text(content, encoding="utf-8")
        logger.info("  Prepared runtime isolation: %s", tmp_python)

    # 4. Generate XML config
    python_exe = tmp_python / "python.exe"
    log_dir = install_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    xml_content = _UPDATER_XML_TEMPLATE.format(
        service_id=service_name,
        service_name=service_name,
        python_exe=python_exe,
        working_dir=install_dir,
        install_dir=install_dir,
        log_dir=log_dir,
    )
    xml_path = install_dir / f"{service_name}.xml"
    xml_path.write_text(xml_content, encoding="utf-8")
    logger.info("  Generated XML: %s", xml_path)

    # 5. Register via WinSW
    result = subprocess.run(
        [str(updater_exe), "install"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode == 0:
        logger.info("  Updater service '%s' installed successfully", service_name)
    else:
        logger.error(
            "  WinSW install FAILED (rc=%d): stdout=%s stderr=%s",
            result.returncode,
            (result.stdout or "").strip(),
            (result.stderr or "").strip(),
        )

    # 6. Verify
    if _is_service_installed(service_name):
        logger.info("Updater service verified: OK")
    else:
        logger.error("Updater service STILL not found after install attempt!")


async def _trigger_upgrade(schedule, db: AsyncSession):
    """Execute upgrade trigger sequence."""
    from q2h.config import get_settings

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    schedule.status = "running"
    schedule.started_at = now

    # Audit
    db.add(AuditLog(
        user_id=schedule.scheduled_by,
        action="upgrade_start",
        detail=f"Upgrade {schedule.source_version} -> {schedule.target_version} triggered",
    ))
    await db.commit()

    # Determine paths
    config_path_env = os.environ.get("Q2H_CONFIG")
    if config_path_env:
        config_path = Path(config_path_env)
        install_dir = config_path.parent
    else:
        install_dir = Path(__file__).parent.parent.parent.parent
        config_path = install_dir / "config.yaml"

    # Create backup directory
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    backup_dir = install_dir / "backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Write upgrade request
    _write_upgrade_request(
        install_dir=install_dir,
        config_path=config_path,
        package_path=schedule.package_path,
        backup_dir=backup_dir,
    )

    # Refresh runtime isolation (tmp/python_updater/) before starting Updater
    await asyncio.to_thread(_refresh_updater_runtime, install_dir)

    # Verify Updater service is installed (should have been done at Q2H startup)
    updater_service = _UPDATER_SERVICE
    if not _is_service_installed(updater_service):
        logger.warning("Updater service not installed — attempting install now...")
        await asyncio.to_thread(ensure_updater_service_installed, install_dir)

    if not _is_service_installed(updater_service):
        schedule.status = "failed"
        schedule.error_message = (
            "Updater service could not be installed. "
            "Check logs and verify Qualys2Human.exe (WinSW) exists in the install directory."
        )
        schedule.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(AuditLog(
            user_id=schedule.scheduled_by,
            action="upgrade_failed",
            detail=schedule.error_message,
        ))
        await db.commit()
        request_path = install_dir / "upgrade-request.json"
        request_path.unlink(missing_ok=True)
        return

    # Start Updater service
    try:
        result = subprocess.run(
            ["sc", "start", updater_service],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"sc start returned {result.returncode}: {result.stdout.strip()} {result.stderr.strip()}")
        logger.info("Q2H-Updater service started")
    except Exception as e:
        logger.error("Failed to start Q2H-Updater: %s", e)
        schedule.status = "failed"
        schedule.error_message = f"Failed to start updater service: {e}"
        schedule.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(AuditLog(
            user_id=schedule.scheduled_by,
            action="upgrade_failed",
            detail=schedule.error_message,
        ))
        await db.commit()
        request_path = install_dir / "upgrade-request.json"
        request_path.unlink(missing_ok=True)
        return

    # Q2H will be stopped by the Updater service (mutual exclusion).
    # The Updater calls sc stop Qualys2Human at its own startup.
    logger.info("Updater started — it will stop Q2H and take over.")


async def upgrade_scheduler_loop(db_session_factory):
    """Background loop: check every 30s for scheduled upgrades to trigger.

    Pre-flight retries: up to 3 attempts, 5 minutes apart (per spec).
    Args:
        db_session_factory: AsyncSession factory (SessionLocal).
    """
    MAX_RETRIES = 3
    retry_count = 0
    RETRY_DELAY = 300  # 5 minutes between retries (per spec)

    logger.info("Upgrade scheduler started — checking every 30s")

    while True:
        try:
            await asyncio.sleep(30)

            async with db_session_factory() as db:
                # Find pending upgrade whose scheduled_at has passed
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                schedule = (await db.execute(
                    select(UpgradeSchedule)
                    .where(UpgradeSchedule.status == "pending")
                    .where(UpgradeSchedule.scheduled_at <= now)
                )).scalar_one_or_none()

                if not schedule:
                    retry_count = 0
                    continue

                logger.info(
                    "Found pending upgrade id=%d to %s (scheduled_at=%s, now=%s)",
                    schedule.id, schedule.target_version,
                    schedule.scheduled_at.isoformat(), now.isoformat(),
                )

                # Pre-flight checks (includes disk space)
                ok, reason = await _check_preflight(db, schedule.package_path)
                if not ok:
                    retry_count += 1
                    logger.warning(
                        "Upgrade pre-flight failed (attempt %d/%d): %s -- retrying in %ds",
                        retry_count, MAX_RETRIES, reason, RETRY_DELAY,
                    )
                    if retry_count >= MAX_RETRIES:
                        schedule.status = "failed"
                        schedule.error_message = (
                            f"Pre-flight failed after {MAX_RETRIES} retries: {reason}"
                        )
                        schedule.completed_at = now
                        db.add(AuditLog(
                            user_id=schedule.scheduled_by,
                            action="upgrade_failed",
                            detail=schedule.error_message,
                        ))
                        await db.commit()
                        retry_count = 0
                    else:
                        # Wait 5 minutes before retrying
                        await asyncio.sleep(RETRY_DELAY)
                    continue

                # All checks passed -- trigger upgrade
                retry_count = 0
                logger.info("Triggering scheduled upgrade to %s", schedule.target_version)
                await _trigger_upgrade(schedule, db)

        except asyncio.CancelledError:
            logger.info("Upgrade scheduler stopped")
            break
        except Exception:
            logger.exception("Error in upgrade scheduler loop")
            await asyncio.sleep(30)
