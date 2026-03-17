from datetime import datetime, timezone
from pathlib import Path


def _utcnow() -> datetime:
    """Return a naive UTC datetime (required by asyncpg for TIMESTAMP WITHOUT TIME ZONE)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

import polars as pl
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

from q2h.db.models import ScanReport, Host, Vulnerability, ImportJob, ReportCoherenceCheck, VulnLayerRule
from q2h.ingestion.csv_parser import QualysCSVParser


class QualysImporter:
    def __init__(self, session: AsyncSession, filepath: Path, source: str = "manual"):
        self.session = session
        self.filepath = filepath
        self.source = source
        self.parser = QualysCSVParser(filepath)
        self.report: ScanReport | None = None
        self.job: ImportJob | None = None

    async def run(self) -> ScanReport:
        # 1. Parse header
        metadata = self.parser.parse_header()
        host_summaries = self.parser.parse_host_summary()

        # 2. Create scan report record
        self.report = ScanReport(
            filename=self.filepath.name,
            report_date=metadata.report_date,
            asset_group=metadata.asset_group,
            total_vulns_declared=metadata.total_vulns,
            avg_risk_declared=metadata.avg_risk,
            source=self.source,
        )
        self.session.add(self.report)
        await self.session.flush()

        # 3. Create import job
        self.job = ImportJob(
            scan_report_id=self.report.id,
            status="processing",
            started_at=_utcnow(),
        )
        self.session.add(self.job)
        await self.session.flush()

        # 4. Parse detail rows (filter out Qualys footer lines with IP lists)
        self.parser.find_detail_section_start()
        df = self.parser.parse_detail_rows()
        df = df.filter(~pl.col("IP").str.contains(","))
        self.job.rows_total = len(df)

        # 4b. Load layer classification rules
        rules_result = await self.session.execute(
            select(VulnLayerRule).order_by(VulnLayerRule.priority.desc())
        )
        layer_rules = [
            (r.match_field, r.pattern.lower(), r.layer_id)
            for r in rules_result.scalars().all()
        ]

        # 5. Upsert hosts and insert vulnerabilities
        report_date = metadata.report_date or _utcnow()
        host_cache: dict[str, int] = {}  # ip -> host_id
        rows_processed = 0

        for row in df.iter_rows(named=True):
            ip = row.get("IP", "")
            if not ip:
                continue

            # Atomic upsert host with report_date for first_seen/last_seen
            if ip not in host_cache:
                stmt = pg_insert(Host).values(
                    ip=ip,
                    dns=row.get("DNS"),
                    netbios=row.get("NetBIOS"),
                    os=row.get("OS"),
                    os_cpe=row.get("OS CPE"),
                    first_seen=report_date,
                    last_seen=report_date,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ip"],
                    set_={
                        "dns": stmt.excluded.dns,
                        "netbios": stmt.excluded.netbios,
                        "os": stmt.excluded.os,
                        "os_cpe": stmt.excluded.os_cpe,
                        "first_seen": func.least(Host.first_seen, stmt.excluded.first_seen),
                        "last_seen": func.greatest(Host.last_seen, stmt.excluded.last_seen),
                    },
                )
                result = await self.session.execute(stmt.returning(Host.id))
                host_id = result.scalar_one()
                host_cache[ip] = host_id

            host_id = host_cache[ip]

            # Parse fields
            severity = int(row.get("Severity", "0") or "0")
            qid = int(row.get("QID", "0") or "0")
            port_str = row.get("Port", "")
            port = int(port_str) if port_str and port_str.isdigit() else None
            ssl_str = row.get("SSL", "")
            ssl_val = True if ssl_str and "ssl" in ssl_str.lower() else None
            pci_str = row.get("PCI Vuln", "")
            pci_val = pci_str.lower() == "yes" if pci_str else None

            cve_raw = row.get("CVE ID", "")
            cve_list = [c.strip() for c in cve_raw.split(",") if c.strip()] if cve_raw else None

            def parse_dt(val: str | None) -> datetime | None:
                if not val:
                    return None
                for fmt in ["%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]:
                    try:
                        return datetime.strptime(val.strip(), fmt)
                    except ValueError:
                        continue
                return None

            # Classify by layer rules
            title_val = row.get("Title", "") or ""
            category_val = row.get("Category", "") or ""
            matched_layer_id = None
            for match_field, pattern_lower, lid in layer_rules:
                value = title_val if match_field == "title" else category_val
                if pattern_lower in value.lower():
                    matched_layer_id = lid
                    break

            vuln = Vulnerability(
                scan_report_id=self.report.id,
                host_id=host_id,
                qid=qid,
                title=title_val,
                vuln_status=row.get("Vuln Status"),
                type=row.get("Type"),
                severity=severity,
                port=port,
                protocol=row.get("Protocol"),
                fqdn=row.get("FQDN"),
                ssl=ssl_val,
                first_detected=parse_dt(row.get("First Detected")),
                last_detected=parse_dt(row.get("Last Detected")),
                times_detected=int(row["Times Detected"]) if row.get("Times Detected") else None,
                date_last_fixed=parse_dt(row.get("Date Last Fixed")),
                cve_ids=cve_list,
                vendor_reference=row.get("Vendor Reference"),
                bugtraq_id=row.get("Bugtraq ID"),
                cvss_base=row.get("CVSS Base"),
                cvss_temporal=row.get("CVSS Temporal"),
                cvss3_base=row.get("CVSS3.1 Base"),
                cvss3_temporal=row.get("CVSS3.1 Temporal"),
                threat=row.get("Threat"),
                impact=row.get("Impact"),
                solution=row.get("Solution"),
                results=row.get("Results"),
                pci_vuln=pci_val,
                ticket_state=row.get("Ticket State"),
                tracking_method=row.get("Tracking Method"),
                category=category_val,
                layer_id=matched_layer_id,
            )
            self.session.add(vuln)
            rows_processed += 1

            if rows_processed % 5000 == 0:
                self.job.rows_processed = rows_processed
                self.job.progress = int((rows_processed / self.job.rows_total) * 100)
                await self.session.flush()

        # 6. Run coherence checks
        await self._run_coherence_checks(host_summaries, host_cache, df)

        # 7. Finalize
        self.job.rows_processed = rows_processed
        self.job.progress = 100
        self.job.status = "done"
        self.job.ended_at = _utcnow()
        await self.session.commit()

        # 8. Refresh materialized view for dedup
        await self.session.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns")
        )
        await self.session.commit()

        # 9. Recompute trend snapshots for this import
        from q2h.services.trend_snapshots import recompute_snapshots_for_reports
        await recompute_snapshots_for_reports(self.session, [self.report.id])

        return self.report

    async def _run_coherence_checks(self, host_summaries, host_cache, df: pl.DataFrame):
        metadata = self.parser._metadata
        actual_vuln_count = len(df)
        actual_host_count = df["IP"].n_unique()

        # Check total vulns
        if metadata.total_vulns is not None and metadata.total_vulns != actual_vuln_count:
            self.session.add(ReportCoherenceCheck(
                scan_report_id=self.report.id,
                check_type="total_vulns_mismatch",
                expected_value=str(metadata.total_vulns),
                actual_value=str(actual_vuln_count),
                severity="warning" if abs(metadata.total_vulns - actual_vuln_count) <= 2 else "error",
            ))

        # Check host count
        if metadata.active_hosts is not None and metadata.active_hosts != actual_host_count:
            self.session.add(ReportCoherenceCheck(
                scan_report_id=self.report.id,
                check_type="host_count_mismatch",
                expected_value=str(metadata.active_hosts),
                actual_value=str(actual_host_count),
                severity="warning",
            ))

        # Check per-host vulns
        for hs in host_summaries:
            actual_for_host = len(df.filter(pl.col("IP") == hs.ip))
            if actual_for_host != hs.total_vulns:
                self.session.add(ReportCoherenceCheck(
                    scan_report_id=self.report.id,
                    check_type="host_vuln_mismatch",
                    entity=hs.ip,
                    expected_value=str(hs.total_vulns),
                    actual_value=str(actual_for_host),
                    severity="warning",
                ))

        # Check missing hosts
        summary_ips = {hs.ip for hs in host_summaries}
        detail_ips = set(df["IP"].unique().to_list())
        for missing in summary_ips - detail_ips:
            self.session.add(ReportCoherenceCheck(
                scan_report_id=self.report.id,
                check_type="missing_host",
                entity=missing,
                expected_value="present_in_summary",
                actual_value="absent_from_detail",
                severity="error",
            ))
        for extra in detail_ips - summary_ips:
            self.session.add(ReportCoherenceCheck(
                scan_report_id=self.report.id,
                check_type="missing_host",
                entity=extra,
                expected_value="absent_from_summary",
                actual_value="present_in_detail",
                severity="warning",
            ))
