"""Regression test for the HIDDEN admin-password-revert bug — REHIRE COLLISION.

Root cause (uncovered 2026-05-16):
  The "rehire deleted employee" code path at /api/employees POST derives the
  user's username from `email.split('@')[0]`. When a deleted employee with
  email like `admin@bug-test.com` was re-created, the path matched the REAL
  admin user (`username = "admin"`) and silently overwrote password_hash
  with a generated temp password. This was the ACTUAL revert vector that
  survived all previous "seed-side" fixes.

Fix applied:
  • New `PROTECTED_ADMIN_USERNAMES` / `PROTECTED_ADMIN_ROLES` set.
  • `_safe_user_update()` firewall strips password_hash writes against
    protected accounts (logs warning) — universal defense.
  • Rehire flow now explicitly REJECTS with HTTP 400 when colliding with a
    protected admin username, forcing HR to pick a different email.

This test verifies the firewall behavior end-to-end.
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


async def _cleanup():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    await db.employees.delete_many({"official_email": TEST_EMAIL})
    # Restore admin password to pass123 for next tests / agents
    await db.users.update_one(
        {"username": "admin"},
        {"$set": {"password_hash": hashlib.sha256("pass123".encode()).hexdigest()}},
    )


@pytest.fixture
def admin_setup():
    """Set admin password to a unique sentinel before each test;
    cleanup restores defaults after."""
    asyncio.get_event_loop().run_until_complete(_seed_deleted_employee())
    # Login + change password
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "pass123"}, timeout=60)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    sentinel = "REHIRE-FIREWALL-" + uuid.uuid4().hex[:8] + "!"
    r2 = requests.post(
        f"{API}/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "pass123", "new_password": sentinel},
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    # New token
    new_token = requests.post(f"{API}/auth/login", json={"username": "admin", "password": sentinel}, timeout=60).json()["token"]
    yield new_token, sentinel
    asyncio.get_event_loop().run_until_complete(_cleanup())


def test_rehire_with_admin_email_collision_is_rejected_and_password_preserved(admin_setup):
    """Attempting to rehire an employee whose derived username collides with
    a protected admin must return 400 AND must NEVER overwrite the real
    admin's password. This is the EXACT vector that caused the recurring
    admin-password-revert bug."""
    token, sentinel = admin_setup

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
    # The new firewall should reject — HTTP 400 with a clear message.
    assert r.status_code == 400, (
        f"Expected 400 rejection, got {r.status_code}: {r.text}"
    )
    assert "reserved" in r.text.lower() or "admin account" in r.text.lower(), (
        f"Error message should mention reserved admin: {r.text}"
    )

    # CRITICAL: admin's password MUST still be the sentinel — NOT reverted to
    # pass123 or any temp password.
    login_old = requests.post(
        f"{API}/auth/login", json={"username": "admin", "password": "pass123"}, timeout=60,
    )
    assert login_old.status_code != 200, "Old password came back — REGRESSION! Admin password was overwritten."

    login_new = requests.post(
        f"{API}/auth/login", json={"username": "admin", "password": sentinel}, timeout=60,
    )
    assert login_new.status_code == 200, (
        f"Sentinel password no longer works — REGRESSION! Admin password was overwritten. Body: {login_new.text}"
    )
