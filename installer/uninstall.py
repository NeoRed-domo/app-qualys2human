"""Uninstall — stop service, remove service, optionally drop database, delete files."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))

from utils import banner, check_admin, prompt, prompt_confirm, setup_logging
import service as service_mod

SCRIPT_DIR = Path(__file__).absolute().parent
PACKAGE_ROOT = SCRIPT_DIR.parent


def drop_database(install_dir: Path, logger) -> bool:
    """Drop the qualys2human database and q2h role."""
    from utils import load_config

    config_path = install_dir / "config.yaml"
    if not config_path.exists():
        logger.warning("config.yaml non trouve, suppression DB impossible")
        return False

    config = load_config(config_path)
    db = config.get("database", {})

    pg_bin = install_dir / "pgsql" / "bin" / "psql.exe"
    if not pg_bin.exists():
        pg_bin = "psql"

    env = {**os.environ}

    commands = [
        f"DROP DATABASE IF EXISTS {db.get('name', 'qualys2human')};",
        f"DROP ROLE IF EXISTS {db.get('user', 'q2h')};",
    ]

    for cmd in commands:
        try:
            subprocess.run(
                [str(pg_bin), "-U", "postgres", "-h", "localhost", "-c", cmd],
                env=env, capture_output=True, text=True, timeout=30,
            )
        except Exception as e:
            logger.warning("Commande SQL echouee: %s", e)

    logger.info("[OK] Base de donnees supprimee")
    return True


def uninstall_postgresql(install_dir: Path, logger) -> bool:
    """Stop and uninstall the portable PostgreSQL service and files."""
    # Stop the PostgreSQL service
    logger.info("Arret du service PostgreSQL (postgresql-q2h)...")
    try:
        subprocess.run(
            ["sc", "stop", "postgresql-q2h"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass

    # Wait a moment for the service to stop
    import time
    time.sleep(3)

    # Unregister the Windows service
    logger.info("Suppression du service postgresql-q2h...")
    try:
        result = subprocess.run(
            ["sc", "delete", "postgresql-q2h"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("[OK] Service postgresql-q2h supprime")
        else:
            # Try via pg_ctl unregister
            pg_ctl = install_dir / "pgsql" / "bin" / "pg_ctl.exe"
            if pg_ctl.exists():
                subprocess.run(
                    [str(pg_ctl), "unregister", "-N", "postgresql-q2h"],
                    capture_output=True, text=True, timeout=30,
                )
                logger.info("[OK] Service postgresql-q2h supprime via pg_ctl")
    except Exception as e:
        logger.warning("Suppression service PostgreSQL: %s", e)

    logger.info("[OK] PostgreSQL desinstalle")
    return True


def main():
    banner("uninstall")
    print("  Mode: DESINSTALLATION\n")

    if not check_admin():
        print("[ERREUR] Droits administrateur requis.")
        sys.exit(1)

    install_dir = Path(prompt("Repertoire d'installation", r"C:\Q2H"))
    if not install_dir.exists():
        print(f"[ERREUR] Repertoire non trouve: {install_dir}")
        sys.exit(1)

    logger = setup_logging()
    service_name = prompt("Nom du service Windows", "Qualys2Human")

    # Stop and remove service
    logger.info("Arret et suppression du service '%s'...", service_name)
    service_mod.uninstall_service(install_dir, service_name, logger)
    logger.info("[OK] Service supprime")

    # Ask about database
    keep_db = not prompt_confirm(
        "Voulez-vous supprimer la base de donnees ? (les donnees seront perdues)",
        default=False,
    )
    if not keep_db:
        drop_database(install_dir, logger)
        # Also uninstall PostgreSQL service — avoids needing the unknown
        # superuser password on reinstall
        uninstall_postgresql(install_dir, logger)

    # Delete files
    if prompt_confirm(f"Supprimer le repertoire {install_dir} ?", default=True):
        shutil.rmtree(install_dir, ignore_errors=True)
        logger.info("[OK] Repertoire %s supprime", install_dir)

    print()
    print("=" * 56)
    print("  Desinstallation terminee.")
    if keep_db:
        print("  La base de donnees PostgreSQL a ete conservee.")
    print("=" * 56)


if __name__ == "__main__":
    main()
