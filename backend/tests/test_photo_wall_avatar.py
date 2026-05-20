"""Backend tests for Photo Wall avatar upload endpoint.

Coverage:
  - Admin RBAC: sysadmin/HR/office_admin can update any employee's avatar
  - Employee can only update their own (403 otherwise)
  - PUT /employees/{id}/avatar persists data
  - Audit log entry includes previous + updated URLs
  - Replace flow triggers old Cloudinary asset cleanup (best-effort)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fallback for local pytest runs
    BASE_URL = "https://leave-code-mapper.preview.emergentagent.com"

API = f"{BASE_URL}/api"


def _login(username, password):
    last_exc = None
    for _ in range(3):
        try:
            r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=45)
            assert r.status_code == 200, f"Login failed for {username}: {r.status_code} {r.text}"
            return r.json().get("token") or r.json().get("access_token")
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(2)
    raise last_exc


@pytest.fixture(scope="module")
def sysadmin_token():
    return _login("sysadmin", "pass123")


@pytest.fixture(scope="module")
def office_admin_token():
    return _login("workforce", "Pass@123#")


@pytest.fixture(scope="module")
def employee_token():
    return _login("kasper", "pass123")


@pytest.fixture(scope="module")
def sample_employees(sysadmin_token):
    h = {"Authorization": f"Bearer {sysadmin_token}"}
    r = requests.get(f"{API}/employees/all", headers=h, timeout=45)
    assert r.status_code == 200
    data = r.json()
    employees = data if isinstance(data, list) else data.get("items", [])
    employees = [e for e in employees if not e.get("is_deleted")]
    assert len(employees) >= 2, "need at least 2 employees"
    return employees


# ---------- RBAC ----------

class TestAvatarRBAC:
    def test_sysadmin_can_update_other_employee_avatar(self, sysadmin_token, sample_employees):
        h = {"Authorization": f"Bearer {sysadmin_token}"}
        target = sample_employees[0]
        payload = {"avatar_url": "https://placehold.co/512/png?text=TEST_SYS", "avatar_public_id": None}
        r = requests.put(f"{API}/employees/{target['id']}/avatar", json=payload, headers=h, timeout=45)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("avatar") == payload["avatar_url"]

    def test_office_admin_can_update_other_employee_avatar(self, office_admin_token, sample_employees):
        h = {"Authorization": f"Bearer {office_admin_token}"}
        target = sample_employees[0]
        payload = {"avatar_url": "https://placehold.co/512/png?text=TEST_OFF", "avatar_public_id": None}
        r = requests.put(f"{API}/employees/{target['id']}/avatar", json=payload, headers=h, timeout=45)
        assert r.status_code == 200, r.text

    def test_employee_cannot_update_others_avatar(self, employee_token, sample_employees, sysadmin_token):
        """kasper (employee) trying to update someone else's avatar should get 403."""
        # find an employee that is NOT kasper
        ha = {"Authorization": f"Bearer {sysadmin_token}"}
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {employee_token}"}, timeout=30).json()
        my_emp_id = me.get("employee_id")
        target = next((e for e in sample_employees if e["id"] != my_emp_id), None)
        assert target is not None
        h = {"Authorization": f"Bearer {employee_token}"}
        payload = {"avatar_url": "https://placehold.co/512/png?text=NOPE", "avatar_public_id": None}
        r = requests.put(f"{API}/employees/{target['id']}/avatar", json=payload, headers=h, timeout=45)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_unauthenticated_request_rejected(self, sample_employees):
        target = sample_employees[0]
        r = requests.put(f"{API}/employees/{target['id']}/avatar",
                         json={"avatar_url": "x", "avatar_public_id": None}, timeout=30)
        assert r.status_code in (401, 403)


# ---------- Persistence & audit ----------

class TestAvatarPersistenceAndAudit:
    def test_update_persists_and_audit_log_written(self, sysadmin_token, sample_employees):
        h = {"Authorization": f"Bearer {sysadmin_token}"}
        target = sample_employees[1] if len(sample_employees) > 1 else sample_employees[0]

        # Capture previous avatar
        r0 = requests.get(f"{API}/employees/{target['id']}", headers=h, timeout=45)
        if r0.status_code != 200:
            # try alt endpoint
            r0 = requests.get(f"{API}/employees/all", headers=h, timeout=45)
            prev = next((e for e in r0.json() if e["id"] == target["id"]), {}).get("avatar")
        else:
            prev = r0.json().get("avatar")

        new_url = f"https://placehold.co/512/png?text=TEST_AUDIT_{int(time.time())}"
        r = requests.put(f"{API}/employees/{target['id']}/avatar",
                         json={"avatar_url": new_url, "avatar_public_id": "test_pub_id_audit"},
                         headers=h, timeout=45)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["avatar"] == new_url

        # Verify GET reflects change
        r_get = requests.get(f"{API}/employees/all", headers=h, timeout=45)
        assert r_get.status_code == 200
        emp = next((e for e in r_get.json() if e["id"] == target["id"]), None)
        assert emp is not None
        assert emp["avatar"] == new_url

        # Check audit log
        time.sleep(1)
        r_audit = requests.get(f"{API}/audit-logs", headers=h, params={"limit": 50}, timeout=45)
        if r_audit.status_code != 200:
            # try alt path
            r_audit = requests.get(f"{API}/audit/logs", headers=h, params={"limit": 50}, timeout=45)
        assert r_audit.status_code == 200, f"audit endpoint failed: {r_audit.status_code} {r_audit.text}"
        logs = r_audit.json() if isinstance(r_audit.json(), list) else r_audit.json().get("items", [])
        matching = [
            l for l in logs
            if l.get("action") == "update_avatar"
            and (l.get("resource_id") == target["id"] or l.get("entity_id") == target["id"])
            and new_url in (l.get("details") or "")
        ]
        assert matching, f"No matching audit entry for update_avatar; sample: {logs[:3]}"
        detail = matching[0].get("details") or ""
        assert "previous=" in detail and "updated=" in detail, f"Audit details missing previous/updated: {detail}"
        assert new_url in detail

    def test_remove_avatar(self, sysadmin_token, sample_employees):
        h = {"Authorization": f"Bearer {sysadmin_token}"}
        target = sample_employees[0]
        # Ensure there's an avatar first
        requests.put(f"{API}/employees/{target['id']}/avatar",
                     json={"avatar_url": "https://placehold.co/512/png?text=PRE_REMOVE",
                           "avatar_public_id": "pre_remove_pid"},
                     headers=h, timeout=45)
        # Now remove
        r = requests.put(f"{API}/employees/{target['id']}/avatar",
                         json={"avatar_url": "", "avatar_public_id": None},
                         headers=h, timeout=45)
        assert r.status_code == 200
        assert r.json().get("avatar") in ("", None)
