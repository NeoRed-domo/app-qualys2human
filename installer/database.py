"""Database initialization — PostgreSQL role, database, extensions, Alembic migrations."""

import os
import subprocess
from pathlib import Path


def _find_psql(install_dir: Path) -> str | None:
    """Find psql.exe — check Q2H install, then common PostgreSQL locations."""
    candidates = [
        install_dir / "pgsql" / "bin" / "psql.exe",
    ]
    # Search standard PostgreSQL install paths (newest version first)
    for base in [Path(r"C:\Program Files\PostgreSQL"), Path(r"C:\Program Files (x86)\PostgreSQL")]:
        if base.exists():
            for ver_dir in sorted(base.iterdir(), reverse=True):
                candidates.append(ver_dir / "bin" / "psql.exe")
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _psql(cmd: str, pg_password: str, install_dir: Path, logger=None) -> bool:
    """Run a psql command as the postgres superuser."""
    pg_bin = _find_psql(install_dir)
    if not pg_bin:
        logger.error("psql.exe introuvable. Verifiez l'installation PostgreSQL.")
        return False

    logger.info("  psql: %s", pg_bin)
    env = {**os.environ, "PGPASSWORD": pg_password}
    try:
        result = subprocess.run(
            [pg_bin, "-U", "postgres", "-h", "localhost", "-c", cmd],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode != 0 and "already exists" not in (result.stderr or ""):
            logger.error("psql echoue: %s", result.stderr.strip() if result.stderr else "")
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.error("psql non accessible: %s", e)
        return False


def create_role(db_user: str, db_password: str, pg_superpass: str,
                install_dir: Path, logger=None) -> bool:
    """Create the q2h PostgreSQL role (or update its password if it exists)."""
    logger.info("Creation du role PostgreSQL '%s'...", db_user)
    ok = _psql(
        f"CREATE ROLE {db_user} WITH LOGIN PASSWORD '{db_password}';",
        pg_superpass, install_dir, logger,
    )
    # Always update password — handles the case where role already exists
    # with a different password from a previous installation.
    _psql(
        f"ALTER ROLE {db_user} WITH PASSWORD '{db_password}';",
        pg_superpass, install_dir, logger,
    )
    if ok:
        logger.info("[OK] Role '%s' cree", db_user)
    else:
        logger.info("[OK] Role '%s' existant, mot de passe mis a jour", db_user)
    return True


def create_database(db_name: str, db_user: str, pg_superpass: str,
                    install_dir: Path, logger=None) -> bool:
    """Create the qualys2human database and enable pgcrypto."""
    logger.info("Creation de la base '%s'...", db_name)
    ok = _psql(
        f"CREATE DATABASE {db_name} OWNER {db_user};",
        pg_superpass, install_dir, logger,
    )
    if ok:
        logger.info("[OK] Base '%s' creee", db_name)
    else:
        logger.info("[OK] Base '%s' existante", db_name)
    # Enable pgcrypto on the new database
    pg_bin = _find_psql(install_dir)
    if not pg_bin:
        logger.warning("psql introuvable — pgcrypto non active")
        return ok
    env = {**os.environ, "PGPASSWORD": pg_superpass}
    try:
        subprocess.run(
            [pg_bin, "-U", "postgres", "-h", "localhost", "-d", db_name,
             "-c", "CREATE EXTENSION IF NOT EXISTS pgcrypto;"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        logger.info("[OK] Extension pgcrypto activee")
    except Exception as e:
        logger.warning("pgcrypto: %s", e)
    return ok


def run_migrations(install_dir: Path, db_name: str = "qualys2human",
                   db_user: str = "q2h", db_password: str = "",
                   logger=None) -> bool:
    """Run Alembic migrations."""
    logger.info("Execution des migrations Alembic...")
    python_exe = install_dir / "python" / "python.exe"
    backend_dir = install_dir / "app" / "backend"
    alembic_ini = backend_dir / "alembic.ini"

    if not alembic_ini.exists():
        logger.error("alembic.ini non trouve dans %s", backend_dir)
        return False

    # Pass the database URL directly — bypasses the q2h config system entirely.
    # This is critical because the q2h package in site-packages may have an old
    # config.py that doesn't support Q2H_CONFIG.
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@localhost:5432/{db_name}"
    env = {
        **os.environ,
        "Q2H_DATABASE_URL": db_url,
        "Q2H_CONFIG": str(install_dir / "config.yaml"),
    }

    try:
        result = subprocess.run(
            [str(python_exe), "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir, capture_output=True, text=True, timeout=120,
            env=env,
        )
        if result.returncode != 0:
            # Log full error (stdout + stderr) for diagnosis
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-30:]:
                    logger.error("  %s", line)
            if result.stdout:
                for line in result.stdout.strip().splitlines()[-10:]:
                    logger.error("  stdout: %s", line)
            return False
        logger.info("[OK] Migrations executees")
        return True
    except subprocess.TimeoutExpired:
        logger.error("Migrations timeout (>2 min)")
        return False


def _verify_connection(db_name: str, db_user: str, db_password: str,
                       install_dir: Path, logger) -> bool:
    """Verify that we can connect as the app user before running migrations."""
    pg_bin = _find_psql(install_dir)
    if not pg_bin:
        return False
    env = {**os.environ, "PGPASSWORD": db_password}
    try:
        result = subprocess.run(
            [pg_bin, "-U", db_user, "-h", "localhost", "-d", db_name,
             "-c", "SELECT 1;"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        if result.returncode != 0:
            logger.error("Connexion psql en tant que '%s' echouee:", db_user)
            logger.error("  %s", result.stderr.strip() if result.stderr else "pas de details")
            return False
        logger.info("[OK] Connexion psql en tant que '%s' verifiee", db_user)
        return True
    except Exception as e:
        logger.error("Verification connexion echouee: %s", e)
        return False


def _verify_config_password(install_dir: Path, db_password: str, logger) -> bool:
    """Check that config.yaml contains the expected password."""
    from utils import load_config
    config_path = install_dir / "config.yaml"
    if not config_path.exists():
        logger.error("config.yaml non trouve: %s", config_path)
        return False
    config = load_config(config_path)
    stored = config.get("database", {}).get("password", "")
    masked_expected = db_password[:4] + "..." if len(db_password) > 4 else "***"
    masked_stored = stored[:4] + "..." if len(stored) > 4 else "***"
    if stored != db_password:
        logger.error("Mot de passe dans config.yaml (%s) != mot de passe attendu (%s)",
                     masked_stored, masked_expected)
        return False
    logger.info("[OK] config.yaml: mot de passe coherent (%s)", masked_expected)
    return True


def run_all(install_dir: Path, *, db_name: str = "qualys2human", db_user: str = "q2h",
            db_password: str, pg_superpass: str, logger=None) -> bool:
    """Full database initialization."""
    if not create_role(db_user, db_password, pg_superpass, install_dir, logger):
        return False
    if not create_database(db_name, db_user, pg_superpass, install_dir, logger):
        return False

    # Verify connection and config before running migrations
    if not _verify_connection(db_name, db_user, db_password, install_dir, logger):
        logger.error("La connexion PostgreSQL en tant que '%s' a echoue.", db_user)
        logger.error("Verifiez pg_hba.conf et le mot de passe.")
        return False
    _verify_config_password(install_dir, db_password, logger)

    if not run_migrations(install_dir, db_name=db_name, db_user=db_user,
                          db_password=db_password, logger=logger):
        return False
    return True
