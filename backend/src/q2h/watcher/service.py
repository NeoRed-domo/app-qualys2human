"""File watcher service — monitors DB-configured directories for new Qualys CSV files."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

logger = logging.getLogger("q2h.watcher")


class FileWatcherService:
    """Polls DB-configured paths for new CSV files and triggers import."""

    def __init__(
        self,
        db_session_factory,
        import_callback,
        poll_interval: int = 10,
        stable_seconds: int = 5,
    ):
        """
        Args:
            db_session_factory: async_sessionmaker that yields AsyncSession.
            import_callback: async callable(filepath: Path) that performs the import.
            poll_interval: seconds between poll cycles.
            stable_seconds: wait time to check file has stopped growing.
        """
        self.db_session_factory = db_session_factory
        self.import_callback = import_callback
        self.poll_interval = poll_interval
        self.stable_seconds = stable_seconds
        self._known_files: dict[str, float] = {}  # path -> last-seen mtime
        self._running = False
        self._task: asyncio.Task | None = None
        # Activity tracking for UI feedback
        self._scanning = False
        self._importing: str | None = None
        self._last_import: str | None = None
        self._last_error: str | None = None
        self._import_count: int = 0

    async def _load_paths_from_db(self) -> list[tuple[str, str, bool, datetime | None]]:
        """Query watch_paths WHERE enabled=True. Returns list of (path, pattern, recursive, ignore_before)."""
        from q2h.db.models import WatchPath

        async with self.db_session_factory() as session:
            result = await session.execute(
                select(WatchPath.path, WatchPath.pattern, WatchPath.recursive, WatchPath.ignore_before)
                .where(WatchPath.enabled.is_(True))
            )
            return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    def start(self) -> asyncio.Task:
        """Start the watcher loop as a background asyncio task."""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("File watcher started")
        return self._task

    def rescan(self):
        """Clear known files — next poll cycle will rediscover and import missing files.

        Files already in DB are protected by dedup in _auto_import (main.py).
        """
        count = len(self._known_files)
        self._known_files.clear()
        logger.info("Rescan triggered: cleared %d known files — will rediscover on next poll", count)

    async def stop(self):
        """Stop the watcher loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("File watcher stopped")

    async def _poll_loop(self):
        """Main loop: scan directories every poll_interval seconds."""
        # Initial scan — populate known files without triggering imports
        await self._initial_scan()

        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)
                if not self._running:
                    break
                await self._scan_directories()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in watcher poll loop")
                await asyncio.sleep(self.poll_interval)

    async def _initial_scan(self):
        """Record all existing CSV files so we don't re-import on startup."""
        watch_paths = await self._load_paths_from_db()
        if not watch_paths:
            logger.info("No watch paths configured — watcher idle")
            return

        for watch_path, pattern, recursive, ignore_before in watch_paths:
            p = Path(watch_path)
            if not p.exists():
                logger.warning("Watch path does not exist: %s", watch_path)
                continue
            matches = p.rglob(pattern) if recursive else p.glob(pattern)
            for csv_file in matches:
                try:
                    file_mtime = csv_file.stat().st_mtime
                    if ignore_before:
                        if datetime.fromtimestamp(file_mtime) < ignore_before:
                            continue
                    key = str(csv_file.resolve())
                    self._known_files[key] = file_mtime
                except OSError:
                    pass

        logger.info(
            "Initial scan: %d existing file(s) registered across %d path(s)",
            len(self._known_files),
            len(watch_paths),
        )

    async def _scan_directories(self):
        """Look for new or modified files in watched directories."""
        self._scanning = True
        try:
            await self._do_scan()
        finally:
            self._scanning = False

    async def _do_scan(self):
        """Inner scan logic — separated so _scanning flag is always cleared."""
        watch_paths = await self._load_paths_from_db()
        for watch_path, pattern, recursive, ignore_before in watch_paths:
            p = Path(watch_path)
            if not p.exists():
                continue
            matches = p.rglob(pattern) if recursive else p.glob(pattern)
            for csv_file in matches:
                try:
                    key = str(csv_file.resolve())
                    current_mtime = csv_file.stat().st_mtime
                except OSError:
                    continue

                # Skip files older than ignore_before threshold
                if ignore_before:
                    try:
                        if datetime.fromtimestamp(current_mtime) < ignore_before:
                            continue
                    except OSError:
                        continue

                prev_mtime = self._known_files.get(key)
                if prev_mtime is not None and current_mtime == prev_mtime:
                    continue  # unchanged

                # New or modified file — check if it's stable (finished writing)
                if not await self._is_stable(csv_file):
                    continue

                self._known_files[key] = current_mtime

                if prev_mtime is None:
                    logger.info("New file detected: %s", csv_file.name)
                else:
                    logger.info("Modified file detected: %s", csv_file.name)

                self._importing = csv_file.name
                try:
                    await self.import_callback(csv_file)
                    logger.info("Import completed: %s", csv_file.name)
                    self._last_import = csv_file.name
                    self._last_error = None
                    self._import_count += 1
                except Exception:
                    logger.exception("Import failed: %s", csv_file.name)
                    self._last_error = csv_file.name
                finally:
                    self._importing = None

    async def _is_stable(self, filepath: Path) -> bool:
        """Check if the file has stopped growing (writer finished)."""
        try:
            size1 = filepath.stat().st_size
            await asyncio.sleep(self.stable_seconds)
            size2 = filepath.stat().st_size
            return size1 == size2 and size2 > 0
        except OSError:
            return False
