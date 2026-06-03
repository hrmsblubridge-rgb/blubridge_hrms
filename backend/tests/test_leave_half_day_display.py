"""Regression test for the half-day leave session display fix.

The admin Leave Details panel now shows the `leave_split` value
("First Half" / "Second Half") when the leave is a half-day. This test
ensures the BACKEND continues to return the `leave_split` field on the
leave list — the frontend rendering depends on it.

If the backend ever drops or renames `leave_split`, the Session row
silently disappears and admins lose the ability to distinguish half-day
sessions. This test fails-fast in that case.
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


def test_half_day_leaves_carry_first_or_second_half(admin_token):
    """Every half-day leave (duration containing '0.5') must have a
    `leave_split` of "First Half" or "Second Half" — never null/missing.
    This is the field the admin Leave detail panel reads to render the
    Session badge."""
    r = httpx.get(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    if not isinstance(rows, list):
        rows = rows.get("leaves") or rows.get("records") or []
    half_day = [l for l in rows if "0.5" in (l.get("duration") or "")]
    if not half_day:
        pytest.skip("No half-day leaves in the current dataset")
    for lv in half_day:
        split = lv.get("leave_split")
        assert split in ("First Half", "Second Half"), (
            f"Half-day leave missing leave_split: emp={lv.get('emp_name')} "
            f"id={lv.get('id')} got={split!r}"
        )


def test_full_day_leaves_do_not_corrupt_split_field(admin_token):
    """Full-day leaves must not accidentally carry a 'First/Second Half'
    label — otherwise the detail panel would falsely show a Session row."""
    r = httpx.get(
        f"{API}/leaves",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=HTTP_TIMEOUT,
    )
    rows = r.json()
    if not isinstance(rows, list):
        rows = rows.get("leaves") or rows.get("records") or []
    full_day = [l for l in rows if "0.5" not in (l.get("duration") or "")]
    if not full_day:
        pytest.skip("No full-day leaves in the current dataset")
    for lv in full_day:
        split = lv.get("leave_split")
        assert split in (None, "", "Full Day"), (
            f"Full-day leave has unexpected split value: emp={lv.get('emp_name')} "
            f"id={lv.get('id')} duration={lv.get('duration')!r} split={split!r}"
        )
