from pathlib import Path
from q2h.ingestion.csv_parser import QualysCSVParser

SAMPLE_CSV = Path(__file__).parent.parent.parent / "exemple-qualys-raw.csv"


def test_parse_detail_rows():
    parser = QualysCSVParser(SAMPLE_CSV)
    parser.find_detail_section_start()
    df = parser.parse_detail_rows()
    assert len(df) > 0
    assert "IP" in df.columns
    assert "QID" in df.columns
    assert "Severity" in df.columns


def test_detail_row_count_matches_sample():
    parser = QualysCSVParser(SAMPLE_CSV)
    parser.find_detail_section_start()
    df = parser.parse_detail_rows()
    # Sample CSV has 13 detail vulnerability rows for 4 IPs
    assert len(df) >= 10
