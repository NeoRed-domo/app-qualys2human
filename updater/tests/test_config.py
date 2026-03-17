import pytest
from pathlib import Path

from q2h_updater.config import load_yaml_config, load_env, resolve_tls_paths


@pytest.fixture
def config_dir(tmp_path):
    """Create a minimal config.yaml and .env."""
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(
        "server:\n"
        "  host: 0.0.0.0\n"
        "  port: 8443\n"
        "  tls_cert: ./certs/server.crt\n"
        "  tls_key: ./certs/server.key\n"
        "database:\n"
        "  host: localhost\n"
        "  port: 5432\n"
        "  name: qualys2human\n"
        "  user: q2h\n"
        "  password: s3cret\n",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text("JWT_SECRET=abc123\nOTHER=ignored\n", encoding="utf-8")
    return tmp_path


def test_load_yaml_config(config_dir):
    cfg = load_yaml_config(config_dir / "config.yaml")
    assert cfg["server"]["port"] == 8443
    assert cfg["database"]["user"] == "q2h"
    assert cfg["database"]["password"] == "s3cret"


def test_load_env(config_dir):
    env = load_env(config_dir / ".env")
    assert env["JWT_SECRET"] == "abc123"
    assert env.get("OTHER") == "ignored"


def test_load_env_missing_file(tmp_path):
    env = load_env(tmp_path / "nonexistent.env")
    assert env == {}


def test_resolve_tls_paths(config_dir):
    cfg = load_yaml_config(config_dir / "config.yaml")
    cert, key = resolve_tls_paths(cfg, config_dir)
    assert cert == config_dir / "certs" / "server.crt"
    assert key == config_dir / "certs" / "server.key"
