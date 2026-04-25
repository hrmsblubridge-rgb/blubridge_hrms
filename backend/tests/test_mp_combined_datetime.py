"""Tests for combined Date+Time parsing in Missed Punch bulk import."""
import sys, os
from datetime import datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import _parse_import_datetime, _parse_import_time, _parse_import_date


def test_combined_dd_mm_yyyy_hhmm():
    d, t = _parse_import_datetime("18-03-2026 09:37")
    assert d == "2026-03-18"
    assert t == "09:37"


def test_combined_dd_slash_mm_yyyy():
    d, t = _parse_import_datetime("18/03/2026 23:30")
    assert d == "2026-03-18"
    assert t == "23:30"


def test_combined_iso():
    d, t = _parse_import_datetime("2026-03-18 09:37:45")
    assert d == "2026-03-18"
    assert t == "09:37"


def test_combined_ampm():
    d, t = _parse_import_datetime("18-03-2026 09:37 AM")
    assert d == "2026-03-18"
    assert t == "09:37"
    d, t = _parse_import_datetime("18-03-2026 06:30 PM")
    assert d == "2026-03-18"
    assert t == "18:30"


def test_time_only():
    d, t = _parse_import_datetime("09:37")
    assert d is None
    assert t == "09:37"


def test_date_only():
    d, t = _parse_import_datetime("18-03-2026")
    assert d == "2026-03-18"
    assert t is None


def test_native_datetime_obj():
    d, t = _parse_import_datetime(datetime(2026, 3, 18, 9, 37))
    assert d == "2026-03-18"
    assert t == "09:37"


def test_native_datetime_at_midnight_treated_as_date():
    d, t = _parse_import_datetime(datetime(2026, 3, 18, 0, 0, 0))
    assert d == "2026-03-18"
    assert t is None


def test_native_time_obj():
    d, t = _parse_import_datetime(time(9, 37))
    assert d is None
    assert t == "09:37"


def test_blank_and_invalid():
    assert _parse_import_datetime(None) == (None, None)
    assert _parse_import_datetime("") == (None, None)
    assert _parse_import_datetime("garbage value") == (None, None)


def test_legacy_parse_import_time_still_works():
    # Time-only
    assert _parse_import_time("09:37") == "09:37"
    # Combined - returns time portion
    assert _parse_import_time("18-03-2026 09:37") == "09:37"
    # AM/PM
    assert _parse_import_time("06:30 PM") == "18:30"
    # Blank
    assert _parse_import_time(None) is None


def test_cross_midnight_anchor():
    """In Time's date should win for cross-midnight rows."""
    in_date, in_time = _parse_import_datetime("18-03-2026 23:30")
    out_date, out_time = _parse_import_datetime("19-03-2026 02:15")
    # When deriving date_iso, In Time wins
    derived_date = in_date or out_date
    assert derived_date == "2026-03-18"
    assert in_time == "23:30"
    assert out_time == "02:15"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
