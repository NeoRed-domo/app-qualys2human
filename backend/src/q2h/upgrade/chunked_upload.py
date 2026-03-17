"""Chunked file upload manager for upgrade packages.

Handles:
- Receiving individual chunks with SHA-256 verification
- Assembling chunks into a single .zip
- Disk space validation
- Automatic cleanup of stale uploads (24h)
"""

import hashlib
import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger("q2h.upgrade")

# In-memory state for the single active upload
_active_upload: dict | None = None


def _get_uploads_dir(install_dir: str | None = None) -> Path:
    """Get or create the uploads temp directory."""
    import os
    if install_dir:
        base = Path(install_dir) / "tmp" / "upgrades"
    else:
        config_path = os.environ.get("Q2H_CONFIG")
        if config_path:
            base = Path(config_path).parent / "tmp" / "upgrades"
        else:
            base = Path(__file__).parent.parent.parent.parent / "tmp" / "upgrades"
    base.mkdir(parents=True, exist_ok=True)
    return base


def check_disk_space(package_size: int, install_dir: str | None = None) -> tuple[bool, int, int]:
    """Check if enough disk space for upgrade (need 3x package size).

    Returns:
        (ok, required_bytes, available_bytes)
    """
    uploads_dir = _get_uploads_dir(install_dir)
    required = package_size * 3
    available = shutil.disk_usage(uploads_dir).free
    return available >= required, required, available


def start_upload(upload_id: str, total_chunks: int, filename: str) -> Path:
    """Initialize a new chunked upload. Cancels any existing upload."""
    global _active_upload

    # Cancel existing upload if any
    if _active_upload and _active_upload["id"] != upload_id:
        cancel_upload(_active_upload["id"])

    upload_dir = _get_uploads_dir() / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    _active_upload = {
        "id": upload_id,
        "dir": upload_dir,
        "total_chunks": total_chunks,
        "received": set(),
        "filename": filename,
        "started_at": time.time(),
    }

    logger.info("Upload started: %s (%d chunks, file=%s)", upload_id, total_chunks, filename)
    return upload_dir


def receive_chunk(
    upload_id: str,
    chunk_index: int,
    chunk_data: bytes,
    checksum: str,
) -> bool:
    """Receive and verify a single chunk.

    Returns True if chunk is valid and saved.
    Raises ValueError if upload not found or checksum mismatch.
    """
    global _active_upload

    if not _active_upload or _active_upload["id"] != upload_id:
        raise ValueError(f"Upload {upload_id} not found or expired")

    # Verify SHA-256 checksum
    actual_hash = hashlib.sha256(chunk_data).hexdigest()
    if actual_hash != checksum:
        raise ValueError(
            f"Chunk {chunk_index} checksum mismatch: expected {checksum}, got {actual_hash}"
        )

    # Write chunk to disk
    chunk_path = _active_upload["dir"] / f"chunk_{chunk_index:06d}"
    chunk_path.write_bytes(chunk_data)
    _active_upload["received"].add(chunk_index)

    return True


def get_upload_status(upload_id: str) -> dict | None:
    """Get status of an upload. Returns None if not found."""
    if not _active_upload or _active_upload["id"] != upload_id:
        return None

    return {
        "upload_id": upload_id,
        "total_chunks": _active_upload["total_chunks"],
        "received_chunks": sorted(_active_upload["received"]),
        "complete": len(_active_upload["received"]) == _active_upload["total_chunks"],
        "filename": _active_upload["filename"],
    }


def is_upload_active() -> bool:
    """Return True if an upload is currently in progress."""
    return _active_upload is not None


def get_active_upload_id() -> str | None:
    """Return the ID of the active upload, or None."""
    return _active_upload["id"] if _active_upload else None


def get_active_upload_dir() -> Path | None:
    """Return the directory of the active upload, or None."""
    return _active_upload["dir"] if _active_upload else None


def assemble_chunks(upload_id: str) -> Path:
    """Assemble all chunks into a single .zip file.

    Returns the path to the assembled .zip.
    Raises ValueError if upload incomplete.
    """
    global _active_upload

    if not _active_upload or _active_upload["id"] != upload_id:
        raise ValueError(f"Upload {upload_id} not found")

    if len(_active_upload["received"]) != _active_upload["total_chunks"]:
        missing = set(range(_active_upload["total_chunks"])) - _active_upload["received"]
        raise ValueError(f"Upload incomplete: missing chunks {sorted(missing)}")

    upload_dir = _active_upload["dir"]
    assembled_path = upload_dir / _active_upload["filename"]

    # Assemble in order
    with open(assembled_path, "wb") as out:
        for i in range(_active_upload["total_chunks"]):
            chunk_path = upload_dir / f"chunk_{i:06d}"
            out.write(chunk_path.read_bytes())

    # Clean up individual chunks
    for i in range(_active_upload["total_chunks"]):
        (upload_dir / f"chunk_{i:06d}").unlink(missing_ok=True)

    logger.info("Assembled %d chunks into %s", _active_upload["total_chunks"], assembled_path)
    return assembled_path


def cancel_upload(upload_id: str):
    """Cancel and clean up an upload."""
    global _active_upload

    upload_dir = _get_uploads_dir() / upload_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    if _active_upload and _active_upload["id"] == upload_id:
        _active_upload = None

    logger.info("Upload cancelled: %s", upload_id)


def cleanup_stale_uploads(max_age_hours: int = 24):
    """Remove upload directories older than max_age_hours."""
    uploads_dir = _get_uploads_dir()
    if not uploads_dir.exists():
        return

    cutoff = time.time() - (max_age_hours * 3600)
    for entry in uploads_dir.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
            logger.info("Cleaned up stale upload: %s", entry.name)
