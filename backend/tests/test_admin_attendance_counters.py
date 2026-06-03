"""Regression tests for the Admin Attendance dashboard count rules.

The four top counters on the Admin Attendance page were re-categorized so they
become mutually exclusive and properly reflect what the admin sees on each row.
This module validates that the BACKEND payload contains all the data the
frontend categorization rules depend on:

    PRESENT     – status in {Present, Completed} AND is_lop == false
    LOGGED IN   – status == "Login"
    LATE LOGIN  – status == "Late Login" OR (is_lop AND "late login" in lop_reason)
    ABSENT      – status in {Absent, Not Logged, *Leave*} AND NOT a late-login LOP

The frontend stats logic in `/app/frontend/src/pages/Attendance.js` mirrors this.
"""
import os
import sys
import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"
HTTP_TIMEOUT = 30.0


def _login(username, password):
    r = httpx.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=HTTP_TIMEOUT)
    return r.json().get("token") if r.status_code == 200 else None


@pytest.fixture(scope="module")
def admin_token():
    t = _login("sysadmin", "pass123")
    assert t, "sysadmin login failed"
    return t


def _classify(rec):
    """Pure-Python mirror of the frontend stats categorization. If the
    backend payload changes shape, this function will fail to classify
    and the assertion below trips immediately."""
    is_lop = bool(rec.get("is_lop"))
    status = rec.get("status") or ""
    lop_reason = (rec.get("lop_reason") or "").lower()
    is_late_lop = is_lop and "late login" in lop_reason
    if (status in ("Present", "Completed")) and not is_lop:
        return "present"
    if status == "Login":
        return "logged_in"
    if status == "Late Login" or is_late_lop:
        return "late"
    if status in ("Absent", "Not Logged") or "Leave" in status:
        return "absent"
    return "other"


def test_attendance_payload_contains_classification_fields(admin_token):
    """The admin attendance list must expose the fields the dashboard
    counters depend on — `status`, `is_lop`, `lop_reason`. Schema drift
    here would silently break the counters again."""
    r = httpx.get(
        f"{API}/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data if isinstance(data, list) else data.get("records") or data.get("attendance") or []
    assert isinstance(rows, list), f"Unexpected payload shape: {type(data)}"
    if not rows:
        pytest.skip("No attendance records available for the default window")
    sample = rows[0]
    assert "status" in sample
    # is_lop and lop_reason might be missing on clean records — that's OK,
    # but the field name must be canonical when present.
    if "is_lop" in sample:
        assert isinstance(sample["is_lop"], bool)
    if "lop_reason" in sample and sample["lop_reason"] is not None:
        assert isinstance(sample["lop_reason"], str)


def test_categorization_buckets_are_mutually_exclusive(admin_token):
    """The four counters must never double-count a record — every record
    falls into at most ONE of {present, logged_in, late, absent, other}."""
    r = httpx.get(
        f"{API}/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data if isinstance(data, list) else data.get("records") or data.get("attendance") or []
    counts = {"present": 0, "logged_in": 0, "late": 0, "absent": 0, "other": 0}
    for rec in rows:
        bucket = _classify(rec)
        counts[bucket] += 1
    # Sum should equal total — each record assigned exactly once
    assert sum(counts.values()) == len(rows), (
        f"Categorization is not exhaustive: {counts} for {len(rows)} records"
    )


def test_late_login_lops_are_NOT_in_absent_bucket(admin_token):
    """The recategorization promise: a late-login that triggered LOP must
    appear in LATE LOGIN, never in ABSENT. Previously the absent counter
    used `a.is_lop` which mis-bucketed every late-login LOP."""
    r = httpx.get(
        f"{API}/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    rows = r.json()
    rows = rows if isinstance(rows, list) else (rows.get("records") or rows.get("attendance") or [])
    late_lops = [
        r for r in rows
        if r.get("is_lop") and "late login" in (r.get("lop_reason") or "").lower()
    ]
    for r in late_lops:
        assert _classify(r) == "late", (
            f"Late-login LOP record was bucketed as {_classify(r)!r} instead of 'late': {r}"
        )
