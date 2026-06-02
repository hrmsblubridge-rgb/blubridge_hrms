"""Regression tests for the BluBridge HRMS Birthday widget consistency.

These tests enforce two invariants that previously regressed:

1. **Unified window across admin and employee dashboards.** Both call the
   same `GET /api/dashboard/birthdays` endpoint and (when no override is
   passed) receive the SAME 30-day window. The frontend `Dashboard.js`
   used to pass `windowDays=7` while `EmployeeDashboard.js` passed
   `windowDays=30`, creating visible drift between the two portals.

2. **Active-only filter.** The birthday widget MUST hide Inactive /
   Resigned / Soft-deleted employees even when their DOB falls within
   the window. Previously the endpoint only excluded `is_deleted=True`,
   so Inactive/Resigned employees could leak in.

The tests construct a synthetic employee with a DOB exactly N days in
the future (using IST clock), flip their `employee_status` through
Active → Inactive → Resigned, and assert that only the Active state
surfaces them in the widget.

The test is fully self-cleaning — the synthetic doc is deleted in a
finally block whether assertions pass or fail.
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"
HTTP_TIMEOUT = 30.0


def _login(username, password):
    r = httpx.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200:
        return None
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    t = _login("sysadmin", "pass123")
    assert t, "sysadmin login failed"
    return t


@pytest.fixture(scope="module")
def employee_token():
    t = _login("user", "pass123")
    assert t, "employee 'user' login failed"
    return t


def _birthdays(token, params=None):
    r = httpx.get(
        f"{API}/dashboard/birthdays",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1) Default window is 30 days — unified across logins
# ---------------------------------------------------------------------------

def test_default_window_is_30_days(admin_token):
    body = _birthdays(admin_token)
    assert body["window_days"] == 30


def test_admin_and_employee_see_identical_payload(admin_token, employee_token):
    admin = _birthdays(admin_token)
    emp = _birthdays(employee_token)
    # Same window
    assert admin["window_days"] == emp["window_days"] == 30
    # Same set of employees in both buckets (order-stable: server already sorts)
    admin_ids = sorted([e["id"] for e in admin["upcoming"]])
    emp_ids = sorted([e["id"] for e in emp["upcoming"]])
    assert admin_ids == emp_ids, (
        f"Admin and employee dashboards diverged: admin={admin_ids} employee={emp_ids}"
    )
    admin_today = sorted([e["id"] for e in admin["today"]])
    emp_today = sorted([e["id"] for e in emp["today"]])
    assert admin_today == emp_today


# ---------------------------------------------------------------------------
# 2) Inactive / Resigned / Soft-deleted employees are EXCLUDED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inactive_and_resigned_employees_are_excluded(admin_token):
    """Synthetic round-trip: insert an employee with a DOB 5 days in the
    future, flip status and assert exclusion logic at each state."""
    # Import here so the test module remains importable without backend deps
    from server import db, get_ist_now, EmployeeStatus  # noqa

    now = get_ist_now().date()
    target = now + timedelta(days=5)
    # Use a clearly-old birth year so admins can tell this is synthetic
    dob_iso = target.replace(year=1992).isoformat()

    emp_id = str(uuid.uuid4())
    synth = {
        "id": emp_id,
        "emp_id": f"BDAY-TEST-{emp_id[:8]}",
        "full_name": "__BIRTHDAY_TEST_EMP__",
        "official_email": f"bday-test-{emp_id[:8]}@example.com",
        "department": "Test",
        "team": "Test",
        "designation": "Test",
        "date_of_birth": dob_iso,
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": False,
    }
    await db.employees.insert_one(synth)

    try:
        def _has(body):
            return any(e["id"] == emp_id for e in body["upcoming"])

        # ACTIVE → visible
        await db.employees.update_one(
            {"id": emp_id}, {"$set": {"employee_status": EmployeeStatus.ACTIVE}}
        )
        assert _has(_birthdays(admin_token)), "Active employee MUST be visible"

        # INACTIVE → hidden
        await db.employees.update_one(
            {"id": emp_id}, {"$set": {"employee_status": EmployeeStatus.INACTIVE}}
        )
        assert not _has(_birthdays(admin_token)), "Inactive employee MUST be hidden"

        # RESIGNED → hidden
        await db.employees.update_one(
            {"id": emp_id}, {"$set": {"employee_status": EmployeeStatus.RESIGNED}}
        )
        assert not _has(_birthdays(admin_token)), "Resigned employee MUST be hidden"

        # Back to ACTIVE but soft-deleted → still hidden
        await db.employees.update_one(
            {"id": emp_id},
            {"$set": {"employee_status": EmployeeStatus.ACTIVE, "is_deleted": True}},
        )
        assert not _has(_birthdays(admin_token)), "Soft-deleted employee MUST be hidden"

    finally:
        # Always clean up to keep the regression suite idempotent.
        await db.employees.delete_one({"id": emp_id})


# ---------------------------------------------------------------------------
# 3) Window-day parameter still works (back-compat for any direct caller)
# ---------------------------------------------------------------------------

def test_explicit_window_param_overrides_default(admin_token):
    body = _birthdays(admin_token, {"window_days": 7})
    assert body["window_days"] == 7
    # No upcoming entry beyond the requested window
    for u in body["upcoming"]:
        assert u["days_until"] <= 7
