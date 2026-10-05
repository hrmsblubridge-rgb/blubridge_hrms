"""Acceptance tests for the shift-aware single-punch classifier and the
approved missed-punch override (spec 2026-07-24).

Pure unit tests — no test data is written to the database.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import (  # noqa: E402
    _single_punch_is_checkout,
    _overlay_missed_punch,
    AttendanceStatus,
)

DAY_SHIFT = {"login_time": "10:00", "logout_time": "21:00", "total_hours": 11}
NIGHT_SHIFT = {"login_time": "22:00", "logout_time": "06:00", "total_hours": 8}


def _dt(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm)


# TEST 1 — only morning punch stays a Check-In
def test_morning_single_punch_is_checkin():
    punch = _dt(2026, 7, 20, 9, 55)
    assert _single_punch_is_checkout(punch, "20-07-2026", DAY_SHIFT) is False


# TEST 2 — only evening punch is a Check-Out for a day shift
def test_evening_single_punch_is_checkout():
    punch = _dt(2026, 7, 20, 22, 0)
    assert _single_punch_is_checkout(punch, "20-07-2026", DAY_SHIFT) is True


def test_midday_before_midpoint_is_checkin():
    # Day shift 10:00 + 11h → midpoint 15:30. 13:00 → IN.
    punch = _dt(2026, 7, 20, 13, 0)
    assert _single_punch_is_checkout(punch, "20-07-2026", DAY_SHIFT) is False


def test_after_midpoint_is_checkout():
    punch = _dt(2026, 7, 20, 18, 0)
    assert _single_punch_is_checkout(punch, "20-07-2026", DAY_SHIFT) is True


# TEST 10 — night shift: a 10 PM punch is the Check-IN
def test_night_shift_10pm_is_checkin():
    punch = _dt(2026, 7, 20, 22, 0)
    assert _single_punch_is_checkout(punch, "20-07-2026", NIGHT_SHIFT) is False


# TEST 9 — extended/overnight: an 01:00 next-day punch (attributed to the
# previous working date by the effective-date rule) is the Check-OUT.
def test_night_shift_after_midnight_punch_is_checkout():
    punch = _dt(2026, 7, 21, 4, 0)  # next calendar day, attendance date 20-07
    assert _single_punch_is_checkout(punch, "20-07-2026", NIGHT_SHIFT) is True


# No shift resolvable → never guess, keep legacy behaviour (IN)
def test_no_shift_keeps_legacy_checkin():
    punch = _dt(2026, 7, 20, 22, 0)
    assert _single_punch_is_checkout(punch, "20-07-2026", None) is False
    assert _single_punch_is_checkout(punch, "20-07-2026", {}) is False
    assert _single_punch_is_checkout(punch, "20-07-2026", {"login_time": "10:00", "total_hours": 0}) is False


# TEST 3/4 — approved missed punch overrides an OUT-only row
def test_overlay_checkin_onto_out_only_row():
    rec = {
        "employee_id": "e1", "date": "20-07-2026",
        "check_in": None, "check_in_24h": None,
        "check_out": "10:00 PM", "check_out_24h": "22:00",
        "status": AttendanceStatus.NOT_LOGGED, "is_lop": False, "lop_reason": None,
    }
    mp = {"punch_type": "Check-in", "check_in_time": "09:55", "check_out_time": None}
    _overlay_missed_punch(rec, mp)
    assert rec["check_in_24h"] == "09:55"
    assert rec["check_out_24h"] == "22:00"           # retained
    assert rec["status"] == AttendanceStatus.PRESENT  # flipped from Not Logged
    assert rec["total_hours_decimal"] == pytest.approx(12.08, abs=0.01)


def test_overlay_both_replaces_provisional_times():
    rec = {
        "employee_id": "e1", "date": "20-07-2026",
        "check_in": "10:00 PM", "check_in_24h": "22:00",
        "check_out": None, "check_out_24h": None,
        "status": AttendanceStatus.LOGIN, "is_lop": False, "lop_reason": None,
    }
    mp = {"punch_type": "Both", "check_in_time": "09:55", "check_out_time": "22:00"}
    _overlay_missed_punch(rec, mp)
    assert rec["check_in_24h"] == "09:55"
    assert rec["check_out_24h"] == "22:00"
    assert rec["status"] == AttendanceStatus.PRESENT  # Login → Present (both punches)


def test_overlay_checkout_only_retains_existing_in():
    rec = {
        "employee_id": "e1", "date": "20-07-2026",
        "check_in": "09:55 AM", "check_in_24h": "09:55",
        "check_out": None, "check_out_24h": None,
        "status": AttendanceStatus.LOGIN, "is_lop": False, "lop_reason": None,
    }
    mp = {"punch_type": "Check-out", "check_out_time": "22:00", "check_in_time": None}
    _overlay_missed_punch(rec, mp)
    assert rec["check_in_24h"] == "09:55"   # retained
    assert rec["check_out_24h"] == "22:00"
    assert rec["status"] == AttendanceStatus.PRESENT


# TEST 11 — idempotency of the overlay
def test_overlay_idempotent():
    rec = {
        "employee_id": "e1", "date": "20-07-2026",
        "check_in": None, "check_in_24h": None,
        "check_out": "10:00 PM", "check_out_24h": "22:00",
        "status": AttendanceStatus.NOT_LOGGED, "is_lop": False, "lop_reason": None,
    }
    mp = {"punch_type": "Both", "check_in_time": "09:55", "check_out_time": "22:00"}
    _overlay_missed_punch(rec, mp)
    first = dict(rec)
    _overlay_missed_punch(rec, mp)
    assert rec == first


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
