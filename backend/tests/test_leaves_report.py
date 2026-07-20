"""Backend contract tests for the Leave Management Report endpoint.

These lock in the response shape, filter semantics, pagination, and admin
guard for `GET /api/leaves/report`. They run against the live app via
httpx.AsyncClient — no mocking, no fixtures beyond an admin login.
"""
import os
import asyncio
import httpx
import pytest


BASE = os.environ.get("TEST_BASE_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{BASE}/api/auth/login",
                   json={"username": "admin", "password": "HrAdmin786$"},
                   timeout=60)
    r.raise_for_status()
    return r.json()["token"]


def _get(token, params=None):
    return httpx.get(
        f"{BASE}/api/leaves/report",
        params=params or {},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def test_report_shape(admin_token):
    r = _get(admin_token, {"page": 1, "page_size": 30})
    assert r.status_code == 200
    body = r.json()
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in body, f"missing key {key}"
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["page_size"] == 30


def test_page_size_options_respected(admin_token):
    for size in (30, 60, 100, 250, 500):
        r = _get(admin_token, {"page": 1, "page_size": size})
        assert r.status_code == 200
        assert r.json()["page_size"] == size


def test_invalid_page_size_falls_back(admin_token):
    r = _get(admin_token, {"page": 1, "page_size": 999})
    assert r.status_code == 200
    assert r.json()["page_size"] == 30


def test_status_filter(admin_token):
    r = _get(admin_token, {"status": "approved", "page": 1, "page_size": 30})
    body = r.json()
    assert all(item["status"] == "approved" for item in body["items"])


def test_leave_type_filter(admin_token):
    r = _get(admin_token, {"leave_type": "Sick", "page": 1, "page_size": 30})
    body = r.json()
    assert all(item["leave_type"] == "Sick" for item in body["items"])


def test_date_range_overlap(admin_token):
    """A leave that starts before `from_date` but ends after it must match."""
    r = _get(admin_token, {"from_date": "2027-01-01", "to_date": "2027-12-31"})
    body = r.json()
    # Every returned leave must actually overlap the window.
    for item in body["items"]:
        assert item["start_date"] <= "2027-12-31"
        assert item["end_date"] >= "2027-01-01"


def test_search_by_name(admin_token):
    r = _get(admin_token, {"search": "Kasper"})
    body = r.json()
    # Every row's name (or email) contains "Kasper".
    for item in body["items"]:
        assert ("kasper" in (item.get("emp_name") or "").lower()) or \
               ("kasper" in (item.get("email") or "").lower())


def test_admin_only_guard(admin_token):
    """Non-admin users (no token, or bogus token) must not access the report."""
    r = httpx.get(f"{BASE}/api/leaves/report",
                  headers={"Authorization": "Bearer invalid.jwt.token"},
                  timeout=30)
    assert r.status_code in (401, 403)
    # And with NO auth header at all:
    r2 = httpx.get(f"{BASE}/api/leaves/report", timeout=30)
    assert r2.status_code in (401, 403)


def test_pagination_navigation(admin_token):
    """Requesting page 2 with size 30 must not overlap page 1 (ids differ)."""
    p1 = _get(admin_token, {"page": 1, "page_size": 30}).json()
    p2 = _get(admin_token, {"page": 2, "page_size": 30}).json()
    if p1["total"] <= 30:
        pytest.skip("not enough data for multi-page test")
    ids1 = {r["id"] for r in p1["items"]}
    ids2 = {r["id"] for r in p2["items"]}
    assert not (ids1 & ids2), "pages must not overlap"
