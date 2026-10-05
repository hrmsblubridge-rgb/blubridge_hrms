"""Regression tests for "Future Out-Time" missed-punch validation.

Bug fixed (CHANGELOG 2026-05-13):
  An employee submitted a missed-punch with check_out_time `22:05` for TODAY
  at 09:02 AM. HR approved it at 13:27 PM (still ~9 hours before the actual
  10:05 PM). The system applied the correction, surfacing a phantom future
  out-time (10:05 PM) on the live attendance grid.

  Fix: `_enforce_no_future_missed_punch` rejects any submitted/approved
  missed-punch with a date or HH:MM in the future (IST).
"""
import os
from datetime import datetime, timezone, timedelta
import requests
import pytest

API = "http://localhost:8001/api"


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "pass123"}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def some_employee_id() -> str:
    """Pick the first active employee for testing."""
    # Use admin token for the lookup
    token = requests.post(
        f"{API}/auth/login", json={"username": "admin", "password": "pass123"}, timeout=60
    ).json()["token"]
    r = requests.get(
        f"{API}/employees",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("employees") if isinstance(body, dict) else body
    assert items, "No employees available for test"
    return items[0]["id"]


def _ist_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def _post_missed_punch(token: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{API}/missed-punches",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=60,
    )


def test_reject_future_same_day_check_out(admin_token, some_employee_id):
    """An OUT time later than now (IST) on TODAY's date must be rejected."""
    today = _ist_now().strftime("%Y-%m-%d")
    # 23:55 — virtually always in the future regardless of when test runs
    r = _post_missed_punch(admin_token, {
        "employee_id": some_employee_id,
        "date": today,
        "punch_type": "Check-out",
        "check_out_time": "23:55",
        "reason": "regression: future OUT time must be rejected",
        "auto_approve": False,
    })
    assert r.status_code == 400, r.text
    assert "future" in r.text.lower()


def test_reject_future_date(admin_token, some_employee_id):
    """A missed-punch for tomorrow's date must be rejected outright."""
    tomorrow = (_ist_now() + timedelta(days=1)).strftime("%Y-%m-%d")
    r = _post_missed_punch(admin_token, {
        "employee_id": some_employee_id,
        "date": tomorrow,
        "punch_type": "Check-out",
        "check_out_time": "09:00",
        "reason": "regression: future date must be rejected",
        "auto_approve": False,
    })
    assert r.status_code == 400, r.text
    assert "future" in r.text.lower()


def test_reject_datetime_local_future(admin_token, some_employee_id):
    """The HTML <input type="datetime-local"> sends `YYYY-MM-DDTHH:MM`.
    A future HH:MM inside that string must still be rejected."""
    today = _ist_now().strftime("%Y-%m-%d")
    r = _post_missed_punch(admin_token, {
        "employee_id": some_employee_id,
        "date": today,
        "punch_type": "Check-in",
        "check_in_time": f"{today}T23:55",
        "reason": "regression: future datetime-local must be rejected",
        "auto_approve": False,
    })
    assert r.status_code == 400, r.text
    assert "future" in r.text.lower()


def test_accept_past_yesterday(admin_token, some_employee_id):
    """A yesterday-dated missed-punch must NOT trigger future validation,
    regardless of the HH:MM. (Cleanup: just check we don't return 400
    for the future-time reason. The endpoint may still reject for other
    reasons like duplicate — that's acceptable, just NOT for being future.)"""
    yesterday = (_ist_now() - timedelta(days=1)).strftime("%Y-%m-%d")
    r = _post_missed_punch(admin_token, {
        "employee_id": some_employee_id,
        "date": yesterday,
        "punch_type": "Check-out",
        "check_out_time": "23:55",
        "reason": "regression: yesterday's late punch is allowed",
        "auto_approve": False,
    })
    # 200 = created, or 400 with "already exists" duplicate. Neither must
    # mention "future" — that would be the regression.
    if r.status_code == 400:
        assert "future" not in r.text.lower(), f"Should not reject past dates as future: {r.text}"
    else:
        assert r.status_code == 200, r.text
        # Cleanup: delete the test request we just created
        try:
            rid = r.json().get("id")
            if rid:
                # Reject it via HR token so it cannot impact other tests
                requests.put(
                    f"{API}/missed-punches/{rid}/reject",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=30,
                )
        except Exception:
            pass
