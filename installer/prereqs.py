"""Prerequisites — OS checks, PostgreSQL silent install, TLS certificate generation."""

import ipaddress
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).absolute().parent
PACKAGE_ROOT = SCRIPT_DIR.parent


def check_os(logger) -> bool:
    """Verify Windows Server 2016+ (build >= 14393)."""
    if platform.system() != "Windows":
        logger.error("Ce programme est prevu pour Windows Server.")
        return False
    build = int(platform.version().split(".")[-1])
    if build < 14393:
        logger.error("Windows Server 2016 ou superieur requis (build actuel: %s)", build)
        return False
    logger.info("[OK] Windows %s (build %s)", platform.version(), build)
    return True


def check_disk_space(install_dir: Path, min_gb: float = 2.0, logger=None) -> bool:
    """Verify enough free disk space."""
    drive = install_dir.anchor or install_dir.parts[0]
    usage = shutil.disk_usage(drive)
    free_gb = usage.free / (1024 ** 3)
    if free_gb < min_gb:
        logger.error("Espace disque insuffisant: %.1f Go libre (minimum %.1f Go)", free_gb, min_gb)
        return False
    logger.info("[OK] Espace disque: %.1f Go libre", free_gb)
    return True


def check_port(port: int, logger=None) -> bool:
    """Verify that the target port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            logger.info("[OK] Port %d disponible", port)
            return True
        except OSError:
            logger.error("Port %d deja utilise", port)
            return False


def _check_existing_postgresql(logger) -> bool:
    """Check if PostgreSQL is already running (port 5432 or service)."""
    # Check port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(("127.0.0.1", 5432))
            logger.warning("PostgreSQL semble deja actif sur le port 5432")
            return True
        except OSError:
            pass
    # Check service
    try:
        result = subprocess.run(
            ["sc", "query", "postgresql-q2h"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and "RUNNING" in result.stdout:
            logger.warning("Service postgresql-q2h deja installe et actif")
            return True
    except Exception:
        pass
    return False


def is_postgresql_running() -> bool:
    """Public check: is PostgreSQL already active? (silent, no logging)"""
    # Check port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(("127.0.0.1", 5432))
            return True
        except OSError:
            return False


def install_postgresql(install_dir: Path, pg_password: str, logger=None) -> bool:
    """Install PostgreSQL silently from bundled installer."""
    # Skip if already running
    if _check_existing_postgresql(logger):
        logger.info("[OK] PostgreSQL existant detecte, installation ignoree")
        return True

    pg_installer = PACKAGE_ROOT / "prerequisites" / "postgresql-18.2-1-windows-x64.exe"
    if not pg_installer.exists():
        logger.error("Installeur PostgreSQL non trouve: %s", pg_installer)
        return False

    pg_data_dir = install_dir / "pgsql" / "data"
    pg_install_dir = install_dir / "pgsql"

    logger.info("Installation de PostgreSQL (silencieux)...")
    logger.info("  Installeur: %s", pg_installer)
    logger.info("  Destination: %s", pg_install_dir)
    cmd = [
        str(pg_installer),
        "--mode", "unattended",
        "--unattendedmodeui", "none",
        "--prefix", str(pg_install_dir),
        "--datadir", str(pg_data_dir),
        "--superpassword", pg_password,
        "--serverport", "5432",
        "--servicename", "postgresql-q2h",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error("PostgreSQL installation echouee (code %d)", result.returncode)
            # Log both stdout and stderr — EDB installer writes to both
            if result.stdout:
                for line in result.stdout.strip().splitlines()[:20]:
                    logger.error("  stdout: %s", line)
            if result.stderr:
                for line in result.stderr.strip().splitlines()[:20]:
                    logger.error("  stderr: %s", line)
            if not result.stdout and not result.stderr:
                logger.error("  Aucune sortie capturee. Verifiez le log EDB: %s",
                             pg_install_dir / "installation_summary.log")
            return False
        logger.info("[OK] PostgreSQL installe dans %s", pg_install_dir)
        return True
    except subprocess.TimeoutExpired:
        logger.error("PostgreSQL installation timeout (>10 min)")
        return False


def copy_winsw(install_dir: Path, service_name: str = "Qualys2Human",
               logger=None) -> bool:
    """Copy WinSW executable, renamed to match the service name.

    WinSW requires the .exe and .xml to share the same base name.
    """
    src = PACKAGE_ROOT / "prerequisites" / "WinSW-x64.exe"
    if not src.exists():
        logger.error("WinSW non trouve: %s", src)
        return False
    dst = install_dir / f"{service_name}.exe"
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info("[OK] WinSW copie dans %s", dst)
    return True


def generate_tls_cert(install_dir: Path, logger=None) -> bool:
    """Generate a self-signed TLS certificate."""
    certs_dir = install_dir / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)
    cert_file = certs_dir / "server.crt"
    key_file = certs_dir / "server.key"

    if cert_file.exists() and key_file.exists():
        logger.info("[OK] Certificats TLS existants conserves")
        return True

    logger.info("Generation du certificat TLS auto-signe...")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta, timezone

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Qualys2Human"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NeoRed"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        key_file.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        logger.info("[OK] Certificat TLS genere: %s", cert_file)
        return True
    except ImportError:
        pass

    # Fallback: use openssl command line
    try:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key_file), "-out", str(cert_file),
            "-days", "3650", "-subj", "/CN=Qualys2Human/O=NeoRed",
        ], check=True, capture_output=True)
        logger.info("[OK] Certificat TLS genere (openssl): %s", cert_file)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.error("Echec generation certificat TLS: %s", e)
        return False


def run_all(install_dir: Path, server_port: int, pg_password: str,
            service_name: str = "Qualys2Human", logger=None) -> bool:
    """Run all prerequisite checks and installations."""
    if not check_os(logger):
        return False
    if not check_disk_space(install_dir, logger=logger):
        return False
    if not check_port(server_port, logger=logger):
        return False
    if not install_postgresql(install_dir, pg_password, logger=logger):
        return False
    if not copy_winsw(install_dir, service_name=service_name, logger=logger):
        return False
    if not generate_tls_cert(install_dir, logger=logger):
        return False
    return True
