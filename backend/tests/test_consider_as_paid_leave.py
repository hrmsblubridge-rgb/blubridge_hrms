"""Tests for Admin 'Consider as Paid Leave' feature (apply-on-behalf + approve).

Local DB only. Reseeds TEST_PL_ users each run.
"""
import os
import subprocess
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]

ADMIN_CREDS = [("admin", "pass123"), ("admin", "HrAdmin@2109")]


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password})
    return r


@pytest.fixture(scope="session", autouse=True)
def seed_data():
    subprocess.run(["python3", "/app/backend/tests/seed_paid_leave_test_data.py", "seed"], check=True)
    yield
    subprocess.run(["python3", "/app/backend/tests/seed_paid_leave_test_data.py", "cleanup"], check=True)
    db.paid_leave_generation.delete_many({"year": 2030, "month": 1})


@pytest.fixture(scope="session")
def admin_token():
    for u, p in ADMIN_CREDS:
        r = _login(u, p)
        if r.status_code == 200:
            return r.json().get("token") or r.json().get("access_token")
    pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture
def A(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}"})
    return s


def _emp(key):
    return db.employees.find_one({"full_name": f"TEST_PL_{key}"}, {"_id": 0})


def _bal(key):
    e = _emp(key)
    return round(float(e.get("available_paid_leave") or 0.0), 1)


# ---------- Admin paid-leave balance endpoint (eligibility) ----------

def test_admin_balance_fulltime2_eligible(A):
    emp = _emp("fulltime2")
    r = A.get(f"{API}/admin/employees/{emp['id']}/paid-leave-balance")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["balance"] == 2.0
    assert data["eligible"] is True


def test_admin_balance_intern_not_eligible(A):
    emp = _emp("intern")
    r = A.get(f"{API}/admin/employees/{emp['id']}/paid-leave-balance")
    assert r.status_code == 200
    data = r.json()
    assert data["eligible"] is False
    assert data.get("reason")


# ---------- Admin Apply for Employee with checkbox (POST /api/leaves) ----------

def test_apply_for_employee_paid_full_day_reserves(A):
    emp = _emp("fulltime2")
    before = _bal("fulltime2")
    payload = {
        "employee_id": emp["id"],
        "leave_type": "Casual Leave",
        "start_date": "2026-11-10",
        "end_date": "2026-11-10",
        "leave_split": "Full Day",
        "reason": "TEST_PL apply paid",
        "consider_as_paid_leave": True,
    }
    r = A.post(f"{API}/leaves", json=payload)
    assert r.status_code in (200, 201), r.text
    lv = r.json()
    assert lv["consider_as_paid_leave"] is True
    assert lv["paid_leave_reservation_status"] in ("reserved", "finalized")
    assert _bal("fulltime2") == round(before - 1.0, 1)
    db.leaves.delete_many({"reason": "TEST_PL apply paid"})
    db.employees.update_one({"id": emp["id"]}, {"$set": {"available_paid_leave": before}})


def test_apply_for_employee_unchecked_no_balance_change(A):
    emp = _emp("fulltime2")
    before = _bal("fulltime2")
    payload = {
        "employee_id": emp["id"],
        "leave_type": "Casual Leave",
        "start_date": "2026-11-11",
        "end_date": "2026-11-11",
        "leave_split": "Full Day",
        "reason": "TEST_PL apply unchecked",
    }
    r = A.post(f"{API}/leaves", json=payload)
    assert r.status_code in (200, 201), r.text
    lv = r.json()
    assert not lv.get("consider_as_paid_leave")
    assert _bal("fulltime2") == before
    db.leaves.delete_many({"reason": "TEST_PL apply unchecked"})


# ---------- Approve pending leave with consider_as_paid_leave ----------

def _create_pending_leave(emp_id, start, end, split="Full Day", reason="TEST_PL pending"):
    import uuid, datetime
    doc = {
        "id": str(uuid.uuid4()), "employee_id": emp_id, "emp_name": "TEST_PL",
        "leave_type": "Casual Leave", "start_date": start, "end_date": end,
        "leave_split": split, "reason": reason, "status": "pending",
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    db.leaves.insert_one(doc)
    return doc["id"]


def test_approve_with_paid_checkbox_finalizes(A):
    emp = _emp("fulltime2")
    before = _bal("fulltime2")
    lid = _create_pending_leave(emp["id"], "2026-11-20", "2026-11-20")
    r = A.put(f"{API}/leaves/{lid}/approve",
              json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r.status_code == 200, r.text
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["status"] == "approved"
    assert lv["consider_as_paid_leave"] is True
    assert lv["paid_leave_reservation_status"] == "finalized"
    assert lv.get("is_lop") is False
    assert _bal("fulltime2") == round(before - 1.0, 1)
    db.leaves.delete_many({"id": lid})
    db.employees.update_one({"id": emp["id"]}, {"$set": {"available_paid_leave": before}})


def test_approve_paid_insufficient_balance_fulltime0(A):
    emp = _emp("fulltime0")
    before = _bal("fulltime0")
    assert before == 0.0
    lid = _create_pending_leave(emp["id"], "2027-02-10", "2027-02-10")
    r = A.put(f"{API}/leaves/{lid}/approve",
              json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r.status_code == 400, r.text
    assert "Cannot mark as Paid Leave: insufficient" in r.json().get("detail", "")
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["status"] == "pending"
    assert not lv.get("consider_as_paid_leave")
    assert _bal("fulltime0") == 0.0
    db.leaves.delete_many({"id": lid})


def test_generate_future_month_then_approve_paid(A):
    emp = _emp("fulltime0")
    assert _bal("fulltime0") == 0.0
    # Clear any prior gen for 2030-01 (safety)
    db.paid_leave_generation.delete_one({"year": 2030, "month": 1})
    r = A.post(f"{API}/admin/paid-leave/generate", json={"year": 2030, "month": 1})
    assert r.status_code == 200, r.text
    # add tag for easy cleanup
    db.paid_leave_generation.update_one({"year": 2030, "month": 1}, {"$set": {"test_tag": "TEST_PL_"}})
    assert _bal("fulltime0") >= 1.0
    lid = _create_pending_leave(emp["id"], "2030-01-10", "2030-01-10")
    r = A.put(f"{API}/leaves/{lid}/approve",
              json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r.status_code == 200, r.text
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["consider_as_paid_leave"] is True
    assert lv["paid_leave_reservation_status"] == "finalized"
    db.leaves.delete_many({"id": lid})


def test_halfbal_half_day_ok_full_day_fails(A):
    emp = _emp("halfbal")
    # Reset to 0.5 in case prior generate test topped it up
    db.employees.update_one({"id": emp["id"]}, {"$set": {"available_paid_leave": 0.5}})
    before = _bal("halfbal")
    assert before == 0.5
    # full-day should fail
    lid_full = _create_pending_leave(emp["id"], "2026-11-25", "2026-11-25", split="Full Day")
    r = A.put(f"{API}/leaves/{lid_full}/approve",
              json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r.status_code == 400
    assert "insufficient" in r.json().get("detail", "")
    db.leaves.delete_many({"id": lid_full})
    # half-day should succeed
    lid_half = _create_pending_leave(emp["id"], "2026-11-26", "2026-11-26", split="First Half")
    r = A.put(f"{API}/leaves/{lid_half}/approve",
              json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r.status_code == 200, r.text
    lv = db.leaves.find_one({"id": lid_half}, {"_id": 0})
    assert lv["consider_as_paid_leave"] is True
    assert _bal("halfbal") == 0.0
    db.leaves.delete_many({"id": lid_half})
    db.employees.update_one({"id": emp["id"]}, {"$set": {"available_paid_leave": before}})


def test_intern_cannot_mark_paid(A):
    emp = _emp("intern")
    lid = _create_pending_leave(emp["id"], "2026-11-28", "2026-11-28")
    r = A.put(f"{API}/leaves/{lid}/approve",
              json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r.status_code == 403, r.text
    db.leaves.delete_many({"id": lid})


def test_reject_paid_reserved_releases_balance(A):
    emp = _emp("fulltime2")
    before = _bal("fulltime2")
    # Apply for employee with paid
    payload = {"employee_id": emp["id"], "leave_type": "Casual Leave",
               "start_date": "2026-12-05", "end_date": "2026-12-05",
               "leave_split": "Full Day", "reason": "TEST_PL reject paid",
               "consider_as_paid_leave": True}
    r = A.post(f"{API}/leaves", json=payload)
    assert r.status_code in (200, 201), r.text
    lid = r.json()["id"]
    assert _bal("fulltime2") == round(before - 1.0, 1)
    rj = A.put(f"{API}/leaves/{lid}/reject", json={"rejection_reason": "test"})
    assert rj.status_code == 200, rj.text
    assert _bal("fulltime2") == before
    db.leaves.delete_many({"id": lid})


def test_double_approve_no_double_deduct(A):
    emp = _emp("fulltime2")
    before = _bal("fulltime2")
    lid = _create_pending_leave(emp["id"], "2026-12-10", "2026-12-10")
    r1 = A.put(f"{API}/leaves/{lid}/approve",
               json={"leave_validity": "valid", "consider_as_paid_leave": True})
    assert r1.status_code == 200
    mid = _bal("fulltime2")
    assert mid == round(before - 1.0, 1)
    # Approving again — should not re-deduct
    r2 = A.put(f"{API}/leaves/{lid}/approve",
               json={"leave_validity": "valid", "consider_as_paid_leave": True})
    # may 200 or 400; balance must not change
    assert _bal("fulltime2") == mid
    db.leaves.delete_many({"id": lid})
    db.employees.update_one({"id": emp["id"]}, {"$set": {"available_paid_leave": before}})


def test_normal_approve_without_checkbox_keeps_lop(A):
    emp = _emp("fulltime2")
    before = _bal("fulltime2")
    lid = _create_pending_leave(emp["id"], "2026-12-15", "2026-12-15")
    r = A.put(f"{API}/leaves/{lid}/approve",
              json={"leave_validity": "valid", "is_lop": True})
    assert r.status_code == 200, r.text
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["status"] == "approved"
    assert lv.get("is_lop") is True
    assert not lv.get("consider_as_paid_leave")
    assert _bal("fulltime2") == before
    db.leaves.delete_many({"id": lid})


# ---------- Regression: list, history, Paid Leave Management ----------

def test_leaves_list_loads(A):
    r = A.get(f"{API}/leaves")
    assert r.status_code == 200


def test_paid_leave_status_loads(A):
    r = A.get(f"{API}/admin/paid-leave/status?year=2026&month=10")
    assert r.status_code == 200
