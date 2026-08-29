"""Payslip 6-digit authorization layer — comprehensive tests.

Covers:
    * Admin BEFORE verification → 403 payslip_auth_required, no salary fields
    * verify: wrong / bad-length / correct-code semantics
    * Admin AFTER verification → 200 on all admin payslip endpoints
    * Session scope: fresh login after logout re-locks
    * Brute-force: 5 wrong codes → 429 lock even on correct code
    * Successful verification resets failed_attempts to 0
    * Employee access is unaffected & security endpoints deny employees
    * No plaintext leakage in status/settings/audit/mongo
    * Regression: /app/backend/tests/test_rbac_isolation.py &
      test_rbac_body_leaks.py still green (executed separately)

NEVER calls POST /api/payslip-security/regenerate.
"""
import json
import os
import time
import uuid

import pytest
import requests


def _load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                os.environ.setdefault(k.strip(), v)
    except FileNotFoundError:
        pass


_load_env("/app/frontend/.env")
_load_env("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = BASE_URL + "/api"
UA = {"User-Agent": "Mozilla/5.0 (payslip-auth-tests)"}
INITIAL_CODE = "082026"

ADMIN_PAYSLIP_PATHS = [
    ("GET", "/payslips/templates", None),
    ("GET", "/payslips/assignments", None),
    ("GET", "/payslips/generated?month=2026-07", None),
    ("GET", "/payslips/adjustments/summary?month=2026-07", None),
]

MONEY_HINTS = {"basic", "hra", "gross", "net", "salary", "ctc", "allowance", "deduction", "pf", "esi"}


def _req(session, method, path, token=None, body=None, retries=3):
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for i in range(retries):
        r = session.request(method, API + path, headers=headers, json=body, timeout=90)
        if r.status_code in (502, 503, 504):
            time.sleep(3)
            continue
        return r
    return r


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    return s


def _login(session, username, password):
    r = _req(session, "POST", "/auth/login", body={"username": username, "password": password})
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token(session):
    return _login(session, "admin", "HrAdmin786$")


@pytest.fixture(scope="module")
def emp_token(session):
    return _login(session, "madhan.s", "Vigil@123")


def _clear_attempts_via_mongo():
    """Directly wipe payslip_auth_attempts (owner mandate: keep module usable)."""
    import subprocess
    subprocess.run(
        [
            "python", "-c",
            "import asyncio, os; from motor.motor_asyncio import AsyncIOMotorClient; "
            "c=AsyncIOMotorClient(os.environ['MONGO_URL']); "
            "db=c[os.environ['DB_NAME']]; "
            "asyncio.get_event_loop().run_until_complete("
            "db.payslip_auth_attempts.delete_many({}))",
        ],
        cwd="/app/backend", env={**os.environ},
        capture_output=True, text=True, timeout=30,
    )


@pytest.fixture(autouse=True, scope="module")
def _preclear_attempts():
    _clear_attempts_via_mongo()
    yield
    _clear_attempts_via_mongo()


# ---------- helpers ---------------------------------------------------------
def _has_money_leak(body_text):
    lower = body_text.lower()
    return any(k in lower for k in MONEY_HINTS)


def _clear_admin_lock(session, admin_token):
    # Backend has no admin-facing endpoint to clear lock. We rely on a successful
    # verification which resets failed_count to 0. However when locked, correct
    # code also returns 429. Only way to clear is via mongo. The problem
    # statement mandates clearing the mongo doc after brute-force test.
    pass


# ============================================================================
# 1. Admin BEFORE verification
# ============================================================================
class Test1_AdminBeforeVerification:
    def test_all_admin_payslip_endpoints_return_403_and_no_salary(self, session, admin_token):
        # Fresh login is guaranteed by module-scope admin_token (session invalidated
        # after prior tests if any). To be robust, log in a fresh session here.
        fresh = _login(session, "admin", "HrAdmin786$")
        for method, path, _ in ADMIN_PAYSLIP_PATHS:
            r = _req(session, method, path, fresh)
            assert r.status_code == 403, f"{method} {path} expected 403 got {r.status_code}: {r.text[:200]}"
            body = r.text
            data = r.json()
            assert data.get("error") == "payslip_auth_required", f"{path}: {data}"
            assert not _has_money_leak(body), f"salary leak in {path}: {body[:200]}"

    def test_post_calculate_and_generate_before_verify(self, session, admin_token):
        fresh = _login(session, "admin", "HrAdmin786$")
        for method, path, body in [
            ("POST", "/payslips/calculate", {"month": "2026-07"}),
            ("POST", "/payslips/generate", {"month": "2026-07"}),
        ]:
            r = _req(session, method, path, fresh, body=body)
            assert r.status_code == 403, f"{path} expected 403 got {r.status_code}"
            assert r.json().get("error") == "payslip_auth_required"
            assert not _has_money_leak(r.text)


# ============================================================================
# 2. Verify flow
# ============================================================================
class Test2_VerifyFlow:
    def test_wrong_code_returns_401(self, session, admin_token):
        # Use a fresh login so previous test-lock state doesn't matter.
        tok = _login(session, "admin", "HrAdmin786$")
        r = _req(session, "POST", "/payslip-security/verify", tok, {"code": "111111"})
        assert r.status_code == 401, (r.status_code, r.text)
        detail = r.json().get("detail", "")
        assert "invalid" in detail.lower()
        assert "close" not in detail.lower() and "match" not in detail.lower()

    def test_bad_length_returns_400(self, session, admin_token):
        tok = _login(session, "admin", "HrAdmin786$")
        r = _req(session, "POST", "/payslip-security/verify", tok, {"code": "1234"})
        assert r.status_code == 400, (r.status_code, r.text)

    def test_correct_code_verifies_and_unlocks(self, session, admin_token):
        tok = _login(session, "admin", "HrAdmin786$")
        r = _req(session, "POST", "/payslip-security/verify", tok, {"code": INITIAL_CODE})
        assert r.status_code == 200, (r.status_code, r.text)
        # Now all admin payslip endpoints must return 200
        for method, path, _ in ADMIN_PAYSLIP_PATHS:
            r = _req(session, method, path, tok)
            assert r.status_code == 200, f"{method} {path} expected 200 got {r.status_code}: {r.text[:200]}"


# ============================================================================
# 3. Session scope
# ============================================================================
class Test3_SessionScope:
    def test_fresh_login_relocks(self, session):
        tok = _login(session, "admin", "HrAdmin786$")
        r = _req(session, "POST", "/payslip-security/verify", tok, {"code": INITIAL_CODE})
        assert r.status_code == 200
        # Same session works
        r = _req(session, "GET", "/payslip-security/status", tok)
        assert r.json().get("verified") is True

        # Fresh login → new session_id → verified must be false
        tok2 = _login(session, "admin", "HrAdmin786$")
        r = _req(session, "GET", "/payslip-security/status", tok2)
        assert r.status_code == 200
        assert r.json().get("verified") is False, r.json()
        # And payslip endpoints must 403 again for new session
        r = _req(session, "GET", "/payslips/templates", tok2)
        assert r.status_code == 403


# ============================================================================
# 4. Brute force lock + reset
# ============================================================================
class Test4_BruteForce:
    def test_lockout_and_correct_code_still_denied_while_locked(self, session):
        tok = _login(session, "admin", "HrAdmin786$")
        # Force 5 wrong attempts
        codes = ["100001", "100002", "100003", "100004", "100005"]
        last_status = None
        for i, c in enumerate(codes):
            r = _req(session, "POST", "/payslip-security/verify", tok, {"code": c})
            last_status = r.status_code
            if i < 4:
                assert last_status == 401, f"attempt {i+1}: {last_status} {r.text[:120]}"
            else:
                assert last_status == 429, f"attempt 5 must return 429, got {last_status}: {r.text[:120]}"

        # Status shows locked_until + failed_attempts=5
        r = _req(session, "GET", "/payslip-security/status", tok)
        s = r.json()
        assert s.get("failed_attempts") == 5, s
        assert s.get("locked_until"), s

        # Correct code while locked -> still 429
        r = _req(session, "POST", "/payslip-security/verify", tok, {"code": INITIAL_CODE})
        assert r.status_code == 429, (r.status_code, r.text)

        # Clear lock via direct mongo mutation (mandated by review request)
        import subprocess
        result = subprocess.run(
            [
                "python", "-c",
                "import asyncio, os; from motor.motor_asyncio import AsyncIOMotorClient; "
                "c=AsyncIOMotorClient(os.environ['MONGO_URL']); "
                "db=c[os.environ['DB_NAME']]; "
                "asyncio.get_event_loop().run_until_complete("
                "db.payslip_auth_attempts.delete_many({}))",
            ],
            cwd="/app/backend",
            env={**os.environ}, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr

        # Successful verification resets failed_attempts to 0
        r = _req(session, "POST", "/payslip-security/verify", tok, {"code": INITIAL_CODE})
        assert r.status_code == 200, (r.status_code, r.text)
        r = _req(session, "GET", "/payslip-security/status", tok)
        assert r.json().get("failed_attempts") == 0
        assert not r.json().get("locked_until")


# ============================================================================
# 5. Employee unaffected
# ============================================================================
class Test5_EmployeeUnaffected:
    def test_employee_my_payslips_works(self, session, emp_token):
        r = _req(session, "GET", "/payslips/my", emp_token)
        # The payslip AUTH-CODE gate must never touch employees. If the admin
        # has hidden the payslips module from this employee via Module
        # Visibility, 403 module_unavailable is the expected answer instead.
        if r.status_code == 403:
            assert r.json().get("error") == "module_unavailable", r.text[:200]
            return
        assert r.status_code == 200, (r.status_code, r.text[:200])

    def test_employee_denied_admin_payslip_endpoints(self, session, emp_token):
        for method, path, _ in ADMIN_PAYSLIP_PATHS:
            r = _req(session, method, path, emp_token)
            # Employee is blocked by RBAC (not the new payslip gate).
            assert r.status_code == 403, f"{path}: {r.status_code}"
            assert not _has_money_leak(r.text)

    def test_employee_denied_payslip_security_endpoints(self, session, emp_token):
        for path in ["/payslip-security/status", "/payslip-security/settings"]:
            r = _req(session, "GET", path, emp_token)
            assert r.status_code == 403, f"{path}: {r.status_code}"
        # And even knowing the code grants no access to admin endpoints
        r = _req(session, "POST", "/payslip-security/verify", emp_token, {"code": INITIAL_CODE})
        assert r.status_code == 403


# ============================================================================
# 6. No plaintext leakage
# ============================================================================
class Test6_NoPlaintextLeak:
    def test_status_and_settings_never_include_code(self, session):
        tok = _login(session, "admin", "HrAdmin786$")
        for path in ["/payslip-security/status", "/payslip-security/settings"]:
            r = _req(session, "GET", path, tok)
            assert r.status_code == 200
            assert INITIAL_CODE not in r.text
            # Also no hash / salt in either response
            data = r.json()
            for k in ("auth_code_hash", "auth_code_salt"):
                assert k not in data, f"{path} leaks {k}: {data}"

    def test_mongo_settings_only_hash_and_salt(self):
        import subprocess
        result = subprocess.run(
            [
                "python", "-c",
                "import asyncio, os, json; from motor.motor_asyncio import AsyncIOMotorClient; "
                "c=AsyncIOMotorClient(os.environ['MONGO_URL']); "
                "db=c[os.environ['DB_NAME']]; "
                "doc=asyncio.get_event_loop().run_until_complete("
                "db.payslip_security_settings.find_one({'id':'payslip_auth'},{'_id':0})); "
                "print(json.dumps(doc, default=str))",
            ],
            cwd="/app/backend",
            env={**os.environ}, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        doc = json.loads(result.stdout.strip())
        assert INITIAL_CODE not in json.dumps(doc)
        assert "auth_code_hash" in doc and "auth_code_salt" in doc
        # Only expected keys
        allowed = {"id", "auth_code_salt", "auth_code_hash", "auth_code_version",
                   "last_regenerated_at", "last_regenerated_by", "last_regenerated_by_id",
                   "created_at", "updated_at"}
        extras = set(doc) - allowed
        assert not extras, f"unexpected fields in settings doc: {extras}"

    def test_audit_rows_have_no_code(self):
        import subprocess
        result = subprocess.run(
            [
                "python", "-c",
                "import asyncio, os, json; from motor.motor_asyncio import AsyncIOMotorClient; "
                "c=AsyncIOMotorClient(os.environ['MONGO_URL']); "
                "db=c[os.environ['DB_NAME']]; "
                "rows=asyncio.get_event_loop().run_until_complete("
                "db.payslip_security_audit.find({},{'_id':0}).sort('timestamp',-1).to_list(50)); "
                "print(json.dumps(rows, default=str))",
            ],
            cwd="/app/backend",
            env={**os.environ}, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        rows = json.loads(result.stdout.strip() or "[]")
        actions = {r["action"] for r in rows}
        for r in rows:
            assert INITIAL_CODE not in json.dumps(r)
            assert "user_id" in r and ("user_name" in r) and "timestamp" in r
        # Expected action names must have been recorded
        assert "payslip_auth_verified" in actions
        assert "payslip_auth_failed" in actions
        assert "payslip_auth_lockout" in actions
