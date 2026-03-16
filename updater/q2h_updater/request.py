"""Read and verify HMAC-signed upgrade-request.json.

The Q2H scheduler writes this file before starting the Updater.
Format: {"payload": {install_dir, config_path, package_path, backup_dir, requested_at}, "hmac": "<sha256>"}
HMAC key = JWT_SECRET from .env.
"""

import hashlib
import hmac
import json
from pathlib import Path


class VerificationError(Exception):
    """Raised when upgrade-request.json fails verification."""


def read_upgrade_request(path: Path, jwt_secret: str) -> dict:
    """Read, verify, and delete upgrade-request.json.

    Returns the payload dict on success.
    Raises FileNotFoundError if file missing.
    Raises VerificationError if HMAC invalid or JSON corrupted.
    Always deletes the file after read (even on failure).
    """
    raw = path.read_text(encoding="utf-8")

    # Always delete after read (security: single-use channel)
    path.unlink(missing_ok=True)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise VerificationError(f"Corrupted JSON: {e}") from e

    payload = data.get("payload")
    expected_mac = data.get("hmac")
    if not payload or not expected_mac:
        raise VerificationError("Missing payload or hmac field")

    # Recompute HMAC (same algorithm as scheduler.py)
    payload_json = json.dumps(payload, sort_keys=True)
    actual_mac = hmac.new(
        jwt_secret.encode(), payload_json.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(actual_mac, expected_mac):
        raise VerificationError("HMAC verification failed -- request tampered or wrong secret")

    return payload
