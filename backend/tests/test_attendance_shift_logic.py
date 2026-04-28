"""Unit tests for attendance shift / work-hours logic.

Covers:
  - Effective-start-time (early arrival) → expected_logout = punch_in + required
  - Late entry → LOP applied
  - Early logout → LOP only when total_worked < required_hours
  - Sunday classification (no LOP)
  - >= required_hours → never early-out flagged
"""
import os
import sys
import importlib.util
from pathlib import Path

# Load server.py without triggering DB connection at import time isn't trivial;
# but server.py initializes Motor lazily on first await — top-level imports of
# pure helpers are safe.
SERVER = Path(__file__).resolve().parent.parent / "server.py"
spec = importlib.util.spec_from_file_location("server_under_test", SERVER)


def _load():
    spec_local = importlib.util.spec_from_file_location("server_under_test", SERVER)
    mod = importlib.util.module_from_spec(spec_local)
    spec_local.loader.exec_module(mod)
    return mod


s = _load()
calc = s.calculate_attendance_status

# Standard 10:00 AM start, 11h required, 0 grace.
SHIFT = {
    "login_time": "10:00",
    "logout_time": "21:00",
    "total_hours": 11,
    "late_grace_minutes": 0,
    "early_out_grace_minutes": 0,
}


def test_case1_early_arrival_full_hours_no_lop():
    """IN 09:28, OUT 20:41 = 11h 13m → no early logout, no LOP."""
    r = calc("09:28", "20:41", SHIFT, attendance_date="22-04-2026")  # Wed
    assert r["status"] == "Present", r
    assert r["is_lop"] is False, r
    assert r["expected_logout"] == "20:28", r  # 09:28 + 11h
    assert round(r["total_hours_decimal"], 2) == 11.22


def test_case2_late_entry_lop_no_early_logout():
    """IN 10:01, OUT 21:00 → late entry LOP."""
    r = calc("10:01", "21:00", SHIFT, attendance_date="22-04-2026")
    assert r["is_lop"] is True
    assert r["status"] == "Loss of Pay"
    assert "Late login" in (r["lop_reason"] or "")
    assert r["expected_logout"] == "21:01"


def test_case3_early_logout_short_hours_lop():
    """IN 10:00, OUT 20:30 = 10h 30m → LOP (short of 11h)."""
    r = calc("10:00", "20:30", SHIFT, attendance_date="22-04-2026")
    assert r["is_lop"] is True
    assert r["status"] == "Loss of Pay"
    assert "short hours" in (r["lop_reason"] or "") or "Early out" in (r["lop_reason"] or "")
    assert r["expected_logout"] == "21:00"


def test_case4_sunday_no_punch_no_lop():
    """Sunday with no punch → status Sunday, no LOP."""
    r = calc("", "", SHIFT, attendance_date="26-04-2026")  # 26-Apr-2026 is Sunday
    assert r["status"] == "Sunday"
    assert r["is_lop"] is False


def test_case5_worked_on_sunday_no_lop():
    """Sunday with punch → Worked on Sunday, no LOP."""
    r = calc("11:00", "20:00", SHIFT, attendance_date="26-04-2026")
    assert r["status"] == "Worked on Sunday"
    assert r["is_lop"] is False
    assert round(r["total_hours_decimal"], 2) == 9.00


def test_early_arrival_completes_required_hours_present():
    """IN 09:00, OUT 20:00 = 11h → not early-out, Present (regardless of clock)."""
    r = calc("09:00", "20:00", SHIFT, attendance_date="22-04-2026")
    assert r["status"] == "Present"
    assert r["is_lop"] is False
    assert r["expected_logout"] == "20:00"


def test_early_arrival_short_hours_is_lop():
    """IN 09:00, OUT 19:30 = 10h 30m → LOP because <11h."""
    r = calc("09:00", "19:30", SHIFT, attendance_date="22-04-2026")
    assert r["is_lop"] is True
    assert r["status"] == "Loss of Pay"


def test_only_login_no_logout():
    """IN only — status = Login, expected_logout dynamic."""
    r = calc("09:30", "", SHIFT, attendance_date="22-04-2026")
    assert r["status"] == "Login"
    assert r["expected_logout"] == "20:30"
    assert r["is_lop"] is False


def test_helper_is_sunday():
    assert s.is_sunday_ddmmyyyy("26-04-2026") is True   # Sun
    assert s.is_sunday_ddmmyyyy("22-04-2026") is False  # Wed
    assert s.is_sunday_ddmmyyyy("") is False
    assert s.is_sunday_ddmmyyyy(None) is False


def test_helper_add_hours():
    assert s.add_hours_to_24h("09:28", 11) == "20:28"
    assert s.add_hours_to_24h("23:00", 2) == "01:00"  # wrap midnight
    assert s.add_hours_to_24h("", 11) is None
    assert s.add_hours_to_24h(None, 11) is None


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\nTotal: {len(fns)}  Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)
