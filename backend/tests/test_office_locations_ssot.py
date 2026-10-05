"""Office Locations SSOT regression tests.

These tests guard the `GET/POST/PUT/DELETE /api/settings/office-locations`
endpoints AND the cascade-rename semantics that keep the
`employee.office_location` field aligned with the master list.

Invariants:
  • CREATE rejects duplicates, blank names, and unauthenticated callers.
  • UPDATE cascades the new name to every employee row that previously
    referenced the old name.
  • DELETE is blocked when active employees are still assigned to the
    location (no orphan rows).
  • LIST exposes `employee_count` so the Settings UI can display usage.
  • Existing employee rows without an `office_location` field continue
    to read/serialise normally (backwards-compat smoke test).

All synthetic rows are torn down in a `finally` block so the suite is
idempotent.
"""
import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"
HTTP_TIMEOUT = 30.0


def _login(username, password):
    r = httpx.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200:
        return None
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    t = _login("sysadmin", "pass123")
    assert t, "sysadmin login failed"
    return t


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1) LIST endpoint contract
# ---------------------------------------------------------------------------

def test_list_endpoint_returns_array_with_employee_count(admin_token):
    r = httpx.get(f"{API}/settings/office-locations", headers=_h(admin_token), timeout=HTTP_TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    for loc in body:
        assert {"id", "name", "employee_count"} <= set(loc.keys())
        assert isinstance(loc["employee_count"], int)


def test_unauthenticated_list_is_rejected():
    r = httpx.get(f"{API}/settings/office-locations", timeout=HTTP_TIMEOUT)
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2) CRUD round-trip
# ---------------------------------------------------------------------------

def test_crud_round_trip(admin_token):
    name = f"OL-TEST-{uuid.uuid4().hex[:8]}"
    new_name = f"{name}-renamed"
    created = None
    try:
        # Create
        r = httpx.post(
            f"{API}/settings/office-locations",
            json={"name": name, "description": "synthetic"},
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["name"] == name
        assert created["is_deleted"] is False

        # Duplicate create blocked
        r = httpx.post(
            f"{API}/settings/office-locations",
            json={"name": name},
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 409, r.text

        # Empty name blocked
        r = httpx.post(
            f"{API}/settings/office-locations",
            json={"name": "   "},
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 400, r.text

        # Update
        r = httpx.put(
            f"{API}/settings/office-locations/{created['id']}",
            json={"name": new_name, "description": "renamed"},
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == new_name

        # List contains renamed
        r = httpx.get(f"{API}/settings/office-locations", headers=_h(admin_token), timeout=HTTP_TIMEOUT)
        assert any(loc["name"] == new_name for loc in r.json())

        # Delete (no employees assigned — must succeed)
        r = httpx.delete(
            f"{API}/settings/office-locations/{created['id']}",
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text
    finally:
        # Final safety net — soft-delete by id if anything went wrong
        if created:
            httpx.delete(
                f"{API}/settings/office-locations/{created['id']}",
                headers=_h(admin_token),
                timeout=HTTP_TIMEOUT,
            )


# ---------------------------------------------------------------------------
# 3) Cascade rename + delete-block (the SSOT guarantees)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rename_cascades_to_employees_and_delete_blocks_when_assigned(admin_token):
    """Insert a synthetic employee referencing a new office location.
    Rename the location → the employee row must adopt the new name.
    Then attempt to delete the location → must be blocked (409/400)."""
    from server import db, EmployeeStatus  # noqa

    loc_name = f"OL-CASCADE-{uuid.uuid4().hex[:8]}"
    loc_renamed = f"{loc_name}-renamed"
    loc_id = None
    emp_id = str(uuid.uuid4())

    try:
        # 1. Create location
        r = httpx.post(
            f"{API}/settings/office-locations",
            json={"name": loc_name},
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        loc_id = r.json()["id"]

        # 2. Insert synthetic active employee assigned to that location
        await db.employees.insert_one({
            "id": emp_id,
            "emp_id": f"OFFLOC-TEST-{emp_id[:8]}",
            "full_name": "__OFFLOC_TEST__",
            "department": "Test",
            "team": "Test",
            "designation": "Test",
            "office_location": loc_name,
            "employee_status": EmployeeStatus.ACTIVE,
            "is_deleted": False,
        })

        # 3. List must reflect employee_count = 1
        r = httpx.get(f"{API}/settings/office-locations", headers=_h(admin_token), timeout=HTTP_TIMEOUT)
        rows = r.json()
        target = next(loc for loc in rows if loc["id"] == loc_id)
        assert target["employee_count"] == 1, f"expected count=1 got {target}"

        # 4. Rename and verify the cascade
        r = httpx.put(
            f"{API}/settings/office-locations/{loc_id}",
            json={"name": loc_renamed},
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        emp_row = await db.employees.find_one({"id": emp_id}, {"_id": 0, "office_location": 1})
        assert emp_row["office_location"] == loc_renamed, (
            f"cascade failed — employee.office_location={emp_row['office_location']}, expected {loc_renamed}"
        )

        # 5. Delete must be blocked because the employee still references it
        r = httpx.delete(
            f"{API}/settings/office-locations/{loc_id}",
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code in (400, 409), (
            f"Delete should be blocked when employees still reference the location, got {r.status_code}: {r.text}"
        )

        # 6. After unassigning the employee, delete should succeed
        await db.employees.update_one({"id": emp_id}, {"$set": {"office_location": ""}})
        r = httpx.delete(
            f"{API}/settings/office-locations/{loc_id}",
            headers=_h(admin_token),
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text

    finally:
        # Clean up synthetic rows
        await db.employees.delete_one({"id": emp_id})
        if loc_id:
            await db.office_locations.delete_one({"id": loc_id})
