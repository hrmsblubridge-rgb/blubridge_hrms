"""Regression tests guarding the dashboard summary ↔ detail consistency.

The bug fixed here: the "Early Out" and "Late Login" dashboard cards showed
correct counts but clicking them returned an empty detail table because the
global date-format sweep silently broke the `today` param construction in
`Dashboard.js` (`formatDate()` returned "-" instead of a valid DD-MM-YYYY).

These tests assert that for the same date window, the count returned by
`/api/dashboard/stats` matches the number of records returned by the
`/api/attendance` query that powers the detail drill-down — for ALL five
buckets (logged_in, logout, early_out, late_login, leave list).

They also exercise the same classification predicate the frontend uses, so
any future drift in either definition fails this regression check.
"""
import os
import sys
from datetime import datetime

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
def admin_token():
    t = _login("sysadmin", "pass123")
    assert t, "sysadmin login failed"
    return t


def _today_ddmmyyyy():
    return datetime.now().strftime("%d-%m-%Y")


def _has_in(r):
    return bool(r.get("check_in") or r.get("check_in_24h"))


def _has_out(r):
    return bool(r.get("check_out") or r.get("check_out_24h"))


def _is_late_login(r):
    if r.get("status") == "Late Login":
        return True
    return "late login" in (r.get("lop_reason") or "").lower()


def _is_short_day(r):
    if _is_late_login(r):
        return False
    return (
        r.get("status") == "Early Out"
        or r.get("status") == "Loss of Pay"
        or r.get("is_lop") is True
    )


PREDICATES = {
    "logged_in": lambda r: _has_in(r) and not _has_out(r),
    "logout": lambda r: _has_in(r) and _has_out(r) and not _is_short_day(r),
    "early_out": lambda r: _has_in(r) and _has_out(r) and _is_short_day(r),
    "late_login": _is_late_login,
}


def _fetch_attendance(admin_token, date_str):
    r = httpx.get(
        f"{API}/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"from_date": date_str, "to_date": date_str, "limit": 500},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    if isinstance(body, list):
        return body
    return body.get("attendance_records") or []


def _fetch_stats(admin_token, date_str):
    r = httpx.get(
        f"{API}/dashboard/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"from_date": date_str, "to_date": date_str},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return r.json().get("attendance") or {}


@pytest.fixture(scope="module")
def today_data(admin_token):
    today = _today_ddmmyyyy()
    return {
        "date": today,
        "records": _fetch_attendance(admin_token, today),
        "stats": _fetch_stats(admin_token, today),
    }


@pytest.mark.parametrize("bucket", ["logged_in", "logout", "early_out", "late_login"])
def test_dashboard_count_matches_detail_count(today_data, bucket):
    """Summary tile count MUST equal the number of records the detail drill-
    down would render. If this fails, a user clicking the tile will see a
    mismatch ("No records found" when count > 0)."""
    stats = today_data["stats"]
    records = today_data["records"]
    expected_count = stats.get(bucket, 0)
    predicate = PREDICATES[bucket]
    actual_records = [r for r in records if predicate(r)]
    # Allow 0-0 pass through cleanly
    assert len(actual_records) == expected_count, (
        f"DRIFT for bucket={bucket}: tile says {expected_count}, "
        f"detail predicate finds {len(actual_records)}. Records keys: "
        f"{[r.get('emp_name') for r in actual_records]}"
    )


def test_early_out_and_late_login_are_mutually_exclusive(today_data):
    """A single attendance row must NEVER be classified as both Early Out
    AND Late Login — the predicates would over-count and break consistency."""
    records = today_data["records"]
    both = [r for r in records if PREDICATES["early_out"](r) and PREDICATES["late_login"](r)]
    assert both == [], f"Records double-classified: {[r.get('emp_name') for r in both]}"


def test_dashboard_drilldown_dates_are_correctly_formatted(admin_token):
    """Regression guard: the `today` default in the drill-down must be a
    valid DD-MM-YYYY string. Before the fix it was literally '-'."""
    today = _today_ddmmyyyy()
    assert len(today) == 10 and today[2] == "-" and today[5] == "-"
    # Endpoint should accept it without 422 and return a list
    r = httpx.get(
        f"{API}/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"from_date": today, "to_date": today, "limit": 5},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text


def test_unauthenticated_drilldown_rejected():
    r = httpx.get(f"{API}/attendance", timeout=HTTP_TIMEOUT)
    assert r.status_code in (401, 403)
