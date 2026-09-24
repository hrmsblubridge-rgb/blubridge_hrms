"""Backend tests for IT Asset Component Phase 1 enhancements.

Covers ONLY the newly added Phase 1 capabilities (additive, does not repeat
what test_it_components.py already asserts):

  1. GET /it/components/availability — counts + available_items + message + exclude
  2. POST /it/assets/{id}/install-components — batch install
  3. Transaction rollback when one component in the batch is already installed
  4. Atomic/concurrency guard on POST /it/components/{id}/install (2nd wins loses)
  5. Asset assignment history (assign -> transfer -> return)
  6. Component employee history inheritance via parent-asset reassignment
     (NO extra physical Remove/Install events emitted)
  7. Return closes all component assignment periods, components stay installed
  8. Physical move DOES emit Removed + Installed events
  9. RBAC: employee token blocked on availability + install-components
"""
import os
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"username": "admin", "password": "HrAdmin@2109"}
EMPLOYEE = {"username": "user", "password": "pass123"}

S = {}  # shared state


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


# ---------------------------------------------------------------- helpers
def _create_asset(tok, tag_suffix=""):
    payload = {
        "category": "Desktop",
        "asset_name": f"TEST_P1_Desktop_{tag_suffix or uuid.uuid4().hex[:6]}",
        "brand": "Dell", "model": "Optiplex",
        "serial_number": f"TESTP1SN-{uuid.uuid4().hex[:8]}",
    }
    r = requests.post(f"{API}/it/assets", headers=_h(tok), json=payload, timeout=20)
    assert r.status_code in (200, 201), f"asset create failed {r.status_code}: {r.text}"
    return r.json()["asset_id"]


def _create_component(tok, ctype="RAM", brand="Kingston", capacity="16 GB"):
    payload = {"type": ctype, "brand": brand, "model": "Fury", "capacity": capacity,
               "status": "Available", "condition": "Good", "source": "Newly Purchased",
               "serial_number": f"TESTP1-{uuid.uuid4().hex[:10]}"}
    r = requests.post(f"{API}/it/components", headers=_h(tok), json=payload, timeout=20)
    assert r.status_code in (200, 201), f"comp create failed {r.status_code}: {r.text}"
    return r.json()["component_id"]


def _get_two_employees(tok):
    r = requests.get(f"{API}/employees?limit=5", headers=_h(tok), timeout=20)
    assert r.status_code == 200, r.text
    items = r.json().get("employees") or r.json().get("items") or r.json().get("data") or []
    if isinstance(items, dict):
        items = items.get("items") or items.get("employees") or []
    emps = [e for e in items if e.get("id")]
    assert len(emps) >= 2, f"need >=2 employees, got {len(emps)}"
    return emps[0], emps[1]


def _snap(e):
    return {"employee_id": e["id"], "employee_name": e.get("full_name") or e.get("name"),
            "emp_code": e.get("emp_code") or e.get("employee_code"),
            "department": e.get("department"), "designation": e.get("designation")}


# ---------------------------------------------------------------- 1. Availability
def test_availability_shape_and_counts(admin_token):
    # Seed at least one Available RAM
    S["ram1"] = _create_component(admin_token, "RAM")
    r = requests.get(f"{API}/it/components/availability?type=RAM",
                     headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "counts" in j and "available_items" in j
    for k in ("total", "used", "available", "under_repair", "damaged", "disposed"):
        assert k in j["counts"], f"missing counts.{k}"
    # available_items must all be status=Available and parent_asset_id null
    for c in j["available_items"]:
        assert c.get("status") == "Available"
        assert c.get("parent_asset_id") in (None, "")


def test_availability_exclude_param(admin_token):
    cid = S["ram1"]
    r = requests.get(f"{API}/it/components/availability?type=RAM&exclude={cid}",
                     headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    ids = [c["component_id"] for c in r.json()["available_items"]]
    assert cid not in ids, f"exclude failed, {cid} still present"


def test_availability_none_message(admin_token):
    # Use a nonsense type => no components
    r = requests.get(f"{API}/it/components/availability?type=NoSuchTypeXYZ",
                     headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j["available_items"] == []
    assert j.get("message") and "NoSuchTypeXYZ" in j["message"]


# ---------------------------------------------------------------- 2. Bulk install
def test_bulk_install_two_components(admin_token):
    aid = _create_asset(admin_token, "bulk")
    S["asset_bulk"] = aid
    c1 = _create_component(admin_token, "RAM")
    c2 = _create_component(admin_token, "RAM")
    S["bulk_c1"], S["bulk_c2"] = c1, c2
    r = requests.post(f"{API}/it/assets/{aid}/install-components",
                      headers=_h(admin_token),
                      json={"items": [{"component_id": c1}, {"component_id": c2, "slot": "B1"}]},
                      timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["installed"] == 2
    # Verify persistence
    for cid in (c1, c2):
        d = requests.get(f"{API}/it/components/{cid}", headers=_h(admin_token), timeout=20).json()
        assert d["component"]["parent_asset_id"] == aid
        assert d["component"]["status"] == "Installed"


# ---------------------------------------------------------------- 3. Transaction rollback
def test_bulk_install_rollback_on_failure(admin_token):
    aid_a = _create_asset(admin_token, "rbA")
    aid_b = _create_asset(admin_token, "rbB")
    c_pre = _create_component(admin_token, "RAM")
    c_free = _create_component(admin_token, "RAM")

    # Pre-install c_pre into aid_a
    r0 = requests.post(f"{API}/it/components/{c_pre}/install", headers=_h(admin_token),
                       json={"parent_asset_id": aid_a}, timeout=20)
    assert r0.status_code == 200, r0.text

    # Try batch on aid_b: c_free (ok) + c_pre (already installed)
    r = requests.post(f"{API}/it/assets/{aid_b}/install-components",
                      headers=_h(admin_token),
                      json={"items": [{"component_id": c_free}, {"component_id": c_pre}]},
                      timeout=30)
    assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text}"
    # Rollback assertion: c_free must be back to Available with no parent
    d = requests.get(f"{API}/it/components/{c_free}", headers=_h(admin_token), timeout=20).json()
    assert d["component"]["parent_asset_id"] in (None, ""), \
        f"rollback failed, c_free still installed in {d['component']['parent_asset_id']}"
    assert d["component"]["status"] == "Available"


# ---------------------------------------------------------------- 4. Concurrency guard
def test_concurrency_guard_single_install(admin_token):
    aid_a = _create_asset(admin_token, "cgA")
    aid_b = _create_asset(admin_token, "cgB")
    cid = _create_component(admin_token, "RAM")
    r1 = requests.post(f"{API}/it/components/{cid}/install", headers=_h(admin_token),
                       json={"parent_asset_id": aid_a}, timeout=20)
    assert r1.status_code == 200, r1.text
    r2 = requests.post(f"{API}/it/components/{cid}/install", headers=_h(admin_token),
                       json={"parent_asset_id": aid_b}, timeout=20)
    assert r2.status_code in (400, 409), f"expected fail, got {r2.status_code} {r2.text}"
    d = requests.get(f"{API}/it/components/{cid}", headers=_h(admin_token), timeout=20).json()
    assert d["component"]["parent_asset_id"] == aid_a, "component leaked to second asset"


# ---------------------------------------------------------------- 5-7. Asset+Component assignment history
def test_asset_assign_transfer_return_histories(admin_token):
    e1, e2 = _get_two_employees(admin_token)
    aid = _create_asset(admin_token, "hist")
    S["hist_asset"] = aid
    ram = _create_component(admin_token, "RAM")
    S["hist_ram"] = ram

    # Install RAM BEFORE assigning
    r = requests.post(f"{API}/it/components/{ram}/install", headers=_h(admin_token),
                      json={"parent_asset_id": aid}, timeout=20)
    assert r.status_code == 200, r.text

    # Assign to E1
    r = requests.post(f"{API}/it/assets/{aid}/assign", headers=_h(admin_token),
                      json=_snap(e1), timeout=20)
    assert r.status_code == 200, r.text

    # Transfer to E2
    r = requests.post(f"{API}/it/assets/{aid}/transfer", headers=_h(admin_token),
                      json=_snap(e2), timeout=20)
    assert r.status_code == 200, r.text

    # Asset assignment history should be E1(closed) then E2(open)
    r = requests.get(f"{API}/it/assets/{aid}/components", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    ah = r.json()["assignment_history"]
    assert len(ah) >= 2, f"asset history too short: {ah}"
    assert ah[0]["employee_id"] == e1["id"] and ah[0]["to"] is not None
    assert ah[-1]["employee_id"] == e2["id"] and ah[-1]["to"] is None

    # Component-level: inherit E1(closed) -> E2(open) via asset reassign
    r = requests.get(f"{API}/it/components/{ram}", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    j = r.json()
    ch = j["assignments"]
    assert len(ch) >= 2, f"comp assignments too short: {ch}"
    assert ch[0]["employee_id"] == e1["id"] and ch[0]["to"] is not None
    assert ch[-1]["employee_id"] == e2["id"] and ch[-1]["to"] is None

    # Physical history must ONLY contain Created + Installed (no Remove/Install noise from reassign)
    actions = [h["action"] for h in j["history"]]
    assert "Removed" not in actions, f"unexpected Removed event from reassign: {actions}"
    # Installed only once
    assert actions.count("Installed") == 1, f"unexpected extra Install: {actions}"

    # Return the asset -> all component periods should close, component stays installed
    r = requests.post(f"{API}/it/assets/{aid}/return", headers=_h(admin_token),
                      json={"return_status": "Available"}, timeout=20)
    assert r.status_code == 200, r.text
    d = requests.get(f"{API}/it/components/{ram}", headers=_h(admin_token), timeout=20).json()
    assert d["component"]["parent_asset_id"] == aid, "return should NOT auto-remove component"
    for p in d["assignments"]:
        assert p["to"] is not None, f"open period after return: {p}"


# ---------------------------------------------------------------- 8. Physical move records events
def test_physical_move_records_events(admin_token):
    aid_a = _create_asset(admin_token, "mvA")
    aid_b = _create_asset(admin_token, "mvB")
    cid = _create_component(admin_token, "RAM")

    r = requests.post(f"{API}/it/components/{cid}/install", headers=_h(admin_token),
                      json={"parent_asset_id": aid_a}, timeout=20)
    assert r.status_code == 200

    r = requests.post(f"{API}/it/components/{cid}/remove", headers=_h(admin_token),
                      json={"reason": "Upgrade", "new_status": "Available"}, timeout=20)
    assert r.status_code == 200, r.text

    r = requests.post(f"{API}/it/components/{cid}/install", headers=_h(admin_token),
                      json={"parent_asset_id": aid_b}, timeout=20)
    assert r.status_code == 200, r.text

    d = requests.get(f"{API}/it/components/{cid}", headers=_h(admin_token), timeout=20).json()
    actions = [h["action"] for h in d["history"]]
    assert actions.count("Installed") == 2
    assert actions.count("Removed") == 1
    # Verify parent asset ids in history
    parents = [h.get("parent_asset_id") for h in d["history"] if h["action"] in ("Installed", "Removed")]
    assert aid_a in parents and aid_b in parents


# ---------------------------------------------------------------- 9. RBAC
def test_employee_forbidden_on_availability(emp_token):
    r = requests.get(f"{API}/it/components/availability?type=RAM",
                     headers=_h(emp_token), timeout=20)
    assert r.status_code == 403, f"expected 403 got {r.status_code}"


def test_employee_forbidden_on_bulk_install(emp_token):
    # Use any known asset id (or fake one — RBAC must reject before lookup)
    r = requests.post(f"{API}/it/assets/AST-0001/install-components",
                      headers=_h(emp_token), json={"items": []}, timeout=20)
    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
