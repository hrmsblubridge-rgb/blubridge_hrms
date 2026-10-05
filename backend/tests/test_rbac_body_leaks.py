"""Extended RBAC / body-leak audit.

Independent verification requested by main agent — inspect JSON RESPONSE BODIES
(not just status codes) for every reported endpoint, cover self-service edit
IDOR (PUT late-requests/early-out-requests/missed-punches of another employee),
sample more deny-by-default admin endpoints, and confirm security_denials mongo
logging does NOT leak JWTs / passwords.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
UA = {"User-Agent": "Mozilla/5.0 (rbac-body-audit)"}

ADMIN = ("admin", "HrAdmin786$")
EMP_B = ("madhan.s", "Vigil@123")
EMP_C = ("dinesh.t", "Vigil@123")


def _login(creds):
    last = None
    for _ in range(5):
        r = requests.post(f"{API}/auth/login",
                          json={"username": creds[0], "password": creds[1]},
                          headers=UA, timeout=90)
        last = r
        if r.status_code == 200:
            d = r.json()
            return d["token"], d.get("user", {})
        time.sleep(1)
    raise AssertionError(f"login failed for {creds[0]}: {last.status_code} {last.text[:200]}")


def _req(method, token, path, **kw):
    h = {**UA, "Authorization": f"Bearer {token}"}
    for _ in range(4):
        r = requests.request(method, f"{API}{path}", headers=h, timeout=120, **kw)
        if r.status_code not in (502, 503, 504):
            return r
        time.sleep(2)
    return r


@pytest.fixture(scope="module")
def actors():
    at, _ = _login(ADMIN)
    bt, bu = _login(EMP_B)
    ct, cu = _login(EMP_C)
    return {
        "admin_token": at,
        "b_token": bt, "b_id": bu["employee_id"], "b_user": bu,
        "c_token": ct, "c_id": cu["employee_id"], "c_user": cu,
    }


# ---------------- BODY INSPECTION on every reported endpoint ----------------
def test_body_dashboard_stats_no_admin_fields(actors):
    r = _req("GET", actors["b_token"], "/dashboard/stats")
    assert r.status_code == 200
    body = r.json()
    forbidden = {"total_research_unit", "pending_approvals", "total_employees",
                 "company_attendance", "total_present", "total_absent"}
    leaked = forbidden.intersection(body.keys())
    assert not leaked, f"dashboard/stats leaks admin fields: {leaked}"
    # nested attendance object must belong to caller only
    att = body.get("attendance") or {}
    assert att.get("employee_id") in (actors["b_id"], None)


def test_body_leaves_only_own_rows(actors):
    r = _req("GET", actors["b_token"], "/leaves")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    other_rows = [x for x in rows if x.get("employee_id") not in (actors["b_id"], None)]
    assert not other_rows, f"/leaves leaked {len(other_rows)} other rows"
    # response text must not mention Employee C's id anywhere either
    assert actors["c_id"] not in r.text


def test_body_attendance_only_own_rows(actors):
    r = _req("GET", actors["b_token"],
             "/attendance?from_date=24-08-2026&to_date=28-08-2026")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    bad = [x for x in rows if x.get("employee_id") not in (actors["b_id"], None)]
    assert not bad, f"attendance leaked {len(bad)} other-employee rows: {bad[:2]}"
    assert actors["c_id"] not in r.text


def test_body_departments_minimal(actors):
    r = _req("GET", actors["b_token"], "/departments")
    assert r.status_code == 200
    for d in r.json():
        assert set(d.keys()) == {"id", "name"}, d


def test_body_teams_minimal(actors):
    r = _req("GET", actors["b_token"], "/teams")
    assert r.status_code == 200
    for t in r.json():
        assert set(t.keys()) == {"id", "name"}, t


def test_body_employee_avatars_self_only(actors):
    r = _req("GET", actors["b_token"], "/employee-avatars")
    assert r.status_code == 200
    keys = set(r.json().keys())
    assert keys <= {actors["b_id"]}, f"avatar map leaked: {keys - {actors['b_id']}}"


def test_body_employees_all_denied(actors):
    r = _req("GET", actors["b_token"], "/employees/all")
    assert r.status_code == 403
    assert actors["c_id"] not in r.text


def test_body_dashboard_leave_list_denied(actors):
    r = _req("GET", actors["b_token"], "/dashboard/leave-list")
    assert r.status_code == 403
    assert actors["c_id"] not in r.text


# ---------------- extra deny-by-default sample ----------------
@pytest.mark.parametrize("path", [
    "/reports/leaves",
    "/settings/module-visibility",
    "/warnings",
    "/payslips",
    "/verification/list",
    "/verification",
])
def test_extra_admin_endpoints_denied(actors, path):
    r = _req("GET", actors["b_token"], path)
    # any of 403/404 is acceptable (404 = route doesn't exist which is not a leak)
    assert r.status_code in (403, 404), f"{path} unexpectedly {r.status_code}"
    if r.status_code == 200:
        assert actors["c_id"] not in r.text


# ---------------- IDOR: PUT on other employee's self-service edit ----------------
def _create_late_request(token):
    payload = {"date": "2026-08-28", "expected_time": "09:30",
               "actual_time": "10:30",
               "reason": f"TEST_rbac_{uuid.uuid4().hex[:6]}"}
    return _req("POST", token, "/late-requests", json=payload)


def _create_early_out(token):
    payload = {"date": "2026-08-28", "actual_time": "16:30",
               "reason": f"TEST_rbac_{uuid.uuid4().hex[:6]}"}
    return _req("POST", token, "/early-out-requests", json=payload)


def _create_missed_punch(token):
    payload = {"date": "2026-08-28", "punch_type": "Check-in",
               "check_in_time": "09:00",
               "reason": f"TEST_rbac_{uuid.uuid4().hex[:6]}"}
    return _req("POST", token, "/missed-punches", json=payload)


def _fetch_or_create(token, list_path, create_fn):
    """Return an existing pending request id, else create a new one."""
    r = _req("GET", token, list_path)
    if r.status_code == 200:
        body = r.json()
        rows = body if isinstance(body, list) else (body.get("data") or body.get("requests") or [])
        if rows:
            rid = rows[0].get("id") or rows[0].get("_id")
            if rid:
                return rid, r
    c = create_fn(token)
    if c.status_code in (200, 201):
        d = c.json()
        return d.get("id") or d.get("_id"), c
    return None, c


def test_idor_late_request_edit(actors):
    rid, r = _fetch_or_create(actors["c_token"], "/late-requests", _create_late_request)
    if not rid:
        pytest.skip(f"cannot obtain late-request as C ({r.status_code}) {r.text[:120]}")
    edit = _req("PUT", actors["b_token"], f"/late-requests/{rid}",
                json={"date": "2026-08-28", "expected_time": "09:30",
                      "actual_time": "10:45", "reason": "hijack attempt"})
    assert edit.status_code == 403, f"IDOR: B could PUT C's late-request ({edit.status_code}) {edit.text[:200]}"


def test_idor_early_out_edit(actors):
    rid, r = _fetch_or_create(actors["c_token"], "/early-out-requests", _create_early_out)
    if not rid:
        pytest.skip(f"cannot obtain early-out as C ({r.status_code}) {r.text[:120]}")
    edit = _req("PUT", actors["b_token"], f"/early-out-requests/{rid}",
                json={"date": "2026-08-28", "actual_time": "16:45",
                      "reason": "hijack attempt"})
    assert edit.status_code == 403, f"IDOR: B could PUT C's early-out ({edit.status_code}) {edit.text[:200]}"


def test_idor_missed_punch_edit(actors):
    rid, r = _fetch_or_create(actors["c_token"], "/missed-punches", _create_missed_punch)
    if not rid:
        pytest.skip(f"cannot obtain missed-punch as C ({r.status_code}) {r.text[:120]}")
    edit = _req("PUT", actors["b_token"], f"/missed-punches/{rid}",
                json={"date": "2026-08-28", "punch_type": "Check-in",
                      "check_in_time": "09:15", "reason": "hijack attempt"})
    assert edit.status_code == 403, f"IDOR: B could PUT C's missed-punch ({edit.status_code}) {edit.text[:200]}"


# ---------------- Birthday widget sanitisation (deep check) ----------------
def test_birthday_widget_sanitised_deep(actors):
    r = _req("GET", actors["b_token"], "/dashboard/birthdays")
    assert r.status_code == 200
    data = r.json()
    items = (data.get("today") or []) + (data.get("upcoming") or [])
    # any DOB year leakage? day/month allowed, YYYY-MM-DD not.
    for it in items:
        for k, v in it.items():
            if isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-":
                # looks like an ISO date with year — forbidden for employee view
                pytest.fail(f"birthday leaked full DOB: {k}={v}")


# ---------------- Security logging: no JWT / password in denial log ----------------
def test_security_denials_do_not_contain_secrets(actors):
    # trigger a denial
    _req("GET", actors["b_token"], "/employees/all")
    # read backend log tail
    try:
        with open("/var/log/supervisor/backend.err.log") as f:
            tail = f.read()[-20000:]
    except Exception:
        pytest.skip("cannot read supervisor backend log")
    assert "RBAC DENY 403" in tail, "expected 'RBAC DENY 403' log line"
    # log line must not contain the raw JWT or passwords
    assert "HrAdmin786$" not in tail
    assert "Vigil@123" not in tail
    assert actors["b_token"] not in tail
