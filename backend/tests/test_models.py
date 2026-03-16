from q2h.db.models import ScanReport, Host, Vulnerability, ImportJob, ReportCoherenceCheck


def test_scan_report_model_exists():
    report = ScanReport(filename="test.csv", source="manual")
    assert report.filename == "test.csv"
    assert report.source == "manual"


def test_vulnerability_severity_range():
    vuln = Vulnerability(qid=12345, title="Test Vuln", severity=5)
    assert vuln.severity == 5


def test_import_job_default_status():
    job = ImportJob(status="pending")
    assert job.status == "pending"
