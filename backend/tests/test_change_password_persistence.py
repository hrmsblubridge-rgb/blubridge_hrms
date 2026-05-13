"""Regression tests for the change-password flow + non-idempotent seed bug.

Bug fixed (CHANGELOG):
  The startup seed unconditionally reset admin.password_hash to hash("pass123"),
  silently wiping any password the admin had changed via the UI. After every
  backend restart, the old password came back. The fix splits role/name
  migration from password setting — password is only seeded when missing.

These tests run against the LIVE backend (http://localhost:8001) using the
existing admin seed credentials. They are idempotent: every test ends by
resetting the admin password back to `pass123`.
"""
import os
import time
import json
import requests
import pytest

API = "http://localhost:8001/api"
ADMIN_USER = "admin"
DEFAULT_PWD = "pass123"


def _login(username: str, password: str) -> str | None:
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=60)
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


def _ensure_admin_pwd(target: str = DEFAULT_PWD):
    """Best-effort: cycle the admin password back to a known target.

    Tries the target first (idempotent fast path), then every password the
    tests in this file are known to set. If none work, raises.
    """
    KNOWN_PASSWORDS = [
        DEFAULT_PWD, target,
        "newpass123", "SuperSecret#2026",
        "RegressionPwd!1",
        "First!1A", "Second!2B", "Third!3C",
        "RestartPersist!9",
    ]
    seen = set()
    for candidate in KNOWN_PASSWORDS:
        if candidate in seen:
            continue
        seen.add(candidate)
        tok = _login(ADMIN_USER, candidate)
        if tok:
            if candidate != target:
                _change_password(tok, candidate, target)
            return
    raise RuntimeError("Cannot reset admin password — unknown credentials")


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    # Always restore default after each test so other tests / agents work.
    _ensure_admin_pwd(DEFAULT_PWD)


def test_change_password_happy_path():
    """Admin can log in, change password, then log in with the new one;
    the old password is rejected."""
    _ensure_admin_pwd(DEFAULT_PWD)
    tok = _login(ADMIN_USER, DEFAULT_PWD)
    assert tok, "Admin login with seed password must succeed"

    new = "RegressionPwd!1"
    r = _change_password(tok, DEFAULT_PWD, new)
    assert r.status_code == 200, r.text
    assert "successfully" in r.json().get("message", "").lower()

    # New password works
    assert _login(ADMIN_USER, new), "Login with new password must succeed"
    # Old password no longer works
    assert _login(ADMIN_USER, DEFAULT_PWD) is None, "Old password must be rejected"


def test_change_password_rejects_wrong_current():
    _ensure_admin_pwd(DEFAULT_PWD)
    tok = _login(ADMIN_USER, DEFAULT_PWD)
    r = _change_password(tok, "WRONG_CURRENT", "irrelevant")
    assert r.status_code == 400
    assert "incorrect" in r.text.lower()
    # Password unchanged
    assert _login(ADMIN_USER, DEFAULT_PWD), "Password must be unchanged on rejection"


def test_multiple_consecutive_password_changes():
    _ensure_admin_pwd(DEFAULT_PWD)
    sequence = [DEFAULT_PWD, "First!1A", "Second!2B", "Third!3C"]
    for cur, nxt in zip(sequence, sequence[1:]):
        tok = _login(ADMIN_USER, cur)
        assert tok, f"Login with {cur} must succeed"
        r = _change_password(tok, cur, nxt)
        assert r.status_code == 200, r.text
        # New works, old fails
        assert _login(ADMIN_USER, nxt)
        assert _login(ADMIN_USER, cur) is None


@pytest.mark.skipif(
    not os.environ.get("RUN_RESTART_TEST"),
    reason="Restart test only runs when RUN_RESTART_TEST=1 (requires supervisor)",
)
def test_password_persists_across_backend_restart():
    """The regression case: after change-password, restart backend, new
    password MUST still work (previously the seed wiped it)."""
    _ensure_admin_pwd(DEFAULT_PWD)
    tok = _login(ADMIN_USER, DEFAULT_PWD)
    new = "RestartPersist!9"
    r = _change_password(tok, DEFAULT_PWD, new)
    assert r.status_code == 200

    # Restart backend
    rc = os.system("sudo supervisorctl restart backend >/dev/null 2>&1")
    assert rc == 0
    # Wait for backend to come back
    for _ in range(20):
        try:
            requests.get(f"{API}/auth/login", timeout=3)
            break
        except Exception:
            time.sleep(1)
    time.sleep(4)

    assert _login(ADMIN_USER, new), "New password MUST persist across restart (regression: seed used to wipe it)"
    assert _login(ADMIN_USER, DEFAULT_PWD) is None, "Old seed password must NOT come back"
