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
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=30000, connectTimeoutMS=30000)
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
    """Inline disposition now returns our backend streaming proxy URL.

    The previous behaviour (Cloudinary signed download URL) caused the new tab
    to render blank for PDFs because Cloudinary's `/download` endpoint forces
    `Content-Disposition: attachment`. We now route inline views through
    `/api/documents/stream` which re-streams with `Content-Disposition: inline`.
    """
    emp_id, doc_type, _ext = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed"] is True
    assert body["proxied"] is True
    assert body["expires_in"] == 600  # stream token TTL
    assert "/api/documents/stream?token=" in body["url"]


def test_signed_url_returns_200_from_cloudinary(admin_token, doc_target):
    """The streaming proxy must serve the document inline (HTTP 200,
    Content-Type: application/pdf, Content-Disposition: inline)."""
    emp_id, doc_type, ext = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type})
    stream_url = r.json()["url"]
    head = httpx.get(stream_url, timeout=HTTP_TIMEOUT, follow_redirects=True)
    assert head.status_code == 200, f"Stream URL did not return 200: {head.status_code}"
    if ext == "pdf":
        assert head.headers.get("content-type", "").startswith("application/pdf")
        # Magic bytes prove the bytes actually arrived (the original bug
        # symptom was a blank tab → empty body).
        assert head.content[:4] == b"%PDF", "Streamed body is not a valid PDF"
    assert "inline" in head.headers.get("content-disposition", "").lower()


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


# --- Streaming proxy guards -------------------------------------------------

def test_stream_rejects_bad_token():
    """Forged or malformed tokens MUST be rejected with 401, never silently
    serve someone else's document."""
    r = httpx.get(f"{API}/documents/stream", params={"token": "not.a.jwt.token.value"}, timeout=HTTP_TIMEOUT)
    assert r.status_code == 401, r.text


def test_stream_rejects_session_token_replay(admin_token, doc_target):
    """A regular session JWT (different `aud`) must NOT be accepted by the
    stream endpoint — audience scoping prevents token replay."""
    r = httpx.get(f"{API}/documents/stream", params={"token": admin_token}, timeout=HTTP_TIMEOUT)
    assert r.status_code == 401, r.text


def test_attachment_path_still_uses_cloudinary(admin_token, doc_target):
    """Download path is intentionally untouched — still returns a Cloudinary
    signed URL with `attachment=1` (preserves the working download behaviour)."""
    emp_id, doc_type, _ = doc_target
    r = _get("/documents/secure-url", token=admin_token,
            params={"employee_id": emp_id, "document_type": doc_type, "disposition": "attachment"})
    body = r.json()
    assert "api.cloudinary.com" in body["url"]
    assert "attachment=1" in body["url"]
