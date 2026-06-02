"""Regression tests for Issue #2 — Settings Master Data SSOT.

Departments / Teams / Designations / Shifts ARE the single source of truth.
The consumer pages (Employees, Attendance, Leave, etc.) must read from the
same `/api/...` endpoints that Settings writes to. This test:

1. Creates a brand-new master entity via Settings (POST).
2. Verifies the same entity is immediately visible via the consumer-side
   GET endpoint that the Employees form fetches.
3. Cleans up (soft-delete) and verifies it's gone from the consumer view.

If a future change reintroduces a hardcoded list anywhere in the
consumer path, these tests fail.
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
    r = httpx.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return None
    return r.json().get("token")


@pytest.fixture(scope="module")
def hr_token():
    """Settings write actions require HR or System Admin role."""
    t = _login("sysadmin", "pass123")
    assert t, "Could not log in sysadmin"
    return t


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# -------------------- DEPARTMENT SSOT --------------------

def test_department_added_in_settings_visible_in_consumer_api(hr_token):
    unique = f"SSOT-Dept-{uuid.uuid4().hex[:8]}"
    created = httpx.post(
        f"{API}/settings/departments",
        json={"name": unique, "description": "SSOT regression marker"},
        headers=_h(hr_token), timeout=HTTP_TIMEOUT,
    )
    assert created.status_code in (200, 201), created.text
    dept_id = created.json().get("id")
    try:
        # Consumer endpoint used by Employees.js, Filters, Reports, etc.
        consumer = httpx.get(f"{API}/departments", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
        names = {d.get("name") for d in consumer.json()}
        assert unique in names, "New department is NOT visible via /api/departments"
        # And it's visible via the settings list too
        settings = httpx.get(f"{API}/settings/departments", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
        settings_names = {d.get("name") for d in settings.json()}
        assert unique in settings_names
    finally:
        # Cleanup
        if dept_id:
            httpx.delete(f"{API}/settings/departments/{dept_id}", headers=_h(hr_token), timeout=HTTP_TIMEOUT)


def test_deleted_department_not_visible_in_consumer_api(hr_token):
    unique = f"SSOT-DelDept-{uuid.uuid4().hex[:8]}"
    created = httpx.post(
        f"{API}/settings/departments",
        json={"name": unique, "description": "to-be-deleted"},
        headers=_h(hr_token), timeout=HTTP_TIMEOUT,
    )
    dept_id = created.json().get("id")
    # Delete via Settings
    httpx.delete(f"{API}/settings/departments/{dept_id}", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
    # Consumer must NOT see it
    consumer = httpx.get(f"{API}/departments", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
    names = {d.get("name") for d in consumer.json()}
    assert unique not in names, "Soft-deleted department leaked into /api/departments"


# -------------------- TEAM SSOT --------------------

def test_team_added_in_settings_visible_in_consumer_api(hr_token):
    unique = f"SSOT-Team-{uuid.uuid4().hex[:8]}"
    created = httpx.post(
        f"{API}/settings/teams",
        json={"name": unique, "department": "Research Unit", "description": "SSOT marker"},
        headers=_h(hr_token), timeout=HTTP_TIMEOUT,
    )
    assert created.status_code in (200, 201), created.text
    team_id = created.json().get("id")
    try:
        consumer = httpx.get(f"{API}/teams", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
        names = {t.get("name") for t in consumer.json()}
        assert unique in names, "New team is NOT visible via /api/teams"
    finally:
        if team_id:
            httpx.delete(f"{API}/settings/teams/{team_id}", headers=_h(hr_token), timeout=HTTP_TIMEOUT)


# -------------------- DESIGNATION SSOT --------------------

def test_designation_added_in_settings_visible_in_consumer_api(hr_token):
    unique = f"SSOT-Desig-{uuid.uuid4().hex[:8]}"
    created = httpx.post(
        f"{API}/settings/designations",
        json={"name": unique, "description": "SSOT marker"},
        headers=_h(hr_token), timeout=HTTP_TIMEOUT,
    )
    assert created.status_code in (200, 201), created.text
    desig_id = created.json().get("id")
    try:
        # Designations consumer (Employees form, Profile etc.) reads here:
        consumer = httpx.get(f"{API}/settings/designations", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
        names = {d.get("name") for d in consumer.json()}
        assert unique in names, "New designation is NOT visible via /api/settings/designations"
    finally:
        if desig_id:
            httpx.delete(f"{API}/settings/designations/{desig_id}", headers=_h(hr_token), timeout=HTTP_TIMEOUT)


# -------------------- SHIFT SSOT --------------------

def test_shifts_endpoint_returns_settings_data(hr_token):
    settings = httpx.get(f"{API}/settings/shifts", headers=_h(hr_token), timeout=HTTP_TIMEOUT)
    assert settings.status_code == 200, settings.text
    # Must return a list (shape contract). Empty is acceptable but unusual.
    data = settings.json()
    assert isinstance(data, list)


# -------------------- GUARD against hardcoded consumer dropdowns --------------------

def test_no_hardcoded_FIXED_dropdowns_in_consumer_pages():
    """Catch any reintroduction of hardcoded `FIXED_DEPARTMENTS` etc. arrays
    in consumer pages — they cause Settings additions to NOT appear in
    Employees forms, Filters, Reports, etc."""
    src_root = "/app/frontend/src"
    offenders = []
    for dirpath, _, files in os.walk(src_root):
        for fn in files:
            if not (fn.endswith(".js") or fn.endswith(".jsx")):
                continue
            full = os.path.join(dirpath, fn)
            with open(full, "r", encoding="utf-8") as f:
                txt = f.read()
            for needle in ("FIXED_DEPARTMENTS", "FIXED_TEAMS", "FIXED_DESIGNATIONS"):
                # Only flag DEFINITIONS, not occurrences in comments/strings
                if f"const {needle}" in txt:
                    offenders.append(f"{full} : {needle}")
    assert offenders == [], "Reintroduced hardcoded dropdowns:\n" + "\n".join(offenders)
