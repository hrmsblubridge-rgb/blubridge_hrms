"""Pure-logic tests for Vigilance break Total auto-calculation (Total = To − From).

Total is ALWAYS derived from From & To (overnight allowed); any user-supplied
Total is ignored. Stored canonically as 'HH:MM:SS' (ss=00 → renders 'HH:MM').
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vigilance import service as svc  # noqa: E402


def test_basic_difference_24h():
    assert svc.compute_break_total("13:00", "13:15") == "00:15:00"


def test_basic_difference_12h_stored():
    # Stored clock format is 12-hour "HH:MM AM/PM".
    assert svc.compute_break_total("01:00 PM", "02:30 PM") == "01:30:00"


def test_overnight_wraps_past_midnight():
    assert svc.compute_break_total("23:50", "00:10") == "00:20:00"


def test_overnight_12h():
    assert svc.compute_break_total("11:50 PM", "12:10 AM") == "00:20:00"


def test_blank_from_returns_empty():
    assert svc.compute_break_total("", "13:15") == ""


def test_blank_to_returns_empty():
    assert svc.compute_break_total("13:00", "") == ""


def test_both_blank_returns_empty():
    assert svc.compute_break_total("", "") == ""


def test_equal_endpoints_zero():
    assert svc.compute_break_total("09:00", "09:00") == "00:00:00"


def test_long_break():
    assert svc.compute_break_total("09:00", "12:45") == "03:45:00"


def test_display_renders_hh_mm():
    # canonical HH:MM:SS with ss=00 renders as HH:MM for the UI/export
    assert svc.display_duration(svc.compute_break_total("13:00", "13:15")) == "00:15"


def test_validate_breaks_ignores_user_total():
    # router-level helper must override a wrong user-supplied Total
    from vigilance.router import _validate_breaks
    breaks, err = _validate_breaks([
        {"label": "Lunch Break", "from": "13:00", "to": "13:45", "total": "99:99"},
    ])
    assert err is None
    assert breaks[0]["total"] == "00:45:00"


def test_validate_breaks_blank_endpoint_blank_total():
    from vigilance.router import _validate_breaks
    breaks, err = _validate_breaks([
        {"label": "Morning Break", "from": "10:00", "to": "", "total": "05:00"},
    ])
    assert err is None
    assert breaks[0]["total"] == ""
