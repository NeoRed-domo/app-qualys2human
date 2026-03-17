import json
import pytest
from pathlib import Path

from q2h_updater.status import UpgradeStatus, STEPS


def test_initial_status(tmp_path):
    status = UpgradeStatus(tmp_path / "upgrade-status.json", "1.1.11.1", "1.2.0.0")
    data = status.read()
    assert data["state"] == "pending"
    assert data["step"] == 0
    assert data["total_steps"] == len(STEPS)
    assert data["source_version"] == "1.1.11.1"
    assert data["target_version"] == "1.2.0.0"


def test_advance_step(tmp_path):
    status = UpgradeStatus(tmp_path / "upgrade-status.json", "1.0.0.0", "2.0.0.0")
    status.advance("backup_database", estimated_minutes=5)
    data = status.read()
    assert data["state"] == "running"
    assert data["step"] == 1
    assert data["step_label"] == "backup_database"
    assert data["estimated_remaining_minutes"] == 5


def test_complete(tmp_path):
    status = UpgradeStatus(tmp_path / "upgrade-status.json", "1.0.0.0", "2.0.0.0")
    status.complete()
    data = status.read()
    assert data["state"] == "complete"
    assert data["percent"] == 100


def test_fail(tmp_path):
    status = UpgradeStatus(tmp_path / "upgrade-status.json", "1.0.0.0", "2.0.0.0")
    status.advance("extract_package", estimated_minutes=2)
    status.fail("Zip extraction failed: corrupted archive")
    data = status.read()
    assert data["state"] == "failed"
    assert "corrupted" in data["error"]


def test_step_list_matches_spec():
    # Spec defines 6 steps (per upgrade-status.json section)
    assert len(STEPS) == 6
    assert STEPS[0] == "backup_database"
    assert STEPS[-1] == "restart_service"
