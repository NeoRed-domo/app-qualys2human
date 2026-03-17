"""Manage upgrade-status.json -- shared state between service and HTTP server.

Written by the service as it progresses through steps.
Read by the HTTP server to serve GET /upgrade-status.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# Ordered list of upgrade steps (per spec: 6 steps)
STEPS = [
    "backup_database",
    "backup_files",
    "extract_package",
    "run_migrations",
    "refresh_matview",
    "restart_service",
]


class UpgradeStatus:
    """Thread-safe status file writer/reader."""

    def __init__(self, path: Path, source_version: str, target_version: str):
        self._path = path
        self._data = {
            "state": "pending",
            "step": 0,
            "total_steps": len(STEPS),
            "step_label": "",
            "percent": 0,
            "estimated_remaining_minutes": 0,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "source_version": source_version,
            "target_version": target_version,
        }
        self._write()

    def _write(self):
        # Write to temp file then rename for atomic updates (avoids
        # serving partial JSON to the HTTP server reading from another thread)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def read(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def advance(self, step_label: str, estimated_minutes: int = 0):
        """Move to the next step."""
        step_index = STEPS.index(step_label) + 1 if step_label in STEPS else self._data["step"] + 1
        self._data["state"] = "running"
        self._data["step"] = step_index
        self._data["step_label"] = step_label
        self._data["percent"] = int((step_index / len(STEPS)) * 100)
        self._data["estimated_remaining_minutes"] = estimated_minutes
        self._write()

    def complete(self):
        """Mark upgrade as complete."""
        self._data["state"] = "complete"
        self._data["percent"] = 100
        self._data["step"] = len(STEPS)
        self._data["step_label"] = "done"
        self._data["estimated_remaining_minutes"] = 0
        self._write()

    def fail(self, error: str):
        """Mark upgrade as failed."""
        self._data["state"] = "failed"
        self._data["error"] = error
        self._write()
