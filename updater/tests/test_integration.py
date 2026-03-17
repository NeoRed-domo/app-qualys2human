# updater/tests/test_integration.py
"""Integration test: simulate upgrade flow without real services."""

import hashlib
import hmac
import json
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from q2h_updater.config import load_yaml_config, load_env
from q2h_updater.request import read_upgrade_request
from q2h_updater.status import UpgradeStatus, STEPS
from q2h_updater.steps import (
    UpgradeContext, backup_files, extract_package, rollback, _patch_pth,
)


@pytest.fixture
def fake_install(tmp_path):
    """Create a complete fake installation directory."""
    install_dir = tmp_path / "Q2H"
    install_dir.mkdir()

    # config.yaml
    (install_dir / "config.yaml").write_text(
        "server:\n  host: 0.0.0.0\n  port: 8443\n"
        "  tls_cert: ./certs/server.crt\n  tls_key: ./certs/server.key\n"
        "database:\n  host: localhost\n  port: 5432\n"
        "  name: qualys2human\n  user: q2h\n  password: test123\n",
        encoding="utf-8",
    )

    # .env
    (install_dir / ".env").write_text("JWT_SECRET=test-secret-123\n", encoding="utf-8")

    # Dirs
    (install_dir / "certs").mkdir()
    (install_dir / "certs" / "server.crt").write_text("cert-data")
    (install_dir / "certs" / "server.key").write_text("key-data")
    (install_dir / "keys").mkdir()
    (install_dir / "keys" / "master.key").write_bytes(b"key")
    (install_dir / "data").mkdir()
    (install_dir / "data" / "logo-custom.svg").write_text("<svg>custom</svg>")
    (install_dir / "app" / "backend" / "src" / "q2h" / "upgrade").mkdir(parents=True)
    (install_dir / "app" / "backend" / "src" / "q2h" / "upgrade" / "__init__.py").write_text(
        'APP_VERSION = "1.1.11.1"\n'
    )
    (install_dir / "python").mkdir()
    (install_dir / "python" / "python312._pth").write_text(".\nLib\nimport site\n")

    # Create upgrade package (.zip)
    package = tmp_path / "Qualys2Human-2.0.0.0.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("Qualys2Human-2.0.0.0/VERSION", "2.0.0.0")
        zf.writestr("Qualys2Human-2.0.0.0/app/backend/src/q2h/__init__.py", "# v2")
        zf.writestr("Qualys2Human-2.0.0.0/python/python.exe", "fake-exe")
        zf.writestr("Qualys2Human-2.0.0.0/python/python312._pth", ".\nLib\nimport site\n")
        zf.writestr("Qualys2Human-2.0.0.0/data/new-asset.txt", "new")
        zf.writestr("Qualys2Human-2.0.0.0/updater/q2h_updater/__init__.py", "# v2")

    # Create upgrade-request.json
    backup_dir = install_dir / "backups" / "20260314"
    backup_dir.mkdir(parents=True)
    payload = {
        "install_dir": str(install_dir),
        "config_path": str(install_dir / "config.yaml"),
        "package_path": str(package),
        "backup_dir": str(backup_dir),
        "requested_at": "2026-03-14T10:00:00+00:00",
    }
    payload_json = json.dumps(payload, sort_keys=True)
    mac = hmac.new(b"test-secret-123", payload_json.encode(), hashlib.sha256).hexdigest()
    (install_dir / "upgrade-request.json").write_text(
        json.dumps({"payload": payload, "hmac": mac}, indent=2)
    )

    return install_dir, package, backup_dir


def test_full_flow_request_to_extract(fake_install):
    """Test: read request -> backup files -> extract package -> verify."""
    install_dir, package, backup_dir = fake_install

    # 1. Read request
    env = load_env(install_dir / ".env")
    payload = read_upgrade_request(
        install_dir / "upgrade-request.json",
        jwt_secret=env["JWT_SECRET"],
    )
    assert payload["install_dir"] == str(install_dir)

    # 2. Backup files
    config = load_yaml_config(install_dir / "config.yaml")
    ctx = UpgradeContext(
        install_dir=install_dir,
        config_path=install_dir / "config.yaml",
        package_path=package,
        backup_dir=backup_dir,
        config=config,
        logger=MagicMock(),
    )
    backup_files(ctx)
    assert (backup_dir / "config.yaml").exists()
    assert (backup_dir / "certs" / "server.crt").exists()

    # 3. Extract package
    extract_package(ctx)
    assert (install_dir / "app" / "backend" / "src" / "q2h" / "__init__.py").exists()
    # Custom files preserved
    assert (install_dir / "data" / "logo-custom.svg").exists()
    # New files added
    assert (install_dir / "data" / "new-asset.txt").exists()
    # ._pth patched
    pth = (install_dir / "python" / "python312._pth").read_text()
    assert "..\\app\\backend\\src" in pth

    # 4. Rollback
    rollback(ctx)
    assert (install_dir / "config.yaml").read_text(encoding="utf-8").startswith("server:")
    assert (install_dir / "certs" / "server.crt").read_text() == "cert-data"


def test_status_lifecycle(tmp_path):
    """Test status file lifecycle: pending -> running -> complete."""
    status = UpgradeStatus(tmp_path / "status.json", "1.0.0.0", "2.0.0.0")
    assert status.read()["state"] == "pending"

    for step in STEPS:
        status.advance(step, estimated_minutes=3)
        data = status.read()
        assert data["state"] == "running"
        assert data["step_label"] == step

    status.complete()
    assert status.read()["state"] == "complete"
    assert status.read()["percent"] == 100
