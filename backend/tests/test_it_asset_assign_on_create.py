"""Backend tests for the NEW IT Asset assign-on-create feature.

Covers:
  1. Create asset WITH an active employee -> status Assigned, assigned_to set,
     assignment history has open period for that employee.
  2. Create asset WITHOUT employee still yields status In Stock and assigned_to null.
  3. Create asset with assign_employee_id = INACTIVE employee -> 400 with
     the message 'Selected employee is no longer active.' (only if an
     inactive employee exists in the environment).
  4. Post-creation Assign flow (POST /it/assets/{id}/assign) still works.
  5. RBAC: employee token gets 403 on POST /it/assets and admin endpoints.
"""
import os
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"username": "admin", "password": "HrAdmin@2109"}
EMPLOYEE = {"username": "user", "password": "pass123"}


def _login(c):
    r = requests.post(f"{API}/auth/login", json=c, timeout=60)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def emp_token():
    return _login(EMPLOYEE)


def _get_active_employee(tok):
    r = requests.get(f"{API}/employees?status=Active&limit=5", headers=_h(tok), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("employees") or body.get("items") or []
    assert items, f"no active employees: {body}"
    return items[0]


def _get_inactive_employee(tok):
    for s in ("Inactive", "Resigned"):
        r = requests.get(f"{API}/employees?status={s}&limit=3", headers=_h(tok), timeout=30)
        if r.status_code == 200:
            items = r.json().get("employees") or r.json().get("items") or []
            if items:
                return items[0]
    return None


def _base_payload(tag=""):
    return {
        "category": "Desktop",
        "name": f"TEST_AoC_{tag or uuid.uuid4().hex[:6]}",
        "brand": "Dell",
        "model": "Optiplex",
        "serial_number": f"TESTAOC-{uuid.uuid4().hex[:10]}",
    }


# ------------------------------------------------------------ 1. WITH active emp
def test_create_asset_with_active_employee(admin_token):
    emp = _get_active_employee(admin_token)
    payload = _base_payload("active")
    payload["assign_employee_id"] = emp["id"]
    r = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    a = r.json()
    assert a["status"] == "Assigned", a
    assert (a.get("assigned_to") or {}).get("employee_id") == emp["id"]
    aid = a["asset_id"]

    # assignment history has that employee open
    r2 = requests.get(f"{API}/it/assets/{aid}/components", headers=_h(admin_token), timeout=20)
    assert r2.status_code == 200, r2.text
    ah = r2.json().get("assignment_history") or []
    assert any(h.get("employee_id") == emp["id"] and h.get("to") is None for h in ah), ah


# ------------------------------------------------------------ 2. WITHOUT emp
def test_create_asset_without_employee(admin_token):
    payload = _base_payload("noemp")
    r = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    a = r.json()
    assert a["status"] == "In Stock", a
    assert a.get("assigned_to") in (None, {}), a


# ------------------------------------------------------------ 3. INACTIVE emp rejected
def test_create_asset_inactive_employee_rejected(admin_token):
    inactive = _get_inactive_employee(admin_token)
    if not inactive:
        pytest.skip("No inactive/resigned employee available in this environment")
    payload = _base_payload("inact")
    payload["assign_employee_id"] = inactive["id"]
    r = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text}"
    assert "no longer active" in r.text.lower(), r.text


# ------------------------------------------------------------ 3b. Bogus emp id rejected
def test_create_asset_bogus_employee_rejected(admin_token):
    payload = _base_payload("bogus")
    payload["assign_employee_id"] = "does-not-exist-" + uuid.uuid4().hex[:6]
    r = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code == 400, f"{r.status_code} {r.text}"


# ------------------------------------------------------------ 4. Post-create assign still works
def test_post_create_assign_flow(admin_token):
    emp = _get_active_employee(admin_token)
    payload = _base_payload("later")
    r = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    aid = r.json()["asset_id"]

    snap = {"employee_id": emp["id"], "employee_name": emp.get("full_name") or emp.get("name"),
            "emp_code": emp.get("emp_id") or emp.get("emp_code"),
            "department": emp.get("department"), "designation": emp.get("designation")}
    r2 = requests.post(f"{API}/it/assets/{aid}/assign", headers=_h(admin_token), json=snap, timeout=20)
    assert r2.status_code == 200, r2.text

    r3 = requests.get(f"{API}/it/assets/{aid}", headers=_h(admin_token), timeout=20).json()
    assert r3["asset"]["status"] == "Assigned"
    assert r3["asset"]["assigned_to"]["employee_id"] == emp["id"]


# ------------------------------------------------------------ 5. Employee endpoints for the picker
def test_employees_active_filter(admin_token):
    r = requests.get(f"{API}/employees?status=Active&limit=5", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    items = r.json().get("employees") or []
    assert items, "no active employees returned"
    for e in items:
        st = (e.get("employee_status") or "Active")
        assert st == "Active", f"non-active leaked: {e.get('id')} {st}"


# ------------------------------------------------------------ 6. RBAC
def test_employee_forbidden_on_create(emp_token):
    payload = _base_payload("rbac")
    r = requests.post(f"{API}/it/assets", headers=_h(emp_token), json=payload, timeout=20)
    assert r.status_code == 403, f"{r.status_code} {r.text}"


def test_employee_forbidden_on_list(emp_token):
    r = requests.get(f"{API}/it/assets", headers=_h(emp_token), timeout=20)
    assert r.status_code == 403


def test_employee_own_it_assets_ok(emp_token):
    r = requests.get(f"{API}/employee/it-assets", headers=_h(emp_token), timeout=20)
    assert r.status_code == 200, r.text


def test_employee_own_it_components_ok(emp_token):
    r = requests.get(f"{API}/employee/it-components", headers=_h(emp_token), timeout=20)
    assert r.status_code == 200, r.text
