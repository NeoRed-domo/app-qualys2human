import pytest
from q2h.upgrade.version import parse_version, is_newer


class TestParseVersion:
    def test_valid_4_segment(self):
        assert parse_version("1.1.11.1") == (1, 1, 11, 1)

    def test_valid_with_v_prefix(self):
        assert parse_version("v1.0.0.0") == (1, 0, 0, 0)

    def test_valid_with_whitespace(self):
        assert parse_version("  1.2.3.4  ") == (1, 2, 3, 4)

    def test_invalid_3_segments(self):
        with pytest.raises(ValueError, match="Invalid version"):
            parse_version("1.2.3")

    def test_invalid_5_segments(self):
        with pytest.raises(ValueError, match="Invalid version"):
            parse_version("1.2.3.4.5")

    def test_invalid_non_numeric(self):
        with pytest.raises(ValueError):
            parse_version("1.2.3.beta")

    def test_invalid_empty(self):
        with pytest.raises(ValueError):
            parse_version("")


class TestIsNewer:
    def test_major_upgrade(self):
        assert is_newer("2.0.0.0", "1.9.9.9") is True

    def test_evolution_upgrade(self):
        assert is_newer("1.2.0.0", "1.1.99.99") is True

    def test_minor_upgrade(self):
        assert is_newer("1.1.12.0", "1.1.11.9") is True

    def test_build_upgrade(self):
        assert is_newer("1.1.11.2", "1.1.11.1") is True

    def test_same_version(self):
        assert is_newer("1.1.11.1", "1.1.11.1") is False

    def test_downgrade_rejected(self):
        assert is_newer("1.0.0.0", "1.1.0.0") is False

    def test_numeric_not_string_comparison(self):
        # "9" > "11" as strings but 9 < 11 as numbers
        assert is_newer("1.1.11.0", "1.1.9.0") is True
