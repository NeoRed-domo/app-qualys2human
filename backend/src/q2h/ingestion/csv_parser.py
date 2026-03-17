import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl


@dataclass
class ReportMetadata:
    report_name: str | None = None
    report_date: datetime | None = None
    company_name: str | None = None
    asset_group: str | None = None
    active_hosts: int | None = None
    total_vulns: int | None = None
    avg_risk: float | None = None


@dataclass
class HostSummary:
    ip: str
    total_vulns: int
    security_risk: float


class QualysCSVParser:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self._raw_lines: list[str] = []
        self._detail_start_line: int = -1
        self._metadata: ReportMetadata | None = None
        self._host_summaries: list[HostSummary] = []
        self._load_lines()

    def _load_lines(self):
        self._encoding = "utf-8"
        encodings = ["utf-8", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                with open(self.filepath, encoding=enc) as f:
                    self._raw_lines = f.readlines()
                self._encoding = enc
                return
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode {self.filepath}")

    def _parse_csv_line(self, line: str) -> list[str]:
        reader = csv.reader([line.strip()])
        for row in reader:
            return row
        return []

    def parse_header(self) -> ReportMetadata:
        meta = ReportMetadata()
        lines = self._raw_lines

        # Line 1: report name, date
        if len(lines) > 0:
            row = self._parse_csv_line(lines[0])
            if len(row) >= 2:
                meta.report_name = row[0]
                date_match = re.search(r"(\d{2}/\d{2}/\d{4})", row[1])
                if date_match:
                    meta.report_date = datetime.strptime(date_match.group(1), "%m/%d/%Y")

        # Line 2: company
        if len(lines) > 1:
            row = self._parse_csv_line(lines[1])
            if row:
                meta.company_name = row[0]

        # Scan for asset group section
        for j in range(len(lines)):
            row = self._parse_csv_line(lines[j])
            if row and row[0] == "Asset Groups":
                if j + 1 < len(lines):
                    val_row = self._parse_csv_line(lines[j + 1])
                    if len(val_row) >= 3:
                        meta.asset_group = val_row[0]
                        meta.active_hosts = int(val_row[2]) if val_row[2] else None
                break

        # Scan for total vulns section
        for j in range(len(lines)):
            row = self._parse_csv_line(lines[j])
            if row and row[0] == "Total Vulnerabilities":
                if j + 1 < len(lines):
                    val_row = self._parse_csv_line(lines[j + 1])
                    if len(val_row) >= 2:
                        meta.total_vulns = int(val_row[0]) if val_row[0] else None
                        meta.avg_risk = float(val_row[1]) if val_row[1] else None
                break

        self._metadata = meta
        return meta

    def parse_host_summary(self) -> list[HostSummary]:
        hosts = []
        for j, line in enumerate(self._raw_lines):
            row = self._parse_csv_line(line)
            if row and len(row) >= 3 and row[0] == "IP" and row[1] == "Total Vulnerabilities":
                for k in range(j + 1, len(self._raw_lines)):
                    val_row = self._parse_csv_line(self._raw_lines[k])
                    if not val_row or not val_row[0]:
                        break
                    hosts.append(HostSummary(
                        ip=val_row[0],
                        total_vulns=int(val_row[1]) if val_row[1] else 0,
                        security_risk=float(val_row[2]) if val_row[2] else 0.0,
                    ))
                break
        self._host_summaries = hosts
        return hosts

    def find_detail_section_start(self) -> int:
        """Find the line number where the detail vuln rows begin."""
        for j, line in enumerate(self._raw_lines):
            row = self._parse_csv_line(line)
            if row and len(row) > 10 and row[0] == "IP" and row[1] == "DNS" and row[2] == "NetBIOS":
                self._detail_start_line = j
                return j
        raise ValueError("Cannot find detail vulnerability section in CSV")

    def parse_detail_rows(self) -> pl.DataFrame:
        """Parse the detail vulnerability rows using Python csv (handles complex quoting)."""
        if self._detail_start_line < 0:
            self.find_detail_section_start()
        detail_text = "".join(self._raw_lines[self._detail_start_line:])
        reader = csv.DictReader(io.StringIO(detail_text))
        rows = [row for row in reader if row.get("IP")]
        if not rows:
            return pl.DataFrame()
        return pl.DataFrame(rows)
