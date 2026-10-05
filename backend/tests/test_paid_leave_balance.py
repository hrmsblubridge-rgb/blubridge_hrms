"""Tests for the Paid Leave system (balance calc + validation).

Paid Leave business rules:
- 1 credit earned per calendar month (counting the joining month).
- Unused balance carries forward indefinitely.
- Half-day usage consumes 0.5; remaining 0.5 stays usable.
- Past + future date applications supported.
- Balance is point-in-time validated against the LEAVE START DATE.
- is_lop is forced to False for any Paid Leave.
"""
import os
import sys
import uuid
from datetime import date

import httpx
import pytest
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"
HTTP_TIMEOUT = 30.0
DB = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)[os.environ["DB_NAME"]]


def _login(username, password):
    r = httpx.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=HTTP_TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("sysadmin", "pass123")


@pytest.fixture
def test_employee():
    """Create a throwaway employee with DOJ = 2026-01-01 and clean up after."""
    eid = str(uuid.uuid4())
    DB.employees.insert_one({
        "id": eid,
        "emp_id": f"PL_TEST_{eid[:8]}",
        "full_name": "Paid Leave Test",
        "official_email": f"pltest+{eid[:8]}@example.com",
        "phone_number": "0000000000",
        "department": "Research Unit",
        "team": "Framework - Parallelism",
        "designation": "Engineer",
        "employment_type": "Full-time",
        "employee_status": "Active",
        "date_of_joining": "2026-01-01",
        # Confirmation Date set = DOJ so the employee is Paid-Leave ELIGIBLE
        # (business rule: Full-Time + valid Confirmation Date). Using DOJ keeps
        # accrual_start unchanged, so every balance assertion below is unaffected.
        "confirmation_date": "2026-01-01",
        "is_deleted": False,
    })
    yield eid
    DB.employees.delete_one({"id": eid})
    DB.leaves.delete_many({"employee_id": eid})


def _balance(token, eid, ref=None):
    params = {"reference_date": ref} if ref else {}
    r = httpx.get(
        f"{API}/admin/employees/{eid}/paid-leave-balance",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _create_leave(token, eid, leave_type, start, end, split="Full Day", auto_approve=True, expect=200):
    r = httpx.post(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": eid,
            "leave_type": leave_type,
            "leave_split": split,
            "start_date": start,
            "end_date": end,
            "reason": "Paid leave pytest fixture row",
            "auto_approve": auto_approve,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == expect, f"Expected {expect} got {r.status_code}: {r.text}"
    return r.json()


# ---------- BALANCE CALCULATION ----------

def test_balance_accumulates_one_per_month(admin_token, test_employee):
    """DOJ 2026-01-01 → at 2026-04-15 earned=4 (Jan, Feb, Mar, Apr)."""
    bal = _balance(admin_token, test_employee, "2026-04-15")
    assert bal["earned"] == 4.0
    assert bal["used"] == 0.0
    assert bal["balance"] == 4.0


def test_balance_zero_before_doj(admin_token, test_employee):
    bal = _balance(admin_token, test_employee, "2025-12-15")
    assert bal["earned"] == 0.0
    assert bal["balance"] == 0.0


def test_balance_half_day_consumes_half(admin_token, test_employee):
    _create_leave(admin_token, test_employee, "Paid", "2026-03-10", "2026-03-10", split="First Half")
    bal = _balance(admin_token, test_employee, "2026-03-15")
    assert bal["used"] == 0.5
    assert bal["balance"] == 3.0 - 0.5


def test_balance_full_day_consumes_one(admin_token, test_employee):
    _create_leave(admin_token, test_employee, "Paid Leave", "2026-02-05", "2026-02-05")
    bal = _balance(admin_token, test_employee, "2026-02-28")
    assert bal["used"] == 1.0
    assert bal["balance"] == 2.0 - 1.0


# ---------- VALIDATION ----------

def test_apply_blocked_when_over_balance(admin_token, test_employee):
    """DOJ Jan 1 → applying for Jan 1 itself: earned=1, used=0, available=1.
    A 2-day leave Jan 1-2 should be blocked (needs 2, has 1)."""
    r = httpx.post(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": test_employee,
            "leave_type": "Paid",
            "leave_split": "Full Day",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "reason": "Overdraw attempt — should be blocked",
            "auto_approve": True,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 400
    assert "Insufficient Paid Leave balance" in r.json()["detail"]


def test_apply_succeeds_when_balance_is_sufficient(admin_token, test_employee):
    """At Mar 15: earned=3, used=0 → 3-day leave should succeed."""
    lv = _create_leave(admin_token, test_employee, "Paid", "2026-03-15", "2026-03-17")
    assert lv["status"] == "approved"
    # is_lop must be False for Paid Leave (HR rule)
    assert lv["is_lop"] is False


def test_paid_leave_is_lop_forced_false_on_create(admin_token, test_employee):
    """Even if admin sends is_lop=True with auto_approve, Paid Leave must be paid."""
    r = httpx.post(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": test_employee,
            "leave_type": "Paid",
            "leave_split": "Full Day",
            "start_date": "2026-04-10",
            "end_date": "2026-04-10",
            "reason": "Forced non-LOP test for Paid Leave row",
            "auto_approve": True,
            "is_lop": True,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_lop"] is False


def test_other_leave_types_unaffected_by_paid_validator(admin_token, test_employee):
    """Sick Leave must not be subject to Paid Leave balance check."""
    # Sick leave for 10 days on Jan 1 — Paid Leave only has 1 credit by Jan, but
    # since this is SICK, the validator must NOT block it.
    r = httpx.post(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": test_employee,
            "leave_type": "Sick",
            "leave_split": "Full Day",
            "start_date": "2026-01-10",
            "end_date": "2026-01-19",
            "reason": "Sick leave should not be subject to Paid Leave checks",
            "auto_approve": True,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text


# ---------- HALF-DAY USAGE ----------

def test_remaining_half_day_still_usable(admin_token, test_employee):
    """After 0.5 used, remaining 0.5 should still allow a half-day apply."""
    _create_leave(admin_token, test_employee, "Paid", "2026-01-15", "2026-01-15", split="First Half")
    # Balance at 2026-01-15: earned=1, used=0.5 → available=0.5
    # A second half-day on Jan 16 (still Jan, still 1 credit) must succeed.
    lv = _create_leave(admin_token, test_employee, "Paid", "2026-01-16", "2026-01-16", split="Second Half")
    assert lv["leave_split"] == "Second Half"
    # But a THIRD half-day in Jan must be blocked (0.5+0.5+0.5 > 1).
    r = httpx.post(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": test_employee,
            "leave_type": "Paid",
            "leave_split": "First Half",
            "start_date": "2026-01-17",
            "end_date": "2026-01-17",
            "reason": "Third half-day in Jan — should be blocked",
            "auto_approve": True,
        },
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 400


# ---------- PAST + FUTURE DATES ----------

def test_past_date_uses_historical_balance(admin_token, test_employee):
    """Apply for past Feb date — historical balance (Jan + Feb = 2) should allow."""
    lv = _create_leave(admin_token, test_employee, "Paid", "2026-02-20", "2026-02-21")
    assert lv["status"] == "approved"


def test_future_date_uses_future_balance(admin_token, test_employee):
    """Apply for future Dec date — by Dec, lots of credits accumulated."""
    lv = _create_leave(admin_token, test_employee, "Paid", "2026-12-01", "2026-12-05")
    assert lv["status"] == "approved"


# ---------- DISPLAY BALANCE ----------

def test_display_balance_includes_future_committed_leaves(admin_token, test_employee):
    """Display balance (no reference_date) must count all future-booked
    Paid Leaves so the employee sees what's actually available."""
    _create_leave(admin_token, test_employee, "Paid", "2026-08-10", "2026-08-12")
    bal_display = _balance(admin_token, test_employee)
    assert bal_display["used"] >= 3.0
