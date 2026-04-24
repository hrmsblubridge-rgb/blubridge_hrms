"""
Unit tests for cross-midnight attendance handling.

Validates:
- get_effective_attendance_date: punches <= threshold attributed to previous day
- attendance_shift_offset: cross-midnight times get later offset than evening
- Configurable threshold via CROSS_MIDNIGHT_THRESHOLD_MINUTES
- Edge cases (exact boundary, single punch, multi-punch after midnight)
"""
import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure backend is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import (
    get_effective_attendance_date,
    attendance_shift_offset,
    CROSS_MIDNIGHT_THRESHOLD_MINUTES,
    IST,
)


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


# -------- get_effective_attendance_date --------

def test_normal_morning_punch_uses_same_day():
    # 09:00 AM on 24-Apr-2026 → 24-04-2026
    assert get_effective_attendance_date(_ist(2026, 4, 24, 9, 0)) == "24-04-2026"


def test_normal_evening_punch_uses_same_day():
    assert get_effective_attendance_date(_ist(2026, 4, 24, 20, 0)) == "24-04-2026"


def test_cross_midnight_1am_attributes_to_previous_day():
    # 01:00 AM 25-Apr → 24-04-2026 (previous day)
    assert get_effective_attendance_date(_ist(2026, 4, 25, 1, 0)) == "24-04-2026"


def test_cross_midnight_exactly_5am_attributes_to_previous_day():
    # Boundary: 05:00 AM is inclusive → previous day
    assert get_effective_attendance_date(_ist(2026, 4, 25, 5, 0)) == "24-04-2026"


def test_punch_just_after_5am_is_new_day():
    # 05:01 AM is a new day
    assert get_effective_attendance_date(_ist(2026, 4, 25, 5, 1)) == "25-04-2026"


def test_punch_at_6am_is_new_day():
    assert get_effective_attendance_date(_ist(2026, 4, 25, 6, 0)) == "25-04-2026"


def test_month_boundary_rollover():
    # 02:00 AM on 1-May should attribute to 30-Apr
    assert get_effective_attendance_date(_ist(2026, 5, 1, 2, 0)) == "30-04-2026"


def test_year_boundary_rollover():
    # 03:00 AM on 1-Jan-2027 should attribute to 31-Dec-2026
    assert get_effective_attendance_date(_ist(2027, 1, 1, 3, 0)) == "31-12-2026"


# -------- attendance_shift_offset --------

def test_offset_morning_in_punch():
    # 09:00 → 540 (normal, same-day)
    assert attendance_shift_offset("09:00") == 540


def test_offset_evening_punch():
    assert attendance_shift_offset("20:00") == 1200


def test_offset_cross_midnight_punch_has_larger_offset():
    # 01:00 (cross-midnight) should be LARGER than 20:00 (evening)
    assert attendance_shift_offset("01:00") > attendance_shift_offset("20:00")


def test_offset_cross_midnight_5am_is_cross():
    # 05:00 boundary is cross-midnight (<= threshold)
    assert attendance_shift_offset("05:00") == 300 + 1440


def test_offset_501_is_not_cross_midnight():
    assert attendance_shift_offset("05:01") == 301


def test_offset_handles_none_and_empty():
    assert attendance_shift_offset("") is None
    assert attendance_shift_offset(None) is None


def test_offset_handles_invalid_format():
    assert attendance_shift_offset("bad") is None


def test_in_out_order_for_overnight_shift():
    # IN=20:00 evening, OUT=01:00 next-day early morning
    in_off = attendance_shift_offset("20:00")
    out_off = attendance_shift_offset("01:00")
    assert in_off < out_off, "Cross-midnight OUT must sort after evening IN"


def test_in_out_order_for_day_shift():
    in_off = attendance_shift_offset("09:00")
    out_off = attendance_shift_offset("18:00")
    assert in_off < out_off


def test_threshold_default_is_5am():
    assert CROSS_MIDNIGHT_THRESHOLD_MINUTES == 300


# -------- Merge-style IN/OUT selection (simulates merge logic) --------

def _pick_in_out(*times):
    """Simulate merge: IN=min offset, OUT=max offset among candidate times."""
    entries = [(t, attendance_shift_offset(t)) for t in times if t]
    entries = [(t, o) for t, o in entries if o is not None]
    if not entries:
        return None, None
    # Deduplicate
    seen = {}
    for t, o in entries:
        seen[t] = o
    uniq = list(seen.items())
    in_pick = min(uniq, key=lambda c: c[1])
    out_pick = max(uniq, key=lambda c: c[1])
    return in_pick[0], (out_pick[0] if out_pick[0] != in_pick[0] else None)


def test_merge_normal_day_shift():
    in_t, out_t = _pick_in_out("09:00", "18:00")
    assert in_t == "09:00"
    assert out_t == "18:00"


def test_merge_overnight_shift_in_evening_out_after_midnight():
    # Employee IN at 20:00, OUT at 01:00 next day (grouped to same effective date)
    in_t, out_t = _pick_in_out("20:00", "01:00")
    assert in_t == "20:00"
    assert out_t == "01:00"


def test_merge_existing_in_plus_late_cross_midnight_punch():
    # Existing record has IN=09:00; new batch brings 02:00 cross-midnight only
    in_t, out_t = _pick_in_out("09:00", "02:00")
    assert in_t == "09:00"
    assert out_t == "02:00"


def test_merge_multiple_cross_midnight_punches_takes_last_as_out():
    # Multiple punches 00:00-05:00 → IN is earliest (morning existing), OUT is last
    in_t, out_t = _pick_in_out("09:00", "01:00", "02:30", "04:00")
    assert in_t == "09:00"
    assert out_t == "04:00"


def test_merge_single_punch_only():
    in_t, out_t = _pick_in_out("09:00")
    assert in_t == "09:00"
    assert out_t is None


def test_merge_only_cross_midnight_punches():
    # Only cross-midnight punches: first becomes IN, last becomes OUT
    in_t, out_t = _pick_in_out("01:00", "03:00", "04:30")
    assert in_t == "01:00"
    assert out_t == "04:30"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
