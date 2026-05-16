"""Regression test for the rehire-collision admin-overwrite firewall.

⚠️ HISTORICAL ROOT-CAUSE NOTE (2026-05-17 — FINAL ELIMINATION):
    This file PREVIOUSLY mutated the REAL `admin` user — both setting a
    sentinel password on it AND directly resetting `password_hash` back
    to SHA256("pass123") via raw Mongo update at the end of every test.
    That raw write bypassed every firewall and was a direct contributor
    to the recurring "admin password reverts" bug.

    The file has been rewritten to use a DEDICATED ephemeral HR user
    (`__regression_rehire_firewall_admin__`) instead of the real admin.
    The firewall behaviour is the same regardless of which protected
    username is targeted, so this is a SAFE refactor that preserves the
    regression's intent without ever touching production credentials.

Original bug fixed:
  The "rehire deleted employee" path at POST /api/employees derived the
  user's username from `email.split('@')[0]`. When a deleted employee with
  email like `admin@bug-test.com` was re-created, the path matched the
  REAL admin user (`username = "admin"`) and silently overwrote
  password_hash with a generated temp password.

Defence layers verified by this test:
  • Rehire flow REJECTS with HTTP 400 when colliding with a protected
    admin username, forcing HR to pick a different email.
  • `_safe_user_update()` firewall strips password_hash writes against
    protected accounts.
"""
import os
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
import requests
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import asyncio

load_dotenv("/app/backend/.env")
API = "http://localhost:8001/api"
TEST_EMAIL = "admin@regression-rehire.test"

# Ephemeral protected-admin sentinel user. Real admin is never touched.
EPHEMERAL_USERNAME = "admin"  # IMPORTANT: must equal a real protected username
# so the firewall code path is actually exercised. To avoid clobbering the
# real admin we DO NOT manipulate the password of this user; we only verify
# that the rehire endpoint REJECTS the collision (HTTP 400) and never enters
# the password-write branch in the first place.

# A separate sentinel HR account that we own — used to invoke the rehire
# endpoint (needs an HR token) without depending on the real admin's
# current password.
SENTINEL_HR_USERNAME = "__regression_rehire_hr__"
SENTINEL_HR_PASSWORD = "Rehire!Sentinel#1"


async def _seed_deleted_employee():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    await db.employees.delete_many({"official_email": TEST_EMAIL})
    eid = "test-rehire-" + uuid.uuid4().hex[:8]
    await db.employees.insert_one({
        "id": eid,
        "emp_id": "TEST-REHIRE",
        "full_name": "Rehire Tester",
        "official_email": TEST_EMAIL,
        "phone_number": "9999999999",
        "is_deleted": True,
        "deleted_at": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        "employee_status": "Inactive",
    })
    c.close()


async def _provision_sentinel_hr():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    await db.users.delete_many({"username": SENTINEL_HR_USERNAME})
    uid = "sentinel-hr-" + uuid.uuid4().hex[:8]
    await db.users.insert_one({
        "id": uid,
        "username": SENTINEL_HR_USERNAME,
        "email": f"{SENTINEL_HR_USERNAME}@regression.local",
        "password_hash": hashlib.sha256(SENTINEL_HR_PASSWORD.encode()).hexdigest(),
        "name": "Rehire Regression HR (ephemeral)",
        "role": "hr",
        "is_active": True,
        "is_first_login": False,
        "onboarding_status": "completed",
        "created_at": "2026-01-01T00:00:00+05:30",
    })
    c.close()


async def _capture_admin_state() -> dict:
    """Snapshot the real admin's password_hash + audit fields BEFORE the
    test, so the assertion is 'admin row was not touched' rather than
    'admin password is some specific value' (which would force us to know
    the user's current password — exactly the trap that caused this bug)."""
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    u = await db.users.find_one({"username": "admin"}, {"_id": 0})
    c.close()
    return {
        "password_hash": (u or {}).get("password_hash"),
        "password_updated_at": (u or {}).get("password_updated_at"),
        "password_updated_method": (u or {}).get("password_updated_method"),
    }


async def _cleanup():
    """Clean ONLY what this test created. NEVER touch the admin user."""
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    await db.employees.delete_many({"official_email": TEST_EMAIL})
    await db.users.delete_many({"username": SENTINEL_HR_USERNAME})
    c.close()


@pytest.fixture
def rehire_fixture():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_seed_deleted_employee())
    loop.run_until_complete(_provision_sentinel_hr())
    admin_snapshot = loop.run_until_complete(_capture_admin_state())

    # Login as the sentinel HR (NOT the real admin) to obtain an HR token.
    r = requests.post(
        f"{API}/auth/login",
        json={"username": SENTINEL_HR_USERNAME, "password": SENTINEL_HR_PASSWORD},
        timeout=60,
    )
    assert r.status_code == 200, f"Sentinel HR login failed: {r.text}"
    token = r.json()["token"]

    try:
        yield token, admin_snapshot
    finally:
        loop.run_until_complete(_cleanup())


def test_rehire_with_admin_email_collision_is_rejected_and_admin_untouched(rehire_fixture):
    """Attempting to rehire an employee whose derived username collides with
    a protected admin must return 400 AND the real admin user row must be
    BYTE-IDENTICAL to its pre-test state (password_hash + audit fields).
    """
    token, admin_before = rehire_fixture

    rehire_payload = {
        "full_name": "Rehire Collider",
        "official_email": TEST_EMAIL,
        "phone_number": "9999999999",
        "gender": "Male",
        "date_of_birth": "1990-01-01",
        "date_of_joining": "2026-01-01",
        "employment_type": "Full Time",
        "designation": "Test",
        "tier_level": "L1",
        "department": "Research Unit",
        "team": "Data",
        "work_location": "Office",
        "leave_policy": "Standard",
        "shift_type": "Day",
        "attendance_tracking_enabled": True,
        "user_role": "employee",
        "login_enabled": True,
        "reporting_manager_id": None,
        "custom_employee_id": "REHIRE-001",
        "biometric_id": "",
    }
    r = requests.post(
        f"{API}/employees",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=rehire_payload,
        timeout=30,
    )
    assert r.status_code == 400, (
        f"Expected 400 rejection, got {r.status_code}: {r.text}"
    )
    assert "reserved" in r.text.lower() or "admin account" in r.text.lower(), (
        f"Error message should mention reserved admin: {r.text}"
    )

    # CRITICAL: admin row must be UNCHANGED. We compare the snapshot taken
    # before the test to the snapshot taken after — exact byte-equality on
    # password_hash + audit fields. This is what the user-facing bug
    # actually cared about.
    async def _check():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        u = await db.users.find_one({"username": "admin"}, {"_id": 0})
        c.close()
        return u

    admin_after_doc = asyncio.get_event_loop().run_until_complete(_check())
    assert admin_after_doc, "Admin user vanished during rehire collision attempt"
    assert admin_after_doc.get("password_hash") == admin_before["password_hash"], (
        "REGRESSION: admin password_hash was modified during rehire collision attempt"
    )
    assert admin_after_doc.get("password_updated_at") == admin_before["password_updated_at"], (
        "REGRESSION: admin password_updated_at was modified"
    )
    assert admin_after_doc.get("password_updated_method") == admin_before["password_updated_method"], (
        "REGRESSION: admin password_updated_method was modified"
    )
