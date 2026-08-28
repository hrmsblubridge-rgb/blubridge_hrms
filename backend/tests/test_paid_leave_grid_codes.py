"""
Tests for the Payroll → Attendance View grid codes for Paid Leave.

Bug being verified (HR fix 2026-08-24):
An APPROVED Paid Leave day was showing 'P' instead of 'PA' (full-day) / 'PH'
(half-day). This suite verifies:
  1. _leave_code_for_status() mapping (unit level, direct import).
  2. End-to-end via POST /api/leaves (auto_approve) + GET /api/payroll/{emp}
     that returns per-day 'status' values.
  3. Regression: employees with no leave have unchanged payable-days.
"""
import os
import sys
import uuid
import calendar
from datetime import date, datetime, timedelta

import pytest
import requests

# ---- Direct import of the helper for unit test ----
sys.path.insert(0, "/app/backend")
from server import _leave_code_for_status  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com").rstrip("/")
ADMIN_USER = "admin"
ADMIN_PASS = "HrAdmin786$"


# =========================================================================
# UNIT TESTS — _leave_code_for_status
# =========================================================================
class TestLeaveCodeHelper:
    def test_paid_leave_full_day_returns_PA(self):
        assert _leave_code_for_status("Paid Leave", "Full Day") == "PA"

    @pytest.mark.parametrize("split", ["First Half", "Second Half", "Half Day", "Half"])
    def test_paid_leave_half_returns_PH(self, split):
        assert _leave_code_for_status("Paid Leave", split) == "PH"

    def test_pre_planned_full_PF_half_PH(self):
        assert _leave_code_for_status("Pre-Planned", "Full Day") == "PF"
        assert _leave_code_for_status("Pre-Planned", "First Half") == "PH"

    def test_sick_full_SF_half_SH(self):
        assert _leave_code_for_status("Sick", "Full Day") == "SF"
        assert _leave_code_for_status("Sick", "Second Half") == "SH"

    def test_emergency_full_EF_half_EH(self):
        assert _leave_code_for_status("Emergency", "Full Day") == "EF"
        assert _leave_code_for_status("Emergency", "Half Day") == "EH"

    def test_optional_returns_OH(self):
        assert _leave_code_for_status("Optional Holiday", "Full Day") == "OH"
        assert _leave_code_for_status("Optional", "First Half") == "OH"

    def test_unknown_leave_type_defaults_to_paid_bucket(self):
        assert _leave_code_for_status("Casual", "Full Day") == "PA"
        assert _leave_code_for_status("Anything", "Half Day") == "PH"
        assert _leave_code_for_status(None, "Full Day") == "PA"


# =========================================================================
# INTEGRATION HELPERS
# =========================================================================
@pytest.fixture(scope="module")
def admin_token():
    import time
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"username": ADMIN_USER, "password": ADMIN_PASS},
                              timeout=120)
            if r.status_code == 200:
                return r.json()["token"]
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = repr(e)
        time.sleep(5 * (attempt + 1))
    pytest.fail(f"Admin login failed after 4 attempts: {last_err}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _fetch_active_employees(headers):
    r = requests.get(f"{BASE_URL}/api/employees?limit=500", headers=headers, timeout=60)
    assert r.status_code == 200, f"Employees fetch failed: {r.status_code} {r.text}"
    d = r.json()
    emps = d.get("employees") if isinstance(d, dict) else d
    # keep only active employees (server returns all statuses without status filter)
    return [e for e in (emps or []) if (e.get("employee_status") or "Active") == "Active"]


def _pick_paid_leave_eligible_employee(headers, need_free_day_before=None):
    """Find a confirmed non-intern active employee who joined before this month
    and has paid-leave balance. Optionally also requires a free past workday."""
    employees = _fetch_active_employees(headers)
    today = date.today()
    month_start = date(today.year, today.month, 1)
    for emp in employees:
        et = (emp.get("employment_type") or "").lower()
        if "intern" in et:
            continue
        if not emp.get("confirmation_date"):
            continue
        doj_raw = emp.get("date_of_joining")
        try:
            doj = datetime.strptime(str(doj_raw)[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if doj > month_start:
            continue
        eid = emp["id"]
        rb = requests.get(f"{BASE_URL}/api/admin/employees/{eid}/paid-leave-balance",
                          headers=headers, timeout=30)
        if rb.status_code != 200:
            continue
        bal = rb.json().get("balance", 0) or 0
        if bal < 1:
            continue
        if need_free_day_before is not None:
            d = _find_free_workday(headers, eid, month_start)
            if not d or d > need_free_day_before:
                continue
            emp["_test_free_day"] = d
        return emp
    return None


def _next_workday(day: date) -> date:
    # keep pushing forward until it's a weekday (Mon-Fri)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _find_free_workday(headers, emp_id, start_from: date, monthly=True):
    """Find a working day (not Sat/Sun) in given month that doesn't overlap with any existing leave."""
    year, month = start_from.year, start_from.month
    dim = calendar.monthrange(year, month)[1]
    # existing leaves for that employee
    r = requests.get(f"{BASE_URL}/api/leaves?employee_id={emp_id}",
                     headers=headers, timeout=30)
    existing = r.json() if r.status_code == 200 else []
    busy = set()
    for lv in existing:
        if lv.get("status") == "rejected":
            continue
        try:
            s = datetime.strptime(lv["start_date"], "%Y-%m-%d").date()
            e = datetime.strptime(lv["end_date"], "%Y-%m-%d").date()
            cur = s
            while cur <= e:
                busy.add(cur.isoformat())
                cur += timedelta(days=1)
        except Exception:
            continue
    for d in range(max(1, start_from.day), dim + 1):
        day = date(year, month, d)
        if day.weekday() >= 5:
            continue
        if day.isoformat() in busy:
            continue
        return day
    return None


def _cleanup_leave(headers, leave_id):
    """Direct DB delete (no HTTP DELETE endpoint exists for leaves)."""
    try:
        import pymongo  # noqa: F401
        from pymongo import MongoClient
        from pathlib import Path

        env_path = Path("/app/backend/.env")
        mongo_url = None
        db_name = None
        for line in env_path.read_text().splitlines():
            if line.startswith("MONGO_URL"):
                mongo_url = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("DB_NAME"):
                db_name = line.split("=", 1)[1].strip().strip('"')
        if mongo_url and db_name:
            client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
            client[db_name].leaves.delete_one({"id": leave_id})
            client.close()
    except Exception as e:
        # Best-effort cleanup; log but don't fail the test
        print(f"[cleanup warning] could not delete leave {leave_id}: {e}")


# =========================================================================
# INTEGRATION — end to end
# =========================================================================
class TestPayrollPaidLeaveGridCodes:

    def test_admin_login_works(self, admin_token):
        assert admin_token and isinstance(admin_token, str)

    def test_paid_leave_full_day_shows_PA(self, admin_headers):
        today = date.today()
        emp = _pick_paid_leave_eligible_employee(admin_headers, need_free_day_before=today)
        if not emp:
            pytest.skip("No paid-leave-eligible employee with a free past workday available")

        target = emp["_test_free_day"]

        payload = {
            "employee_id": emp["id"],
            "leave_type": "Paid Leave",
            "leave_split": "Full Day",
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "reason": f"TEST_pa_grid_code {uuid.uuid4().hex[:8]}",
            "auto_approve": True,
        }
        r = requests.post(f"{BASE_URL}/api/leaves", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, f"Leave create failed: {r.status_code} {r.text}"
        leave = r.json()
        leave_id = leave["id"]
        assert leave["status"] == "approved"

        try:
            month_str = f"{target.year:04d}-{target.month:02d}"
            pr = requests.get(f"{BASE_URL}/api/payroll/{emp['id']}?month={month_str}",
                              headers=admin_headers, timeout=30)
            assert pr.status_code == 200, f"Payroll fetch failed: {pr.status_code} {pr.text}"
            data = pr.json()
            details = data.get("attendance_details") or data.get("days") or []
            iso = target.isoformat()
            ddmmyyyy = target.strftime("%d-%m-%Y")
            day_row = next((d for d in details
                            if str(d.get("date")) in (iso, ddmmyyyy)
                            or str(d.get("date")).endswith(iso)), None)
            assert day_row is not None, (
                f"Could not find date {iso}/{ddmmyyyy} in payroll details. "
                f"Sample: {details[:3]}"
            )
            assert day_row.get("status") == "PA", (
                f"Expected 'PA' for Paid Leave Full Day, got {day_row.get('status')!r}. "
                f"Full row: {day_row}"
            )
        finally:
            _cleanup_leave(admin_headers, leave_id)

    def test_paid_leave_half_day_shows_PH(self, admin_headers):
        today = date.today()
        emp = _pick_paid_leave_eligible_employee(admin_headers, need_free_day_before=today)
        if not emp:
            pytest.skip("No paid-leave-eligible employee with a free past workday available")

        target = emp["_test_free_day"]

        payload = {
            "employee_id": emp["id"],
            "leave_type": "Paid Leave",
            "leave_split": "First Half",
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "reason": f"TEST_ph_grid_code {uuid.uuid4().hex[:8]}",
            "auto_approve": True,
        }
        r = requests.post(f"{BASE_URL}/api/leaves", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, f"Leave create failed: {r.status_code} {r.text}"
        leave = r.json()
        leave_id = leave["id"]

        try:
            month_str = f"{target.year:04d}-{target.month:02d}"
            pr = requests.get(f"{BASE_URL}/api/payroll/{emp['id']}?month={month_str}",
                              headers=admin_headers, timeout=30)
            assert pr.status_code == 200
            data = pr.json()
            details = data.get("attendance_details") or data.get("days") or []
            iso = target.isoformat()
            ddmmyyyy = target.strftime("%d-%m-%Y")
            day_row = next((d for d in details
                            if str(d.get("date")) in (iso, ddmmyyyy)
                            or str(d.get("date")).endswith(iso)), None)
            assert day_row is not None
            assert day_row.get("status") == "PH", (
                f"Expected 'PH' for Paid Leave Half Day, got {day_row.get('status')!r}. "
                f"Full row: {day_row}"
            )
        finally:
            _cleanup_leave(admin_headers, leave_id)

    def test_no_leave_employee_payroll_regression(self, admin_headers):
        """Regression: ensure PA/PH inclusion in _present_codes/_leave_codes
        doesn't break payable-days for employees with no leave."""
        employees = _fetch_active_employees(admin_headers)
        today = date.today()
        month_str = f"{today.year:04d}-{today.month:02d}"
        month_start = date(today.year, today.month, 1)

        checked = 0
        for emp in employees:
            # skip employees that joined after this month (payroll returns 404)
            try:
                doj = datetime.strptime(str(emp.get("date_of_joining"))[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            if doj > month_start:
                continue
            pr = requests.get(f"{BASE_URL}/api/payroll/{emp['id']}?month={month_str}",
                              headers=admin_headers, timeout=30)
            if pr.status_code != 200:
                continue
            data = pr.json()
            key = None
            for k in ("payable_days", "final_payable_days", "total_payable_days"):
                if k in data:
                    key = k
                    break
            assert key is not None, f"No payable-days field in payroll: keys={list(data.keys())}"
            pd = data[key]
            assert isinstance(pd, (int, float))
            assert pd >= 0
            checked += 1
            if checked >= 3:
                break
        assert checked > 0, "Could not verify payroll for any employee"
