"""Import management API — history, manual upload, progress."""

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, func, desc, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.engine import get_db
from q2h.db.models import (
    ImportJob,
    ScanReport,
    Vulnerability,
    ReportCoherenceCheck,
    Host,
)
from q2h.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/imports", tags=["imports"])


# In-memory import state (covers the gap before ImportJob is created in DB)
class _ImportState:
    running: bool = False
    filename: str = ""

_import_state = _ImportState()


class ImportJobResponse(BaseModel):
    id: int
    scan_report_id: int
    filename: str
    source: str
    report_date: str | None
    status: str
    progress: int
    rows_processed: int
    rows_total: int
    started_at: str | None
    ended_at: str | None
    error_message: str | None


class ImportListResponse(BaseModel):
    items: list[ImportJobResponse]
    total: int


class ImportUploadResponse(BaseModel):
    started: bool
    message: str


@router.get("", response_model=ImportListResponse)
async def list_imports(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List import history with pagination, most recent first."""
    offset = (page - 1) * page_size

    count_q = select(func.count()).select_from(ImportJob)
    total = (await db.execute(count_q)).scalar()

    q = (
        select(ImportJob, ScanReport.filename, ScanReport.source, ScanReport.report_date)
        .join(ScanReport, ImportJob.scan_report_id == ScanReport.id)
        .order_by(desc(ImportJob.id))
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()

    items = []
    for job, filename, source, report_date in rows:
        items.append(ImportJobResponse(
            id=job.id,
            scan_report_id=job.scan_report_id,
            filename=filename,
            source=source,
            report_date=str(report_date) if report_date else None,
            status=job.status,
            progress=job.progress,
            rows_processed=job.rows_processed,
            rows_total=job.rows_total,
            started_at=str(job.started_at) if job.started_at else None,
            ended_at=str(job.ended_at) if job.ended_at else None,
            error_message=job.error_message,
        ))

    return ImportListResponse(items=items, total=total)


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get status of a single import job."""
    q = (
        select(ImportJob, ScanReport.filename, ScanReport.source, ScanReport.report_date)
        .join(ScanReport, ImportJob.scan_report_id == ScanReport.id)
        .where(ImportJob.id == job_id)
    )
    row = (await db.execute(q)).first()
    if not row:
        raise HTTPException(404, "Import job not found")

    job, filename, source, report_date = row
    return ImportJobResponse(
        id=job.id,
        scan_report_id=job.scan_report_id,
        filename=filename,
        source=source,
        report_date=str(report_date) if report_date else None,
        status=job.status,
        progress=job.progress,
        rows_processed=job.rows_processed,
        rows_total=job.rows_total,
        started_at=str(job.started_at) if job.started_at else None,
        ended_at=str(job.ended_at) if job.ended_at else None,
        error_message=job.error_message,
    )


async def _run_import(filepath: Path):
    """Background task that runs a CSV import with its own session."""
    import q2h.db.engine as db_engine
    from q2h.ingestion.importer import QualysImporter

    try:
        async with db_engine.SessionLocal() as session:
            importer = QualysImporter(session, filepath, source="manual")
            await importer.run()
            logger.info("Background import completed: %s", filepath.name)
    except Exception:
        logger.exception("Background import failed: %s", filepath.name)
    finally:
        _import_state.running = False
        _import_state.filename = ""
        try:
            filepath.unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    """Upload a Qualys CSV and trigger import in the background."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    tmp_dir = Path(tempfile.gettempdir()) / "q2h_uploads"
    tmp_dir.mkdir(exist_ok=True)
    # Use UUID filename to prevent path traversal via user-controlled filename
    safe_name = f"{uuid.uuid4().hex}.csv"
    tmp_path = tmp_dir / safe_name
    tmp_path.write_bytes(content)

    _import_state.running = True
    _import_state.filename = file.filename or ""
    asyncio.create_task(_run_import(tmp_path))
    return ImportUploadResponse(started=True, message="IMPORT_STARTED")


@router.delete("/reset-all", status_code=204)
async def reset_all(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Delete ALL data: vulnerabilities, jobs, coherence checks, reports, hosts."""
    await db.execute(delete(Vulnerability))
    await db.execute(delete(ImportJob))
    await db.execute(delete(ReportCoherenceCheck))
    await db.execute(delete(ScanReport))
    await db.execute(delete(Host))
    await db.commit()
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"))
    await db.commit()
    # Clear trend snapshots (all data deleted)
    await db.execute(text("DELETE FROM trend_snapshots"))
    await db.commit()
    return Response(status_code=204)


@router.delete("/report/{report_id}", status_code=204)
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Delete a single report and its associated data (vulns, jobs, checks).

    Hosts are NOT deleted (shared across reports).
    """
    report = (
        await db.execute(select(ScanReport).where(ScanReport.id == report_id))
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(404, "Report not found")

    # Block deletion while import is in progress
    active_job = (
        await db.execute(
            select(ImportJob).where(
                ImportJob.scan_report_id == report_id,
                ImportJob.status == "processing",
            )
        )
    ).scalar_one_or_none()
    if active_job:
        raise HTTPException(409, "Cannot delete report while import is in progress")

    await db.execute(
        delete(Vulnerability).where(Vulnerability.scan_report_id == report_id)
    )
    await db.execute(
        delete(ImportJob).where(ImportJob.scan_report_id == report_id)
    )
    await db.execute(
        delete(ReportCoherenceCheck).where(
            ReportCoherenceCheck.scan_report_id == report_id
        )
    )
    await db.execute(delete(ScanReport).where(ScanReport.id == report_id))
    await db.commit()
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns"))
    await db.commit()
    # Recompute trend snapshots (report deleted — full recompute is safest)
    from q2h.services.trend_snapshots import recompute_all_snapshots
    await recompute_all_snapshots(db)
    return Response(status_code=204)
