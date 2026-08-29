"""
RBAC / data-isolation regression suite.

Security model under test:
    EMPLOYEE -> OWN HRMS RECORDS ONLY
    ADMIN    -> AUTHORISED COMPANY-WIDE HRMS RECORDS
    BIRTHDAY WIDGET -> SANITISED BIRTHDAY FIELDS ONLY

Covers the reported vulnerability (a valid employee JWT could read company-wide
employee / attendance / leave / department / team / avatar / dashboard data) plus
IDOR attempts via query-parameter and path-id tampering.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
UA = {"User-Agent": "Mozilla/5.0 (rbac-tests)"}

ADMIN = ("admin", "HrAdmin786$")
EMP_B = ("madhan.s", "Vigil@123")
EMP_C = ("dinesh.t", "Vigil@123")

ADMIN_ONLY_PATHS = [
    "/employees/all",
    "/employees",
    "/employees/autocomplete?q=a",
    "/employees/stats",
    "/dashboard/leave-list",
    "/attendance/stats",
    "/payroll",
    "/reports/attendance",
    "/star-rewards",
    "/onboarding/list",
    "/leaves/report",
    "/audit-logs",
]


def _login(creds):
    for _ in range(4):
        r = requests.post(f"{API}/auth/login",
                          json={"username": creds[0], "password": creds[1]},
                          headers=UA, timeout=90)
        if r.status_code == 200:
            d = r.json()
            return d["token"], d.get("user", {})
    raise AssertionError(f"login failed for {creds[0]}: {r.status_code} {r.text[:200]}")


def _get(token, path):
    for _ in range(4):
        r = requests.get(f"{API}{path}", headers={**UA, "Authorization": f"Bearer {token}"}, timeout=120)
        if r.status_code not in (502, 503, 504):
            return r
    return r


@pytest.fixture(scope="module")
def actors():
    at, _ = _login(ADMIN)
    bt, bu = _login(EMP_B)
    ct, cu = _login(EMP_C)
    assert bu.get("role") == "employee"
    assert cu.get("role") == "employee"
    return {
        "admin_token": at,
        "b_token": bt, "b_id": bu["employee_id"],
        "c_token": ct, "c_id": cu["employee_id"],
    }


# ============================ EMPLOYEE DENIALS ============================
@pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
def test_employee_denied_admin_endpoints(actors, path):
    r = _get(actors["b_token"], path)
    assert r.status_code == 403, f"{path} returned {r.status_code}"
    assert actors["c_id"] not in r.text


def test_unauthenticated_is_rejected():
    r = requests.get(f"{API}/employees/all", headers=UA, timeout=60)
    assert r.status_code in (401, 403)


# ============================ SCOPED READS ============================
def test_employee_attendance_is_self_only(actors):
    r = _get(actors["b_token"], "/attendance?from_date=01-08-2026&to_date=28-08-2026")
    assert r.status_code == 200
    ids = {row.get("employee_id") for row in r.json()}
    assert ids <= {actors["b_id"]}, ids


def test_employee_cannot_override_attendance_owner(actors):
    r = _get(actors["b_token"],
             f"/attendance?employee_id={actors['c_id']}&from_date=01-08-2026&to_date=28-08-2026")
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        ids = {row.get("employee_id") for row in r.json()}
        assert ids <= {actors["b_id"]}, ids


def test_employee_cannot_filter_attendance_by_other_name(actors):
    r = _get(actors["b_token"], "/attendance?employee_name=Dinesh&from_date=01-08-2026&to_date=28-08-2026")
    assert r.status_code == 200
    ids = {row.get("employee_id") for row in r.json()}
    assert ids <= {actors["b_id"]}, ids


def test_employee_leaves_are_self_only(actors):
    r = _get(actors["b_token"], "/leaves")
    assert r.status_code == 200
    ids = {row.get("employee_id") for row in r.json()}
    assert ids <= {actors["b_id"]}, ids


def test_employee_cannot_override_leave_owner(actors):
    r = _get(actors["b_token"], f"/leaves?employee_id={actors['c_id']}")
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        ids = {row.get("employee_id") for row in r.json()}
        assert ids <= {actors["b_id"]}, ids


def test_employee_dashboard_stats_is_personal(actors):
    r = _get(actors["b_token"], "/dashboard/stats")
    assert r.status_code == 200
    body = r.json()
    assert body.get("scope") == "self"
    assert "total_research_unit" not in body
    assert "pending_approvals" not in body
    assert body["attendance"]["employee_id"] == actors["b_id"]


def test_employee_avatar_map_is_self_only(actors):
    r = _get(actors["b_token"], "/employee-avatars")
    assert r.status_code == 200
    assert set(r.json().keys()) <= {actors["b_id"]}


def test_employee_departments_are_minimal(actors):
    r = _get(actors["b_token"], "/departments")
    assert r.status_code == 200
    for d in r.json():
        assert set(d.keys()) == {"id", "name"}


def test_employee_teams_are_minimal(actors):
    r = _get(actors["b_token"], "/teams")
    assert r.status_code == 200
    for t in r.json():
        assert set(t.keys()) == {"id", "name"}


def test_employee_team_detail_is_forbidden(actors):
    r = _get(actors["b_token"], "/teams/any-id")
    assert r.status_code == 403


# ============================ IDOR / BOLA ============================
@pytest.mark.parametrize("tmpl", [
    "/employees/{id}",
    "/payroll/{id}",
    "/employees/{id}/salary",
    "/employees/{id}/documents",
    "/employees/{id}/education-experience",
    "/star-rewards/history/{id}",
])
def test_employee_cannot_read_other_employee_objects(actors, tmpl):
    r = _get(actors["b_token"], tmpl.format(id=actors["c_id"]))
    assert r.status_code == 403, f"{tmpl} -> {r.status_code}"


# ============================ BIRTHDAY EXCEPTION ============================
FORBIDDEN_BIRTHDAY_FIELDS = {
    "biometric_id", "personal_email", "official_email", "phone", "mobile",
    "address", "salary", "monthly_salary", "pan", "pan_number", "bank_account",
    "date_of_birth", "emp_id", "custom_employee_id", "emergency_contact",
}


def test_birthday_widget_works_and_is_sanitised(actors):
    r = _get(actors["b_token"], "/dashboard/birthdays")
    assert r.status_code == 200
    data = r.json()
    assert "today" in data and "upcoming" in data
    items = data["today"] + data["upcoming"]
    assert items, "birthday widget returned no colleagues — feature must keep working"
    for item in items:
        assert item.get("full_name")
        assert item.get("birthday_month")
        assert FORBIDDEN_BIRTHDAY_FIELDS.isdisjoint(item.keys()), item


# ============================ ADMIN REGRESSION ============================
def test_admin_still_sees_company_wide_data(actors):
    t = actors["admin_token"]
    r = _get(t, "/employees/all")
    assert r.status_code == 200 and len(r.json()) > 1
    r = _get(t, "/leaves")
    assert r.status_code == 200
    r = _get(t, "/attendance?from_date=01-08-2026&to_date=28-08-2026")
    assert r.status_code == 200
    ids = {row.get("employee_id") for row in r.json()}
    assert len(ids) > 1, "admin attendance must stay company-wide"
    r = _get(t, "/dashboard/leave-list")
    assert r.status_code == 200
    r = _get(t, "/dashboard/stats")
    assert r.status_code == 200 and "total_research_unit" in r.json()
    r = _get(t, "/departments")
    assert r.status_code == 200 and "employee_count" in r.json()[0]
    r = _get(t, "/teams")
    assert r.status_code == 200 and "member_count" in r.json()[0]
    r = _get(t, "/employee-avatars")
    assert r.status_code == 200 and len(r.json()) > 1


# ============================ EMPLOYEE SELF-SERVICE ============================
@pytest.mark.parametrize("path", [
    "/employee/profile",
    "/employee/dashboard",
    "/employee/attendance",
    "/employee/leaves",
    "/holidays",
    "/policies",
    "/notifications",
    "/late-requests",
    "/missed-punches",
    "/early-out-requests",
    "/issue-tickets",
    "/payslips/my",
])
def test_employee_self_service_still_works(actors, path):
    r = _get(actors["b_token"], path)
    # A module the admin has hidden from this employee via Module Visibility
    # legitimately answers 403 module_unavailable — that is not an RBAC failure.
    if r.status_code == 403 and r.json().get("error") == "module_unavailable":
        pytest.skip(f"{path}: module hidden for this employee by Module Visibility")
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:150]}"
