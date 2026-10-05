"""
Backend tests for Policy Department-wise Applicability feature.
Verifies:
  - PUT /api/policies/{id} persistence for applicability_mode / applicable_departments
  - GET /api/policies returns applicable_department_names (resolved) for admins
  - Invalid applicability_mode => 400
  - Eligible-employee filtering (admin summary) changes correctly
  - Backward-compat for unconfigured (mode=null) policies
  - Acknowledgement history not deleted after applicability changes
  - Non-admin (employee) forbidden (403) on PUT
  - Employee visibility (GET /api/policies as employee) reflects mode
CRITICAL: All mutations are restored to original values in teardown.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "HrAdmin@2109"
EMP_USER = "user"
EMP_PASS = "pass123"

TARGET_POLICY = "policy_leave"  # main-agent already smoke-tested on policy_leave
GLOBAL_POLICY = "policy_it"


TIMEOUT = 120

def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=TIMEOUT)
    assert r.status_code == 200, f"login failed {username}: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_USER, ADMIN_PASS)


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def emp_token():
    try:
        return _login(EMP_USER, EMP_PASS)
    except AssertionError:
        return None


@pytest.fixture(scope="module")
def departments(admin_h):
    r = requests.get(f"{API}/departments", headers=admin_h, timeout=120)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def original_policy_state(admin_h):
    """Snapshot original applicability of the target policy so we can restore."""
    r = requests.get(f"{API}/policies", headers=admin_h, timeout=120)
    assert r.status_code == 200
    policies = r.json()
    target = next((p for p in policies if p.get("id") == TARGET_POLICY), None)
    assert target is not None, f"policy {TARGET_POLICY} not found"
    return {
        "applicability_mode": target.get("applicability_mode"),
        "applicable_departments": target.get("applicable_departments") or [],
    }


@pytest.fixture(scope="module", autouse=True)
def restore_target_policy(admin_h, original_policy_state):
    """Autouse teardown to always restore original state, even on failures."""
    yield
    restore_payload = {
        "applicability_mode": original_policy_state["applicability_mode"],
        "applicable_departments": original_policy_state["applicable_departments"],
    }
    r = requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h, json=restore_payload, timeout=120)
    print(f"\n[TEARDOWN] Restored {TARGET_POLICY} to {restore_payload}: {r.status_code}")


# ---------- Tests ----------

def test_admin_login(admin_token):
    assert admin_token


def test_departments_returns_id_and_name(departments):
    assert isinstance(departments, list) and len(departments) > 0
    d = departments[0]
    assert "id" in d and "name" in d


def test_get_policies_admin_has_applicability_fields(admin_h):
    r = requests.get(f"{API}/policies", headers=admin_h, timeout=120)
    assert r.status_code == 200
    policies = r.json()
    target = next((p for p in policies if p.get("id") == TARGET_POLICY), None)
    assert target is not None
    # These keys should be present (even if null / empty)
    assert "applicability_mode" in target
    # Admin should get applicable_department_names when mode=selected
    # We'll strongly assert after setting it below.


def test_put_invalid_mode_returns_400(admin_h):
    r = requests.put(
        f"{API}/policies/{TARGET_POLICY}",
        headers=admin_h,
        json={"applicability_mode": "everyone"},
        timeout=120,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"


def test_put_selected_persists_and_resolves_names(admin_h, departments):
    # Pick a department (prefer 'Vigilance' if exists to match madhan.s)
    dept = next((d for d in departments if d.get("name") == "Vigilance"), departments[0])
    dept_id = dept["id"]
    dept_name = dept["name"]

    # Set to selected with this dept
    r = requests.put(
        f"{API}/policies/{TARGET_POLICY}",
        headers=admin_h,
        json={"applicability_mode": "selected", "applicable_departments": [dept_id]},
        timeout=120,
    )
    assert r.status_code == 200, r.text

    # GET and verify persistence + resolved names for admin
    r = requests.get(f"{API}/policies", headers=admin_h, timeout=120)
    assert r.status_code == 200
    target = next((p for p in r.json() if p.get("id") == TARGET_POLICY), None)
    assert target["applicability_mode"] == "selected"
    assert dept_id in (target.get("applicable_departments") or [])
    names = target.get("applicable_department_names") or []
    assert dept_name in names, f"expected {dept_name} in resolved names, got {names}"


def test_put_all_clears_applicable_departments(admin_h):
    r = requests.put(
        f"{API}/policies/{TARGET_POLICY}",
        headers=admin_h,
        json={"applicability_mode": "all", "applicable_departments": ["should", "be", "cleared"]},
        timeout=120,
    )
    assert r.status_code == 200
    r = requests.get(f"{API}/policies", headers=admin_h, timeout=120)
    target = next((p for p in r.json() if p.get("id") == TARGET_POLICY), None)
    assert target["applicability_mode"] == "all"
    assert (target.get("applicable_departments") or []) == []


def test_put_null_restores_unconfigured(admin_h):
    r = requests.put(
        f"{API}/policies/{TARGET_POLICY}",
        headers=admin_h,
        json={"applicability_mode": None},
        timeout=120,
    )
    assert r.status_code == 200
    r = requests.get(f"{API}/policies", headers=admin_h, timeout=120)
    target = next((p for p in r.json() if p.get("id") == TARGET_POLICY), None)
    assert target.get("applicability_mode") in (None, "")


def test_eligible_employee_summary_reflects_mode(admin_h, departments):
    """Verify /api/admin/policy-acknowledgements/summary counts reflect mode changes."""
    dept = next((d for d in departments if d.get("name") == "Vigilance"), departments[0])
    dept_id = dept["id"]

    def get_row():
        r = requests.get(f"{API}/admin/policy-acknowledgements/summary", headers=admin_h, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        rows = data if isinstance(data, list) else data.get("items") or data.get("data") or []
        return next((row for row in rows if row.get("policy_id") == TARGET_POLICY or row.get("id") == TARGET_POLICY), None)

    # Mode = all
    requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                 json={"applicability_mode": "all"}, timeout=120)
    row_all = get_row()
    all_count = None
    if row_all:
        all_count = row_all.get("total_eligible") or row_all.get("eligible_count") or row_all.get("eligible")
    print(f"[summary] mode=all eligible={all_count}")

    # Mode = selected (single dept)
    requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                 json={"applicability_mode": "selected", "applicable_departments": [dept_id]}, timeout=120)
    row_sel = get_row()
    sel_count = None
    if row_sel:
        sel_count = row_sel.get("total_eligible") or row_sel.get("eligible_count") or row_sel.get("eligible")
    print(f"[summary] mode=selected(dept={dept['name']}) eligible={sel_count}")

    if all_count is not None and sel_count is not None:
        assert sel_count <= all_count, f"selected ({sel_count}) should be <= all ({all_count})"


def test_backward_compat_global_policy_visible_unconfigured(admin_h, emp_token):
    """policy_it is in GLOBAL_POLICIES, should be visible with mode=null."""
    # Ensure it is unconfigured (do NOT mutate if already null; but ensure)
    r = requests.get(f"{API}/policies", headers=admin_h, timeout=120)
    p_it = next((p for p in r.json() if p.get("id") == GLOBAL_POLICY), None)
    assert p_it is not None
    # We won't mutate this one to preserve state; just verify it's visible via employee if possible.
    if emp_token:
        emp_h = {"Authorization": f"Bearer {emp_token}"}
        r = requests.get(f"{API}/policies", headers=emp_h, timeout=120)
        assert r.status_code == 200
        ids = [p.get("id") for p in r.json()]
        assert GLOBAL_POLICY in ids, f"global policy {GLOBAL_POLICY} should be visible to employee"


def test_employee_visibility_selected(admin_h, emp_token, departments):
    """Employee should see 'selected' policy only if their dept is in applicable list."""
    if not emp_token:
        pytest.skip("No employee token available")

    emp_h = {"Authorization": f"Bearer {emp_token}"}
    me = requests.get(f"{API}/auth/me", headers=emp_h, timeout=120)
    if me.status_code != 200:
        pytest.skip("auth/me failed")
    emp_dept_name = (me.json() or {}).get("department")
    print(f"[emp] department={emp_dept_name}")

    matching_dept = next((d for d in departments if d.get("name") == emp_dept_name), None)
    other_dept = next((d for d in departments if d.get("name") != emp_dept_name), None)

    # Case 1: mode=selected with employee's dept -> visible
    if matching_dept:
        r = requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                         json={"applicability_mode": "selected", "applicable_departments": [matching_dept["id"]]},
                         timeout=120)
        assert r.status_code == 200
        r = requests.get(f"{API}/policies", headers=emp_h, timeout=120)
        ids = [p.get("id") for p in r.json()]
        assert TARGET_POLICY in ids, f"policy should be visible to employee in dept {emp_dept_name}"

    # Case 2: mode=selected with OTHER dept -> not visible
    if other_dept:
        r = requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                         json={"applicability_mode": "selected", "applicable_departments": [other_dept["id"]]},
                         timeout=120)
        assert r.status_code == 200
        r = requests.get(f"{API}/policies", headers=emp_h, timeout=120)
        ids = [p.get("id") for p in r.json()]
        assert TARGET_POLICY not in ids, f"policy should NOT be visible to emp when dept mismatches"

    # Case 3: mode=all -> visible
    r = requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                     json={"applicability_mode": "all"}, timeout=120)
    assert r.status_code == 200
    r = requests.get(f"{API}/policies", headers=emp_h, timeout=120)
    ids = [p.get("id") for p in r.json()]
    assert TARGET_POLICY in ids


def test_non_admin_cannot_put_policy(emp_token):
    if not emp_token:
        pytest.skip("No employee token available")
    emp_h = {"Authorization": f"Bearer {emp_token}"}
    r = requests.put(f"{API}/policies/{TARGET_POLICY}", headers=emp_h,
                     json={"applicability_mode": "all"}, timeout=120)
    assert r.status_code == 403, f"expected 403, got {r.status_code}"


def test_ack_history_preserved_after_applicability_change(admin_h, emp_token, departments):
    """Ack an existing policy as employee, then change applicability, ensure ack row still exists."""
    if not emp_token:
        pytest.skip("No employee token available")
    emp_h = {"Authorization": f"Bearer {emp_token}"}

    # Ensure visible: set all
    requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                 json={"applicability_mode": "all"}, timeout=120)

    # Acknowledge (idempotent — if already acked, endpoint returns 200 or 409; both fine)
    ack_r = requests.post(f"{API}/policies/{TARGET_POLICY}/acknowledge", headers=emp_h, timeout=120)
    print(f"[ack] status={ack_r.status_code} body={ack_r.text[:200]}")
    assert ack_r.status_code in (200, 201, 409)

    # Fetch ack via admin endpoint: /api/admin/policy-acknowledgements?policy_id=...&status=acknowledged
    def has_ack():
        r = requests.get(f"{API}/admin/policy-acknowledgements",
                         params={"policy_id": TARGET_POLICY, "status": "acknowledged"},
                         headers=admin_h, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"[ack-history] admin endpoint returned {r.status_code}: {r.text[:200]}")
            return None
        data = r.json()
        rows = data if isinstance(data, list) else data.get("items") or data.get("data") or data.get("rows") or []
        # Match by username 'user' (any field that references it)
        return any(
            (row.get("username") == EMP_USER)
            or (row.get("employee_username") == EMP_USER)
            or ("user" in (row.get("full_name") or "").lower() and row.get("acknowledged_at"))
            for row in rows
        ), len([r for r in rows if r.get("acknowledged_at")])

    before = has_ack()
    print(f"[ack-history] before_change={before}")

    # Change applicability to selected (single dept), then back to 'all'
    dept = next((d for d in departments if d.get("name") != "Vigilance"), departments[0])
    requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                 json={"applicability_mode": "selected", "applicable_departments": [dept["id"]]}, timeout=120)

    # Now flip back to 'all' — if ack rows were DELETED, they would not reappear.
    requests.put(f"{API}/policies/{TARGET_POLICY}", headers=admin_h,
                 json={"applicability_mode": "all"}, timeout=120)

    after = has_ack()
    print(f"[ack-history] after_change(back_to_all)={after}")

    # Under 'all' mode the eligible set matches original 'all' — if ack DB rows were preserved,
    # the count must be >= before count.
    if isinstance(before, tuple) and isinstance(after, tuple):
        assert after[1] >= before[1], f"Ack rows lost after applicability change: before={before[1]} after={after[1]} — BUG"
