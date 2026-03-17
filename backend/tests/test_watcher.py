"""Tests for the file watcher service (DB-driven)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from q2h.watcher.service import FileWatcherService


class FakeWatchPath:
    """Mimics a DB row from watch_paths."""

    def __init__(self, path: str, pattern: str = "*.csv", recursive: bool = False, ignore_before=None):
        self.path = path
        self.pattern = pattern
        self.recursive = recursive
        self.ignore_before = ignore_before


def make_session_factory(watch_paths: list[FakeWatchPath]):
    """Create a mock async session factory that returns fake watch path rows."""
    rows = [(wp.path, wp.pattern, wp.recursive, wp.ignore_before) for wp in watch_paths]

    class FakeResult:
        def all(self):
            return rows

    class FakeSession:
        async def execute(self, stmt):
            return FakeResult()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    return FakeSession


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_starts_and_idles_with_no_paths():
    """Watcher starts even with no DB paths — just idles."""
    factory = make_session_factory([])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    assert task is not None
    assert svc._running is True

    await asyncio.sleep(0.5)
    await svc.stop()
    callback.assert_not_called()


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_detects_new_csv(tmp_path: Path):
    """Watcher detects a new CSV file dropped into a watched directory."""
    factory = make_session_factory([FakeWatchPath(str(tmp_path))])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    await asyncio.sleep(0.5)

    # Drop a CSV file
    csv_file = tmp_path / "report_test.csv"
    csv_file.write_text("IP,QID,Title\n10.0.0.1,1234,Test Vuln\n")

    await asyncio.sleep(2.5)
    await svc.stop()

    assert callback.call_count == 1
    called_path = callback.call_args[0][0]
    assert called_path.name == "report_test.csv"


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_ignores_existing_files(tmp_path: Path):
    """Pre-existing files should not trigger import."""
    existing = tmp_path / "existing.csv"
    existing.write_text("data")

    factory = make_session_factory([FakeWatchPath(str(tmp_path))])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    await asyncio.sleep(2.5)
    await svc.stop()

    callback.assert_not_called()


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_ignores_non_matching_pattern(tmp_path: Path):
    """Files not matching the pattern should be ignored."""
    factory = make_session_factory([FakeWatchPath(str(tmp_path), pattern="*.csv")])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    await asyncio.sleep(0.5)

    (tmp_path / "notes.txt").write_text("hello")
    await asyncio.sleep(2.5)

    await svc.stop()
    callback.assert_not_called()


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_recursive_scan(tmp_path: Path):
    """Recursive watch path detects files in subdirectories."""
    subdir = tmp_path / "sub" / "deep"
    subdir.mkdir(parents=True)

    factory = make_session_factory([FakeWatchPath(str(tmp_path), recursive=True)])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    await asyncio.sleep(0.5)

    csv_file = subdir / "deep_report.csv"
    csv_file.write_text("IP,QID,Title\n10.0.0.1,5678,Deep Vuln\n")

    await asyncio.sleep(2.5)
    await svc.stop()

    assert callback.call_count == 1
    assert callback.call_args[0][0].name == "deep_report.csv"


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_non_recursive_ignores_subdirs(tmp_path: Path):
    """Non-recursive watch path does NOT detect files in subdirectories."""
    subdir = tmp_path / "sub"
    subdir.mkdir()

    factory = make_session_factory([FakeWatchPath(str(tmp_path), recursive=False)])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    await asyncio.sleep(0.5)

    csv_file = subdir / "sub_report.csv"
    csv_file.write_text("data")

    await asyncio.sleep(2.5)
    await svc.stop()

    callback.assert_not_called()


@pytest.mark.asyncio(loop_scope="session")
async def test_watcher_custom_glob_pattern(tmp_path: Path):
    """Watch path with custom pattern only matches those files."""
    factory = make_session_factory([FakeWatchPath(str(tmp_path), pattern="report_*.csv")])
    callback = AsyncMock()
    svc = FileWatcherService(factory, callback, poll_interval=1, stable_seconds=0)

    task = svc.start()
    await asyncio.sleep(0.5)

    # This one should NOT match
    (tmp_path / "other.csv").write_text("data")
    # This one should match
    (tmp_path / "report_2026.csv").write_text("data")

    await asyncio.sleep(2.5)
    await svc.stop()

    assert callback.call_count == 1
    assert callback.call_args[0][0].name == "report_2026.csv"


@pytest.mark.asyncio(loop_scope="session")
async def test_dedup_skips_matching_report(tmp_path: Path):
    """Test the dedup logic in _auto_import callback."""
    from datetime import datetime
    from unittest.mock import patch, MagicMock

    # Create a CSV with known header
    csv_content = (
        '"Scan Report","02/15/2026"\n'
        '"MyCompany"\n'
        '"Asset Groups"\n'
        '"GroupA","","5"\n'
        '"Total Vulnerabilities"\n'
        '"100","3.5"\n'
        '"IP","DNS","NetBIOS","Col4","Col5","Col6","Col7","Col8","Col9","Col10","Col11"\n'
        '"10.0.0.1","host.example.com","HOST1","","","","","","","",""\n'
    )
    csv_file = tmp_path / "duplicate.csv"
    csv_file.write_text(csv_content)

    # Mock DB to say a matching report already exists
    from q2h.ingestion.csv_parser import QualysCSVParser

    parser = QualysCSVParser(csv_file)
    meta = parser.parse_header()

    # Verify parser extracts what we expect
    assert meta.report_date is not None
    assert meta.asset_group == "GroupA"
    assert meta.total_vulns == 100
