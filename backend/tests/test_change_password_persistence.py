"""Regression tests for the change-password flow.

⚠️ HISTORICAL ROOT-CAUSE NOTE (2026-05-17 — FINAL ELIMINATION):
    This file PREVIOUSLY ran its cleanup fixtures against the REAL `admin`
    user (forcibly resetting its password back to `pass123` after every
    test via /api/auth/change-password). That single behaviour was the
    TRUE root cause of the long-running "admin password auto-reverts"
    bug — every time anyone (agent or developer) ran the backend test
    suite, the admin password silently snapped back to the seed default.
    All previous fixes (seed-side, rehire-side, firewall-side) were
    necessary but not sufficient because they couldn't see the in-process
    pytest hook that was the actual overwriter.

    This file has been rewritten to use a DEDICATED ephemeral test user
    (`__regression_admin_pwd__`) that is provisioned at test start and
    deleted at test end. The real `admin` account is NEVER touched.

Bug originally fixed (CHANGELOG):
  The startup seed unconditionally reset admin.password_hash to hash("pass123"),
  silently wiping any password the admin had changed via the UI. The seed
  was fixed long ago; the symptom kept returning because of THIS file.

These tests run against the LIVE backend (http://localhost:8001).
"""
import os
import time
import uuid
import hashlib
import requests
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import asyncio

load_dotenv("/app/backend/.env")
API = "http://localhost:8001/api"

# Dedicated, throwaway user. Never collides with real admin.
TEST_USERNAME = "__regression_admin_pwd__"
TEST_INITIAL_PWD = "Regression!Init#1"
TEST_USER_ID_PREFIX = "regression-pwd-"


def _login(username: str, password: str) -> str | None:
    r = requests.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=60,
    )
    if r.status_code != 200:
        return None
    return r.json().get("token")


def _change_password(token: str, current: str, new: str) -> requests.Response:
    return requests.post(
        f"{API}/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": current, "new_password": new},
        timeout=60,
    )


async def _provision_test_user():
    """Insert an HR-role test user directly into Mongo so we don't depend
    on any admin endpoint to create it. The user is fully ephemeral."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    await db.users.delete_many({"username": TEST_USERNAME})
    uid = TEST_USER_ID_PREFIX + uuid.uuid4().hex[:8]
    await db.users.insert_one({
        "id": uid,
        "username": TEST_USERNAME,
        "email": f"{TEST_USERNAME}@regression.local",
        "password_hash": hashlib.sha256(TEST_INITIAL_PWD.encode()).hexdigest(),
        "name": "Regression Test HR (ephemeral)",
        "role": "hr",
        "is_active": True,
        "is_first_login": False,
        "onboarding_status": "completed",
        "created_at": "2026-01-01T00:00:00+05:30",
    })
    client.close()
    return uid


async def _teardown_test_user():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    await db.users.delete_many({"username": TEST_USERNAME})
    client.close()


@pytest.fixture
def ephemeral_admin():
    """Provision a throwaway HR-role user, yield (username, password),
    then delete it. The real admin account is NEVER touched."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(_provision_test_user())
    try:
        yield TEST_USERNAME, TEST_INITIAL_PWD
    finally:
        loop.run_until_complete(_teardown_test_user())


def test_change_password_happy_path(ephemeral_admin):
    """User can log in, change password, then log in with the new one;
    the old password is rejected."""
    username, initial = ephemeral_admin
    tok = _login(username, initial)
    assert tok, "Login with initial password must succeed"

    new = "RegressionPwd!1"
    r = _change_password(tok, initial, new)
    assert r.status_code == 200, r.text
    assert "successfully" in r.json().get("message", "").lower()

    assert _login(username, new), "Login with new password must succeed"
    assert _login(username, initial) is None, "Old password must be rejected"


def test_change_password_rejects_wrong_current(ephemeral_admin):
    username, initial = ephemeral_admin
    tok = _login(username, initial)
    r = _change_password(tok, "WRONG_CURRENT", "irrelevant")
    assert r.status_code == 400
    assert "incorrect" in r.text.lower()
    # Password unchanged
    assert _login(username, initial), "Password must be unchanged on rejection"


def test_multiple_consecutive_password_changes(ephemeral_admin):
    username, initial = ephemeral_admin
    sequence = [initial, "First!1A", "Second!2B", "Third!3C"]
    for cur, nxt in zip(sequence, sequence[1:]):
        tok = _login(username, cur)
        assert tok, f"Login with {cur} must succeed"
        r = _change_password(tok, cur, nxt)
        assert r.status_code == 200, r.text
        assert _login(username, nxt)
        assert _login(username, cur) is None


@pytest.mark.skipif(
    not os.environ.get("RUN_RESTART_TEST"),
    reason="Restart test only runs when RUN_RESTART_TEST=1 (requires supervisor)",
)
def test_password_persists_across_backend_restart(ephemeral_admin):
    """The regression case: after change-password, restart backend, new
    password MUST still work (previously the seed wiped it)."""
    username, initial = ephemeral_admin
    tok = _login(username, initial)
    new = "RestartPersist!9"
    r = _change_password(tok, initial, new)
    assert r.status_code == 200

    # Restart backend
    rc = os.system("sudo supervisorctl restart backend >/dev/null 2>&1")
    assert rc == 0
    time.sleep(25)
    for _ in range(30):
        try:
            r = requests.post(
                f"{API}/auth/login",
                json={"username": "__probe__", "password": "__probe__"},
                timeout=10,
            )
            if r.status_code in (200, 401, 400, 422):
                break
        except Exception:
            time.sleep(2)
    time.sleep(3)

    assert _login(username, new), (
        "New password MUST persist across restart (regression: seed used to wipe it)"
    )
    assert _login(username, initial) is None, (
        "Old initial password must NOT come back"
    )
