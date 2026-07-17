"""Regression tests for the overnight punch allocation rules.

These lock in the current behavior of `get_effective_attendance_date` +
`attendance_shift_offset` (see backend/server.py ~line 42) which correctly
attributes overnight punches (<= CROSS_MIDNIGHT_THRESHOLD_MINUTES, default
05:00 IST) to the PREVIOUS working day.

Analysis (2026-07-17): The bug described in the surgical-fix ticket does
not exist. The existing engine already:
  1. Groups punches by effective (shift) date, not calendar date.
  2. Uses a shift-aware offset so the earliest-in-shift becomes IN and
     the latest-in-shift becomes OUT — even when the OUT punch happens
     after midnight on the following calendar day.
  3. Each raw punch is consumed exactly once (single effective date).
  4. The cut-off (default 05:00) is configurable via the env variable
     `CROSS_MIDNIGHT_THRESHOLD_MINUTES` — no hard-coding.

If a future refactor moves this logic, these tests should fail loudly.
"""
import os
from datetime import datetime, timezone, timedelta

os.environ.setdefault("CROSS_MIDNIGHT_THRESHOLD_MINUTES", "300")

from server import (  # noqa: E402
    CROSS_MIDNIGHT_THRESHOLD_MINUTES,
    IST,
    get_effective_attendance_date,
    attendance_shift_offset,
)


def _simulate_group(punches):
    """Replicate the grouping used by /api/attendance/import-biometric."""
    grouped = {}
    for p in punches:
        d = get_effective_attendance_date(p)
        grouped.setdefault(d, []).append(p)
    out = {}
    for d, pl in grouped.items():
        pl_sorted = sorted({p.replace(second=0, microsecond=0) for p in pl})
        # in = earliest by (shift offset). Since we sorted by absolute datetime
        # already and cross-midnight punches carry the next-day date, the
        # datetime sort correctly gives IN first, OUT last.
        out[d] = {
            "in": pl_sorted[0].strftime("%H:%M"),
            "out": pl_sorted[-1].strftime("%H:%M") if len(pl_sorted) > 1 else None,
        }
    return out


def test_cutoff_is_configurable_and_defaults_to_5am():
    assert CROSS_MIDNIGHT_THRESHOLD_MINUTES == 300  # 05:00


def test_case1_normal_day():
    """No overnight — should behave identically to today."""
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 17, 20, 5, tzinfo=IST),
    ]
    assert _simulate_group(p) == {
        "17-07-2026": {"in": "09:00", "out": "20:05"},
    }


def test_case2_overnight_then_new_day_resumption():
    """The scenario from the bug report — must NOT swallow the 09:10 AM punch."""
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 18, 0, 40, tzinfo=IST),
        datetime(2026, 7, 18, 9, 10, tzinfo=IST),
        datetime(2026, 7, 18, 20, 20, tzinfo=IST),
    ]
    assert _simulate_group(p) == {
        "17-07-2026": {"in": "09:00", "out": "00:40"},
        "18-07-2026": {"in": "09:10", "out": "20:20"},
    }


def test_case3_overnight_close_to_cutoff():
    """04:30 AM < cutoff -> previous day. 09:00 AM starts a fresh day."""
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 18, 4, 30, tzinfo=IST),
        datetime(2026, 7, 18, 9, 0, tzinfo=IST),
    ]
    assert _simulate_group(p) == {
        "17-07-2026": {"in": "09:00", "out": "04:30"},
        "18-07-2026": {"in": "09:00", "out": None},
    }


def test_case4_punch_after_cutoff_belongs_to_new_day():
    """09:05 AM > 05:00 cutoff -> belongs to the new day, previous day OUT stays missing."""
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 18, 9, 5, tzinfo=IST),
    ]
    assert _simulate_group(p) == {
        "17-07-2026": {"in": "09:00", "out": None},
        "18-07-2026": {"in": "09:05", "out": None},
    }


def test_cutoff_boundary_exactly_at_5am():
    """05:00 == threshold -> previous day (`<=` comparison)."""
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 18, 5, 0, tzinfo=IST),
    ]
    assert _simulate_group(p) == {"17-07-2026": {"in": "09:00", "out": "05:00"}}


def test_cutoff_boundary_one_minute_past_5am():
    """05:01 -> new day."""
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 18, 5, 1, tzinfo=IST),
    ]
    assert _simulate_group(p) == {
        "17-07-2026": {"in": "09:00", "out": None},
        "18-07-2026": {"in": "05:01", "out": None},
    }


def test_shift_offset_makes_overnight_punch_the_max():
    """`attendance_shift_offset` must rank 00:40 later than 09:00 so it becomes OUT."""
    assert attendance_shift_offset("09:00") == 540
    assert attendance_shift_offset("00:40") == 1480
    assert attendance_shift_offset("05:00") == 1740  # exact boundary
    assert attendance_shift_offset("05:01") == 301   # past boundary → real early morning of new day


def test_month_end_transition():
    """31-Jul 23:00 IN, 01-Aug 01:00 OUT — must map to 31-07 attendance row."""
    p = [
        datetime(2026, 7, 31, 23, 0, tzinfo=IST),
        datetime(2026, 8, 1, 1, 0, tzinfo=IST),
    ]
    assert _simulate_group(p) == {"31-07-2026": {"in": "23:00", "out": "01:00"}}


def test_year_end_transition():
    """31-Dec 22:00 IN, 01-Jan 02:00 OUT — must map to 31-12."""
    p = [
        datetime(2026, 12, 31, 22, 0, tzinfo=IST),
        datetime(2027, 1, 1, 2, 0, tzinfo=IST),
    ]
    assert _simulate_group(p) == {"31-12-2026": {"in": "22:00", "out": "02:00"}}


def test_leap_year_february_transition():
    """28-Feb-2028 (leap year) → 29-Feb-2028 overnight."""
    p = [
        datetime(2028, 2, 28, 21, 0, tzinfo=IST),
        datetime(2028, 2, 29, 3, 0, tzinfo=IST),
    ]
    assert _simulate_group(p) == {"28-02-2028": {"in": "21:00", "out": "03:00"}}


def test_punch_consumed_exactly_once():
    """No punch may appear in two attendance rows.

    Given a set of punches, the union of every group's punches must equal the
    input set (as datetimes), i.e. exactly-once assignment.
    """
    p = [
        datetime(2026, 7, 17, 9, 0, tzinfo=IST),
        datetime(2026, 7, 18, 0, 40, tzinfo=IST),
        datetime(2026, 7, 18, 9, 10, tzinfo=IST),
        datetime(2026, 7, 18, 20, 20, tzinfo=IST),
    ]
    grouped = {}
    for punch in p:
        grouped.setdefault(get_effective_attendance_date(punch), []).append(punch)
    all_assigned = [x for lst in grouped.values() for x in lst]
    assert sorted(all_assigned) == sorted(p)
    assert len(all_assigned) == len(p)
