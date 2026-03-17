# updater/q2h_updater/service.py
"""Q2H-Updater main orchestrator.

Sequence:
1. Read + verify upgrade-request.json
2. Read config.yaml + .env
3. Wait for port 8443 to be free
4. Start HTTPS maintenance server
5. Execute upgrade steps with status updates
6. On failure: rollback, show error on maintenance page
7. On success: record in upgrade_history, restart Q2H, exit
"""

import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

logger = logging.getLogger("q2h_updater")


def _setup_logging(log_dir: Path):
    """Configure logging to file + console."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "updater.log"

    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Prevent duplicate handlers on repeated calls

    # File handler (rolling, 10 MB, 5 backups -- same as main Q2H)
    fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5,
                             encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)


def _wait_port_free(port: int, timeout: int = 60):
    """Wait until a TCP port is free (Q2H has fully stopped)."""
    logger.info("Waiting for port %d to be free...", port)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(1)
            sock.connect(("127.0.0.1", port))
            sock.close()
            # Port is still in use
            time.sleep(2)
        except (ConnectionRefusedError, OSError):
            # Port is free
            logger.info("Port %d is free", port)
            return
        finally:
            sock.close()
    raise RuntimeError(f"Port {port} not freed within {timeout}s -- Q2H may not have stopped")


def _estimate_duration(install_dir: Path, config: dict) -> int:
    """Estimate upgrade duration in minutes from DB size."""
    try:
        from q2h_updater.config import build_db_url
        import psycopg2
        conn = psycopg2.connect(build_db_url(config))
        cur = conn.cursor()
        cur.execute("SELECT pg_database_size(current_database())")
        db_size_bytes = cur.fetchone()[0]
        conn.close()
        db_size_gb = db_size_bytes / (1024 ** 3)
    except Exception:
        db_size_gb = 1  # Conservative default
    # Formula from spec: base 2 min + ~3 min/GB + ~1 min/migration
    return max(2, int(2 + db_size_gb * 3 + 1))


def _read_schedule_info(config: dict) -> dict:
    """Read schedule metadata from the most recent pending/running upgrade_schedule.

    Returns dict with scheduled_by, scheduled_at, source_version, target_version.
    """
    try:
        from q2h_updater.config import build_db_url
        import psycopg2
        conn = psycopg2.connect(build_db_url(config))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT scheduled_by, scheduled_at, source_version, target_version "
                "FROM upgrade_schedules "
                "WHERE status IN ('pending', 'running') "
                "ORDER BY created_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                return {
                    "scheduled_by": row[0],
                    "scheduled_at": row[1].isoformat() if row[1] else None,
                    "source_version": row[2],
                    "target_version": row[3],
                }
        finally:
            conn.close()
    except Exception:
        pass
    return {"scheduled_by": None, "scheduled_at": None,
            "source_version": None, "target_version": None}


def _record_result(config: dict, source_version: str, target_version: str,
                   scheduled_at: str | None, started_at: datetime,
                   status: str, error_message: str | None,
                   initiated_by: int | None, backup_path: str | None):
    """Write upgrade result to upgrade_history via psycopg2.

    Note: upgrade_history accepts 'completed', 'failed', 'rolled_back'.
    But upgrade_schedules only accepts 'pending', 'running', 'completed', 'failed', 'cancelled'.
    So 'rolled_back' must be mapped to 'failed' for the schedule table.
    """
    try:
        from q2h_updater.config import build_db_url
        import psycopg2

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        started_naive = started_at.replace(tzinfo=None) if started_at.tzinfo else started_at
        duration = int((now - started_naive).total_seconds())

        conn = psycopg2.connect(build_db_url(config))
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO upgrade_history "
                "(source_version, target_version, scheduled_at, started_at, completed_at, "
                " duration_seconds, status, error_message, initiated_by, backup_path) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (source_version, target_version, scheduled_at, started_naive, now,
                 duration, status, error_message, initiated_by, backup_path),
            )
            # Map status for upgrade_schedules (does NOT accept 'rolled_back')
            schedule_status = "failed" if status == "rolled_back" else status
            cur.execute(
                "UPDATE upgrade_schedules SET status = %s, completed_at = %s, "
                "error_message = %s WHERE status = 'running'",
                (schedule_status, now, error_message),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("Recorded upgrade result: %s", status)
    except Exception as e:
        logger.error("Failed to record upgrade result: %s", e)


def _extract_version_from_package(package_path: Path) -> str:
    """Read VERSION file from the .zip package."""
    import zipfile
    with zipfile.ZipFile(package_path, "r") as zf:
        version_files = [n for n in zf.namelist() if n.endswith("/VERSION")]
        if version_files:
            return zf.read(version_files[0]).decode().strip()
    return "unknown"


def _find_install_dir() -> Path:
    """Find Q2H install directory from env var or common paths."""
    candidates = [
        Path(os.environ.get("Q2H_INSTALL_DIR", "")),
        Path(r"C:\Q2H"),
        Path(r"C:\Qualys2Human"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "config.yaml").exists():
            return c
    return Path(os.environ.get("Q2H_INSTALL_DIR", r"C:\Q2H"))


def _run_maintenance_mode(install_dir: Path):
    """Unplanned maintenance: show maintenance page until Q2H restarts."""
    from q2h_updater.config import load_yaml_config, resolve_tls_paths
    from q2h_updater.server import start_maintenance_server

    _setup_logging(install_dir / "logs")

    logger.info("=" * 60)
    logger.info("Q2H-Updater — MAINTENANCE MODE (no upgrade request)")
    logger.info("=" * 60)

    # Stop Q2H service (mutual exclusion)
    logger.info("Stopping Qualys2Human service...")
    subprocess.run(["sc", "stop", "Qualys2Human"], capture_output=True, timeout=30)

    config_path = install_dir / "config.yaml"
    config = load_yaml_config(config_path)
    port = config.get("server", {}).get("port", 8443)
    cert_path, key_path = resolve_tls_paths(config, install_dir)

    # Wait for port to be free
    _wait_port_free(port, timeout=120)

    # Start maintenance server — stays alive until this service is stopped
    server, _ = start_maintenance_server(port, cert_path, key_path,
                                         install_dir / "upgrade-status.json")
    logger.info("Maintenance page active on port %d — waiting for service stop...", port)

    # Block until the service is stopped externally (sc stop or Q2H restart)
    try:
        while True:
            time.sleep(5)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        server.shutdown()
        logger.info("Maintenance server stopped")


def run():
    """Main entry point for the Q2H-Updater service."""
    from q2h_updater.config import load_yaml_config, load_env, resolve_tls_paths
    from q2h_updater.request import read_upgrade_request, VerificationError
    from q2h_updater.status import UpgradeStatus
    from q2h_updater.server import start_maintenance_server
    from q2h_updater.steps import (
        UpgradeContext, StepError,
        backup_database, backup_files, extract_package,
        run_migrations, refresh_matview, restart_service, rollback,
    )

    install_dir = _find_install_dir()

    # Step 0: Find upgrade-request.json
    request_path = install_dir / "upgrade-request.json"

    if not request_path.exists():
        # No upgrade request → maintenance mode
        _run_maintenance_mode(install_dir)
        return

    _setup_logging(install_dir / "logs")

    logger.info("=" * 60)
    logger.info("Q2H-Updater starting — upgrade mode")
    logger.info("=" * 60)

    # Mutual exclusion: stop Q2H service (Updater takes over)
    logger.info("Stopping Qualys2Human service...")
    subprocess.run(["sc", "stop", "Qualys2Human"], capture_output=True, timeout=30)

    # Step 1: Read and verify request
    env_data = load_env(install_dir / ".env")
    jwt_secret = env_data.get("JWT_SECRET", "dev-secret-change-in-prod")

    try:
        payload = read_upgrade_request(request_path, jwt_secret)
    except (VerificationError, FileNotFoundError) as e:
        logger.error("Request verification failed: %s", e)
        sys.exit(1)

    install_dir = Path(payload["install_dir"])
    config_path = Path(payload["config_path"])
    package_path = Path(payload["package_path"])
    backup_dir = Path(payload["backup_dir"])

    # Reconfigure logging with proper install_dir
    _setup_logging(install_dir / "logs")
    logger.info("Install dir: %s", install_dir)
    logger.info("Package: %s", package_path)
    logger.info("Backup dir: %s", backup_dir)

    # Step 2: Read config
    config = load_yaml_config(config_path)
    port = config.get("server", {}).get("port", 8443)
    cert_path, key_path = resolve_tls_paths(config, install_dir)

    # Read schedule metadata from DB (source/target version, scheduled_by, scheduled_at)
    schedule_info = _read_schedule_info(config)
    source_version = schedule_info["source_version"] or "unknown"
    target_version = schedule_info["target_version"] or _extract_version_from_package(package_path)
    initiated_by = schedule_info["scheduled_by"]
    scheduled_at_str = schedule_info["scheduled_at"]

    logger.info("Upgrade: %s -> %s", source_version, target_version)

    started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create status file
    status_file = install_dir / "upgrade-status.json"
    status = UpgradeStatus(status_file, source_version, target_version)

    # Step 3: Wait for port to be free
    try:
        _wait_port_free(port)
    except RuntimeError as e:
        logger.error(str(e))
        status.fail(str(e))
        _record_result(config, source_version, target_version, scheduled_at_str, started_at,
                       "failed", str(e), initiated_by, str(backup_dir))
        sys.exit(1)

    # Step 4: Start maintenance server
    server, server_thread = start_maintenance_server(port, cert_path, key_path, status_file)

    # Step 5: Estimate duration
    estimated_minutes = _estimate_duration(install_dir, config)
    logger.info("Estimated duration: %d min", estimated_minutes)

    # Step 6: Execute upgrade steps
    ctx = UpgradeContext(
        install_dir=install_dir,
        config_path=config_path,
        package_path=package_path,
        backup_dir=backup_dir,
        config=config,
        logger=logger,
    )

    steps = [
        ("backup_database", backup_database, estimated_minutes),
        ("backup_files", backup_files, max(1, estimated_minutes - 1)),
        ("extract_package", extract_package, max(1, estimated_minutes - 2)),
        ("run_migrations", run_migrations, max(1, estimated_minutes - 3)),
        ("refresh_matview", refresh_matview, 1),
    ]

    error_message = None
    final_status = "completed"

    for step_label, step_fn, est_remaining in steps:
        status.advance(step_label, est_remaining)
        logger.info("--- Step: %s ---", step_label)
        try:
            step_fn(ctx)
        except (StepError, Exception) as e:
            error_message = f"Step '{step_label}' failed: {e}"
            logger.error(error_message)
            status.fail(error_message)

            logger.info("Starting rollback...")
            try:
                rollback(ctx)
                final_status = "rolled_back"
            except Exception as rb_err:
                logger.error("Rollback also failed: %s", rb_err)
                final_status = "failed"

            # Record failure
            _record_result(config, source_version, target_version, scheduled_at_str, started_at,
                           final_status, error_message, initiated_by, str(backup_dir))

            # Restart Q2H with old version (stop maintenance server first)
            logger.info("Stopping maintenance server...")
            server.shutdown()
            time.sleep(2)
            try:
                subprocess.run(["sc", "start", ctx.service_name],
                               capture_output=True, timeout=30)
            except Exception:
                pass

            sys.exit(1)

    # All upgrade steps succeeded — now restart Q2H
    logger.info("=" * 60)
    logger.info("Upgrade complete: %s -> %s", source_version, target_version)
    logger.info("=" * 60)

    status.complete()

    # Record success
    _record_result(config, source_version, target_version, scheduled_at_str, started_at,
                   "completed", None, initiated_by, str(backup_dir))

    # Give browser time to poll and see "complete" state before shutting down server
    logger.info("Waiting for browser to see completion status...")
    time.sleep(8)

    # Stop maintenance server to free the port, then start Q2H
    logger.info("Stopping maintenance server to free port %d...", port)
    server.shutdown()
    time.sleep(2)

    logger.info("--- Step: restart_service ---")
    try:
        restart_service(ctx)
        logger.info("Q2H restarted successfully")
    except Exception as e:
        logger.error("Failed to restart Q2H: %s (manual start required)", e)

    # Clean up status file
    status_file.unlink(missing_ok=True)
