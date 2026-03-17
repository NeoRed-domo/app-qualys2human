import os
import pytest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from q2h_updater.steps import (
    UpgradeContext,
    StepError,
    backup_database,
    backup_files,
    extract_package,
    run_migrations,
    refresh_matview,
    restart_service,
    rollback,
    _patch_pth,
)


@pytest.fixture
def ctx(tmp_path):
    """Create a minimal UpgradeContext for testing."""
    install_dir = tmp_path / "q2h"
    install_dir.mkdir()
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    package_path = tmp_path / "package.zip"
    package_path.write_bytes(b"fake zip")

    # Create config.yaml
    config_yaml = install_dir / "config.yaml"
    config_yaml.write_text(
        "server:\n  port: 8443\n  tls_cert: ./certs/server.crt\n  tls_key: ./certs/server.key\n"
        "database:\n  host: localhost\n  port: 5432\n  name: qualys2human\n  user: q2h\n  password: test\n",
        encoding="utf-8",
    )
    # Create .env
    (install_dir / ".env").write_text("JWT_SECRET=abc\n", encoding="utf-8")
    # Create dirs that should be backed up
    (install_dir / "certs").mkdir()
    (install_dir / "certs" / "server.crt").write_text("cert")
    (install_dir / "keys").mkdir()
    (install_dir / "keys" / "master.key").write_bytes(b"key")
    (install_dir / "data").mkdir()
    (install_dir / "data" / "logo.svg").write_text("svg")

    from q2h_updater.config import load_yaml_config
    config = load_yaml_config(config_yaml)

    return UpgradeContext(
        install_dir=install_dir,
        config_path=config_yaml,
        package_path=package_path,
        backup_dir=backup_dir,
        config=config,
        logger=MagicMock(),
    )


def test_backup_files(ctx):
    backup_files(ctx)
    assert (ctx.backup_dir / "config.yaml").exists()
    assert (ctx.backup_dir / ".env").exists()
    assert (ctx.backup_dir / "certs" / "server.crt").exists()
    assert (ctx.backup_dir / "keys" / "master.key").exists()
    assert (ctx.backup_dir / "data" / "logo.svg").exists()


@patch("subprocess.run")
def test_backup_database_success(mock_run, ctx):
    mock_run.return_value = MagicMock(returncode=0)
    backup_database(ctx)
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    # Should use pg_dump with correct db name
    cmd = call_args[0][0]
    assert "pg_dump" in str(cmd[0]) or cmd[0] == "pg_dump"
    assert "-d" in cmd
    assert "qualys2human" in cmd


@patch("subprocess.run")
def test_backup_database_failure(mock_run, ctx):
    mock_run.return_value = MagicMock(returncode=1, stderr="connection refused")
    with pytest.raises(StepError, match="pg_dump"):
        backup_database(ctx)


@pytest.fixture
def package_zip(tmp_path):
    """Create a minimal valid upgrade .zip."""
    zip_path = tmp_path / "Qualys2Human-2.0.0.0.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Qualys2Human-2.0.0.0/VERSION", "2.0.0.0")
        zf.writestr("Qualys2Human-2.0.0.0/app/backend/src/q2h/__init__.py", "# v2")
        zf.writestr("Qualys2Human-2.0.0.0/python/python.exe", "fake")
        zf.writestr("Qualys2Human-2.0.0.0/python/python312._pth", ".\nLib\nimport site\n")
        zf.writestr("Qualys2Human-2.0.0.0/updater/q2h_updater/__init__.py", "# v2 updater")
        zf.writestr("Qualys2Human-2.0.0.0/data/logo-default.svg", "<svg/>")
    return zip_path


def test_extract_package(ctx, package_zip):
    # Create existing dirs to be replaced
    (ctx.install_dir / "app").mkdir(parents=True)
    (ctx.install_dir / "app" / "old_file.txt").write_text("old")
    (ctx.install_dir / "python").mkdir(parents=True)
    (ctx.install_dir / "python" / "python312._pth").write_text(".\nLib\nimport site\n")

    ctx.package_path = package_zip
    extract_package(ctx)

    # app/ replaced
    assert not (ctx.install_dir / "app" / "old_file.txt").exists()
    assert (ctx.install_dir / "app" / "backend" / "src" / "q2h" / "__init__.py").exists()
    # python/ replaced
    assert (ctx.install_dir / "python" / "python.exe").exists()
    # updater/ replaced
    assert (ctx.install_dir / "updater" / "q2h_updater" / "__init__.py").exists()
    # ._pth patched
    pth_content = (ctx.install_dir / "python" / "python312._pth").read_text()
    assert "..\\app\\backend\\src" in pth_content
    # data/ merged (existing preserved, new added)
    assert (ctx.install_dir / "data" / "logo.svg").exists()  # original preserved
    assert (ctx.install_dir / "data" / "logo-default.svg").exists()  # new added


def test_patch_pth(tmp_path):
    pth = tmp_path / "python312._pth"
    pth.write_text(".\nLib\nimport site\n", encoding="utf-8")
    _patch_pth(tmp_path, MagicMock())
    content = pth.read_text()
    assert content.startswith("..\\app\\backend\\src\n")


@patch("subprocess.run")
def test_run_migrations_success(mock_run, ctx):
    mock_run.return_value = MagicMock(returncode=0)
    run_migrations(ctx)
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "alembic" in cmd
    env = call_args[1].get("env") or call_args.kwargs.get("env")
    assert "Q2H_DATABASE_URL" in env
    assert "Q2H_CONFIG" in env


@patch("subprocess.run")
def test_run_migrations_failure(mock_run, ctx):
    mock_run.return_value = MagicMock(returncode=1, stderr="migration error", stdout="")
    with pytest.raises(StepError, match="Migration"):
        run_migrations(ctx)


def test_rollback_restores_files(ctx):
    # Setup: backup has config.yaml, original was replaced
    (ctx.backup_dir / "config.yaml").write_text("original config", encoding="utf-8")
    (ctx.backup_dir / "certs").mkdir()
    (ctx.backup_dir / "certs" / "server.crt").write_text("original cert")
    (ctx.install_dir / "config.yaml").write_text("new config", encoding="utf-8")

    rollback(ctx)

    assert (ctx.install_dir / "config.yaml").read_text() == "original config"
    assert (ctx.install_dir / "certs" / "server.crt").read_text() == "original cert"
