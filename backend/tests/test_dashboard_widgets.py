"""Tests for the Phase-2 dashboard widgets:
- GET /api/dashboard/birthdays  → today + upcoming birthdays
- GET /api/employee/dashboard/weekly-hours → live per-day working hours
"""
import os
import sys
from datetime import date, timedelta

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


# -------------------- BIRTHDAY WIDGET --------------------

def test_birthdays_endpoint_returns_today_and_upcoming(admin_token):
    r = httpx.get(
        f"{API}/dashboard/birthdays",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "today" in body and isinstance(body["today"], list)
    assert "upcoming" in body and isinstance(body["upcoming"], list)
    assert body["window_days"] == 7


def test_birthdays_upcoming_is_chronologically_sorted(admin_token):
    r = httpx.get(
        f"{API}/dashboard/birthdays",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"window_days": 30},
        timeout=HTTP_TIMEOUT,
    )
    upcoming = r.json()["upcoming"]
    days = [u["days_until"] for u in upcoming]
    assert days == sorted(days), f"Upcoming not sorted: {days}"
    # No future "today" entries leaking through
    for u in upcoming:
        assert u["days_until"] >= 1


def test_birthdays_items_have_required_fields(admin_token):
    r = httpx.get(
        f"{API}/dashboard/birthdays?window_days=30",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    body = r.json()
    sample = (body["today"] + body["upcoming"])
    if not sample:
        pytest.skip("DB has no birthdays in the next 30 days — environmental")
    for e in sample:
        for key in ("id", "full_name", "department", "team", "date_of_birth"):
            assert key in e, f"missing {key} in birthday entry"


def test_birthdays_window_param_respected(admin_token):
    r7 = httpx.get(f"{API}/dashboard/birthdays?window_days=7",
                   headers={"Authorization": f"Bearer {admin_token}"}, timeout=HTTP_TIMEOUT).json()
    r30 = httpx.get(f"{API}/dashboard/birthdays?window_days=30",
                    headers={"Authorization": f"Bearer {admin_token}"}, timeout=HTTP_TIMEOUT).json()
    # 30-day window must include at least as many as 7-day
    assert len(r30["upcoming"]) >= len(r7["upcoming"])
    for u in r7["upcoming"]:
        assert u["days_until"] <= 7


def test_birthdays_unauthenticated_rejected():
    r = httpx.get(f"{API}/dashboard/birthdays", timeout=HTTP_TIMEOUT)
    assert r.status_code in (401, 403)


# -------------------- WEEKLY HOURS WIDGET --------------------

def test_weekly_hours_requires_employee_profile(admin_token):
    """sysadmin has no employee_id — must 404."""
    r = httpx.get(
        f"{API}/employee/dashboard/weekly-hours",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 404


def test_weekly_hours_structure_for_employee():
    """Login as a known employee user (seeded by the previous test fixture)
    and validate the response shape."""
    tok = _login("user", "pass123")
    if not tok:
        pytest.skip("Employee test user 'user' not available with pass123 — env-only")
    r = httpx.get(
        f"{API}/employee/dashboard/weekly-hours",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "week_start" in body and "week_end" in body
    assert isinstance(body["days"], list) and len(body["days"]) == 7
    # Days must be Mon→Sun, all-hours numeric and non-negative
    expected = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert [d["day"] for d in body["days"]] == expected
    for d in body["days"]:
        assert isinstance(d["hours"], (int, float))
        assert d["hours"] >= 0
    assert isinstance(body["avg_hours"], (int, float))
    assert isinstance(body["total_hours"], (int, float))


def test_weekly_hours_unauthenticated_rejected():
    r = httpx.get(f"{API}/employee/dashboard/weekly-hours", timeout=HTTP_TIMEOUT)
    assert r.status_code in (401, 403)
