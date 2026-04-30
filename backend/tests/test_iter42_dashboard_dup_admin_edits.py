"""Iteration 42 backend tests covering:
1) Dashboard stats — strict mutually-exclusive bucket sums match total_employees
2) Employee duplicate guards — case-insensitive Email + Biometric ID
3) Admin/HR edit endpoints for Leave, Late, Early-Out, Missed-Punch (any status, status preserved, audit fields written)
"""
import os
import uuid
import pytest
import requests
from pathlib import Path


def _load_frontend_env():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be configured in frontend/.env"
API = f"{BASE_URL}/api"

HR_USER = {"username": "admin", "password": "pass123"}
EMP_USER = {"username": "kasper", "password": "pass123"}


# ---------------- fixtures ----------------
def _login(user):
    last_exc = None
    for attempt in range(5):
        try:
            r = requests.post(f"{API}/auth/login", json=user, timeout=90)
            if r.status_code == 200:
                body = r.json()
                return body.get("access_token") or body.get("token")
            print(f"login attempt {attempt+1}: {r.status_code} {r.text[:200]}")
        except Exception as e:
            last_exc = e
            print(f"login attempt {attempt+1} exception: {e}")
    if last_exc:
        raise last_exc
    return None


@pytest.fixture(scope="module")
def hr_token():
    tok = _login(HR_USER)
    assert tok, "HR login failed"
    return tok


@pytest.fixture(scope="module")
def emp_token():
    tok = _login(EMP_USER)
    if not tok:
        pytest.skip("Employee login failed")
    return tok


@pytest.fixture(scope="module")
def hr_headers(hr_token):
    return {"Authorization": f"Bearer {hr_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def emp_headers(emp_token):
    return {"Authorization": f"Bearer {emp_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def emp_user_info(emp_headers, hr_headers):
    r = requests.get(f"{API}/auth/me", headers=emp_headers, timeout=30)
    assert r.status_code == 200
    user = r.json()
    # Find matching employee record by email (employee_id in leaves refers to employees.id)
    email = user.get("email")
    emp_id = None
    if email:
        er = requests.get(
            f"{API}/employees", headers=hr_headers,
            params={"search": email, "limit": 5}, timeout=30,
        )
        if er.status_code == 200:
            data = er.json()
            employees = data if isinstance(data, list) else data.get("employees", [])
            for e in employees:
                if (e.get("official_email") or "").lower() == email.lower():
                    emp_id = e.get("id")
                    break
    user["employee_record_id"] = emp_id or user.get("id")
    return user


# ---------------- Dashboard stats ----------------
class TestDashboardStats:
    def test_dashboard_stats_buckets_sum_total(self, hr_headers):
        r = requests.get(f"{API}/dashboard/stats", headers=hr_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        att = body.get("attendance", {})
        for k in ("total_employees", "logged_in", "logout", "early_out", "not_logged", "late_login"):
            assert k in att, f"missing key {k} in attendance: {att}"
        total = att["total_employees"]
        bucket_sum = att["logged_in"] + att["logout"] + att["early_out"] + att["not_logged"]
        assert bucket_sum == total, (
            f"Mutually-exclusive buckets must equal total_employees. "
            f"logged_in={att['logged_in']} + logout={att['logout']} + "
            f"early_out={att['early_out']} + not_logged={att['not_logged']} "
            f"= {bucket_sum}, expected {total}"
        )
        # Late login is overlay only — must be <= logged_in + logout + early_out
        assert att["late_login"] <= (att["logged_in"] + att["logout"] + att["early_out"]), (
            "late_login is a secondary overlay — cannot exceed records that have an IN punch"
        )

    def test_dashboard_stats_with_date_range(self, hr_headers):
        # 7-day range
        from datetime import datetime, timedelta
        today = datetime.now()
        from_d = (today - timedelta(days=7)).strftime("%d-%m-%Y")
        to_d = today.strftime("%d-%m-%Y")
        r = requests.get(
            f"{API}/dashboard/stats", headers=hr_headers,
            params={"from_date": from_d, "to_date": to_d}, timeout=30
        )
        assert r.status_code == 200, r.text
        att = r.json()["attendance"]
        # In a multi-day window, sum of buckets is per-day-per-employee but the
        # endpoint still reports `not_logged = max(0, total - employees_with_in)`.
        # We only assert response shape + non-negativity here.
        for k in ("logged_in", "logout", "early_out", "not_logged", "late_login"):
            assert att[k] >= 0


# ---------------- Employee duplicate guards ----------------
class TestEmployeeDuplicateGuards:
    @pytest.fixture(scope="class")
    def created(self, hr_headers):
        """Create one employee for the class; clean up after."""
        suffix = uuid.uuid4().hex[:6]
        email = f"TEST_dup_{suffix}@example.com"
        bio = f"TESTBIO{suffix.upper()}"
        payload = {
            "full_name": f"TEST Dup {suffix}",
            "official_email": email,
            "personal_email": f"personal_{suffix}@example.com",
            "phone": "9999999999",
            "department": "Research Unit",
            "team": "QA",
            "designation": "Engineer",
            "shift_type": "General",
            "biometric_id": bio,
            "date_of_joining": "2026-01-01",
            "gender": "Male",
            "marital_status": "Single",
        }
        r = requests.post(f"{API}/employees", headers=hr_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
        emp = r.json()
        yield {"email": email, "bio": bio, "id": emp.get("id")}
        # cleanup
        if emp.get("id"):
            requests.delete(f"{API}/employees/{emp['id']}", headers=hr_headers, timeout=20)

    def test_duplicate_email_same_case_rejected(self, hr_headers, created):
        payload = {
            "full_name": "Other Person",
            "official_email": created["email"],
            "personal_email": "other@example.com",
            "phone": "8888888888",
            "department": "Research Unit",
            "team": "QA",
            "designation": "Engineer",
            "shift_type": "General",
            "date_of_joining": "2026-01-01",
            "gender": "Male",
            "marital_status": "Single",
        }
        r = requests.post(f"{API}/employees", headers=hr_headers, json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "Email already exists" in r.text

    def test_duplicate_email_different_case_rejected(self, hr_headers, created):
        upper_email = created["email"].upper()
        payload = {
            "full_name": "Other Person 2",
            "official_email": upper_email,
            "personal_email": "other2@example.com",
            "phone": "7777777777",
            "department": "Research Unit",
            "team": "QA",
            "designation": "Engineer",
            "shift_type": "General",
            "date_of_joining": "2026-01-01",
            "gender": "Male",
            "marital_status": "Single",
        }
        r = requests.post(f"{API}/employees", headers=hr_headers, json=payload, timeout=30)
        assert r.status_code == 400, f"case-insensitive duplicate email should be rejected: {r.status_code} {r.text}"
        assert "Email already exists" in r.text

    def test_duplicate_biometric_different_case_rejected(self, hr_headers, created):
        suffix = uuid.uuid4().hex[:5]
        payload = {
            "full_name": f"Bio Dup {suffix}",
            "official_email": f"TEST_biodup_{suffix}@example.com",
            "personal_email": f"pbio_{suffix}@example.com",
            "phone": "6666666666",
            "department": "Research Unit",
            "team": "QA",
            "designation": "Engineer",
            "shift_type": "General",
            "biometric_id": created["bio"].lower(),  # different case
            "date_of_joining": "2026-01-01",
            "gender": "Male",
            "marital_status": "Single",
        }
        r = requests.post(f"{API}/employees", headers=hr_headers, json=payload, timeout=30)
        assert r.status_code == 400, f"case-insensitive duplicate biometric should be rejected: {r.status_code} {r.text}"
        assert "Biometric ID already exists" in r.text


# ---------------- Admin edit: Leave ----------------
class TestAdminEditLeave:
    @pytest.fixture(scope="class")
    def approved_leave(self, emp_headers, hr_headers, emp_user_info):
        # Employee creates a leave
        # Use a unique date to avoid collisions w/ existing data
        from datetime import datetime, timedelta
        import random
        d = (datetime.now() + timedelta(days=200 + random.randint(0, 500))).strftime("%Y-%m-%d")
        payload = {
            "employee_id": emp_user_info["employee_record_id"],
            "leave_type": "Sick Leave",
            "leave_split": "Full Day",
            "start_date": d,
            "end_date": d,
            "reason": "TEST iter42 leave",
        }
        r = requests.post(f"{API}/leaves", headers=emp_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), f"create leave failed: {r.status_code} {r.text}"
        leave = r.json()
        leave_id = leave.get("id")
        # HR approves so we can prove edit-on-approved works
        ra = requests.put(f"{API}/leaves/{leave_id}/approve", headers=hr_headers, timeout=30)
        assert ra.status_code == 200, f"approve failed: {ra.status_code} {ra.text}"
        yield leave_id
        # cleanup — best effort
        requests.delete(f"{API}/leaves/{leave_id}", headers=hr_headers, timeout=15)

    def test_hr_can_edit_approved_leave_status_preserved(self, hr_headers, approved_leave):
        new_reason = f"TEST iter42 EDITED {uuid.uuid4().hex[:5]}"
        r = requests.put(
            f"{API}/leaves/{approved_leave}",
            headers=hr_headers,
            json={"reason": new_reason, "leave_type": "Casual Leave"},
            timeout=20,
        )
        assert r.status_code == 200, f"edit failed: {r.status_code} {r.text}"
        body = r.json()
        assert body["reason"] == new_reason
        assert body["leave_type"] == "Casual Leave"
        assert body["status"] == "approved", "status must be preserved"
        assert body.get("edited_by"), "audit field edited_by missing"
        assert body.get("edited_at"), "audit field edited_at missing"

        # Re-fetch to confirm persistence (no duplicate created)
        g = requests.get(f"{API}/leaves", headers=hr_headers,
                         params={"employee_name": ""}, timeout=20)
        assert g.status_code == 200
        records = g.json() if isinstance(g.json(), list) else g.json().get("leaves", [])
        same_id = [r for r in records if r.get("id") == approved_leave]
        assert len(same_id) == 1, f"should be exactly 1 record with id={approved_leave}, found {len(same_id)}"

    def test_employee_cannot_edit_leave_via_admin_endpoint(self, emp_headers, approved_leave):
        r = requests.put(
            f"{API}/leaves/{approved_leave}",
            headers=emp_headers,
            json={"reason": "should be denied"},
            timeout=20,
        )
        assert r.status_code == 403, f"non-HR should be denied: {r.status_code} {r.text}"


# ---------------- Admin edit: Late / Early-out / Missed-punch ----------------
def _create_late_request(emp_headers, date=None):
    from datetime import datetime, timedelta
    import random
    payload = {
        "date": date or (datetime.now() + timedelta(days=200 + random.randint(0, 500))).strftime("%Y-%m-%d"),
        "expected_time": "10:00",
        "actual_time": "10:30",
        "reason": "TEST iter42 late",
    }
    r = requests.post(f"{API}/late-requests", headers=emp_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create late failed: {r.status_code} {r.text}"
    return r.json().get("id"), payload["date"]


def _create_early_out(emp_headers, date=None):
    from datetime import datetime, timedelta
    import random
    payload = {
        "date": date or (datetime.now() + timedelta(days=200 + random.randint(0, 500))).strftime("%Y-%m-%d"),
        "expected_time": "19:00",
        "actual_time": "17:00",
        "reason": "TEST iter42 early out",
    }
    r = requests.post(f"{API}/early-out-requests", headers=emp_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create early-out failed: {r.status_code} {r.text}"
    return r.json().get("id"), payload["date"]


def _create_missed_punch(emp_headers, date=None):
    from datetime import datetime, timedelta
    import random
    payload = {
        "date": date or (datetime.now() + timedelta(days=200 + random.randint(0, 500))).strftime("%Y-%m-%d"),
        "punch_type": "Both",
        "check_in_time": "10:00",
        "check_out_time": "19:00",
        "reason": "TEST iter42 missed punch",
    }
    r = requests.post(f"{API}/missed-punches", headers=emp_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create missed-punch failed: {r.status_code} {r.text}"
    return r.json().get("id"), payload["date"]


class TestAdminEditApprovedRequests:
    """Validates HR can edit approved/rejected late/early-out/missed-punch
    while preserving status and writing edit audit fields."""

    def test_late_request_hr_edit_approved_preserves_status(self, emp_headers, hr_headers):
        rid, d = _create_late_request(emp_headers)
        # approve (no body — RequestApproveBody pydantic schema is bugged
        # with required StarReward fields; sending no body keeps Optional=None)
        ra = requests.put(f"{API}/late-requests/{rid}/approve", headers=hr_headers, timeout=30)
        assert ra.status_code == 200, ra.text
        # HR edits even though approved
        r = requests.put(
            f"{API}/late-requests/{rid}", headers=hr_headers,
            json={"date": d, "expected_time": "10:00",
                  "actual_time": "10:45", "reason": "TEST iter42 EDITED"},
            timeout=30,
        )
        assert r.status_code == 200, f"HR edit on approved late failed: {r.status_code} {r.text}"
        body = r.json()
        assert body["status"] == "approved", "status must be preserved"
        assert body["actual_time"] == "10:45"
        assert body.get("edited_by")
        assert body.get("edited_at")
        # cleanup
        requests.delete(f"{API}/late-requests/{rid}", headers=hr_headers, timeout=15)

    def test_late_request_employee_cannot_edit_non_pending(self, emp_headers, hr_headers):
        rid, d = _create_late_request(emp_headers)
        # approve so it's no longer pending
        requests.put(f"{API}/late-requests/{rid}/approve", headers=hr_headers, timeout=30)
        r = requests.put(
            f"{API}/late-requests/{rid}", headers=emp_headers,
            json={"date": d, "expected_time": "10:00",
                  "actual_time": "10:50", "reason": "should be denied"},
            timeout=30,
        )
        assert r.status_code == 400, f"employee edit on non-pending should be 400: {r.status_code} {r.text}"
        assert "Can only edit pending requests" in r.text
        requests.delete(f"{API}/late-requests/{rid}", headers=hr_headers, timeout=15)

    def test_early_out_hr_edit_approved_preserves_status(self, emp_headers, hr_headers):
        rid, d = _create_early_out(emp_headers)
        ra = requests.put(f"{API}/early-out-requests/{rid}/approve", headers=hr_headers, timeout=30)
        assert ra.status_code == 200, ra.text
        r = requests.put(
            f"{API}/early-out-requests/{rid}", headers=hr_headers,
            json={"date": d, "expected_time": "19:00",
                  "actual_time": "17:30", "reason": "TEST iter42 EDITED EO"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "approved"
        assert body["actual_time"] == "17:30"
        assert body.get("edited_by") and body.get("edited_at")
        requests.delete(f"{API}/early-out-requests/{rid}", headers=hr_headers, timeout=15)

    def test_missed_punch_hr_edit_approved_preserves_status(self, emp_headers, hr_headers):
        rid, d = _create_missed_punch(emp_headers)
        ra = requests.put(f"{API}/missed-punches/{rid}/approve", headers=hr_headers, timeout=30)
        assert ra.status_code == 200, ra.text
        r = requests.put(
            f"{API}/missed-punches/{rid}", headers=hr_headers,
            json={"date": d, "punch_type": "Both",
                  "check_in_time": "10:15", "check_out_time": "19:00",
                  "reason": "TEST iter42 EDITED MP"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "approved"
        assert body["check_in_time"] == "10:15"
        assert body.get("edited_by") and body.get("edited_at")
        requests.delete(f"{API}/missed-punches/{rid}", headers=hr_headers, timeout=15)
