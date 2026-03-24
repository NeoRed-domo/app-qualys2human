"""Individual upgrade step implementations.

Each step function takes an UpgradeContext and raises StepError on failure.
Steps follow the same logic as installer/upgrade.py but adapted for the
Updater context (runtime isolation, status reporting).
"""

import logging
import os
import shutil
import ssl
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


class StepError(Exception):
    """Raised when an upgrade step fails."""


@dataclass
class UpgradeContext:
    """Shared context passed to each upgrade step."""
    install_dir: Path
    config_path: Path
    package_path: Path
    backup_dir: Path
    config: dict
    logger: logging.Logger
    service_name: str = "Qualys2Human"


def _pg_exe(install_dir: Path, name: str) -> str:
    """Find a PostgreSQL executable (pg_dump, psql)."""
    local = install_dir / "pgsql" / "bin" / f"{name}.exe"
    return str(local) if local.exists() else name


def backup_database(ctx: UpgradeContext):
    """Step 1: Backup database via pg_dump (timeout 3600s)."""
    db = ctx.config.get("database", {})
    pg_dump = _pg_exe(ctx.install_dir, "pg_dump")
    dump_file = ctx.backup_dir / "qualys2human.sql"

    env = {**os.environ, "PGPASSWORD": str(db.get("password", ""))}
    cmd = [
        pg_dump,
        "-U", str(db.get("user", "q2h")),
        "-h", str(db.get("host", "localhost")),
        "-p", str(db.get("port", 5432)),
        "-d", str(db.get("name", "qualys2human")),
        "-f", str(dump_file),
    ]

    ctx.logger.info("pg_dump -> %s", dump_file)
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=7200)
    except subprocess.TimeoutExpired:
        raise StepError("pg_dump timed out after 7200s (2h)")

    if result.returncode != 0:
        raise StepError(f"pg_dump failed (rc={result.returncode}): {result.stderr[:500]}")

    ctx.logger.info("Database backup complete: %s", dump_file)


def backup_files(ctx: UpgradeContext):
    """Step 2: Backup config, .env, certs/, keys/, data/, updater/, app/, python/.

    Per spec: must backup app/ and python/ so rollback can restore the old version.
    """
    ctx.backup_dir.mkdir(parents=True, exist_ok=True)

    # Single files (use ctx.config_path, not hardcoded install_dir/config.yaml)
    for src_path in [ctx.config_path, ctx.install_dir / ".env"]:
        if src_path.exists():
            shutil.copy2(src_path, ctx.backup_dir / src_path.name)
            ctx.logger.info("  Backed up %s", src_path.name)

    # Directories (including app/ and python/ per spec)
    for dirname in ["certs", "keys", "data", "updater", "app", "python"]:
        src = ctx.install_dir / dirname
        if src.exists():
            shutil.copytree(src, ctx.backup_dir / dirname)
            ctx.logger.info("  Backed up %s/", dirname)

    ctx.logger.info("File backup complete: %s", ctx.backup_dir)


def _patch_pth(python_dir: Path, logger):
    """Patch python*._pth so app/backend/src takes priority over site-packages."""
    pth_files = list(python_dir.glob("python*._pth"))
    if not pth_files:
        return
    pth = pth_files[0]
    content = pth.read_text(encoding="utf-8")
    src_rel = "..\\app\\backend\\src"
    if src_rel not in content:
        content = src_rel + "\n" + content
        pth.write_text(content, encoding="utf-8")
        logger.info("  Patched %s", pth.name)


def extract_package(ctx: UpgradeContext):
    """Step 3: Extract .zip, replace app/ and python/, update updater/, patch ._pth."""
    with zipfile.ZipFile(ctx.package_path, "r") as zf:
        # Find the archive root (e.g., "Qualys2Human-2.0.0.0/")
        names = zf.namelist()
        roots = {n.split("/")[0] for n in names if "/" in n}
        if len(roots) != 1:
            raise StepError(f"Unexpected archive structure: {roots}")
        archive_root = roots.pop()

        # Extract to temp dir first
        temp_extract = ctx.install_dir / "tmp" / "_upgrade_extract"
        if temp_extract.exists():
            shutil.rmtree(temp_extract)
        zf.extractall(temp_extract)

    extracted = temp_extract / archive_root

    # Replace app/ and python/
    for subdir in ["app", "python"]:
        src = extracted / subdir
        dst = ctx.install_dir / subdir
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            ctx.logger.info("  Replaced %s/", subdir)

    # Update updater/ (safe: we run from tmp/python_updater/)
    updater_src = extracted / "updater"
    if updater_src.exists():
        updater_dst = ctx.install_dir / "updater"
        if updater_dst.exists():
            shutil.rmtree(updater_dst)
        shutil.copytree(updater_src, updater_dst)
        ctx.logger.info("  Updated updater/")

    # Merge data/ (preserve user-customized files)
    data_src = extracted / "data"
    data_dst = ctx.install_dir / "data"
    if data_src.exists():
        preserve = {"settings.json"}
        preserve_prefixes = ("logo-custom",)
        for src_file in data_src.rglob("*"):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(data_src)
            dst_file = data_dst / rel
            if dst_file.name in preserve or dst_file.name.startswith(preserve_prefixes):
                if dst_file.exists():
                    continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
        ctx.logger.info("  Merged data/ (custom files preserved)")

    # Patch ._pth
    _patch_pth(ctx.install_dir / "python", ctx.logger)

    # Cleanup temp
    shutil.rmtree(temp_extract, ignore_errors=True)
    ctx.logger.info("Package extracted and applied")


def run_migrations(ctx: UpgradeContext):
    """Step 4: Run Alembic migrations (timeout 3600s)."""
    from q2h_updater.config import build_alembic_db_url

    python_exe = ctx.install_dir / "python" / "python.exe"
    backend_dir = ctx.install_dir / "app" / "backend"
    db_url = build_alembic_db_url(ctx.config)

    env = {
        **os.environ,
        "Q2H_DATABASE_URL": db_url,
        "Q2H_CONFIG": str(ctx.config_path),
    }

    cmd = [str(python_exe), "-m", "alembic", "upgrade", "head"]
    ctx.logger.info("Running Alembic migrations...")

    try:
        result = subprocess.run(
            cmd, cwd=backend_dir, capture_output=True, text=True,
            timeout=3600, env=env,
        )
    except subprocess.TimeoutExpired:
        raise StepError("Alembic migrations timed out after 3600s")

    if result.returncode != 0:
        error_lines = (result.stderr or "").strip().splitlines()[-30:]
        raise StepError(f"Migration failed:\n" + "\n".join(error_lines))

    ctx.logger.info("Migrations complete")


def refresh_matview(ctx: UpgradeContext):
    """Step 5: Refresh materialized view (guards against failed rollback)."""
    db = ctx.config.get("database", {})
    psql = _pg_exe(ctx.install_dir, "psql")
    env = {**os.environ, "PGPASSWORD": str(db.get("password", ""))}

    try:
        # Check if view is populated
        result = subprocess.run(
            [psql, "-U", str(db.get("user", "q2h")), "-h", "localhost",
             "-d", str(db.get("name", "qualys2human")), "-t", "-A",
             "-c", "SELECT ispopulated FROM pg_matviews WHERE matviewname = 'latest_vulns'"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        populated = result.stdout.strip()
        if populated == "f":
            ctx.logger.warning("Materialized view not populated -- refreshing (non-concurrent)...")
            refresh_sql = "REFRESH MATERIALIZED VIEW latest_vulns"
        else:
            ctx.logger.info("Refreshing materialized view (concurrent)...")
            refresh_sql = "REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"
        refresh_result = subprocess.run(
            [psql, "-U", str(db.get("user", "q2h")), "-h", "localhost",
             "-d", str(db.get("name", "qualys2human")),
             "-c", refresh_sql],
            env=env, capture_output=True, text=True, timeout=3600,
        )
        if refresh_result.returncode != 0:
            ctx.logger.error("Matview refresh failed (non-fatal): %s",
                             (refresh_result.stderr or "")[:200])
        else:
            ctx.logger.info("Materialized view refreshed")
    except Exception as e:
        ctx.logger.warning("Matview refresh check failed: %s (non-fatal)", e)


def restart_service(ctx: UpgradeContext):
    """Step 6: Restart Q2H service and verify it's running."""
    import time

    ctx.logger.info("Starting %s service...", ctx.service_name)
    try:
        subprocess.run(
            ["sc", "start", ctx.service_name],
            capture_output=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise StepError(f"Failed to start {ctx.service_name}: {e.stderr}")

    # Poll Windows service state (not the port — maintenance server may still hold it)
    ctx.logger.info("Waiting for service to reach RUNNING state...")
    for attempt in range(1, 21):
        try:
            result = subprocess.run(
                ["sc", "query", ctx.service_name],
                capture_output=True, text=True, timeout=10,
            )
            if "RUNNING" in result.stdout:
                ctx.logger.info("Service %s is RUNNING (attempt %d)", ctx.service_name, attempt)
                return
        except Exception:
            pass
        time.sleep(3)

    raise StepError(f"Service {ctx.service_name} did not reach RUNNING state after 60s")


def rollback(ctx: UpgradeContext):
    """Restore files and database from backup, then restart Q2H."""
    ctx.logger.warning("Rolling back from %s ...", ctx.backup_dir)

    # Restore single files
    for name in ["config.yaml", ".env"]:
        src = ctx.backup_dir / name
        if src.exists():
            shutil.copy2(src, ctx.install_dir / name)

    # Restore directories (including app/, python/, updater/ -- per spec)
    for dirname in ["certs", "keys", "data", "updater", "app", "python"]:
        src = ctx.backup_dir / dirname
        dst = ctx.install_dir / dirname
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    # Re-patch ._pth after restoring python/
    _patch_pth(ctx.install_dir / "python", ctx.logger)

    ctx.logger.info("Files restored from backup")

    # Restore database
    dump_file = ctx.backup_dir / "qualys2human.sql"
    if dump_file.exists():
        db = ctx.config.get("database", {})
        psql = _pg_exe(ctx.install_dir, "psql")
        env = {**os.environ, "PGPASSWORD": str(db.get("password", ""))}
        db_name = str(db.get("name", "qualys2human"))
        db_user = str(db.get("user", "q2h"))

        try:
            # Drop and recreate schema
            subprocess.run(
                [psql, "-U", db_user, "-h", "localhost", "-d", db_name,
                 "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
                env=env, capture_output=True, text=True, timeout=120,
            )
            # Restore dump
            ctx.logger.info("Restoring database (timeout 7200s / 2h)...")
            result = subprocess.run(
                [psql, "-U", db_user, "-h", "localhost", "-d", db_name,
                 "-f", str(dump_file)],
                env=env, capture_output=True, text=True, timeout=7200,
            )
            if result.returncode == 0:
                ctx.logger.info("Database restored")
            else:
                ctx.logger.warning("Partial DB restore: %s", (result.stderr or "")[:200])
        except Exception as e:
            ctx.logger.error("Database restore failed: %s", e)
    else:
        ctx.logger.warning("No SQL dump in backup -- database NOT restored")
