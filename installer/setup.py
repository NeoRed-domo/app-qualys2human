"""Qualys2Human — Main installer orchestrator.

Usage:
    python setup.py [--install-dir C:\\Q2H] [--port 8443] [--non-interactive]
"""

import argparse
import shutil
import ssl
import sys
import time
import urllib.request
from pathlib import Path

# Installer modules are in the same directory
sys.path.insert(0, str(Path(__file__).absolute().parent))

from utils import (
    banner, check_admin, generate_password, prompt, prompt_confirm,
    setup_logging, validate_password_strength,
)
import prereqs
import config as config_mod
import database
import service

SCRIPT_DIR = Path(__file__).absolute().parent
PACKAGE_ROOT = SCRIPT_DIR.parent
VERSION_FILE = PACKAGE_ROOT / "VERSION"


def read_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "dev"


def copy_app_files(install_dir: Path, logger):
    """Copy application files from package to installation directory."""
    logger.info("Copie des fichiers applicatifs...")

    # Copy Python embedded
    src_python = PACKAGE_ROOT / "python"
    dst_python = install_dir / "python"
    if src_python.exists():
        if dst_python.exists():
            shutil.rmtree(dst_python)
        shutil.copytree(src_python, dst_python)
        logger.info("  [OK] python/")

    # Copy app (backend + frontend)
    src_app = PACKAGE_ROOT / "app"
    dst_app = install_dir / "app"
    if src_app.exists():
        if dst_app.exists():
            shutil.rmtree(dst_app)
        shutil.copytree(src_app, dst_app)
        logger.info("  [OK] app/")

    # Copy data assets (branding, etc.) — only if not already present
    src_data = PACKAGE_ROOT / "data"
    dst_data = install_dir / "data"
    if src_data.exists() and not dst_data.exists():
        shutil.copytree(src_data, dst_data)
        logger.info("  [OK] data/")

    # Copy updater (standalone upgrade service)
    src_updater = PACKAGE_ROOT / "updater"
    dst_updater = install_dir / "updater"
    if src_updater.exists():
        if dst_updater.exists():
            shutil.rmtree(dst_updater)
        shutil.copytree(src_updater, dst_updater)
        logger.info("  [OK] updater/")

    # Patch python312._pth to prepend app/backend/src so the source q2h package
    # takes priority over the pip-installed one in Lib/site-packages.
    # Embedded Python ignores PYTHONPATH — the ._pth file is the only way.
    pth_files = list((install_dir / "python").glob("python*._pth"))
    if pth_files:
        pth = pth_files[0]
        content = pth.read_text(encoding="utf-8")
        src_rel = "..\\app\\backend\\src"
        if src_rel not in content:
            # Prepend before all other entries so source wins over site-packages
            content = src_rel + "\n" + content
            pth.write_text(content, encoding="utf-8")
            logger.info("  [OK] %s patche: %s ajoute", pth.name, src_rel)

    logger.info("[OK] Fichiers copies")


def health_check(port: int, logger, retries: int = 10, delay: float = 3.0) -> bool:
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
    parser = argparse.ArgumentParser(description="Install Qualys2Human")
    parser.add_argument("--install-dir", default=r"C:\Q2H")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    version = read_version()
    banner(version)
    ni = args.non_interactive

    # Setup logging
    install_dir = Path(prompt("Repertoire d'installation", args.install_dir, non_interactive=ni))
    log_file = install_dir / "logs" / "install.log"
    logger = setup_logging(log_file)

    # Check admin privileges
    if not check_admin():
        logger.error("Ce programme doit etre execute en tant qu'administrateur.")
        sys.exit(1)
    logger.info("[OK] Droits administrateur")

    # --- Prompts ---
    server_port = int(prompt("Port HTTPS", str(args.port), non_interactive=ni))

    # Admin password (mandatory, validated)
    while True:
        admin_password = prompt("Mot de passe administrateur", password=True, non_interactive=ni)
        if ni:
            admin_password = admin_password or "Qualys2Human!"
            break
        err = validate_password_strength(admin_password)
        if err:
            print(f"  [!] {err}")
            continue
        confirm = prompt("Confirmer le mot de passe", password=True, non_interactive=ni)
        if admin_password != confirm:
            print("  [!] Les mots de passe ne correspondent pas")
            continue
        break

    service_name = prompt("Nom du service Windows", "Qualys2Human", non_interactive=ni)

    # Detect existing PostgreSQL before generating passwords
    existing_pg = prereqs.is_postgresql_running()
    if existing_pg and not ni:
        print()
        print("  PostgreSQL est deja installe sur cette machine.")
        print("  Le mot de passe superuser (postgres) est necessaire pour creer")
        print("  la base de donnees et le role applicatif.")
        pg_superpass = prompt("Mot de passe PostgreSQL (superuser postgres)", password=True, non_interactive=ni)
    else:
        # Generate secure password for fresh PostgreSQL install
        # safe=True (alphanumeric only) because it's passed as CLI argument
        pg_superpass = generate_password(32, safe=True)

    # safe=True: alphanumeric only — avoids SQL/YAML escaping issues
    db_password = generate_password(32, safe=True)

    # --- Step 1: Prerequisites ---
    print("\n--- Etape 1/5 : Prerequis ---")
    if not prereqs.run_all(install_dir, server_port, pg_superpass,
                          service_name=service_name, logger=logger):
        logger.error("Prerequis non satisfaits. Installation annulee.")
        sys.exit(1)

    # --- Step 2: Copy files ---
    print("\n--- Etape 2/5 : Copie des fichiers ---")
    copy_app_files(install_dir, logger)

    # --- Step 3: Configuration ---
    print("\n--- Etape 3/5 : Configuration ---")
    config_mod.run_all(install_dir, db_password=db_password, server_port=server_port, logger=logger)

    # --- Step 4: Database ---
    print("\n--- Etape 4/5 : Base de donnees ---")
    if not database.run_all(
        install_dir, db_password=db_password, pg_superpass=pg_superpass, logger=logger,
    ):
        logger.error("Initialisation de la base echouee.")
        sys.exit(1)

    # --- Step 5: Service ---
    print("\n--- Etape 5/5 : Service Windows ---")
    if not service.install_service(install_dir, service_name, logger=logger):
        logger.error("Installation du service echouee.")
        sys.exit(1)

    # Install Updater service (Manual start, for web-based upgrades)
    service.install_updater_service(install_dir, logger=logger)

    # --- Health check ---
    print()
    health_check(server_port, logger)

    # --- Done ---
    print()
    print("=" * 56)
    print("  Installation terminee avec succes!")
    print(f"  Repertoire : {install_dir}")
    print(f"  Application: https://localhost:{server_port}")
    print(f"  Identifiant: admin")
    print(f"  Service    : {service_name}")
    print()
    print("  IMPORTANT: Le mot de passe de la base de donnees a ete")
    print("  genere aleatoirement et stocke dans config.yaml.")
    print("  Ne partagez jamais ce fichier.")
    print("=" * 56)


if __name__ == "__main__":
    main()
