"""
Backend tests for password reset flows:
  A) Admin direct reset (auto-generated + manual)
  B) Employee self-service reset via /forgot-password + /reset-password
Does NOT change SHA-256 hashing scheme.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "pass123"
EMP_ID = "8f8dd31b-11ef-47d5-8a0c-ce03e81b839f"
EMP_USER = "Umesh.Gana"
EMP_ORIGINAL_PASS = "pass123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- A) ADMIN DIRECT RESET ----------
class TestAdminDirectReset:
    def test_1_auto_generate_reset(self, admin_headers):
        r = requests.post(
            f"{API}/admin/employees/{EMP_ID}/reset-credentials",
            headers=admin_headers,
            json={"auto_generate": True, "force_change_on_next_login": True},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("generated") is True
        assert isinstance(data.get("password"), str) and len(data["password"]) >= 8
        assert data.get("force_change_on_next_login") is True
        # stash for next test
        pytest.generated_password = data["password"]

    def test_2_login_with_new_auto_password(self):
        pwd = getattr(pytest, "generated_password", None)
        assert pwd, "Auto-generated password missing"
        r = requests.post(f"{API}/auth/login", json={"username": EMP_USER, "password": pwd}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert ("token" in body) or ("access_token" in body), f"login body missing token: {body}"

    def test_3_old_password_fails(self):
        r = requests.post(f"{API}/auth/login", json={"username": EMP_USER, "password": EMP_ORIGINAL_PASS}, timeout=30)
        assert r.status_code in (400, 401), f"Old password should not work, got {r.status_code}"

    def test_4_manual_reset_does_not_echo_password(self, admin_headers):
        new_pw = "NewPass123"
        r = requests.post(
            f"{API}/admin/employees/{EMP_ID}/reset-credentials",
            headers=admin_headers,
            json={"auto_generate": False, "password": new_pw, "confirm_password": new_pw, "force_change_on_next_login": False},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("generated") is False
        assert "password" not in data or data.get("password") in (None, "")

    def test_5_login_with_manual_password(self):
        r = requests.post(f"{API}/auth/login", json={"username": EMP_USER, "password": "NewPass123"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert ("token" in body) or ("access_token" in body)

    def test_6_reject_weak_short_password(self, admin_headers):
        r = requests.post(
            f"{API}/admin/employees/{EMP_ID}/reset-credentials",
            headers=admin_headers,
            json={"auto_generate": False, "password": "abc1", "confirm_password": "abc1"},
            timeout=30,
        )
        assert r.status_code == 400, r.text

    def test_7_reject_no_digit_password(self, admin_headers):
        r = requests.post(
            f"{API}/admin/employees/{EMP_ID}/reset-credentials",
            headers=admin_headers,
            json={"auto_generate": False, "password": "abcdefghij", "confirm_password": "abcdefghij"},
            timeout=30,
        )
        assert r.status_code == 400, r.text

    def test_8_reject_mismatched_confirm(self, admin_headers):
        r = requests.post(
            f"{API}/admin/employees/{EMP_ID}/reset-credentials",
            headers=admin_headers,
            json={"auto_generate": False, "password": "GoodPass123", "confirm_password": "OtherPass123"},
            timeout=30,
        )
        assert r.status_code == 400, r.text


# ---------- B) SELF-SERVICE RESET ----------
class TestSelfServiceReset:
    def test_1_forgot_password_unknown(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"identifier": "no_such_user_xyz_999"}, timeout=30)
        assert r.status_code == 404, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "user not found" in detail

    def test_2_forgot_password_valid_username(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"identifier": EMP_USER}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        sent = data.get("sent_to", "")
        assert "@" in sent and "*" in sent, f"sent_to should be masked, got {sent}"

    def test_3_validate_invalid_token(self):
        r = requests.get(f"{API}/auth/reset-password/validate", params={"token": "invalid_token_xyz"}, timeout=30)
        assert r.status_code == 400, r.text

    def test_4_token_flow_from_db(self, admin_headers):
        """Use Mongo directly to fetch a freshly-issued reset token, then
        validate + consume it, then ensure reuse is blocked + login works."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        assert mongo_url and db_name

        # Request fresh token
        r = requests.post(f"{API}/auth/forgot-password", json={"identifier": EMP_USER}, timeout=30)
        assert r.status_code == 200

        async def _fetch_latest_token():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            doc = await db.password_reset_tokens.find(
                {"username": EMP_USER, "used": {"$ne": True}},
                {"_id": 0},
            ).sort("created_at", -1).to_list(length=1)
            client.close()
            return doc[0] if doc else None

        doc = asyncio.run(_fetch_latest_token())
        assert doc, "No reset token row found"
        token = doc.get("token")
        assert token, "Token missing"

        # Validate
        r = requests.get(f"{API}/auth/reset-password/validate", params={"token": token}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("username") == EMP_USER

        # Use (one-time)
        new_pw = "SelfReset123"
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": token, "new_password": new_pw, "confirm_password": new_pw},
            timeout=30,
        )
        assert r.status_code == 200, r.text

        # Login with new password works
        r = requests.post(f"{API}/auth/login", json={"username": EMP_USER, "password": new_pw}, timeout=30)
        assert r.status_code == 200, r.text

        # Reuse of token fails
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": token, "new_password": new_pw, "confirm_password": new_pw},
            timeout=30,
        )
        assert r.status_code == 400, f"Token reuse should be blocked, got {r.status_code}"

        # Weak password rejected
        r2 = requests.post(f"{API}/auth/forgot-password", json={"identifier": EMP_USER}, timeout=30)
        assert r2.status_code == 200
        doc2 = asyncio.run(_fetch_latest_token())
        tok2 = doc2.get("token")
        rw = requests.post(
            f"{API}/auth/reset-password",
            json={"token": tok2, "new_password": "abc", "confirm_password": "abc"},
            timeout=30,
        )
        assert rw.status_code == 400


# ---------- RESTORE original password for next runs ----------
def test_zzz_restore_original_password(admin_headers=None):
    """Restore Umesh.Gana password to 'pass123' (7 chars) via direct Mongo update
    because the admin reset endpoint rejects passwords shorter than 8 chars."""
    import asyncio, hashlib
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    assert mongo_url and db_name, "MONGO_URL / DB_NAME missing"

    async def _restore():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        pwd_hash = hashlib.sha256(EMP_ORIGINAL_PASS.encode()).hexdigest()
        res = await db.users.update_one(
            {"username": EMP_USER},
            {"$set": {"password_hash": pwd_hash, "must_change_password": False}},
        )
        client.close()
        return res.modified_count

    modified = asyncio.run(_restore())
    r2 = requests.post(f"{API}/auth/login", json={"username": EMP_USER, "password": EMP_ORIGINAL_PASS}, timeout=30)
    assert r2.status_code == 200, f"Could not restore original password (modified={modified}): {r2.text}"
