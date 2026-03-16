"""Installer utilities — logging, prompts, password generation."""

import logging
import os
import secrets
import string
import sys
from pathlib import Path


def setup_logging(log_file: Path | None = None) -> logging.Logger:
    """Configure installer logging to console + optional file."""
    logger = logging.getLogger("q2h.installer")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("[%(levelname)s] %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    return logger


def prompt(message: str, default: str = "", password: bool = False,
           non_interactive: bool = False) -> str:
    """Prompt user for input. In non-interactive mode, return default."""
    if non_interactive:
        return default
    suffix = f" [{default}]" if default and not password else ""
    try:
        if password:
            import getpass
            value = getpass.getpass(f"  {message}: ").strip()
        else:
            value = input(f"  {message}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nInstallation annulee.")
        sys.exit(1)
    return value or default


def prompt_confirm(message: str, default: bool = True,
                   non_interactive: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    if non_interactive:
        return default
    suffix = "[O/n]" if default else "[o/N]"
    try:
        value = input(f"  {message} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nInstallation annulee.")
        sys.exit(1)
    if not value:
        return default
    return value in ("o", "oui", "y", "yes")


def generate_password(length: int = 32, safe: bool = False) -> str:
    """Generate a cryptographically secure random password.

    Args:
        safe: If True, use only alphanumeric chars (safe for CLI arguments).
    """
    if safe:
        alphabet = string.ascii_letters + string.digits
    else:
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_secret(length: int = 64) -> str:
    """Generate a hex secret (for JWT, etc.)."""
    return secrets.token_hex(length // 2)


def check_admin() -> bool:
    """Check if running with administrator privileges (Windows)."""
    if os.name != "nt":
        return os.geteuid() == 0
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def validate_password_strength(password: str) -> str | None:
    """Validate admin password strength. Returns error message or None."""
    if len(password) < 10:
        return "Le mot de passe doit contenir au moins 10 caracteres"
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password)
    if not (has_upper and has_lower and has_digit and has_special):
        return "Le mot de passe doit contenir majuscules, minuscules, chiffres et caracteres speciaux"
    return None


def banner(version: str):
    """Display installer banner."""
    print()
    print("=" * 56)
    print("  Qualys2Human — Installer")
    print(f"  Version: {version}")
    print("  NeoRed (c) 2026")
    print("=" * 56)
    print()


def load_config(path) -> dict:
    """Parse a simple YAML config (2-level max) without PyYAML dependency.

    Works for the Q2H config.yaml format (flat sections with key: value pairs).
    """
    from pathlib import Path
    config: dict = {}
    current_section: dict | None = None
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = raw_line.split("#")[0].rstrip()
        if not stripped:
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        if indent == 0 and ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip().strip("'\"")
            if val:
                config[key.strip()] = val
            else:
                current_section = {}
                config[key.strip()] = current_section
        elif indent >= 2 and current_section is not None and ":" in stripped:
            key, _, val = stripped.strip().partition(":")
            val = val.strip().strip("'\"")
            try:
                val = int(val)  # type: ignore[assignment]
            except (ValueError, TypeError):
                pass
            current_section[key.strip()] = val
    return config
