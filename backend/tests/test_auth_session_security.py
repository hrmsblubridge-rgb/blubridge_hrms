"""Regression: JWT session security (HR security report 2026-07).

- Access tokens are short-lived (<=10 min), carry token_type/session_id/jti,
  and are NEVER extended by protected API calls (exp fixed at issuance).
- Refresh tokens rotate on every use; replaying a rotated token revokes the
  whole session (theft detection).
- Logout revokes the session server-side: old access AND refresh tokens die.
Run: REACT_APP_BACKEND_URL=<url> pytest tests/test_auth_session_security.py
"""
import base64
import json
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN = {"username": "admin", "password": "HrAdmin786$"}

pytestmark = pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not set")


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], d["refresh_token"]


def _claims(token):
    p = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))


def test_access_token_shape_and_ttl():
    at, rt = _login()
    ac = _claims(at)
    assert ac["token_type"] == "access"
    for k in ("user_id", "role", "session_id", "jti", "iat", "exp"):
        assert k in ac
    assert ac["exp"] - ac["iat"] <= 10 * 60 + 1  # no sliding, short-lived
    rc = _claims(rt)
    assert rc["token_type"] == "refresh"
    assert rc["session_id"] == ac["session_id"]


def test_token_type_separation():
    at, rt = _login()
    # Refresh token must not access protected APIs
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {rt}"})
    assert r.status_code == 401
    # Access token must not be accepted by the refresh endpoint
    r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": at})
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_revokes_session():
    at, rt = _login()
    r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    at2, rt2 = r.json()["token"], r.json()["refresh_token"]
    assert rt2 != rt
    # Replay of the OLD refresh token → 401 + full session revocation
    r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401
    r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": rt2})
    assert r.status_code == 401
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {at2}"})
    assert r.status_code == 401


def test_logout_revokes_access_and_refresh():
    at, rt = _login()
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {at}"})
    assert r.status_code == 200
    r = requests.post(f"{BASE_URL}/api/auth/logout", headers={"Authorization": f"Bearer {at}"})
    assert r.status_code == 200
    # Old access token must be dead immediately
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {at}"})
    assert r.status_code == 401
    assert "revoked" in r.json().get("detail", "").lower()
    # Refresh must also be dead
    r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401
