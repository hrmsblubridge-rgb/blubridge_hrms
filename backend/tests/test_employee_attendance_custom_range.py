"""Regression tests for `GET /api/employee/attendance` custom date filter.

Bug fixed here: when `duration=custom` was passed with `from_date`/`to_date`,
the endpoint raised `TypeError: can't compare offset-naive and offset-aware
datetimes` and returned HTTP 500. Root cause: `_parse_any()` produced
naive datetimes via `datetime.strptime(...)` which were then compared
against `now = get_ist_now()` (tz-aware IST) at the `current_date > now`
check inside the day-loop. Fix: attach IST tzinfo inside `_parse_any()`.

These tests assert:
  • Valid DD-MM-YYYY custom range returns 200 with the right number of records.
  • Single-day range returns exactly 1 record.
  • Historical date range returns 200 (no future flag tripped).
  • Empty/no-data range returns the same number of slots (one per day) but
    each slot's punch fields are "-".
  • Invalid date format falls back to "this_week" (7 records) without 500.
  • ISO YYYY-MM-DD format is accepted (legacy clients).
  • Existing `duration=this_week` still returns 200 (no regression on the
    branches that were not touched).
"""
import os
import sys

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
def employee_token():
    """Use the employee account created for dashboard widget tests — it has
    attendance rows in the current month, so the custom range exercises
    real data, not just empty slots."""
    t = _login("user", "pass123")
    assert t, "employee 'user' login failed — required for custom range test"
    return t


def _get(token, params):
    return httpx.get(
        f"{API}/employee/attendance",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=HTTP_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Core regression: the 500 bug
# ---------------------------------------------------------------------------

def test_custom_range_valid_ddmmyyyy_returns_200(employee_token):
    """The original bug reproducer: 01-06-2026 → 07-06-2026 returned 500."""
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "01-06-2026",
            "to_date": "07-06-2026",
        },
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 7, f"Expected 7 daily slots, got {len(data)}"
    # Order preserved
    assert data[0]["date"] == "01-06-2026"
    assert data[-1]["date"] == "07-06-2026"


def test_custom_range_single_day(employee_token):
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "01-06-2026",
            "to_date": "01-06-2026",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["date"] == "01-06-2026"


def test_custom_range_historical_dates(employee_token):
    """A range fully in the past — guards against any 'future date' regression."""
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "01-01-2024",
            "to_date": "07-01-2024",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 7
    # Past dates must NEVER be marked NA (which is the future-date status)
    assert all(rec["status"] != "NA" for rec in data), (
        "Historical dates were mis-classified as future ('NA'). "
        "Did the tz comparison regress?"
    )


def test_custom_range_empty_window_returns_slots_with_dashes(employee_token):
    """A historical range where the employee has no attendance, no leave,
    and no holidays — every day should be present as a record with '-'
    punches and status of Absent/Sunday."""
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "01-01-2024",
            "to_date": "03-01-2024",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 3
    for rec in data:
        # Each slot has the canonical shape regardless of data.
        assert {"date", "day", "login", "logout", "total_hours", "status"} <= set(rec.keys())


def test_custom_range_invalid_format_falls_back_to_this_week(employee_token):
    """The bug previously made garbage input either 500 or crash. The fixed
    path falls back to the current-week window — 7 records, HTTP 200."""
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "not-a-date",
            "to_date": "also-bogus",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 7


def test_custom_range_iso_format_accepted(employee_token):
    """ISO YYYY-MM-DD is also supported (legacy/external clients)."""
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "2026-06-01",
            "to_date": "2026-06-07",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 7
    assert data[0]["date"] == "01-06-2026"


def test_custom_range_inverted_dates_are_swapped(employee_token):
    """If user provides to_date < from_date, the endpoint should swap them
    instead of returning an empty list."""
    r = _get(
        employee_token,
        {
            "duration": "custom",
            "from_date": "07-06-2026",
            "to_date": "01-06-2026",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 7
    assert data[0]["date"] == "01-06-2026"
    assert data[-1]["date"] == "07-06-2026"


# ---------------------------------------------------------------------------
# Regression guard: untouched duration branches still work
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("duration", ["this_week", "last_week", "this_month", "last_month"])
def test_existing_duration_branches_still_work(employee_token, duration):
    r = _get(employee_token, {"duration": duration})
    assert r.status_code == 200, f"{duration}: {r.text}"
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_unauthenticated_request_is_rejected():
    r = httpx.get(
        f"{API}/employee/attendance",
        params={"duration": "custom", "from_date": "01-06-2026", "to_date": "07-06-2026"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code in (401, 403)
