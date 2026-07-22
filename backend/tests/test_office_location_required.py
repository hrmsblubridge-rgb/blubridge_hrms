"""
Iteration 59 backend tests — Office Location required + historical migration.

Covers:
  1. POST /api/employees — omit / blank office_location → 400
  2. POST /api/employees — valid office_location='Besant Nagar - Chennai' → 201
  3. PUT /api/employees/{id} — office_location='' → 400
  4. PUT /api/employees/{id} — office_location='Mandaveli - Chennai' → 200
  5. GET /api/employees — active have office_location; 1 Inactive Sathish E kept blank;
                          Besant Nagar - Chennai active count == 53
"""
import os
import time
import uuid
import pytest
import requests


def _read_base_url():
    # Prefer local backend to avoid preview-ingress latency
    return "http://localhost:8001"


BASE_URL = _read_base_url()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "HrAdmin786$"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
                      timeout=180)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    assert tok, f"No token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _base_payload(unique_suffix: str):
    """Minimum required Employee payload (unique fields randomised)."""
    return {
        "full_name": f"TEST OL Emp {unique_suffix}",
        "official_email": f"test_ol_{unique_suffix}@example.com",
        "personal_email": f"test_ol_{unique_suffix}@personal.com",
        "phone_number": "9999999999",
        "date_of_joining": "2025-01-01",
        "department": "Research Unit",
        "team": "Research",
        "designation": "Research Associate",
        "custom_employee_id": f"OLTST{unique_suffix}",
        "biometric_id": f"BIOOL{unique_suffix}",
        "gender": "Male",
        "date_of_birth": "1995-01-01",
    }


# ---------- CREATE validation ----------

class TestCreateEmployeeOfficeLocationRequired:

    def test_create_missing_office_location_returns_400(self, headers):
        suffix = uuid.uuid4().hex[:6]
        payload = _base_payload(suffix)
        # omit office_location entirely
        payload.pop("office_location", None)
        r = requests.post(f"{BASE_URL}/api/employees",
                          json=payload, headers=headers, timeout=180)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        body = r.json()
        detail = body.get("detail") or body.get("message") or ""
        assert "Office Location is required" in str(detail), \
            f"Expected 'Office Location is required' in detail, got: {body}"

    def test_create_blank_office_location_returns_400(self, headers):
        suffix = uuid.uuid4().hex[:6]
        payload = _base_payload(suffix)
        payload["office_location"] = ""
        r = requests.post(f"{BASE_URL}/api/employees",
                          json=payload, headers=headers, timeout=180)
        assert r.status_code == 400
        assert "Office Location is required" in str(r.json().get("detail", ""))

    def test_create_whitespace_office_location_returns_400(self, headers):
        suffix = uuid.uuid4().hex[:6]
        payload = _base_payload(suffix)
        payload["office_location"] = "   "
        r = requests.post(f"{BASE_URL}/api/employees",
                          json=payload, headers=headers, timeout=180)
        assert r.status_code == 400
        assert "Office Location is required" in str(r.json().get("detail", ""))


# ---------- CREATE happy path + UPDATE tests (share the created employee) ----------

class TestCreateUpdateHappyPath:

    _created_id = None
    _created_suffix = None

    def test_create_with_valid_office_location_succeeds(self, headers):
        suffix = uuid.uuid4().hex[:6]
        TestCreateUpdateHappyPath._created_suffix = suffix
        payload = _base_payload(suffix)
        payload["office_location"] = "Besant Nagar - Chennai"

        r = requests.post(f"{BASE_URL}/api/employees",
                          json=payload, headers=headers, timeout=180)
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
        body = r.json()
        emp = body.get("employee") or body
        emp_id = emp.get("id") or body.get("id")
        assert emp_id, f"No id in create response: {body}"
        TestCreateUpdateHappyPath._created_id = emp_id

        # GET verify persistence
        g = requests.get(f"{BASE_URL}/api/employees/{emp_id}",
                         headers=headers, timeout=180)
        assert g.status_code == 200
        fetched = g.json()
        assert fetched.get("office_location") == "Besant Nagar - Chennai"
        assert fetched.get("full_name") == payload["full_name"]

    def test_update_blank_office_location_returns_400(self, headers):
        emp_id = TestCreateUpdateHappyPath._created_id
        assert emp_id, "Prior create test must have run"
        r = requests.put(f"{BASE_URL}/api/employees/{emp_id}",
                         json={"office_location": ""},
                         headers=headers, timeout=180)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "Office Location is required" in str(r.json().get("detail", ""))

    def test_update_whitespace_office_location_returns_400(self, headers):
        emp_id = TestCreateUpdateHappyPath._created_id
        assert emp_id
        r = requests.put(f"{BASE_URL}/api/employees/{emp_id}",
                         json={"office_location": "   "},
                         headers=headers, timeout=180)
        assert r.status_code == 400

    def test_update_to_mandaveli_succeeds(self, headers):
        emp_id = TestCreateUpdateHappyPath._created_id
        assert emp_id
        r = requests.put(f"{BASE_URL}/api/employees/{emp_id}",
                         json={"office_location": "Mandaveli - Chennai"},
                         headers=headers, timeout=180)
        assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"

        # GET verify
        g = requests.get(f"{BASE_URL}/api/employees/{emp_id}",
                         headers=headers, timeout=180)
        assert g.status_code == 200
        assert g.json().get("office_location") == "Mandaveli - Chennai"

    def test_restore_original_office_location(self, headers):
        emp_id = TestCreateUpdateHappyPath._created_id
        assert emp_id
        # Restore to Besant Nagar (the original create value)
        r = requests.put(f"{BASE_URL}/api/employees/{emp_id}",
                         json={"office_location": "Besant Nagar - Chennai"},
                         headers=headers, timeout=180)
        assert r.status_code == 200

    def test_cleanup_soft_delete(self, headers):
        emp_id = TestCreateUpdateHappyPath._created_id
        if not emp_id:
            pytest.skip("No employee to clean up")
        r = requests.delete(f"{BASE_URL}/api/employees/{emp_id}",
                            headers=headers, timeout=180)
        assert r.status_code in (200, 204), f"Delete failed: {r.status_code} {r.text}"


# ---------- Reactivate-deleted branch verification (iter60 fix) ----------

class TestReactivateBranchOfficeLocation:
    """
    Verify that POST /api/employees using an email whose previous record is
    soft-deleted takes the 'existing_deleted' branch AND correctly persists
    the office_location value from the new request (not the stale/default).
    """

    def test_reactivate_persists_new_office_location(self, headers):
        """
        The reactivate branch is entered only when a record with the same email
        exists and has `is_deleted: True`. The DELETE endpoint does soft
        deactivate (employee_status=Inactive) but does NOT set is_deleted.
        To exercise the reactivate branch we flip is_deleted=True directly
        in Mongo, then POST with the same email.
        """
        import os
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL") or \
            open("/app/backend/.env").read().split('MONGO_URL="')[1].split('"')[0]
        db_name = os.environ.get("DB_NAME") or \
            open("/app/backend/.env").read().split('DB_NAME="')[1].split('"')[0]
        client = MongoClient(mongo_url)
        db = client[db_name]

        suffix = uuid.uuid4().hex[:6]
        payload = _base_payload(suffix)
        payload["office_location"] = "Besant Nagar - Chennai"

        # Step 1 — create fresh employee
        r = requests.post(f"{BASE_URL}/api/employees",
                          json=payload, headers=headers, timeout=180)
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
        emp = r.json().get("employee") or r.json()
        emp_id = emp.get("id") or r.json().get("id")
        assert emp_id, f"No id in create response: {r.json()}"

        # Step 2 — flip is_deleted=True directly in Mongo to simulate the
        #          state the reactivate branch expects.
        upd = db.employees.update_one(
            {"id": emp_id},
            {"$set": {"is_deleted": True,
                      "deleted_at": "2025-01-01T00:00:00",
                      "office_location": "STALE_VALUE"}},
        )
        assert upd.modified_count == 1

        # Step 3 — POST with SAME email + DIFFERENT office_location →
        #          should hit the reactivate branch (L5205-5238)
        new_payload = _base_payload(suffix)  # same email/custom_id
        new_payload["office_location"] = "Mandaveli - Chennai"
        r2 = requests.post(f"{BASE_URL}/api/employees",
                           json=new_payload, headers=headers, timeout=180)
        assert r2.status_code in (200, 201), f"Reactivate failed: {r2.status_code} {r2.text}"
        body2 = r2.json()
        # Reactivate path returns the employee dict directly
        rehired_id = body2.get("id") or (body2.get("employee") or {}).get("id")
        assert rehired_id, f"No id in reactivate response: {body2}"
        assert rehired_id == emp_id, "Reactivate should reuse the same employee id"

        # Step 4 — GET verify office_location matches the NEW payload
        g = requests.get(f"{BASE_URL}/api/employees/{rehired_id}",
                         headers=headers, timeout=180)
        assert g.status_code == 200
        fetched = g.json()
        assert fetched.get("office_location") == "Mandaveli - Chennai", (
            f"Reactivate branch did NOT persist new office_location. "
            f"Expected 'Mandaveli - Chennai', got: {fetched.get('office_location')!r}"
        )
        assert (fetched.get("is_deleted") or False) is False, "Should be reactivated"

        # Cleanup
        requests.delete(f"{BASE_URL}/api/employees/{rehired_id}",
                        headers=headers, timeout=180)


# ---------- Historical migration verification ----------

class TestMigrationInvariants:

    def _all_employees(self, headers):
        """Paginate through /api/employees (max 500 per page) — include inactive."""
        all_emps = []
        page = 1
        # Include inactive by using status filter loop OR include_deleted flag
        while True:
            r = requests.get(
                f"{BASE_URL}/api/employees",
                headers=headers,
                params={"limit": 500, "page": page, "include_deleted": "true"},
                timeout=180,
            )
            assert r.status_code == 200, f"List failed: {r.status_code} {r.text}"
            body = r.json()
            emps = body.get("employees") or []
            all_emps.extend(emps)
            pages = body.get("pages", 1)
            if page >= pages or not emps:
                break
            page += 1
        return all_emps

    def test_no_active_employee_has_empty_office_location(self, headers):
        emps = self._all_employees(headers)
        assert emps, "Empty employees list"
        offenders = []
        for e in emps:
            status = (e.get("employee_status") or "").strip().lower()
            # Active = anything not Inactive/Resigned (blank status treated as active)
            if status in ("inactive", "resigned"):
                continue
            ol = (e.get("office_location") or "").strip()
            if not ol:
                offenders.append({
                    "id": e.get("id"),
                    "full_name": e.get("full_name"),
                    "status": e.get("employee_status"),
                })
        assert not offenders, f"Active employees with empty office_location: {offenders}"

    def test_exactly_one_inactive_has_empty_office_location_and_is_sathish(self, headers):
        emps = self._all_employees(headers)
        inactive_blank = [
            e for e in emps
            if (e.get("employee_status") or "").strip().lower() in ("inactive", "resigned")
            and not (e.get("office_location") or "").strip()
        ]
        # Should be exactly 1 — Sathish E — per spec
        assert len(inactive_blank) == 1, \
            f"Expected exactly 1 relieved employee with blank office_location, got {len(inactive_blank)}: " \
            f"{[(e.get('full_name'), e.get('employee_status')) for e in inactive_blank]}"
        assert "Sathish" in (inactive_blank[0].get("full_name") or ""), \
            f"Expected Sathish E, got: {inactive_blank[0].get('full_name')}"

    def test_besant_nagar_active_count_is_53(self, headers):
        emps = self._all_employees(headers)
        besant_active = [
            e for e in emps
            if (e.get("office_location") or "").strip() == "Besant Nagar - Chennai"
            and (e.get("employee_status") or "").strip().lower() not in ("inactive", "resigned")
        ]
        assert len(besant_active) == 53, \
            f"Expected 53 active employees at Besant Nagar - Chennai, got {len(besant_active)}"
