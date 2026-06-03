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


# ---------------------------------------------------------------------------
# 4) DOB format tolerance — guards against the "silent skip" regression
#    where employees with valid-but-unusual DOB strings were dropped.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("dob_format_value_builder", [
    # YYYY-MM-DD
    lambda today: today.replace(year=1990).isoformat(),
    # DD-MM-YYYY (Indian numeric)
    lambda today: today.replace(year=1990).strftime("%d-%m-%Y"),
    # DD/MM/YYYY
    lambda today: today.replace(year=1990).strftime("%d/%m/%Y"),
    # DD-Mon-YYYY (the new global display format)
    lambda today: today.replace(year=1990).strftime("%d-%b-%Y"),
    # ISO datetime with time (what JS Date.toISOString() emits)
    lambda today: today.replace(year=1990).isoformat() + "T00:00:00.000Z",
])
async def test_today_birthday_shown_for_every_dob_format(admin_token, dob_format_value_builder):
    """The widget MUST surface today's birthday regardless of the format
    the DOB happens to be stored in. Previously `_parse_date_flex` silently
    returned None for several legitimate formats and the employee was
    skipped — this parametric test locks that bug closed."""
    from server import db, get_ist_now, EmployeeStatus  # noqa

    today = get_ist_now().date()
    emp_id = str(uuid.uuid4())
    dob_value = dob_format_value_builder(today)

    await db.employees.insert_one({
        "id": emp_id,
        "emp_id": f"BDAY-FMT-{emp_id[:8]}",
        "full_name": "__BDAY_FMT_TEST__",
        "department": "Test",
        "team": "Test",
        "designation": "Test",
        "date_of_birth": dob_value,
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": False,
    })

    try:
        body = _birthdays(admin_token)
        today_ids = [e["id"] for e in body["today"]]
        assert emp_id in today_ids, (
            f"Today's birthday DROPPED for DOB format {dob_value!r}. "
            f"today_ids={today_ids}"
        )
    finally:
        await db.employees.delete_one({"id": emp_id})


# ---------------------------------------------------------------------------
# 5) Boundary cases (today / tomorrow / N+30 / leap-year)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("days_offset,expected_bucket", [
    (0, "today"),
    (1, "upcoming"),
    (15, "upcoming"),
    (30, "upcoming"),    # exactly on window boundary — must appear
    (31, "neither"),     # one day outside — must NOT appear
])
async def test_birthday_window_boundaries(admin_token, days_offset, expected_bucket):
    from datetime import timedelta
    from server import db, get_ist_now, EmployeeStatus  # noqa

    today = get_ist_now().date()
    target = today + timedelta(days=days_offset)
    dob_value = target.replace(year=1990).isoformat()
    emp_id = str(uuid.uuid4())

    await db.employees.insert_one({
        "id": emp_id,
        "emp_id": f"BDAY-BNDRY-{emp_id[:8]}",
        "full_name": "__BDAY_BNDRY__",
        "department": "Test",
        "team": "Test",
        "designation": "Test",
        "date_of_birth": dob_value,
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": False,
    })

    try:
        body = _birthdays(admin_token)
        today_ids = [e["id"] for e in body["today"]]
        upcoming_ids = [e["id"] for e in body["upcoming"]]
        if expected_bucket == "today":
            assert emp_id in today_ids
        elif expected_bucket == "upcoming":
            assert emp_id in upcoming_ids, (
                f"+{days_offset}d expected in upcoming, missing. upcoming={upcoming_ids}"
            )
        else:
            assert emp_id not in today_ids and emp_id not in upcoming_ids
    finally:
        await db.employees.delete_one({"id": emp_id})


@pytest.mark.asyncio
async def test_leap_year_dob_does_not_crash(admin_token):
    """A DOB of Feb-29 must not 500 the endpoint in non-leap years."""
    from server import db, EmployeeStatus  # noqa
    emp_id = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": emp_id,
        "emp_id": f"BDAY-LEAP-{emp_id[:8]}",
        "full_name": "__BDAY_LEAP__",
        "department": "Test",
        "team": "Test",
        "designation": "Test",
        "date_of_birth": "2000-02-29",
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": False,
    })
    try:
        body = _birthdays(admin_token)
        # Whether it lands in window or not depends on the current date,
        # but the endpoint MUST respond 200 — no Feb-29-in-2025 crash.
        assert "today" in body and "upcoming" in body
    finally:
        await db.employees.delete_one({"id": emp_id})


@pytest.mark.asyncio
async def test_multiple_employees_same_day_all_appear(admin_token):
    """If 3 employees share the same DOB (today), all 3 must appear."""
    from server import db, get_ist_now, EmployeeStatus  # noqa
    today = get_ist_now().date()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    docs = [{
        "id": i,
        "emp_id": f"BDAY-MULTI-{i[:8]}",
        "full_name": f"__BDAY_MULTI_{n}__",
        "department": "Test",
        "team": "Test",
        "designation": "Test",
        "date_of_birth": today.replace(year=1985 + n).isoformat(),
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": False,
    } for n, i in enumerate(ids)]
    for d in docs:
        await db.employees.insert_one(d)
    try:
        body = _birthdays(admin_token)
        today_ids = {e["id"] for e in body["today"]}
        for i in ids:
            assert i in today_ids, f"missing synthetic id {i} in today bucket"
    finally:
        for i in ids:
            await db.employees.delete_one({"id": i})
