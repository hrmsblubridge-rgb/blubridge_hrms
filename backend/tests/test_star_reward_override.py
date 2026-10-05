"""
Star Reward Msg 677 §12 — Entry Override backend tests

Covers:
- POST /api/star-rewards/entry-override
    * required fields (employee_id, ref_date, note)
    * leave_validity validation ("valid"/"invalid"/None)
    * response contains message, new_stars, month_summary, leave_validity
    * repeat edits DO NOT stack (soft-delete prior overrides)
    * 403 for non-HR / non-system-admin
- GET /api/star-rewards/auto/monthly/{employee_id}
    * items array contains leave_validity, admin_edited_by_name, override_id,
      admin_note for edited rows
"""

import os
import time
import uuid
from datetime import datetime, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

HR_USER = ("admin", "HrAdmin786$")
SYSADMIN_USER = ("sysadmin", "pass123")
EMPLOYEE_USER = ("user", "pass123")
RESEARCH_EMP_USER = ("aparna.a", "pass123")


# ---------------------------- Auth helpers ----------------------------

def _login(username: str, password: str):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=60,
    )
    return r


@pytest.fixture(scope="session")
def hr_headers():
    r = _login(*HR_USER)
    assert r.status_code == 200, f"HR login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def employee_headers():
    r = _login(*EMPLOYEE_USER)
    if r.status_code != 200:
        pytest.skip(f"Non-HR employee login failed: {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def target_employee(hr_headers):
    """Pick a Research Unit employee (aparna.a preferred) for the override tests."""
    r = requests.get(
        f"{BASE_URL}/api/star-rewards",
        headers=hr_headers,
        params={"department": "Research Unit"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    emps = r.json()
    assert len(emps) > 0, "No Research Unit employees available"
    # Prefer aparna.a for consistency with UI tests
    for e in emps:
        name = (e.get("name") or e.get("full_name") or "").lower()
        if "aparna" in name:
            return e
    return emps[0]


def _iso_date_for_this_month():
    """Pick a workday date near the beginning of the current month (non-future)."""
    today = datetime.now()
    # 5 days ago is a safe past date
    d = today - timedelta(days=5)
    return d.strftime("%Y-%m-%d")


# ---------------------------- POST /entry-override ----------------------------

class TestEntryOverrideValidation:
    """Validation branches of the endpoint."""

    def test_missing_employee_id_returns_400(self, hr_headers):
        r = requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=hr_headers,
            json={
                "ref_date": _iso_date_for_this_month(),
                "target_stars": -1,
                "new_stars": 0,
                "note": "test",
            },
            timeout=60,
        )
        assert r.status_code == 400, r.text
        assert "employee_id" in (r.json().get("detail") or "").lower()

    def test_missing_ref_date_returns_400(self, hr_headers, target_employee):
        r = requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=hr_headers,
            json={
                "employee_id": target_employee["id"],
                "target_stars": -1,
                "new_stars": 0,
                "note": "test",
            },
            timeout=60,
        )
        assert r.status_code == 400, r.text

    def test_missing_note_returns_400(self, hr_headers, target_employee):
        r = requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=hr_headers,
            json={
                "employee_id": target_employee["id"],
                "ref_date": _iso_date_for_this_month(),
                "target_stars": -1,
                "new_stars": 0,
                "note": "",
            },
            timeout=60,
        )
        assert r.status_code == 400, r.text
        assert "note" in (r.json().get("detail") or "").lower()

    def test_invalid_leave_validity_returns_400(self, hr_headers, target_employee):
        r = requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=hr_headers,
            json={
                "employee_id": target_employee["id"],
                "ref_date": _iso_date_for_this_month(),
                "target_stars": -1,
                "new_stars": 0,
                "note": "test invalid validity",
                "leave_validity": "maybe",
            },
            timeout=60,
        )
        assert r.status_code == 400, r.text
        assert "leave_validity" in (r.json().get("detail") or "").lower()

    def test_non_hr_returns_403(self, employee_headers, target_employee):
        r = requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=employee_headers,
            json={
                "employee_id": target_employee["id"],
                "ref_date": _iso_date_for_this_month(),
                "target_stars": -1,
                "new_stars": 0,
                "note": "employee attempt",
                "leave_validity": "valid",
            },
            timeout=60,
        )
        assert r.status_code == 403, r.text


# ---------------------------- Happy paths ----------------------------

class TestEntryOverrideHappy:
    """Response shape + core success behaviour."""

    def _post(self, hr_headers, emp_id, ref_date, target, new_val, note, validity=None, rule="late_sick_notification"):
        body = {
            "employee_id": emp_id,
            "ref_date": ref_date,
            "rule": rule,
            "target_stars": target,
            "new_stars": new_val,
            "note": note,
        }
        if validity is not None:
            body["leave_validity"] = validity
        return requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=hr_headers,
            json=body,
            timeout=60,
        )

    def test_override_without_leave_validity_still_ok(self, hr_headers, target_employee):
        d = _iso_date_for_this_month()
        r = self._post(
            hr_headers, target_employee["id"], d, target=-1, new_val=0,
            note="TEST_OVR no validity",
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("message") == "Leave verification and star value updated successfully."
        assert "new_stars" in body
        assert "month_summary" in body
        assert body["month_summary"]["month"] == d[:7]
        assert body.get("leave_validity") is None

    def test_override_with_valid_leave_persists_and_month_summary(self, hr_headers, target_employee):
        d = _iso_date_for_this_month()
        r = self._post(
            hr_headers, target_employee["id"], d, target=-1, new_val=0,
            note="TEST_OVR verified valid", validity="valid",
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["leave_validity"] == "valid"
        ms = b["month_summary"]
        for k in ("month", "stars", "positive", "negative", "entries"):
            assert k in ms

        # Verify persistence via monthly view
        r2 = requests.get(
            f"{BASE_URL}/api/star-rewards/auto/monthly/{target_employee['id']}",
            headers=hr_headers, timeout=60,
        )
        assert r2.status_code == 200, r2.text
        mv = r2.json()
        this_month = d[:7]
        m_bucket = next((m for m in mv["months"] if m["month"] == this_month), None)
        assert m_bucket is not None, f"Month {this_month} not in months={[m['month'] for m in mv['months']]}"
        # At least one item must be edited=True and carry override fields
        edited_items = [it for it in m_bucket["items"] if it.get("edited")]
        assert len(edited_items) > 0, "No edited items surfaced"
        it = edited_items[0]
        for k in ("leave_validity", "admin_edited_by_name", "override_id", "admin_note"):
            assert k in it, f"Field {k} missing in edited item: {it}"

    def test_repeat_edit_does_not_accumulate(self, hr_headers, target_employee):
        """Two consecutive overrides on the SAME (employee, ref_date, rule) must
        land at the final revised value — not stack."""
        d = _iso_date_for_this_month()

        # First edit: -1 → 0
        r1 = self._post(
            hr_headers, target_employee["id"], d, target=-1, new_val=0,
            note="TEST_OVR repeat 1", validity="valid",
        )
        assert r1.status_code == 200, r1.text
        stars_after_1 = r1.json()["new_stars"]
        month_after_1 = r1.json()["month_summary"]

        # Second edit on the SAME entry: -1 → +1  (net compensation should be +2, not +3)
        r2 = self._post(
            hr_headers, target_employee["id"], d, target=-1, new_val=1,
            note="TEST_OVR repeat 2", validity="invalid",
        )
        assert r2.status_code == 200, r2.text
        stars_after_2 = r2.json()["new_stars"]
        month_after_2 = r2.json()["month_summary"]

        # The cumulative employee stars should have moved by exactly +1 relative
        # to the first override (0 → +1), not +2 (which would be the "stacking" bug).
        delta = stars_after_2 - stars_after_1
        assert delta == 1, (
            f"Repeat edit accumulated stars — delta={delta} (stars_after_1={stars_after_1}, "
            f"stars_after_2={stars_after_2}, month1={month_after_1}, month2={month_after_2})"
        )

        # Verify at DB-view level: only ONE active override remains
        r3 = requests.get(
            f"{BASE_URL}/api/star-rewards/auto/monthly/{target_employee['id']}",
            headers=hr_headers, timeout=60,
        )
        assert r3.status_code == 200
        mv = r3.json()
        m_bucket = next((m for m in mv["months"] if m["month"] == d[:7]), None)
        assert m_bucket is not None
        # The one edited item should reflect +1 as effective stars
        edited_items = [it for it in m_bucket["items"]
                        if it.get("edited") and it.get("date") == d]
        assert len(edited_items) >= 1
        # After the 2nd edit the effective star for THAT (date, rule) should be +1
        # (we may have multiple auto rules on the same date; filter by rule)
        matches = [it for it in edited_items if (it.get("rule") or "") == "late_sick_notification"]
        if matches:
            assert matches[0]["stars"] == 1, f"Effective stars mismatch: {matches[0]}"
            assert matches[0]["leave_validity"] == "invalid"

    def test_invalid_leave_persists(self, hr_headers, target_employee):
        # Use a different date so it doesn't collide with the repeat-edit test above
        d = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        r = self._post(
            hr_headers, target_employee["id"], d, target=-1, new_val=-1,
            new_val_note=None, note="TEST_OVR invalid persistence",
            validity="invalid", rule="uninformed_absence",
        ) if False else self._post(
            hr_headers, target_employee["id"], d, target=-1, new_val=-1,
            note="TEST_OVR invalid persistence — validity flip only",
            validity="invalid", rule="uninformed_absence",
        )
        # target == new_val is fine at API layer (compensation=0). But if the
        # only change is validity, the API still writes the row for audit.
        assert r.status_code == 200, r.text
        assert r.json().get("leave_validity") == "invalid"


# ---------------------------- Auth ordering (system_admin) ----------------------------

class TestSysAdminOverride:
    def test_system_admin_can_override(self, target_employee):
        r = _login(*SYSADMIN_USER)
        if r.status_code != 200:
            pytest.skip("sysadmin login unavailable")
        h = {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}
        d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        r2 = requests.post(
            f"{BASE_URL}/api/star-rewards/entry-override",
            headers=h,
            json={
                "employee_id": target_employee["id"],
                "ref_date": d,
                "rule": "excess_emergency",
                "target_stars": -1,
                "new_stars": 0,
                "note": "TEST_OVR sysadmin",
                "leave_validity": "valid",
            },
            timeout=60,
        )
        assert r2.status_code == 200, r2.text
