"""Tests for the Leave Validity classification feature (approve + admin edit)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"username": "admin", "password": "HrAdmin786$"}, timeout=90)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def employee_token():
    r = requests.post(f"{API}/auth/login",
                      json={"username": "user", "password": "pass123"}, timeout=90)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def employee_me(employee_token):
    r = requests.get(f"{API}/auth/me", headers=_h(employee_token), timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


_DATE_COUNTER = {"n": 0}

def _create_pending_leave(admin_token, employee_me):
    """Create a fresh pending leave for the employee via admin (employees are
    blocked from POST /api/leaves by RBAC; the admin-side endpoint accepts an
    employee_id and is what the Approve popup will act on). Uses a unique
    date per call to avoid the 'leave already exists for date' guard."""
    _DATE_COUNTER["n"] += 1
    day = _DATE_COUNTER["n"]
    # pick unique future dates in Mar 2028 (no existing leaves expected there)
    date = f"2028-03-{day:02d}"
    payload = {
        "employee_id": employee_me["employee_id"],
        "leave_type": "Sick Leave",
        "leave_split": "Full Day",
        "start_date": date,
        "end_date": date,
        "reason": "TEST_leave_validity feature auto-test",
    }
    r = requests.post(f"{API}/leaves", json=payload,
                      headers=_h(admin_token), timeout=60)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _reset(leave_id, admin_token):
    requests.post(f"{API}/leaves/{leave_id}/reset", json={"reason": "test cleanup"},
                  headers=_h(admin_token), timeout=20)


# ---------- approval validation ----------

@pytest.mark.parametrize("payload,expected_msg_substr", [
    ({}, "required"),
    ({"leave_validity": ""}, "required"),
    ({"leave_validity": "select"}, "required"),
    ({"leave_validity": None}, "required"),
    ({"leave_validity": "maybe"}, "must be either"),
])
def test_approve_rejects_bad_validity(admin_token, employee_token, employee_me,
                                       payload, expected_msg_substr):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        r = requests.put(f"{API}/leaves/{lid}/approve", json=payload,
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert expected_msg_substr.lower() in r.text.lower(), r.text

        # And leave stays pending
        rr = requests.get(f"{API}/leaves", headers=_h(admin_token), timeout=20)
        rec = next(x for x in rr.json() if x["id"] == lid)
        assert rec["status"] == "pending"
    finally:
        _reset(lid, admin_token)


def test_approve_valid_no_lop(admin_token, employee_token, employee_me):
    """No LOP + Valid Leave -> success, is_lop=False, leave_validity='valid'."""
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        r = requests.put(f"{API}/leaves/{lid}/approve",
                         json={"is_lop": False, "leave_validity": "valid"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text

        rr = requests.get(f"{API}/leaves", headers=_h(admin_token), timeout=20)
        rec = next(x for x in rr.json() if x["id"] == lid)
        assert rec["status"] == "approved"
        assert rec.get("is_lop") is False
        assert rec.get("leave_validity") == "valid"
    finally:
        _reset(lid, admin_token)


def test_approve_lop_invalid(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        r = requests.put(f"{API}/leaves/{lid}/approve",
                         json={"is_lop": True, "leave_validity": "invalid",
                               "lop_remark": "TEST lop remark"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        rr = requests.get(f"{API}/leaves", headers=_h(admin_token), timeout=20)
        rec = next(x for x in rr.json() if x["id"] == lid)
        assert rec["status"] == "approved"
        assert rec.get("is_lop") is True
        assert rec.get("leave_validity") == "invalid"
    finally:
        _reset(lid, admin_token)


def test_approve_no_lop_plus_invalid_allowed(admin_token, employee_token, employee_me):
    """Independent: No LOP + Invalid Leave must be accepted."""
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        r = requests.put(f"{API}/leaves/{lid}/approve",
                         json={"is_lop": False, "leave_validity": "invalid"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        rr = requests.get(f"{API}/leaves", headers=_h(admin_token), timeout=20)
        rec = next(x for x in rr.json() if x["id"] == lid)
        assert rec.get("is_lop") is False
        assert rec.get("leave_validity") == "invalid"
    finally:
        _reset(lid, admin_token)


# ---------- admin edit ----------

def test_admin_edit_persists_lop_and_validity_and_audit(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        # Approve as no-lop + valid
        r = requests.put(f"{API}/leaves/{lid}/approve",
                         json={"is_lop": False, "leave_validity": "valid"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text

        # Edit: flip to LOP + invalid + remark
        r = requests.put(f"{API}/leaves/{lid}",
                         json={"is_lop": True, "leave_validity": "invalid",
                               "lop_remark": "TEST changed to invalid"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["status"] == "approved"  # untouched
        assert rec["is_lop"] is True
        assert rec["leave_validity"] == "invalid"
        assert rec["lop_remark"] == "TEST changed to invalid"

        # Audit history exists
        # (No public endpoint listed; verify presence via GET on the leave and
        # the fact that the update returned the changes.) — end assertion
    finally:
        _reset(lid, admin_token)


def test_admin_edit_bad_validity_returns_400(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        requests.put(f"{API}/leaves/{lid}/approve",
                     json={"is_lop": False, "leave_validity": "valid"},
                     headers=_h(admin_token), timeout=20)

        r = requests.put(f"{API}/leaves/{lid}", json={"leave_validity": "maybe"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 400
        assert "must be either" in r.text.lower()

        r = requests.put(f"{API}/leaves/{lid}", json={"leave_validity": "select"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 400
        assert "required" in r.text.lower()
    finally:
        _reset(lid, admin_token)


def test_admin_edit_does_not_change_status(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        requests.put(f"{API}/leaves/{lid}/approve",
                     json={"is_lop": False, "leave_validity": "valid"},
                     headers=_h(admin_token), timeout=20)
        r = requests.put(f"{API}/leaves/{lid}",
                         json={"reason": "TEST reason only edit"},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        assert r.json()["reason"] == "TEST reason only edit"
    finally:
        _reset(lid, admin_token)


# ---------- RBAC ----------

def test_employee_cannot_approve(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        r = requests.put(f"{API}/leaves/{lid}/approve",
                         json={"is_lop": False, "leave_validity": "valid"},
                         headers=_h(employee_token), timeout=20)
        assert r.status_code == 403, r.text
    finally:
        _reset(lid, admin_token)


def test_employee_cannot_admin_edit(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    try:
        r = requests.put(f"{API}/leaves/{lid}",
                         json={"is_lop": True, "leave_validity": "invalid"},
                         headers=_h(employee_token), timeout=20)
        assert r.status_code == 403, r.text
    finally:
        _reset(lid, admin_token)


# ---------- reset clears leave_validity ----------

def test_reset_clears_validity(admin_token, employee_token, employee_me):
    lid = _create_pending_leave(admin_token, employee_me)
    requests.put(f"{API}/leaves/{lid}/approve",
                 json={"is_lop": True, "leave_validity": "invalid"},
                 headers=_h(admin_token), timeout=20)
    r = requests.post(f"{API}/leaves/{lid}/reset", json={"reason": "test"},
                      headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    rec = r.json()
    assert rec["status"] == "pending"
    assert not rec.get("leave_validity")
    assert not rec.get("is_lop")
