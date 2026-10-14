"""Pytest for /api/dashboard/leave-list behavior (TEST_DL_ seeded data)."""
import os
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://blubridge-rgb-import.preview.emergentagent.com").rstrip("/")

ADMIN_CREDS = [("admin", "pass123"), ("admin", "HrAdmin@2109"), ("sysadmin", "pass123")]

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]


@pytest.fixture(scope="module")
def token():
    for u, p in ADMIN_CREDS:
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": u, "password": p}, timeout=20)
        if r.status_code == 200:
            tok = r.json().get("access_token") or r.json().get("token")
            if tok:
                print(f"Logged in as {u}")
                return tok
    pytest.skip("No admin credential worked")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _get_list(headers):
    r = requests.get(f"{BASE_URL}/api/dashboard/leave-list", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _by_name(rows):
    return {r["emp_name"]: r for r in rows if r["emp_name"].startswith("TEST_DL_")}


def test_pending_full_has_type_and_pending(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_pending_full")
    assert r, "pending_full missing"
    assert r["leave_type"] == "Sick"
    assert r["reason"] == "Fever"
    assert r["status"] == "Pending"


def test_approved_full_has_type_and_approved(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_approved_full")
    assert r
    assert r["leave_type"] == "Preplanned"
    assert r["reason"] == "Personal work"
    assert r["status"] == "Approved"


def test_rejected_full_shows_not_login(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_rejected_full")
    assert r
    assert r["leave_type"] == "-"
    assert r["status"] == "Not Login"


def test_cancelled_full_shows_not_login(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_cancelled_full")
    assert r
    assert r["leave_type"] == "-"
    assert r["status"] == "Not Login"


def test_first_half_shows_not_login(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_first_half_pending")
    assert r
    assert r["leave_type"] == "-"
    assert r["status"] == "Not Login"


def test_second_half_shows_not_login(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_second_half_approved")
    assert r
    assert r["leave_type"] == "-"
    assert r["status"] == "Not Login"


def test_nologin_no_leave_shows_not_login(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_nologin")
    assert r
    assert r["leave_type"] == "-"
    assert r["status"] == "Not Login"


def test_rejected_plus_pending_uses_valid_pending(headers):
    rows = _by_name(_get_list(headers))
    r = rows.get("TEST_DL_rejected_plus_pending")
    assert r
    assert r["leave_type"] == "Emergency"
    assert r["reason"] == "Valid pending"
    assert r["status"] == "Pending"


def test_punched_in_not_in_list(headers):
    rows = _by_name(_get_list(headers))
    assert "TEST_DL_punched_in" not in rows


def test_no_duplicates(headers):
    rows = _get_list(headers)
    names = [r["emp_name"] for r in rows if r["emp_name"].startswith("TEST_DL_")]
    assert len(names) == len(set(names)), f"duplicates found: {names}"


def test_stats_count_matches_list(headers):
    rows = _get_list(headers)
    r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers, timeout=30)
    assert r.status_code == 200
    stats = r.json()
    not_logged = stats.get("attendance", {}).get("not_logged")
    # list is capped at 50, so compare appropriately
    assert not_logged is not None
    print(f"stats not_logged={not_logged}, list_len={len(rows)}")
    # Only strict compare when under cap
    if not_logged <= 50:
        assert not_logged == len(rows), f"mismatch: stats={not_logged} list={len(rows)}"


def test_status_transition_pending_to_approved(headers):
    # Flip pending_full -> approved and verify
    emp = db.employees.find_one({"full_name": "TEST_DL_pending_full"})
    db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "approved"}})
    try:
        rows = _by_name(_get_list(headers))
        r = rows["TEST_DL_pending_full"]
        assert r["status"] == "Approved"
        assert r["leave_type"] == "Sick"
    finally:
        db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "pending"}})


def test_status_transition_approved_to_rejected(headers):
    emp = db.employees.find_one({"full_name": "TEST_DL_approved_full"})
    db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "rejected"}})
    try:
        rows = _by_name(_get_list(headers))
        r = rows["TEST_DL_approved_full"]
        assert r["leave_type"] == "-"
        assert r["status"] == "Not Login"
    finally:
        db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "approved"}})
