from pathlib import Path
from q2h.ingestion.csv_parser import QualysCSVParser

SAMPLE_CSV = Path(__file__).parent.parent.parent / "exemple-qualys-raw.csv"


def test_parse_header_metadata():
    parser = QualysCSVParser(SAMPLE_CSV)
    metadata = parser.parse_header()
    assert metadata.report_name is not None
    assert metadata.report_date is not None
    assert metadata.asset_group == "AG_Windows"
    assert metadata.active_hosts == 4
    assert metadata.total_vulns == 11


def test_parse_host_summary():
    parser = QualysCSVParser(SAMPLE_CSV)
    _ = parser.parse_header()
    hosts = parser.parse_host_summary()
    assert len(hosts) == 4
    assert hosts[0].ip == "1.1.1.1"
    assert hosts[0].total_vulns == 2
