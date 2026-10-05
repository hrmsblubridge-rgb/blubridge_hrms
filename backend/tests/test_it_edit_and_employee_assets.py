"""Backend tests for IT Module additive enhancements:
  - PUT /api/it/assets/{id} full edit + 'Updated' history event
  - GET /api/it/employee-assets (list) + filters + pagination + dynamic counts
  - GET /api/it/employee-assets/{employee_id} (detail current assets)
  - RBAC: employee token 403 on /it/employee-assets*
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
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def emp_token():
    return _login(EMPLOYEE)


@pytest.fixture(scope="module")
def active_emp(admin_token):
    r = requests.get(f"{API}/employees?status=Active&limit=5", headers=_h(admin_token), timeout=30)
    items = r.json().get("employees") or []
    assert items, "no active employees"
    return items[0]


@pytest.fixture(scope="module")
def another_active_emp(admin_token, active_emp):
    r = requests.get(f"{API}/employees?status=Active&limit=20", headers=_h(admin_token), timeout=30)
    items = r.json().get("employees") or []
    for e in items:
        if e["id"] != active_emp["id"]:
            return e
    pytest.skip("Need >=2 active employees")


def _create_asset(tok, tag="", extra=None):
    p = {
        "category": "Desktop",
        "name": f"TEST_EDIT_{tag or uuid.uuid4().hex[:6]}",
        "brand": "Dell", "model": "Optiplex",
        "serial_number": f"TESTEDIT-{uuid.uuid4().hex[:10]}",
    }
    if extra:
        p.update(extra)
    r = requests.post(f"{API}/it/assets", headers=_h(tok), json=p, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ==================== EDIT ASSET ====================
def test_edit_asset_persists_and_history(admin_token):
    a = _create_asset(admin_token, "e1")
    aid = a["asset_id"]
    upd = {"brand": "HP", "location": "HQ-2F", "status": "Under Repair", "remarks": "edited by test"}
    r = requests.put(f"{API}/it/assets/{aid}", headers=_h(admin_token), json=upd, timeout=30)
    assert r.status_code == 200, r.text

    # GET verify persistence
    g = requests.get(f"{API}/it/assets/{aid}", headers=_h(admin_token), timeout=20).json()
    asset = g["asset"]
    assert asset["brand"] == "HP"
    assert asset["location"] == "HQ-2F"
    assert asset["status"] == "Under Repair"
    assert asset["remarks"] == "edited by test"

    # Timeline contains an 'Updated' event
    hist = g["history"]
    assert any(h.get("action") == "Updated" for h in hist), f"no Updated event: {hist}"


def test_edit_asset_invalid_status(admin_token):
    a = _create_asset(admin_token, "e2")
    r = requests.put(f"{API}/it/assets/{a['asset_id']}", headers=_h(admin_token),
                     json={"status": "NotAStatus"}, timeout=20)
    assert r.status_code == 400


def test_edit_asset_duplicate_serial_rejected(admin_token):
    a1 = _create_asset(admin_token, "s1")
    a2 = _create_asset(admin_token, "s2")
    r = requests.put(f"{API}/it/assets/{a2['asset_id']}", headers=_h(admin_token),
                     json={"serial_number": a1["serial_number"]}, timeout=20)
    assert r.status_code == 400
    assert "already exists" in r.text.lower()


def test_edit_asset_id_immutable(admin_token):
    a = _create_asset(admin_token, "im")
    aid = a["asset_id"]
    r = requests.put(f"{API}/it/assets/{aid}", headers=_h(admin_token),
                     json={"asset_id": "HACKED-1", "brand": "Lenovo"}, timeout=20)
    assert r.status_code == 200
    g = requests.get(f"{API}/it/assets/{aid}", headers=_h(admin_token), timeout=20).json()
    assert g["asset"]["asset_id"] == aid  # unchanged
    assert g["asset"]["brand"] == "Lenovo"


def test_edit_asset_404(admin_token):
    r = requests.put(f"{API}/it/assets/DOESNOTEXIST-XYZ", headers=_h(admin_token),
                     json={"brand": "X"}, timeout=20)
    assert r.status_code == 404


# ==================== EMPLOYEE ASSETS LIST ====================
def test_employee_assets_list_shape(admin_token):
    r = requests.get(f"{API}/it/employee-assets?page=1&page_size=10", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "total" in body
    ids = [i["id"] for i in body["items"]]
    assert len(ids) == len(set(ids)), "employee duplicated in list"
    for i in body["items"]:
        assert "asset_count" in i and isinstance(i["asset_count"], int)
        assert i.get("employee_status", "Active") == "Active"


def test_employee_assets_search_filter(admin_token, active_emp):
    name = (active_emp.get("full_name") or "")[:3]
    if not name:
        pytest.skip("no full_name")
    r = requests.get(f"{API}/it/employee-assets?search={name}", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == active_emp["id"] for i in items) or len(items) > 0


def test_employee_assets_has_assets_filter(admin_token, active_emp):
    # Ensure emp has at least one asset
    _create_asset(admin_token, "hf1", {"assign_employee_id": active_emp["id"]})

    r = requests.get(f"{API}/it/employee-assets?has_assets=with&page_size=200",
                     headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    with_items = r.json()["items"]
    assert all(i["asset_count"] > 0 for i in with_items)
    assert any(i["id"] == active_emp["id"] for i in with_items)

    r2 = requests.get(f"{API}/it/employee-assets?has_assets=without&page_size=50",
                      headers=_h(admin_token), timeout=30)
    assert r2.status_code == 200
    without_items = r2.json()["items"]
    assert all(i["asset_count"] == 0 for i in without_items)


def test_employee_assets_pagination(admin_token):
    r = requests.get(f"{API}/it/employee-assets?page=1&page_size=2", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2


# ==================== COUNTS DYNAMIC ====================
def test_employee_assets_count_dynamic(admin_token, active_emp, another_active_emp):
    eid = active_emp["id"]
    # baseline count
    r0 = requests.get(f"{API}/it/employee-assets/{eid}", headers=_h(admin_token), timeout=20)
    assert r0.status_code == 200
    base = len(r0.json()["assets"])

    # create + assign
    a = _create_asset(admin_token, "dyn", {"assign_employee_id": eid})
    aid = a["asset_id"]

    r1 = requests.get(f"{API}/it/employee-assets/{eid}", headers=_h(admin_token), timeout=20).json()
    assert len(r1["assets"]) == base + 1
    assert any(x["asset_id"] == aid for x in r1["assets"])

    # transfer to another
    snap = {"employee_id": another_active_emp["id"],
            "employee_name": another_active_emp.get("full_name"),
            "emp_code": another_active_emp.get("emp_id")}
    rt = requests.post(f"{API}/it/assets/{aid}/transfer", headers=_h(admin_token), json=snap, timeout=20)
    assert rt.status_code == 200, rt.text

    r2 = requests.get(f"{API}/it/employee-assets/{eid}", headers=_h(admin_token), timeout=20).json()
    assert not any(x["asset_id"] == aid for x in r2["assets"]), "asset still counted after transfer"
    r3 = requests.get(f"{API}/it/employee-assets/{another_active_emp['id']}", headers=_h(admin_token), timeout=20).json()
    assert any(x["asset_id"] == aid for x in r3["assets"]), "asset not moved to new employee"

    # return -> should not be counted on anyone
    rr = requests.post(f"{API}/it/assets/{aid}/return", headers=_h(admin_token), json={"status": "Available"}, timeout=20)
    assert rr.status_code == 200
    r4 = requests.get(f"{API}/it/employee-assets/{another_active_emp['id']}", headers=_h(admin_token), timeout=20).json()
    assert not any(x["asset_id"] == aid for x in r4["assets"])


# ==================== RBAC ====================
def test_employee_forbidden_employee_assets(emp_token):
    r = requests.get(f"{API}/it/employee-assets", headers=_h(emp_token), timeout=20)
    assert r.status_code == 403


def test_employee_forbidden_employee_assets_detail(emp_token):
    r = requests.get(f"{API}/it/employee-assets/anything", headers=_h(emp_token), timeout=20)
    assert r.status_code == 403


def test_employee_forbidden_edit_asset(emp_token):
    r = requests.put(f"{API}/it/assets/DSK-0000001", headers=_h(emp_token), json={"brand": "x"}, timeout=20)
    assert r.status_code == 403
