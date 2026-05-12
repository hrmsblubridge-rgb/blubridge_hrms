"""Tests for the My Documents (Employee) onboarding upload/re-upload flow.

Covers iteration 44:
  - /api/onboarding/my-status returns the 9 docs with current state
  - /api/onboarding/upload-document blocks re-upload of a verified doc (400)
  - Re-uploading a rejected doc succeeds (200), clears rejection_reason, status flips to uploaded
  - Uploading a not_uploaded doc succeeds (200) and status -> uploaded
  - HR (admin/sysadmin/offadmin) receive an in-app notification per upload
  - /api/dashboard/stats warm response time < 2s (perf regression guard)
"""

import os
import time
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://leave-code-mapper.preview.emergentagent.com").rstrip("/")

KASPER_EMPLOYEE_ID = "278f8421-12dc-495d-b3fe-c657ebe17ee0"


def _login(session: requests.Session, username: str, password: str) -> str:
    r = session.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=45)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def kasper_token():
    s = requests.Session()
    return _login(s, "kasper", "pass123")


@pytest.fixture(scope="module")
def admin_token():
    s = requests.Session()
    return _login(s, "admin", "pass123")


@pytest.fixture(scope="module")
def kasper_client(kasper_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {kasper_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


# ----- /api/onboarding/my-status -----
class TestMyStatus:
    def test_my_status_returns_nine_docs(self, kasper_client):
        r = kasper_client.get(f"{BASE_URL}/api/onboarding/my-status", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "documents" in data
        assert "required_documents" in data
        assert isinstance(data["documents"], list)
        types = {d["document_type"] for d in data["documents"]}
        expected = {"aadhaar_card", "pan_card", "passport", "voter_id", "education",
                    "experience", "offer_letter", "relieving_letter", "photo"}
        assert expected.issubset(types), f"Missing doc types: {expected - types}"

    def test_my_status_reflects_current_state(self, kasper_client):
        r = kasper_client.get(f"{BASE_URL}/api/onboarding/my-status", timeout=15)
        docs = {d["document_type"]: d for d in r.json()["documents"]}
        assert docs["aadhaar_card"]["status"] == "verified"
        assert docs["pan_card"]["status"] == "rejected"
        assert docs["pan_card"].get("rejection_reason"), "rejected doc must have a reason"


# ----- /api/onboarding/upload-document -----
class TestUploadDocument:
    def _payload(self, doc_type: str):
        return {
            "document_type": doc_type,
            "file_url": f"https://res.cloudinary.com/test/image/upload/v1/test_{doc_type}.jpg",
            "file_public_id": f"test_{doc_type}_{int(time.time())}",
            "file_name": f"{doc_type}.jpg",
        }

    def test_verified_doc_cannot_be_reuploaded(self, kasper_client):
        r = kasper_client.post(
            f"{BASE_URL}/api/onboarding/upload-document",
            json=self._payload("aadhaar_card"),
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 for verified doc, got {r.status_code}: {r.text}"
        body = r.json()
        msg = (body.get("detail") or body.get("message") or "").lower()
        assert "approved" in msg or "verified" in msg, f"detail should mention approved/verified: {body}"

    def test_rejected_doc_can_be_reuploaded(self, kasper_client):
        # snapshot pre
        before = kasper_client.get(f"{BASE_URL}/api/onboarding/my-status").json()
        pan_before = next(d for d in before["documents"] if d["document_type"] == "pan_card")
        assert pan_before["status"] == "rejected", "precondition: pan_card must be rejected"

        r = kasper_client.post(
            f"{BASE_URL}/api/onboarding/upload-document",
            json=self._payload("pan_card"),
            timeout=15,
        )
        assert r.status_code == 200, r.text

        # verify persistence via GET
        after = kasper_client.get(f"{BASE_URL}/api/onboarding/my-status").json()
        pan_after = next(d for d in after["documents"] if d["document_type"] == "pan_card")
        assert pan_after["status"] == "uploaded"
        assert pan_after.get("rejection_reason") in (None, ""), "rejection_reason must be cleared"
        assert pan_after.get("file_name") == "pan_card.jpg"

    def test_not_uploaded_doc_can_be_uploaded(self, kasper_client):
        r = kasper_client.post(
            f"{BASE_URL}/api/onboarding/upload-document",
            json=self._payload("photo"),
            timeout=15,
        )
        assert r.status_code == 200, r.text

        after = kasper_client.get(f"{BASE_URL}/api/onboarding/my-status").json()
        photo_after = next(d for d in after["documents"] if d["document_type"] == "photo")
        assert photo_after["status"] == "uploaded"
        assert photo_after.get("file_name") == "photo.jpg"


# ----- HR notification fan-out -----
class TestHRNotifications:
    def test_admin_received_notification_after_kasper_upload(self, admin_client, kasper_client):
        # Trigger a fresh upload to ensure a new notification row exists
        kasper_client.post(
            f"{BASE_URL}/api/onboarding/upload-document",
            json={
                "document_type": "voter_id",
                "file_url": "https://res.cloudinary.com/test/image/upload/v1/voter.jpg",
                "file_public_id": f"voter_{int(time.time())}",
                "file_name": "voter_id.jpg",
            },
            timeout=15,
        )
        time.sleep(1.0)
        r = admin_client.get(f"{BASE_URL}/api/notifications?limit=20", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # API may return list or {notifications:[...]}
        items = data if isinstance(data, list) else data.get("notifications") or data.get("items") or []
        assert items, "admin should have notifications"
        recent_titles = " | ".join((n.get("title") or "") for n in items[:20])
        assert ("Document uploaded" in recent_titles) or ("Document re-uploaded" in recent_titles), \
            f"no doc-upload notification found in latest 20: {recent_titles!r}"
        # And one should link to /verification
        links = [n.get("link") for n in items[:20]]
        assert "/verification" in links


# ----- Dashboard perf regression guard -----
class TestDashboardPerf:
    def test_dashboard_stats_warm_under_2s(self, admin_client):
        # warm-up
        admin_client.get(f"{BASE_URL}/api/dashboard/stats", timeout=20)
        start = time.perf_counter()
        r = admin_client.get(f"{BASE_URL}/api/dashboard/stats", timeout=20)
        elapsed = time.perf_counter() - start
        assert r.status_code == 200, r.text
        assert elapsed < 2.0, f"dashboard/stats warm response took {elapsed:.2f}s (>=2s)"
        data = r.json()
        # Basic shape check - tile counts must exist
        assert isinstance(data, dict)
        # At least one of these common keys should be present
        keys = set(data.keys())
        assert keys, "dashboard/stats returned empty body"
