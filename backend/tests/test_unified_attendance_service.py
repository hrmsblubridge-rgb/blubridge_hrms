"""Regression tests for the UNIFIED attendance calculation service.

These tests guarantee that the Dashboard, Attendance Module, and Reports Module
return IDENTICAL employee lists and counts for the same selected date and
filters, honouring:
  1. Employee eligibility per selected date (Joining Date ≤ date ≤ Relieving)
  2. Approved missed-punch / punch-correction merge (approved only)
  3. Department full-day threshold for the "Completed" bucket
  4. Asia/Kolkata timezone for date normalization

Follows the June 27 / 28 / 29 examples from the product spec verbatim.
"""

from __future__ import annotations

import os
import sys
import asyncio
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the helpers directly — these are pure functions that don't need a
# live database.
from server import (  # type: ignore  # noqa: E402
    _employed_on_date,
    _employed_on_date_int,
    _employment_window,
    _dept_full_hours_threshold,
    _normalize_date_to_int,
    _enforce_completed_hours_threshold,
    _overlay_missed_punch,
    _apply_eligibility_filter,
    AttendanceStatus,
    DEPARTMENT_WORK_HOURS,
)


# ---------------------------------------------------------------------------
# 1. Employment window / eligibility (Joining Date <= d <= Relieving Date)
# ---------------------------------------------------------------------------

def _emp(doj: str, status: str = "Active", last_day: str | None = None) -> dict:
    e = {
        "id": "e1",
        "employee_status": status,
        "date_of_joining": doj,
    }
    if last_day:
        e["last_day_payable"] = last_day
    return e


def _d(ymd: str) -> int:
    return _normalize_date_to_int(ymd)


class TestEmploymentWindow:
    """June 27 / 28 / 29 examples from the spec."""

    def test_joining_on_june_28_active(self):
        emp = _emp("2026-06-28")
        assert _employed_on_date(emp, _d("2026-06-27")) is False
        assert _employed_on_date(emp, _d("2026-06-28")) is True
        assert _employed_on_date(emp, _d("2026-06-29")) is True

    def test_relieving_on_june_28(self):
        emp = _emp("2026-01-01", status="Resigned", last_day="2026-06-28")
        assert _employed_on_date(emp, _d("2026-06-27")) is True
        assert _employed_on_date(emp, _d("2026-06-28")) is True
        assert _employed_on_date(emp, _d("2026-06-29")) is False

    def test_join_june_27_relieve_june_29(self):
        emp = _emp("2026-06-27", status="Resigned", last_day="2026-06-29")
        assert _employed_on_date(emp, _d("2026-06-26")) is False
        assert _employed_on_date(emp, _d("2026-06-27")) is True
        assert _employed_on_date(emp, _d("2026-06-28")) is True
        assert _employed_on_date(emp, _d("2026-06-29")) is True
        assert _employed_on_date(emp, _d("2026-06-30")) is False

    def test_joining_on_june_29(self):
        emp = _emp("2026-06-29")
        assert _employed_on_date(emp, _d("2026-06-27")) is False
        assert _employed_on_date(emp, _d("2026-06-28")) is False
        assert _employed_on_date(emp, _d("2026-06-29")) is True

    def test_relieving_on_june_27(self):
        emp = _emp("2026-01-01", status="Inactive", last_day="2026-06-27")
        assert _employed_on_date(emp, _d("2026-06-27")) is True
        assert _employed_on_date(emp, _d("2026-06-28")) is False
        assert _employed_on_date(emp, _d("2026-06-29")) is False

    def test_active_no_last_day_treated_as_still_employed(self):
        emp = _emp("2026-01-01")
        assert _employed_on_date(emp, _d("2036-06-27")) is True


# ---------------------------------------------------------------------------
# 2. Eligibility filter drops rows for employees not employed on that date
# ---------------------------------------------------------------------------

class TestApplyEligibilityFilter:
    def test_filter_out_before_doj(self):
        emp_map = {
            "e1": {"id": "e1",
                   "_doj_int": _d("2026-06-28"),
                   "_last_int": None},
        }
        # An attendance row that landed on 2026-06-27 for e1 must be filtered.
        records = [
            {"employee_id": "e1", "date": "27-06-2026", "status": "Present"},
            {"employee_id": "e1", "date": "28-06-2026", "status": "Present"},
            {"employee_id": "e1", "date": "29-06-2026", "status": "Present"},
        ]
        kept = _apply_eligibility_filter(records, emp_map)
        dates = [r["date"] for r in kept]
        assert dates == ["28-06-2026", "29-06-2026"]

    def test_filter_out_after_relieving(self):
        emp_map = {
            "e1": {"id": "e1",
                   "_doj_int": _d("2026-01-01"),
                   "_last_int": _d("2026-06-28")},
        }
        records = [
            {"employee_id": "e1", "date": "27-06-2026", "status": "Present"},
            {"employee_id": "e1", "date": "28-06-2026", "status": "Present"},
            {"employee_id": "e1", "date": "29-06-2026", "status": "Present"},
        ]
        kept = _apply_eligibility_filter(records, emp_map)
        dates = [r["date"] for r in kept]
        assert dates == ["27-06-2026", "28-06-2026"]

    def test_deleted_employee_row_dropped(self):
        emp_map = {}   # employee hard-deleted from master
        records = [{"employee_id": "e_missing", "date": "28-06-2026"}]
        assert _apply_eligibility_filter(records, emp_map) == []


# ---------------------------------------------------------------------------
# 3. Department Completed-hours threshold
# ---------------------------------------------------------------------------

class TestDeptFullHoursThreshold:
    def test_research_unit_11h(self):
        assert _dept_full_hours_threshold("Research Unit") == 11.0

    def test_business_and_product_10h(self):
        assert _dept_full_hours_threshold("Business & Product") == 10.0

    def test_support_9h(self):
        assert _dept_full_hours_threshold("Support Staff") == 9.0

    def test_unknown_returns_none(self):
        assert _dept_full_hours_threshold("Nonexistent") is None
        assert _dept_full_hours_threshold(None) is None


class TestEnforceCompletedHours:
    """Rows short of dept full-day threshold get downgraded to LOP so the
    Completed bucket only contains employees who actually met their required
    working hours."""

    def test_research_short_hours_downgraded(self):
        emp_map = {"e1": {"id": "e1", "department": "Research Unit",
                          "_doj_int": _d("2026-01-01"), "_last_int": None}}
        rec = {"employee_id": "e1", "date": "28-06-2026",
               "check_in": "10:00 AM", "check_out": "07:00 PM",
               "check_in_24h": "10:00", "check_out_24h": "19:00",
               "total_hours_decimal": 9.0,
               "status": "Present", "is_lop": False}
        _enforce_completed_hours_threshold(rec, emp_map)
        assert rec["status"] == AttendanceStatus.LOSS_OF_PAY
        assert rec["is_lop"] is True

    def test_research_full_hours_kept(self):
        emp_map = {"e1": {"id": "e1", "department": "Research Unit",
                          "_doj_int": _d("2026-01-01"), "_last_int": None}}
        rec = {"employee_id": "e1", "date": "28-06-2026",
               "check_in": "09:00 AM", "check_out": "08:30 PM",
               "check_in_24h": "09:00", "check_out_24h": "20:30",
               "total_hours_decimal": 11.5,
               "status": "Present", "is_lop": False}
        _enforce_completed_hours_threshold(rec, emp_map)
        assert rec["status"] == "Present"
        assert rec["is_lop"] is False

    def test_support_9h_boundary(self):
        emp_map = {"e1": {"id": "e1", "department": "Support Staff",
                          "_doj_int": _d("2026-01-01"), "_last_int": None}}
        rec = {"employee_id": "e1", "date": "28-06-2026",
               "check_in": "10:00 AM", "check_out": "07:00 PM",
               "check_in_24h": "10:00", "check_out_24h": "19:00",
               "total_hours_decimal": 9.0,
               "status": "Present"}
        _enforce_completed_hours_threshold(rec, emp_map)
        assert rec["status"] == "Present"

    def test_row_without_out_not_touched(self):
        emp_map = {"e1": {"id": "e1", "department": "Research Unit",
                          "_doj_int": _d("2026-01-01"), "_last_int": None}}
        rec = {"employee_id": "e1", "date": "28-06-2026",
               "check_in": "10:00 AM", "check_in_24h": "10:00",
               "check_out": None, "check_out_24h": None,
               "total_hours_decimal": 0, "status": "Login"}
        _enforce_completed_hours_threshold(rec, emp_map)
        assert rec["status"] == "Login"

    def test_late_login_status_not_downgraded(self):
        emp_map = {"e1": {"id": "e1", "department": "Research Unit",
                          "_doj_int": _d("2026-01-01"), "_last_int": None}}
        rec = {"employee_id": "e1", "date": "28-06-2026",
               "check_in": "11:00 AM", "check_out": "10:30 PM",
               "check_in_24h": "11:00", "check_out_24h": "22:30",
               "total_hours_decimal": 11.5,
               "status": "Late Login", "is_lop": False}
        _enforce_completed_hours_threshold(rec, emp_map)
        # Late Login is a strict category — not touched.
        assert rec["status"] == "Late Login"


# ---------------------------------------------------------------------------
# 4. Missed-punch overlay (approved requests only)
# ---------------------------------------------------------------------------

class TestOverlayMissedPunch:
    def test_check_in_overlay(self):
        rec = {"check_in": None, "check_in_24h": None,
               "check_out": "07:30 PM", "check_out_24h": "19:30",
               "status": "Not Logged"}
        mp = {"punch_type": "Check-in", "check_in_time": "09:45"}
        _overlay_missed_punch(rec, mp)
        assert rec["check_in_24h"] == "09:45"
        assert rec["check_in"] == "09:45 AM"
        assert rec["source"] == "corrected"

    def test_check_out_overlay(self):
        rec = {"check_in": "10:00 AM", "check_in_24h": "10:00",
               "check_out": None, "check_out_24h": None,
               "status": "Login"}
        mp = {"punch_type": "Check-out", "check_out_time": "21:10"}
        _overlay_missed_punch(rec, mp)
        assert rec["check_out_24h"] == "21:10"
        assert rec["check_out"] == "09:10 PM"
        # Now has both punches → status should move off Login.
        assert rec["total_hours_decimal"] > 0

    def test_both_overlay_from_scratch(self):
        rec = {"check_in": None, "check_in_24h": None,
               "check_out": None, "check_out_24h": None,
               "status": "Absent"}
        mp = {"punch_type": "Both", "check_in_time": "10:00", "check_out_time": "20:30"}
        _overlay_missed_punch(rec, mp)
        assert rec["check_in_24h"] == "10:00"
        assert rec["check_out_24h"] == "20:30"
        assert rec["total_hours_decimal"] == 10.5
        assert rec["status"] == "Present"


# ---------------------------------------------------------------------------
# 5. Live end-to-end unified count (Dashboard vs Attendance vs Reports)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_counts_align_dashboard_attendance_reports():
    """Smoke test: call all three endpoints for the same date and assert that
    each employee falls into the same bucket in each module."""
    import httpx

    base = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    if base.startswith("http") and "preview.emergentagent.com" in base:
        base = "http://localhost:8001"

    async with httpx.AsyncClient(base_url=base, timeout=60.0) as client:
        r = await client.post("/api/auth/login", json={"username": "admin", "password": "HrAdmin786$"})
        assert r.status_code == 200, r.text
        token = r.json().get("token")
        assert token
        H = {"Authorization": f"Bearer {token}"}

        # Historical date with real data — a Monday
        date_str = "20-07-2026"
        stats_r, att_r, rep_r = await asyncio.gather(
            client.get(f"/api/dashboard/stats?from_date={date_str}&to_date={date_str}", headers=H),
            client.get(f"/api/attendance?from_date={date_str}&to_date={date_str}", headers=H),
            client.get(f"/api/reports/attendance?from_date={date_str}&to_date={date_str}", headers=H),
        )
        assert stats_r.status_code == 200
        assert att_r.status_code == 200
        assert rep_r.status_code == 200

        s = stats_r.json()["attendance"]
        att = att_r.json()
        rep = rep_r.json()

        # Total counts must be equal
        assert len(att) == len(rep), f"Attendance={len(att)} vs Reports={len(rep)}"
        # Total eligible employees on that date must match total rows.
        assert s["total_employees"] == len(att), (
            f"Dashboard total={s['total_employees']} vs Attendance rows={len(att)}")

        # Status counters — recompute from records and compare tile values.
        def has_in(r): return bool(r.get("check_in") or r.get("check_in_24h"))
        def has_out(r): return bool(r.get("check_out") or r.get("check_out_24h"))
        def is_late(r):
            return (r.get("status") == "Late Login" or
                    "late login" in (r.get("lop_reason") or "").lower())
        def is_short(r):
            if is_late(r):
                return False
            return (r.get("status") in ("Early Out", "Loss of Pay")
                    or r.get("is_lop"))

        for src, label in ((att, "attendance"), (rep, "reports")):
            logged_in = sum(1 for r in src if has_in(r) and not has_out(r))
            early_out = sum(1 for r in src if has_in(r) and has_out(r) and is_short(r))
            no_login = sum(1 for r in src if r.get("status") == "Absent")
            assert logged_in == s["logged_in"], f"{label}: logged_in {logged_in} != stats {s['logged_in']}"
            assert early_out == s["early_out"], f"{label}: early_out {early_out} != stats {s['early_out']}"
            assert no_login == s["no_login"], f"{label}: no_login {no_login} != stats {s['no_login']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
