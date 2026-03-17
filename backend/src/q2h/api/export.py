import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.auth.dependencies import get_current_user, require_data_access
from q2h.db.engine import get_db
from q2h.db.models import LatestVuln, Host, ScanReport

router = APIRouter(prefix="/api/export", tags=["export"])


async def _query_vulns(
    db: AsyncSession,
    severities: Optional[str] = None,
    report_id: Optional[int] = None,
    types: Optional[str] = None,
    ip: Optional[str] = None,
    qid: Optional[int] = None,
    os_classes: Optional[str] = None,
) -> list:
    """Query vulnerabilities with optional filters, returning row dicts."""
    q = (
        select(
            Host.ip,
            Host.dns,
            Host.os,
            LatestVuln.qid,
            LatestVuln.title,
            LatestVuln.severity,
            LatestVuln.type,
            LatestVuln.category,
            LatestVuln.vuln_status,
            LatestVuln.port,
            LatestVuln.protocol,
            LatestVuln.first_detected,
            LatestVuln.last_detected,
            LatestVuln.cvss_base,
            LatestVuln.cvss3_base,
            LatestVuln.tracking_method,
            LatestVuln.threat,
            LatestVuln.impact,
            LatestVuln.solution,
        )
        .join(Host, LatestVuln.host_id == Host.id)
    )
    if severities:
        sev_list = [int(s.strip()) for s in severities.split(",")]
        q = q.where(LatestVuln.severity.in_(sev_list))
    if report_id:
        q = q.where(LatestVuln.scan_report_id == report_id)
    if types:
        type_list = [t.strip() for t in types.split(",")]
        q = q.where(LatestVuln.type.in_(type_list))
    if ip:
        q = q.where(Host.ip == ip)
    if qid:
        q = q.where(LatestVuln.qid == qid)
    if os_classes:
        cls_list = [c.strip().lower() for c in os_classes.split(",")]
        conditions = []
        if "windows" in cls_list:
            conditions.append(Host.os.ilike("%windows%"))
        if "nix" in cls_list:
            conditions.append(or_(
                Host.os.ilike("%linux%"), Host.os.ilike("%unix%"),
                Host.os.ilike("%ubuntu%"), Host.os.ilike("%debian%"),
                Host.os.ilike("%centos%"), Host.os.ilike("%red hat%"),
                Host.os.ilike("%rhel%"), Host.os.ilike("%suse%"),
                Host.os.ilike("%fedora%"), Host.os.ilike("%aix%"),
                Host.os.ilike("%solaris%"), Host.os.ilike("%freebsd%"),
            ))
        if conditions:
            q = q.where(or_(*conditions))
    q = q.order_by(LatestVuln.severity.desc(), Host.ip, LatestVuln.qid)

    result = await db.execute(q)
    return result.all()


CSV_COLUMNS = [
    "IP", "DNS", "OS", "QID", "Title", "Severity", "Type", "Category",
    "Status", "Port", "Protocol", "First Detected", "Last Detected",
    "CVSS Base", "CVSS3 Base", "Tracking Method", "Threat", "Impact", "Solution",
]


@router.get("/csv")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    view: str = Query("overview"),
    severities: Optional[str] = Query(None),
    report_id: Optional[int] = Query(None),
    types: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
    qid: Optional[int] = Query(None),
    os_classes: Optional[str] = Query(None),
):
    rows = await _query_vulns(db, severities, report_id, types, ip, qid, os_classes)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for r in rows:
        writer.writerow([
            r.ip, r.dns, r.os, r.qid, r.title, r.severity, r.type, r.category,
            r.vuln_status, r.port, r.protocol,
            r.first_detected.isoformat() if r.first_detected else "",
            r.last_detected.isoformat() if r.last_detected else "",
            r.cvss_base, r.cvss3_base, r.tracking_method,
            (r.threat or "")[:200], (r.impact or "")[:200], (r.solution or "")[:200],
        ])

    output.seek(0)
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"qualys2human_{view}_{now}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
async def export_pdf(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_data_access),
    view: str = Query("overview"),
    severities: Optional[str] = Query(None),
    report_id: Optional[int] = Query(None),
    types: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
    qid: Optional[int] = Query(None),
    os_classes: Optional[str] = Query(None),
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    rows = await _query_vulns(db, severities, report_id, types, ip, qid, os_classes)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Qualys2Human — Export", styles["Title"]))
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    filters_text = f"View: {view}"
    if severities:
        filters_text += f" | Severities: {severities}"
    if ip:
        filters_text += f" | IP: {ip}"
    if qid:
        filters_text += f" | QID: {qid}"
    elements.append(Paragraph(f"Date: {now} — {filters_text}", styles["Normal"]))
    elements.append(Spacer(1, 10 * mm))

    # Table header
    table_cols = ["IP", "QID", "Title", "Sev.", "Type", "Status", "Port", "CVSS3"]
    table_data = [table_cols]

    for r in rows:
        title_short = (r.title or "")[:40]
        if len(r.title or "") > 40:
            title_short += "..."
        table_data.append([
            r.ip, str(r.qid), title_short, str(r.severity),
            r.type or "", r.vuln_status or "", str(r.port or ""),
            r.cvss3_base or "",
        ])

    if len(table_data) > 1:
        col_widths = [80, 50, 180, 35, 80, 70, 40, 50]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#001529")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d9d9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No data to export.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    now_file = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"qualys2human_{view}_{now_file}.pdf"

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
