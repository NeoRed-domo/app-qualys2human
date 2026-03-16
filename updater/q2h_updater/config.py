"""Read config.yaml and .env without PyYAML dependency.

Standalone -- no dependency on Q2H code. Same parsing logic as
installer/utils.py:load_config but with additional helpers.
"""

from pathlib import Path


def load_yaml_config(path: Path) -> dict:
    """Parse simple 2-level YAML (flat sections with key: value pairs).

    Handles the Q2H config.yaml format. Integer values are auto-cast.
    """
    config: dict = {}
    current_section: dict | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
                val = int(val)
            except (ValueError, TypeError):
                pass
            current_section[key.strip()] = val
    return config


def load_env(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Returns empty dict if file missing."""
    if not path.exists():
        return {}
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def resolve_tls_paths(config: dict, install_dir: Path) -> tuple[Path, Path]:
    """Resolve TLS cert/key paths relative to install_dir."""
    server = config.get("server", {})
    cert_rel = server.get("tls_cert", "./certs/server.crt")
    key_rel = server.get("tls_key", "./certs/server.key")
    # Normalize ./path to path
    if cert_rel.startswith("./"):
        cert_rel = cert_rel[2:]
    if key_rel.startswith("./"):
        key_rel = key_rel[2:]
    return install_dir / cert_rel, install_dir / key_rel


def build_db_url(config: dict) -> str:
    """Build a psycopg2 database URL from config.yaml database section."""
    db = config.get("database", {})
    return (
        f"postgresql://{db.get('user', 'q2h')}:"
        f"{db.get('password', '')}@"
        f"{db.get('host', 'localhost')}:{db.get('port', 5432)}/"
        f"{db.get('name', 'qualys2human')}"
    )


def build_alembic_db_url(config: dict) -> str:
    """Build a psycopg2 database URL for Alembic (requires +psycopg2 driver)."""
    db = config.get("database", {})
    return (
        f"postgresql+psycopg2://{db.get('user', 'q2h')}:"
        f"{db.get('password', '')}@"
        f"{db.get('host', 'localhost')}:{db.get('port', 5432)}/"
        f"{db.get('name', 'qualys2human')}"
    )
