"""Upgrade — backup current installation, replace files, run migrations, restart."""

import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))

from utils import banner, check_admin, load_config, prompt, setup_logging
import service as service_mod

SCRIPT_DIR = Path(__file__).absolute().parent
PACKAGE_ROOT = SCRIPT_DIR.parent



def detect_install_dir() -> Path | None:
    """Try to detect existing installation directory."""
    candidates = [Path(r"C:\Q2H"), Path(r"C:\Qualys2Human")]
    for p in candidates:
        if (p / "config.yaml").exists():
            return p
    return None


def backup(install_dir: Path, logger) -> Path | None:
    """Create a backup of config, certs, keys, data, and database."""
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    backup_dir = install_dir / "backups" / ts
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup config files
    for name in ["config.yaml", ".env"]:
        src = install_dir / name
        if src.exists():
            shutil.copy2(src, backup_dir / name)

    # Backup directories
    for dirname in ["certs", "keys", "data"]:
        src = install_dir / dirname
        if src.exists():
            shutil.copytree(src, backup_dir / dirname)

    # Backup database
    logger.info("Sauvegarde de la base de donnees (pg_dump)...")
    pg_dump = install_dir / "pgsql" / "bin" / "pg_dump.exe"
    if not pg_dump.exists():
        pg_dump = "pg_dump"

    dump_file = backup_dir / "qualys2human.sql"
    try:
        config = load_config(install_dir / "config.yaml")
        db_conf = config.get("database", {})
        import os
        env = {**os.environ, "PGPASSWORD": db_conf.get("password", "")}

        subprocess.run(
            [str(pg_dump), "-U", db_conf.get("user", "q2h"), "-h", "localhost",
             "-d", db_conf.get("name", "qualys2human"), "-f", str(dump_file)],
            env=env, capture_output=True, text=True, timeout=300, check=True,
        )
        logger.info("[OK] Base sauvegardee: %s", dump_file)
    except Exception as e:
        logger.warning("Sauvegarde DB echouee: %s", e)

    logger.info("[OK] Backup complet: %s", backup_dir)
    return backup_dir


def _patch_pth(install_dir: Path, logger):
    """Re-patch python*._pth so app/backend/src takes priority over site-packages."""
    pth_files = list((install_dir / "python").glob("python*._pth"))
    if not pth_files:
        return
    pth = pth_files[0]
    content = pth.read_text(encoding="utf-8")
    src_rel = "..\\app\\backend\\src"
    if src_rel not in content:
        content = src_rel + "\n" + content
        pth.write_text(content, encoding="utf-8")
        logger.info("  [OK] %s patche: %s ajoute", pth.name, src_rel)


def upgrade_files(install_dir: Path, logger):
    """Replace app/ and python/ with new versions, and merge data/ (preserving custom files)."""
    for subdir in ["app", "python", "updater"]:
        src = PACKAGE_ROOT / subdir
        dst = install_dir / subdir
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            logger.info("  [OK] %s/ mis a jour", subdir)

    # Re-patch ._pth so source code takes priority over pip-installed package
    _patch_pth(install_dir, logger)

    # Merge data/ — copy new/updated default files but preserve custom logos and settings
    data_src = PACKAGE_ROOT / "data"
    data_dst = install_dir / "data"
    if data_src.exists():
        # Files to never overwrite (user-customized)
        preserve = {"settings.json"}
        preserve_prefixes = ("logo-custom",)
        for src_file in data_src.rglob("*"):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(data_src)
            dst_file = data_dst / rel
            if dst_file.name in preserve or dst_file.name.startswith(preserve_prefixes):
                if dst_file.exists():
                    continue  # keep user's version
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
        logger.info("  [OK] data/ mis a jour (fichiers custom preserves)")


def _refresh_matview(install_dir: Path, db_url: str, logger):
    """Refresh materialized view if not populated (fixes broken rollback/restore)."""
    psql_exe = install_dir / "pgsql" / "bin" / "psql.exe"
    if not psql_exe.exists():
        psql_exe = "psql"

    config = load_config(install_dir / "config.yaml")
    db_conf = config.get("database", {})
    env = {**os.environ, "PGPASSWORD": db_conf.get("password", "")}

    try:
        # Check if view is populated
        result = subprocess.run(
            [str(psql_exe), "-U", db_conf.get("user", "q2h"), "-h", "localhost",
             "-d", db_conf.get("name", "qualys2human"), "-t", "-A",
             "-c", "SELECT ispopulated FROM pg_matviews WHERE matviewname = 'latest_vulns'"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip() == "f":
            logger.warning("Vue materialisee latest_vulns non peuplee — refresh en cours...")
            subprocess.run(
                [str(psql_exe), "-U", db_conf.get("user", "q2h"), "-h", "localhost",
                 "-d", db_conf.get("name", "qualys2human"),
                 "-c", "REFRESH MATERIALIZED VIEW latest_vulns"],
                env=env, capture_output=True, text=True, timeout=600,
            )
            logger.info("[OK] Vue materialisee rafraichie")
    except Exception as e:
        logger.warning("Verification vue materialisee echouee: %s", e)


def run_migrations(install_dir: Path, logger) -> bool:
    """Run Alembic migrations after upgrade."""
    python_exe = install_dir / "python" / "python.exe"
    backend_dir = install_dir / "app" / "backend"

    # Read DB credentials from config.yaml and pass via env var
    # (same approach as database.py — bypasses the q2h config system)
    config = load_config(install_dir / "config.yaml")
    db_conf = config.get("database", {})
    db_url = (
        f"postgresql+psycopg2://{db_conf.get('user', 'q2h')}:"
        f"{db_conf.get('password', '')}@"
        f"{db_conf.get('host', 'localhost')}:{db_conf.get('port', 5432)}/"
        f"{db_conf.get('name', 'qualys2human')}"
    )
    env = {
        **os.environ,
        "Q2H_DATABASE_URL": db_url,
        "Q2H_CONFIG": str(install_dir / "config.yaml"),
    }

    try:
        result = subprocess.run(
            [str(python_exe), "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir, capture_output=True, text=True, timeout=3600,
            env=env,
        )
        if result.returncode != 0:
            logger.error("Migrations echouees:")
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-30:]:
                    logger.error("  %s", line)
            if result.stdout:
                for line in result.stdout.strip().splitlines()[-10:]:
                    logger.error("  stdout: %s", line)
            return False
        logger.info("[OK] Migrations executees")

        # Ensure materialized view is populated (guards against failed rollbacks)
        _refresh_matview(install_dir, db_url, logger)

        return True
    except subprocess.TimeoutExpired:
        logger.error("Migrations timeout")
        return False


def rollback(install_dir: Path, backup_dir: Path, logger):
    """Restore from backup on failure — files AND database."""
    logger.warning("Rollback en cours depuis %s ...", backup_dir)

    # Restore files
    for name in ["config.yaml", ".env"]:
        src = backup_dir / name
        if src.exists():
            shutil.copy2(src, install_dir / name)
    for dirname in ["certs", "keys", "data"]:
        src = backup_dir / dirname
        dst = install_dir / dirname
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    logger.info("[OK] Fichiers restaures depuis le backup")

    # Restore database from SQL dump
    dump_file = backup_dir / "qualys2human.sql"
    if dump_file.exists():
        logger.info("Restauration de la base de donnees...")
        config = load_config(install_dir / "config.yaml")
        db_conf = config.get("database", {})
        db_name = db_conf.get("name", "qualys2human")
        db_user = db_conf.get("user", "q2h")

        psql_exe = install_dir / "pgsql" / "bin" / "psql.exe"
        if not psql_exe.exists():
            psql_exe = "psql"

        env = {**os.environ, "PGPASSWORD": db_conf.get("password", "")}
        try:
            # Drop and recreate to ensure clean state
            subprocess.run(
                [str(psql_exe), "-U", db_user, "-h", "localhost", "-d", db_name,
                 "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
                env=env, capture_output=True, text=True, timeout=30,
            )
            # Restore from dump (large DBs may need several minutes)
            logger.info("Restauration en cours (timeout 15min)...")
            result = subprocess.run(
                [str(psql_exe), "-U", db_user, "-h", "localhost", "-d", db_name,
                 "-f", str(dump_file)],
                env=env, capture_output=True, text=True, timeout=900,
            )
            if result.returncode == 0:
                logger.info("[OK] Base de donnees restauree depuis le backup")
            else:
                logger.warning("Restauration DB partielle: %s",
                               result.stderr[:200] if result.stderr else "")
        except Exception as e:
            logger.warning("Restauration DB echouee: %s", e)
    else:
        logger.warning("Pas de dump SQL dans le backup — base non restauree")


def health_check(port: int, logger, retries: int = 20, delay: float = 5.0) -> bool:
    """Wait for the application to respond on /api/health."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f"https://localhost:{port}/api/health"
    logger.info("Verification: %s ...", url)

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.urlopen(url, timeout=5, context=ctx)
            if req.status == 200:
                logger.info("[OK] Application accessible")
                return True
        except Exception:
            pass
        if attempt < retries:
            time.sleep(delay)

    logger.error("L'application ne repond pas apres %d tentatives", retries)
    return False


def main():
    version_file = PACKAGE_ROOT / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "dev"
    banner(version)
    print("  Mode: MISE A JOUR\n")

    if not check_admin():
        print("[ERREUR] Droits administrateur requis.")
        sys.exit(1)

    install_dir = detect_install_dir()
    if not install_dir:
        install_dir = Path(prompt("Repertoire d'installation existant", r"C:\Q2H"))
    if not (install_dir / "config.yaml").exists():
        print(f"[ERREUR] Installation non trouvee dans {install_dir}")
        sys.exit(1)

    logger = setup_logging(install_dir / "logs" / "upgrade.log")
    service_name = prompt("Nom du service Windows", "Qualys2Human")

    # Step 1: Stop service (waits until fully stopped)
    logger.info("Arret du service '%s'...", service_name)
    service_mod.stop_service(install_dir, service_name, logger)

    # Step 2: Backup
    print("\n--- Sauvegarde ---")
    backup_dir = backup(install_dir, logger)

    # Step 3: Replace files
    print("\n--- Mise a jour des fichiers ---")
    upgrade_files(install_dir, logger)

    # Step 4: Migrations
    print("\n--- Migrations ---")
    if not run_migrations(install_dir, logger):
        if backup_dir:
            rollback(install_dir, backup_dir, logger)
        sys.exit(1)

    # Step 5: Restart
    print("\n--- Redemarrage ---")
    service_mod._winsw(install_dir, "start", service_name, logger)

    # Health check
    config = load_config(install_dir / "config.yaml")
    port = config.get("server", {}).get("port", 8443)
    if not health_check(port, logger, retries=20, delay=5.0):
        logger.warning("L'application ne repond pas. Rollback...")
        if backup_dir:
            rollback(install_dir, backup_dir, logger)
            service_mod._winsw(install_dir, "start", service_name, logger)
        sys.exit(1)

    print()
    print("=" * 56)
    print(f"  Mise a jour vers v{version} terminee!")
    print("=" * 56)


if __name__ == "__main__":
    main()
