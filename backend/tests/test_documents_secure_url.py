"""Tests for the secure document URL endpoint.

The endpoint generates signed Cloudinary Admin-API download URLs that bypass
the default PDF/ZIP delivery restriction returning 401 on raw asset URLs.
"""
import os
import sys
import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"


def _login(username: str, password: str):
    r = httpx.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()["token"]


def _find_document_with_url():
    """Returns (employee_id, document_type, expected_ext) for a real doc."""
    from pymongo import MongoClient
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)
    db = client[os.environ["DB_NAME"]]
    doc = db.onboarding_documents.find_one(
        {"file_url": {"$exists": True, "$ne": None}, "file_public_id": {"$exists": True, "$ne": None}},
        {"_id": 0, "employee_id": 1, "document_type": 1, "file_url": 1},
    )
    client.close()
    assert doc, "No onboarding documents with file_url in DB"
    ext = doc["file_url"].rsplit(".", 1)[-1].lower().split("?")[0]
    return doc["employee_id"], doc["document_type"], ext


HTTP_TIMEOUT = 30.0


def _get(path, token=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.get(f"{API}{path}", params=params, headers=headers, timeout=HTTP_TIMEOUT)


@pytest.fixture(scope="module")
def admin_token():
    t = _login("sysadmin", "pass123")
    assert t, "Failed to login as sysadmin"
    return t


@pytest.fixture(scope="module")
def employee_token():
    """Non-owner employee token used to verify 403."""
    t = _login("user", "pass123")
    assert t, "Failed to login as employee 'user'"
    return t


@pytest.fixture(scope="module")
def doc_target():
    return _find_document_with_url()


def test_admin_can_get_signed_url(admin_token, doc_target):
    emp_id, doc_type, ext = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed"] is True
    assert body["expires_in"] == 900
    assert "api.cloudinary.com" in body["url"]
    assert "signature=" in body["url"]
    assert "expires_at=" in body["url"]
    assert f"format={ext}" in body["url"]


def test_signed_url_returns_200_from_cloudinary(admin_token, doc_target):
    """The original 401 PDF problem is fixed when fetching the signed URL."""
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type})
    signed_url = r.json()["url"]
    head = httpx.head(signed_url, timeout=HTTP_TIMEOUT, follow_redirects=True)
    assert head.status_code == 200, f"Signed URL did not return 200: {head.status_code}"


def test_attachment_disposition_flag(admin_token, doc_target):
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type, "disposition": "attachment"})
    assert r.status_code == 200
    assert "attachment=1" in r.json()["url"]


def test_non_owner_employee_is_blocked(employee_token, doc_target):
    """An employee CANNOT view another employee's document — 403."""
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url", token=employee_token,
            params={"employee_id": emp_id, "document_type": doc_type})
    assert r.status_code == 403, r.text


def test_unauthenticated_is_rejected(doc_target):
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url",
             params={"employee_id": emp_id, "document_type": doc_type})
    assert r.status_code in (401, 403)


def test_bad_token_is_rejected_with_401(doc_target):
    """REGRESSION GUARD: the previous P0 bug had the frontend reading the
    wrong localStorage key, sending `Authorization: Bearer null`. Confirm
    the backend still rejects malformed Bearer tokens — so any frontend
    regression that re-introduces the wrong-key bug fails fast at the
    network layer (status visible in DevTools) instead of silently
    cascading into a raw-URL fallback that triggers Cloudinary 401."""
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url", token="null",
             params={"employee_id": emp_id, "document_type": doc_type})
    assert r.status_code in (401, 403), r.text
    r2 = _get("/documents/secure-url", token="this-is-not-a-jwt",
              params={"employee_id": emp_id, "document_type": doc_type})
    assert r2.status_code in (401, 403), r2.text


def test_missing_doc_returns_404(admin_token):
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": "00000000-0000-0000-0000-000000000000", "document_type": "aadhaar_card"})
    assert r.status_code == 404


def test_invalid_disposition_is_rejected(admin_token, doc_target):
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type, "disposition": "evil"})
    assert r.status_code == 422
