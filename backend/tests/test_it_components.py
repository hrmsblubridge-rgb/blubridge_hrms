"""Backend tests for IT Asset — Component / Sub-Asset Management (NEW feature).

Covers:
- Auth + RBAC (admin allowed, employee denied)
- Meta / types
- Create components (auto ID)
- Install / duplicate-install guard
- Replace (parent preserved, history preserved)
- Move (remove -> install elsewhere; history not overwritten)
- Employee inheritance & self-view
- Maintenance
- Dispose (installed -> blocked; available -> ok; then install blocked)
- Import (component master template + preview + confirm)
- Bulk Assembly (preview + confirm)
- Export (multiple report types)
- Dashboard
- Asset detail components endpoint
"""
import os
import io
import csv
import uuid
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"username": "admin", "password": "HrAdmin@2109"}
EMPLOYEE = {"username": "user", "password": "pass123"}

STATE = {}  # shared across tests (parent asset id, component ids, tokens)


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def emp_token():
    return _login(EMPLOYEE)


# ---------------- 1. AUTH / RBAC ----------------
def test_admin_meta_ok(admin_token):
    r = requests.get(f"{API}/it/components/meta", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert "types" in j and isinstance(j["types"], list) and len(j["types"]) > 0
    assert "Installed" in j["statuses"]


def test_employee_denied_on_admin_endpoints(emp_token):
    endpoints = [
        ("GET", "/it/components/meta"),
        ("GET", "/it/components"),
        ("GET", "/it/components/dashboard"),
        ("GET", "/it/components/export"),
        ("POST", "/it/components"),
        ("POST", "/it/component-types"),
    ]
    for m, p in endpoints:
        if m == "GET":
            r = requests.get(f"{API}{p}", headers=_h(emp_token), timeout=15)
        else:
            r = requests.post(f"{API}{p}", headers=_h(emp_token), json={}, timeout=15)
        assert r.status_code == 403, f"{m} {p} expected 403 got {r.status_code}: {r.text[:150]}"


def test_employee_self_view_ok(emp_token):
    r = requests.get(f"{API}/employee/it-components", headers=_h(emp_token), timeout=20)
    assert r.status_code == 200
    assert "assets" in r.json()


# ---------------- 2. PARENT ASSET SETUP ----------------
def test_create_parent_asset(admin_token):
    payload = {
        "category": "Desktop",
        "brand": "Dell",
        "model": "OptiPlex TEST",
        "serial_number": f"TEST-SN-{uuid.uuid4().hex[:8]}",
        "status": "Available",
        "condition": "New",
        "source": "Newly Purchased",
        "location": "IT Store",
    }
    r = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=25)
    assert r.status_code in (200, 201), f"create asset failed: {r.status_code} {r.text}"
    a = r.json()
    STATE["asset_id"] = a.get("asset_id") or a.get("id")
    assert STATE["asset_id"]


# ---------------- 3. COMPONENT CREATE ----------------
@pytest.mark.parametrize("ctype,label", [
    ("RAM", "ram1"), ("RAM", "ram2"), ("GPU", "gpu_old"),
    ("GPU", "gpu_new"), ("SSD", "ssd1"), ("CPU / Processor", "cpu1"),
])
def test_create_components_legacy_blank_fields(admin_token, ctype, label):
    r = requests.post(f"{API}/it/components", headers=_h(admin_token),
                      json={"type": ctype}, timeout=20)
    assert r.status_code == 200, f"{label}: {r.text}"
    d = r.json()
    assert d["component_id"]
    assert d["status"] == "Available"
    assert d["parent_asset_id"] is None
    STATE[label] = d["component_id"]


def test_component_id_prefix_and_sequence(admin_token):
    # Create two more RAM to verify RAM-XXXX increments
    ids = []
    for _ in range(2):
        r = requests.post(f"{API}/it/components", headers=_h(admin_token),
                          json={"type": "RAM"}, timeout=15)
        assert r.status_code == 200
        ids.append(r.json()["component_id"])
    assert all(cid.startswith("RAM-") for cid in ids)
    nums = sorted(int(c.split("-")[1]) for c in ids)
    assert nums[1] == nums[0] + 1


# ---------------- 4. INSTALL / DUPLICATE GUARD ----------------
def test_install_component(admin_token):
    r = requests.post(f"{API}/it/components/{STATE['ram1']}/install",
                      headers=_h(admin_token),
                      json={"parent_asset_id": STATE["asset_id"], "slot": "DIMM 1"}, timeout=20)
    assert r.status_code == 200, r.text
    # Verify state
    d = requests.get(f"{API}/it/components/{STATE['ram1']}", headers=_h(admin_token)).json()["component"]
    assert d["parent_asset_id"] == STATE["asset_id"]
    assert d["status"] == "Installed"
    assert d["slot"] == "DIMM 1"


def test_duplicate_install_blocked(admin_token):
    # Create a second parent asset
    payload = {"category": "Desktop", "brand": "HP", "model": "TEST2",
               "serial_number": f"TEST-SN2-{uuid.uuid4().hex[:8]}"}
    a2 = requests.post(f"{API}/it/assets", headers=_h(admin_token), json=payload, timeout=20).json()
    STATE["asset_id_2"] = a2.get("asset_id") or a2.get("id")
    r = requests.post(f"{API}/it/components/{STATE['ram1']}/install",
                      headers=_h(admin_token),
                      json={"parent_asset_id": STATE["asset_id_2"]}, timeout=20)
    assert r.status_code == 400
    assert "already installed" in r.text.lower()


def test_install_gpu_old(admin_token):
    r = requests.post(f"{API}/it/components/{STATE['gpu_old']}/install",
                      headers=_h(admin_token),
                      json={"parent_asset_id": STATE["asset_id"], "slot": "PCIE 1"}, timeout=20)
    assert r.status_code == 200


# ---------------- 5. REPLACE ----------------
def test_replace_component_preserves_parent(admin_token):
    r = requests.post(f"{API}/it/components/replace", headers=_h(admin_token), json={
        "parent_asset_id": STATE["asset_id"],
        "old_component_id": STATE["gpu_old"],
        "new_component_id": STATE["gpu_new"],
        "reason": "Hardware Failure",
    }, timeout=25)
    assert r.status_code == 200, r.text

    # Old GPU: parent None, status Damaged, history has Installed+Removed+Replaced
    old = requests.get(f"{API}/it/components/{STATE['gpu_old']}", headers=_h(admin_token)).json()
    assert old["component"]["parent_asset_id"] is None
    assert old["component"]["status"] == "Damaged"
    actions = [h["action"] for h in old["history"]]
    for a in ("Installed", "Removed", "Replaced"):
        assert a in actions, f"missing {a} in {actions}"

    # New GPU: installed in same asset
    new = requests.get(f"{API}/it/components/{STATE['gpu_new']}", headers=_h(admin_token)).json()
    assert new["component"]["parent_asset_id"] == STATE["asset_id"]
    assert new["component"]["status"] == "Installed"


# ---------------- 6. MOVEMENT (remove + reinstall) ----------------
def test_component_movement_history_preserved(admin_token):
    # Install ram2 into asset A
    r = requests.post(f"{API}/it/components/{STATE['ram2']}/install",
                      headers=_h(admin_token),
                      json={"parent_asset_id": STATE["asset_id"], "slot": "DIMM 2"}, timeout=20)
    assert r.status_code == 200
    # Remove
    r = requests.post(f"{API}/it/components/{STATE['ram2']}/remove",
                      headers=_h(admin_token),
                      json={"reason": "Upgrade", "new_status": "Available"}, timeout=20)
    assert r.status_code == 200
    # Install into asset B
    r = requests.post(f"{API}/it/components/{STATE['ram2']}/install",
                      headers=_h(admin_token),
                      json={"parent_asset_id": STATE["asset_id_2"], "slot": "DIMM 1"}, timeout=20)
    assert r.status_code == 200
    hist = requests.get(f"{API}/it/components/{STATE['ram2']}", headers=_h(admin_token)).json()["history"]
    installs = [h for h in hist if h["action"] == "Installed"]
    removes = [h for h in hist if h["action"] == "Removed"]
    assert len(installs) >= 2, f"expected 2+ installs, got {len(installs)}"
    assert len(removes) >= 1
    # Ensure both parent asset ids appear
    parents = {h.get("parent_asset_id") for h in hist if h.get("parent_asset_id")}
    assert STATE["asset_id"] in parents and STATE["asset_id_2"] in parents


# ---------------- 7. EMPLOYEE INHERITANCE ----------------
def test_employee_inheritance(admin_token):
    # Find the 'user' employee record to assign parent asset
    r = requests.get(f"{API}/employees", headers=_h(admin_token), params={"search": "user"}, timeout=15)
    emp = None
    if r.status_code == 200:
        j = r.json()
        items = j.get("employees") or j.get("items") or (j if isinstance(j, list) else [])
        for e in items:
            if (e.get("username") or "").lower() == "user":
                emp = e
                break
    if not emp:
        pytest.skip("Could not find 'user' employee for inheritance test")

    assign_payload = {
        "employee_id": emp.get("employee_id") or emp.get("id"),
        "employee_name": emp.get("name"),
        "assigned_date": "01-01-2026",
    }
    r = requests.post(f"{API}/it/assets/{STATE['asset_id']}/assign",
                      headers=_h(admin_token), json=assign_payload, timeout=20)
    assert r.status_code in (200, 201), r.text

    # Check component holder inheritance
    detail = requests.get(f"{API}/it/components/{STATE['ram1']}", headers=_h(admin_token)).json()
    holder = detail.get("current_holder")
    assert holder is not None
    assert (holder.get("employee_id") == assign_payload["employee_id"]) or holder.get("employee_name")


def test_employee_self_view_lists_own_asset(emp_token):
    r = requests.get(f"{API}/employee/it-components", headers=_h(emp_token), timeout=20)
    assert r.status_code == 200
    assets = r.json().get("assets", [])
    ids = [a["asset_id"] for a in assets]
    assert STATE["asset_id"] in ids, f"expected parent asset {STATE['asset_id']} in {ids}"
    my = next(a for a in assets if a["asset_id"] == STATE["asset_id"])
    assert "configuration" in my


# ---------------- 8. MAINTENANCE ----------------
def test_maintenance_record(admin_token):
    r = requests.post(f"{API}/it/components/{STATE['ssd1']}/maintenance",
                      headers=_h(admin_token),
                      json={"issue": "Slow read speed", "vendor": "TestVendor", "status": "Open"}, timeout=15)
    assert r.status_code == 200
    d = requests.get(f"{API}/it/components/{STATE['ssd1']}", headers=_h(admin_token)).json()
    assert len(d["maintenance"]) >= 1


# ---------------- 9. DISPOSE ----------------
def test_dispose_installed_blocked(admin_token):
    r = requests.post(f"{API}/it/components/{STATE['ram1']}/dispose",
                      headers=_h(admin_token), json={"reason": "test"}, timeout=15)
    assert r.status_code == 400


def test_dispose_available_ok_and_install_blocked(admin_token):
    r = requests.post(f"{API}/it/components/{STATE['cpu1']}/dispose",
                      headers=_h(admin_token),
                      json={"reason": "Aged out", "method": "Scrap"}, timeout=15)
    assert r.status_code == 200
    # Now install should be blocked
    r = requests.post(f"{API}/it/components/{STATE['cpu1']}/install",
                      headers=_h(admin_token),
                      json={"parent_asset_id": STATE["asset_id"]}, timeout=15)
    assert r.status_code == 400
    assert "disposed" in r.text.lower() or "cannot" in r.text.lower()


# ---------------- 10. IMPORT ----------------
def test_import_template_download(admin_token):
    r = requests.get(f"{API}/it/components/import/template", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    assert "component_id" in r.text


def test_import_preview_and_confirm(admin_token):
    csv_content = (
        "component_id,type,name,brand,model,serial_number,part_number,capacity,status,"
        "condition,source,location,purchase_date,purchase_cost,vendor,invoice_number,"
        "warranty_start,warranty_end,remarks\n"
        f",RAM,Test Import RAM,GSkill,Ripjaws,TSN{uuid.uuid4().hex[:6]},P-9,8 GB,Available,Good,"
        "Newly Purchased,IT Store,,,,,,,imported by test\n"
    )
    files = {"file": ("import.csv", csv_content, "text/csv")}
    r = requests.post(f"{API}/it/components/import/preview",
                      headers={"Authorization": f"Bearer {admin_token}"}, files=files, timeout=25)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["valid"] >= 1
    rows = j["rows"]
    r2 = requests.post(f"{API}/it/components/import/confirm",
                       headers=_h(admin_token), json={"rows": rows}, timeout=25)
    assert r2.status_code == 200
    assert r2.json()["created"] >= 1


def test_bulk_assembly(admin_token):
    # Create a fresh available component
    c = requests.post(f"{API}/it/components", headers=_h(admin_token),
                      json={"type": "HDD"}, timeout=15).json()
    cid = c["component_id"]
    csv_content = f"parent_asset_id,component_id,slot\n{STATE['asset_id_2']},{cid},BAY-1\n"
    files = {"file": ("assembly.csv", csv_content, "text/csv")}
    r = requests.post(f"{API}/it/components/assembly/preview",
                      headers={"Authorization": f"Bearer {admin_token}"}, files=files, timeout=25)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["valid"] == 1, j
    r2 = requests.post(f"{API}/it/components/assembly/confirm",
                       headers=_h(admin_token), json={"rows": j["rows"]}, timeout=20)
    assert r2.status_code == 200
    assert r2.json()["installed"] == 1


# ---------------- 11. EXPORT ----------------
@pytest.mark.parametrize("report", ["inventory", "installed", "available", "removed",
                                     "replacement", "movement", "maintenance"])
def test_export_reports(admin_token, report):
    r = requests.get(f"{API}/it/components/export",
                     headers=_h(admin_token), params={"report": report}, timeout=20)
    assert r.status_code == 200, f"{report}: {r.status_code}"
    assert "csv" in r.headers.get("content-type", "").lower()


# ---------------- 12. DASHBOARD ----------------
def test_dashboard(admin_token):
    r = requests.get(f"{API}/it/components/dashboard", headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    j = r.json()
    for k in ("total", "installed", "summary", "by_type", "alerts"):
        assert k in j, f"missing key {k}"
    assert j["installed"] >= 2  # ram1, ram2 (in asset_2), gpu_new, hdd from assembly


# ---------------- 13. ASSET DETAIL COMPONENTS ----------------
def test_asset_components_view(admin_token):
    r = requests.get(f"{API}/it/assets/{STATE['asset_id']}/components",
                     headers=_h(admin_token), timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["asset_id"] == STATE["asset_id"]
    assert isinstance(j["components"], list)
    assert "current_configuration" in j
    types_here = {c["type"] for c in j["components"]}
    # GPU (new one) and RAM should be installed
    assert any(t.startswith("RAM") for t in types_here)


# ---------------- 14. ADD COMPONENT TYPE ----------------
def test_add_new_component_type(admin_token):
    payload = {"name": f"TESTTYPE-{uuid.uuid4().hex[:6]}", "prefix": "TT", "group": "Other"}
    r = requests.post(f"{API}/it/component-types", headers=_h(admin_token), json=payload, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == payload["name"]


# ---------------- 15. REGRESSION: existing IT asset endpoints still work ----------------
def test_regression_it_assets_list(admin_token):
    r = requests.get(f"{API}/it/assets", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200


def test_regression_employee_it_assets(emp_token):
    r = requests.get(f"{API}/employee/it-assets", headers=_h(emp_token), timeout=15)
    assert r.status_code == 200


# ---------------- 16. CLEANUP ----------------
def test_zzz_cleanup(admin_token):
    """Best-effort cleanup — remove test components and archive test assets."""
    for key in ("ram1", "ram2", "gpu_old", "gpu_new", "ssd1", "cpu1"):
        cid = STATE.get(key)
        if not cid:
            continue
        # remove first if installed
        d = requests.get(f"{API}/it/components/{cid}", headers=_h(admin_token))
        if d.status_code == 200 and d.json()["component"].get("parent_asset_id"):
            requests.post(f"{API}/it/components/{cid}/remove",
                          headers=_h(admin_token), json={"reason": "Cleanup"}, timeout=15)
        requests.delete(f"{API}/it/components/{cid}", headers=_h(admin_token), timeout=15)
