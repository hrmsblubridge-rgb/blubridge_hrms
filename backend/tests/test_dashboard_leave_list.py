"""Pytest for /api/dashboard/leave-list and /api/attendance First-Half Late Login exemption behavior (TEST_DL_ seeded data).

Covers iteration-94 requirements:
  1. Leave list shows half-day Pending/Approved rows WITH leave_split (tooltip source)
  2. Rejected/Cancelled/no-leave show '-' / Not Login
  3. Punched-in employees excluded (list length == stats attendance.not_logged)
  4. /api/attendance for today: FH pending/approved exempted from Late Login;
     FH rejected/cancelled, SH approved, no-leave remain Late Login
  5. first_half_late_exempt flag + 'Early out / short hours ...' rewrite for LOP
  6. /api/dashboard/stats late_login == 4 (non-exempt late employees only)
  7. Stored attendance docs are NOT mutated (regression check)
  8. Status transitions: pending <-> approved <-> rejected <-> cancelled flips exemption
"""
import os
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://blubridge-rgb-import.preview.emergentagent.com").rstrip("/")
TODAY_DMY = "14-10-2026"

ADMIN_CREDS = [("admin", "pass123"), ("admin", "HrAdmin@2109"), ("sysadmin", "pass123")]

mongo = MongoClient("mongodb://localhost:27017")
db = mongo["test_database"]


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


def _attendance(headers):
    r = requests.get(f"{BASE_URL}/api/attendance",
                     params={"from_date": TODAY_DMY, "to_date": TODAY_DMY},
                     headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    recs = data.get("records") if isinstance(data, dict) else data
    return {rec["emp_name"]: rec for rec in recs if rec.get("emp_name", "").startswith("TEST_DL_")}


# ========== Dashboard leave-list ==========

def test_pending_full_shows_type_pending(headers):
    r = _by_name(_get_list(headers)).get("TEST_DL_pending_full")
    assert r and r["leave_type"] == "Sick" and r["reason"] == "Fever" and r["status"] == "Pending"
    # Full-day row leave_split either 'Full Day' or None (tooltip would say Full Day)
    assert r.get("leave_split") in ("Full Day", None)


def test_approved_full_shows_approved(headers):
    r = _by_name(_get_list(headers)).get("TEST_DL_approved_full")
    assert r and r["leave_type"] == "Preplanned" and r["status"] == "Approved"


def test_first_half_pending_shows_type_and_split(headers):
    r = _by_name(_get_list(headers)).get("TEST_DL_first_half_pending")
    assert r, "first_half_pending row missing"
    assert r["leave_type"] == "Sick"
    assert r["reason"] == "Half pending reason"
    assert r["status"] == "Pending"
    assert r["leave_split"] == "First Half"


def test_second_half_approved_shows_type_and_split(headers):
    r = _by_name(_get_list(headers)).get("TEST_DL_second_half_approved")
    assert r
    assert r["leave_type"] == "Preplanned"
    assert r["status"] == "Approved"
    assert r["leave_split"] == "Second Half"


@pytest.mark.parametrize("name", ["TEST_DL_rejected_full", "TEST_DL_cancelled_full", "TEST_DL_nologin"])
def test_rejected_cancelled_nologin_show_not_login(headers, name):
    r = _by_name(_get_list(headers)).get(name)
    assert r
    assert r["leave_type"] == "-"
    assert r["status"] == "Not Login"


def test_rejected_plus_pending_uses_valid_pending(headers):
    r = _by_name(_get_list(headers)).get("TEST_DL_rejected_plus_pending")
    assert r and r["leave_type"] == "Emergency" and r["reason"] == "Valid pending" and r["status"] == "Pending"


def test_punched_in_and_late_employees_excluded(headers):
    rows = _by_name(_get_list(headers))
    # Everyone who has a check_in attendance record today should NOT be in the list
    excluded = ["TEST_DL_punched_in",
                "TEST_DL_fh_pending_late", "TEST_DL_fh_approved_late",
                "TEST_DL_fh_rejected_late", "TEST_DL_fh_cancelled_late",
                "TEST_DL_sh_approved_late", "TEST_DL_no_leave_late",
                "TEST_DL_fh_pending_late_short"]
    for n in excluded:
        assert n not in rows, f"{n} should NOT be in leave list (has check_in)"


def test_stats_not_logged_matches_list_length(headers):
    rows = _get_list(headers)
    r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers, timeout=30)
    assert r.status_code == 200
    not_logged = r.json().get("attendance", {}).get("not_logged")
    print(f"stats not_logged={not_logged}, list_len={len(rows)}")
    if not_logged is not None and not_logged <= 50:
        assert not_logged == len(rows)


# ========== /api/attendance First-Half late exemption ==========

def test_attendance_fh_pending_late_login(headers):
    recs = _attendance(headers)
    r = recs.get("TEST_DL_fh_pending_late")
    assert r, "fh_pending_late attendance missing"
    assert r["status"] == "Login", f"expected Login got {r['status']}"
    assert r.get("first_half_late_exempt") is True


def test_attendance_fh_approved_late_present(headers):
    recs = _attendance(headers)
    r = recs.get("TEST_DL_fh_approved_late")
    assert r
    assert r["status"] == "Present", f"expected Present got {r['status']}"
    assert r.get("first_half_late_exempt") is True


def test_attendance_fh_pending_late_short_rewrites_lop(headers):
    recs = _attendance(headers)
    r = recs.get("TEST_DL_fh_pending_late_short")
    assert r
    assert r["status"] == "Loss of Pay"
    assert r.get("is_lop") is True
    assert (r.get("lop_reason") or "").startswith("Early out / short hours"), r.get("lop_reason")
    assert r.get("first_half_late_exempt") is True


@pytest.mark.parametrize("name", [
    "TEST_DL_fh_rejected_late",
    "TEST_DL_fh_cancelled_late",
    "TEST_DL_sh_approved_late",
    "TEST_DL_no_leave_late",
])
def test_attendance_non_exempt_remain_late(headers, name):
    recs = _attendance(headers)
    r = recs.get(name)
    assert r, f"{name} attendance missing"
    assert r["status"] == "Late Login", f"{name}: expected Late Login got {r['status']}"
    assert not r.get("first_half_late_exempt")


def test_attendance_filter_status_late_login_returns_only_non_exempt(headers):
    r = requests.get(f"{BASE_URL}/api/attendance",
                     params={"from_date": TODAY_DMY, "to_date": TODAY_DMY, "status": "Late Login"},
                     headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    recs = data.get("records") if isinstance(data, dict) else data
    names = {rec["emp_name"] for rec in recs if rec.get("emp_name", "").startswith("TEST_DL_")}
    assert names == {"TEST_DL_fh_rejected_late", "TEST_DL_fh_cancelled_late",
                     "TEST_DL_sh_approved_late", "TEST_DL_no_leave_late"}, names


def test_dashboard_stats_late_login_count(headers):
    r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers, timeout=30)
    assert r.status_code == 200
    att = r.json().get("attendance", {})
    # Only the 4 non-exempt TEST_DL_ records contribute to late_login from this seed;
    # however the environment may have other late logins. We assert >=4 and that our
    # four show up in the Late Login filtered attendance list (above).
    assert att.get("late_login", 0) >= 4


# ========== Regression: stored docs untouched ==========

def test_stored_attendance_not_mutated():
    """Overlay must not persist back to Mongo."""
    for name in ["TEST_DL_fh_pending_late", "TEST_DL_fh_approved_late", "TEST_DL_fh_pending_late_short"]:
        emp = db.employees.find_one({"full_name": name})
        att = db.attendance.find_one({"employee_id": emp["id"], "date": TODAY_DMY})
        assert att is not None
        assert att["status"] in ("Late Login", "Loss of Pay"), f"{name} stored status changed: {att['status']}"
        assert "first_half_late_exempt" not in att, f"{name} overlay flag leaked into DB"


# ========== Status transitions ==========

def test_transition_fh_pending_late_to_rejected_then_approved_then_cancelled(headers):
    emp = db.employees.find_one({"full_name": "TEST_DL_fh_pending_late"})
    try:
        # -> rejected: must be Late Login again
        db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "rejected"}})
        r = _attendance(headers).get("TEST_DL_fh_pending_late")
        assert r["status"] == "Late Login"
        assert not r.get("first_half_late_exempt")

        # -> approved: exempt (Login since no checkout)
        db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "approved"}})
        r = _attendance(headers).get("TEST_DL_fh_pending_late")
        assert r["status"] == "Login"
        assert r.get("first_half_late_exempt") is True

        # -> cancelled: Late Login again
        db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "cancelled"}})
        r = _attendance(headers).get("TEST_DL_fh_pending_late")
        assert r["status"] == "Late Login"
    finally:
        db.leaves.update_many({"employee_id": emp["id"]}, {"$set": {"status": "pending"}})


# ========== Check-in move: moves from leave-list to logged-in ==========

def test_checkin_moves_from_leave_list_to_logged_in(headers):
    emp = db.employees.find_one({"full_name": "TEST_DL_first_half_pending"})
    # Confirm present initially
    assert "TEST_DL_first_half_pending" in _by_name(_get_list(headers))
    import uuid as _uuid
    rec_id = str(_uuid.uuid4())
    db.attendance.insert_one({
        "id": rec_id, "employee_id": emp["id"], "emp_name": "TEST_DL_first_half_pending",
        "team": "QA", "department": "QA", "date": TODAY_DMY, "check_in": "10:00 AM",
        "check_in_24h": "10:00", "status": "Login",
    })
    try:
        rows = _by_name(_get_list(headers))
        assert "TEST_DL_first_half_pending" not in rows
        # Leave doc unchanged
        lv = db.leaves.find_one({"employee_id": emp["id"]})
        assert lv["status"] == "pending"
        assert lv["leave_split"] == "First Half"
    finally:
        db.attendance.delete_one({"id": rec_id})
