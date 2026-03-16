import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from q2h.api.auth import router as auth_router
from q2h.api.dashboard import router as dashboard_router
from q2h.api.vulnerabilities import router as vuln_router
from q2h.api.hosts import router as hosts_router
from q2h.api.presets import router as presets_router
from q2h.api.trends import router as trends_router
from q2h.api.export import router as export_router
from q2h.api.imports import router as imports_router
from q2h.api.users import router as users_router
from q2h.api.branding import router as branding_router
from q2h.api.monitoring import router as monitoring_router
from q2h.api.preferences import router as preferences_router
from q2h.api.layers import router as layers_router
from q2h.api.settings import router as settings_router
from q2h.api.ldap import router as ldap_router
from q2h.api.search import router as search_router
from q2h.api.watcher import router as watcher_router, set_watcher_service
from q2h.api.proposals import router as proposals_router
from q2h.api.upgrade import router as upgrade_router
from q2h.upgrade import APP_VERSION

logger = logging.getLogger("q2h")


async def _auto_import(filepath: Path):
    """Callback used by the file watcher to import a CSV, with dedup."""
    import q2h.db.engine as db_engine
    from q2h.ingestion.csv_parser import QualysCSVParser
    from q2h.ingestion.importer import QualysImporter
    from q2h.db.models import ScanReport
    from sqlalchemy import select, and_

    # Dedup: parse header and check for matching report
    try:
        parser = QualysCSVParser(filepath)
        meta = parser.parse_header()
    except Exception:
        logger.exception("Failed to parse header for dedup: %s", filepath.name)
        meta = None

    if meta and meta.report_date:
        async with db_engine.SessionLocal() as session:
            conditions = [ScanReport.report_date == meta.report_date]
            if meta.asset_group:
                conditions.append(ScanReport.asset_group == meta.asset_group)
            if meta.total_vulns is not None:
                conditions.append(ScanReport.total_vulns_declared == meta.total_vulns)

            existing = (
                await session.execute(select(ScanReport).where(and_(*conditions)))
            ).scalar_one_or_none()

            if existing:
                logger.warning(
                    "Skipping duplicate report: %s (matches report id=%d, date=%s, group=%s)",
                    filepath.name,
                    existing.id,
                    meta.report_date,
                    meta.asset_group,
                )
                return

    # No duplicate found — proceed with import
    async with db_engine.SessionLocal() as session:
        importer = QualysImporter(session, filepath, source="auto")
        report = await importer.run()
        logger.info("Auto-imported %s — report id=%s", filepath.name, report.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import q2h.db.engine as db_engine
    from q2h.db.seed import seed_defaults
    from q2h.config import get_settings
    from q2h.watcher.service import FileWatcherService

    # Mutual exclusion: stop Updater service if running (Q2H takes over)
    import subprocess as _sp
    try:
        _sp.run(["sc", "stop", "Qualys2Human-Updater"],
                capture_output=True, text=True, timeout=15)
    except Exception:
        pass

    # Ensure Updater service is installed (idempotent — safe to run every startup)
    try:
        from q2h.upgrade.scheduler import ensure_updater_service_installed
        _config_env = os.environ.get("Q2H_CONFIG")
        if _config_env:
            _install = Path(_config_env).parent
        else:
            _install = Path(__file__).parent.parent.parent
        ensure_updater_service_installed(_install)
    except Exception:
        logger.exception("Failed to ensure Updater service is installed")

    db_engine.init_engine()
    async with db_engine.SessionLocal() as session:
        await seed_defaults(session)

    # Ensure materialized view is populated (guards against failed rollbacks/restores)
    async with db_engine.SessionLocal() as session:
        from sqlalchemy import text as _text
        row = (await session.execute(
            _text("SELECT ispopulated FROM pg_matviews WHERE matviewname = 'latest_vulns'")
        )).first()
        if row and not row[0]:
            logger.warning("Materialized view latest_vulns not populated — refreshing...")
            await session.execute(_text("REFRESH MATERIALIZED VIEW latest_vulns"))
            await session.commit()
            logger.info("Materialized view latest_vulns refreshed")

    # Start file watcher (always — idles if no DB paths enabled)
    settings = get_settings()
    watcher = FileWatcherService(
        db_session_factory=db_engine.SessionLocal,
        import_callback=_auto_import,
        poll_interval=settings.watcher.poll_interval,
        stable_seconds=settings.watcher.stable_seconds,
    )
    set_watcher_service(watcher)
    watcher.start()

    # Background purge of expired data (non-blocking)
    import asyncio

    async def _startup_purge():
        from q2h.api.imports import _import_state
        from q2h.services.retention import purge_expired_data

        if _import_state.running:
            logger.info("Import in progress — skipping startup purge")
            return

        try:
            async with db_engine.SessionLocal() as purge_session:
                retention_row = (await purge_session.execute(
                    _text("SELECT value FROM app_settings WHERE key = 'retention_months'")
                )).scalar()
                retention_months = int(retention_row or "24")

                reports_deleted, vulns_deleted = await purge_expired_data(
                    purge_session, retention_months
                )
                if reports_deleted > 0:
                    logger.info(
                        "Startup purge complete: %d reports, %d vulns",
                        reports_deleted, vulns_deleted,
                    )
        except Exception:
            logger.exception("Startup purge failed")

    asyncio.create_task(_startup_purge())

    # Background upgrade scheduler
    from q2h.upgrade.scheduler import upgrade_scheduler_loop
    scheduler_task = asyncio.create_task(upgrade_scheduler_loop(db_engine.SessionLocal))

    # Stale upload cleanup (once at startup)
    from q2h.upgrade.chunked_upload import cleanup_stale_uploads
    cleanup_stale_uploads()

    # Check for interrupted upgrade (power failure during upgrade)
    _config_env_path = os.environ.get("Q2H_CONFIG")
    if _config_env_path:
        _install_dir = Path(_config_env_path).parent
        _status_file = _install_dir / "upgrade-status.json"
        if _status_file.exists():
            import json as _json
            try:
                _status = _json.loads(_status_file.read_text())
                if _status.get("state") == "running":
                    logger.warning(
                        "Detected interrupted upgrade (state=running). "
                        "Manual intervention may be needed."
                    )
                    # Record in upgrade_history
                    async with db_engine.SessionLocal() as _session:
                        from q2h.db.models import UpgradeHistory
                        _session.add(UpgradeHistory(
                            source_version=_status.get("source_version", "unknown"),
                            target_version=_status.get("target_version", "unknown"),
                            started_at=datetime.fromisoformat(
                                _status.get("started_at", datetime.now(timezone.utc).isoformat())
                            ).replace(tzinfo=None),
                            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                            status="failed",
                            error_message="Upgrade interrupted (server rebooted during upgrade)",
                        ))
                        await _session.commit()
                _status_file.unlink(missing_ok=True)
            except Exception:
                logger.exception("Failed to process interrupted upgrade status")

    yield

    scheduler_task.cancel()
    await watcher.stop()
    await db_engine.dispose_engine()


RELEASE_NOTES = {
    "version": APP_VERSION,
    "date": "2026-03-16",
    "title": {
        "fr": "Visibilité widgets + Exclusion mutuelle",
        "en": "Widget Visibility + Mutual Exclusion",
        "es": "Visibilidad widgets + Exclusión mutua",
        "de": "Widget-Sichtbarkeit + Gegenseitiger Ausschluss",
    },
    "features": [
        {
            "fr": "Système de mise à jour via l'interface web (upload, validation, planification, exécution automatique)",
            "en": "Web-based upgrade system (upload, validate, schedule, automatic execution)",
            "es": "Sistema de actualización web (subir, validar, planificar, ejecución automática)",
            "de": "Web-basiertes Upgrade-System (Upload, Validierung, Planung, automatische Ausführung)",
        },
        {
            "fr": "Widget répartition des OS (donut concentrique classe + type)",
            "en": "OS distribution widget (concentric donut class + type)",
            "es": "Widget de distribución de SO (donut concéntrico clase + tipo)",
            "de": "Betriebssystemverteilungs-Widget (konzentrischer Donut Klasse + Typ)",
        },
        {
            "fr": "Barre de progression sur la page Tendances",
            "en": "Progress bar on Trends page",
            "es": "Barra de progreso en la página de Tendencias",
            "de": "Fortschrittsbalken auf der Trends-Seite",
        },
        {
            "fr": "Accès à la page QIDs non catégorisés pour tous les utilisateurs",
            "en": "Uncategorized QIDs page accessible to all users",
            "es": "Página de QIDs sin categorizar accesible para todos",
            "de": "Seite nicht kategorisierter QIDs für alle Benutzer zugänglich",
        },
        {
            "fr": "Suppression de la priorité numérique — les règles les plus récentes sont prioritaires",
            "en": "Numeric priority removed — newest rules take precedence",
            "es": "Prioridad numérica eliminada — las reglas más recientes prevalecen",
            "de": "Numerische Priorität entfernt — neuere Regeln haben Vorrang",
        },
    ],
    "fixes": [],
    "improvements": [],
}

app = FastAPI(title="Qualys2Human", version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    return response


app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(vuln_router)
app.include_router(hosts_router)
app.include_router(presets_router)
app.include_router(trends_router)
app.include_router(export_router)
app.include_router(imports_router)
app.include_router(users_router)
app.include_router(branding_router)
app.include_router(monitoring_router)
app.include_router(preferences_router)
app.include_router(layers_router)
app.include_router(ldap_router)
app.include_router(search_router)
app.include_router(watcher_router)
app.include_router(settings_router)
app.include_router(proposals_router)
app.include_router(upgrade_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/version")
async def get_version():
    from q2h.release_history import RELEASE_NOTES_HISTORY
    return {"current": APP_VERSION, "notes": RELEASE_NOTES_HISTORY}


# --- Serve frontend static files (production) ---
# Resolve frontend dir from Q2H_CONFIG (installed) or relative to source tree (dev)
_config_env = os.environ.get("Q2H_CONFIG")
if _config_env:
    _frontend_dir = Path(_config_env).parent / "app" / "frontend"
else:
    _frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

if _frontend_dir.is_dir():
    # Serve static assets (js, css, images) under /assets
    _assets_dir = _frontend_dir / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    # SPA catch-all: serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Try to serve a file directly (e.g. favicon.ico, manifest.json)
        if full_path:
            file_path = (_frontend_dir / full_path).resolve()
            # Prevent path traversal: resolved path must stay within frontend dir
            if file_path.is_file() and str(file_path).startswith(str(_frontend_dir.resolve())):
                return FileResponse(str(file_path))
        # Otherwise serve index.html for client-side routing
        return FileResponse(str(_frontend_dir / "index.html"))
