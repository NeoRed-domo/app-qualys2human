import hashlib
import hmac
import json
import pytest
from pathlib import Path

from q2h_updater.request import read_upgrade_request, VerificationError


def _write_request(path: Path, payload: dict, secret: str):
    """Helper: write a valid upgrade-request.json."""
    payload_json = json.dumps(payload, sort_keys=True)
    mac = hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    path.write_text(json.dumps({"payload": payload, "hmac": mac}, indent=2))


@pytest.fixture
def valid_request(tmp_path):
    payload = {
        "install_dir": str(tmp_path),
        "config_path": str(tmp_path / "config.yaml"),
        "package_path": str(tmp_path / "package.zip"),
        "backup_dir": str(tmp_path / "backups" / "20260314"),
        "requested_at": "2026-03-14T10:00:00+00:00",
    }
    req_path = tmp_path / "upgrade-request.json"
    _write_request(req_path, payload, "test-secret")
    return req_path, payload


def test_read_valid_request(valid_request):
    req_path, expected_payload = valid_request
    result = read_upgrade_request(req_path, jwt_secret="test-secret")
    assert result["install_dir"] == expected_payload["install_dir"]
    assert result["package_path"] == expected_payload["package_path"]
    # File should be deleted after read
    assert not req_path.exists()


def test_read_request_bad_hmac(valid_request):
    req_path, _ = valid_request
    with pytest.raises(VerificationError, match="HMAC"):
        read_upgrade_request(req_path, jwt_secret="wrong-secret")
    # File should still be deleted even on failure
    assert not req_path.exists()


def test_read_request_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_upgrade_request(tmp_path / "nonexistent.json", jwt_secret="x")


def test_read_request_corrupted_json(tmp_path):
    req_path = tmp_path / "upgrade-request.json"
    req_path.write_text("not json at all")
    with pytest.raises(VerificationError):
        read_upgrade_request(req_path, jwt_secret="x")
