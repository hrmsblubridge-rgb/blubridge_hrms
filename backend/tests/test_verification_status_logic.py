"""Regression tests for the Verification (onboarding) status-derivation fix.

Bug: employees with ZERO uploaded documents were stored/shown as "Approved"
(historically set by the now-expired skip-onboarding bypass window). Status must
be derived purely from `onboarding_documents`:

  • no document activity        -> not_started
  • any REQUIRED doc rejected   -> rejected
  • all REQUIRED docs verified  -> approved
  • otherwise (uploaded/mixed)  -> under_review ("Pending")
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import derive_onboarding_status  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://blank-tab-debug.preview.emergentagent.com"
).rstrip("/")
ADMIN = ("admin", "HrAdmin786$")

REQ = "aadhaar_card", "pan_card", "education"


def _all(status):
    return [{"document_type": t, "status": status} for t in REQ]


# ---------------------------------------------------------------- pure logic
def test_no_documents_is_not_started():
    assert derive_onboarding_status([]) == "not_started"
    assert derive_onboarding_status(None) == "not_started"


def test_all_not_uploaded_is_not_started():
    assert derive_onboarding_status(_all("not_uploaded")) == "not_started"


def test_all_verified_is_approved():
    assert derive_onboarding_status(_all("verified")) == "approved"


def test_any_required_rejected_is_rejected():
    docs = [
        {"document_type": "aadhaar_card", "status": "verified"},
        {"document_type": "pan_card", "status": "rejected"},
        {"document_type": "education", "status": "verified"},
    ]
    assert derive_onboarding_status(docs) == "rejected"


def test_uploaded_but_unreviewed_is_under_review():
    assert derive_onboarding_status(_all("uploaded")) == "under_review"


def test_mixed_verified_and_uploaded_is_under_review():
    docs = [
        {"document_type": "aadhaar_card", "status": "verified"},
        {"document_type": "pan_card", "status": "uploaded"},
        {"document_type": "education", "status": "not_uploaded"},
    ]
    assert derive_onboarding_status(docs) == "under_review"


def test_only_optional_uploaded_is_under_review():
    # An optional doc uploaded but no required docs -> activity exists -> pending
    docs = [{"document_type": "passport", "status": "uploaded"}]
    assert derive_onboarding_status(docs) == "under_review"


def test_rejected_takes_precedence_over_missing():
    docs = [
        {"document_type": "aadhaar_card", "status": "rejected"},
        {"document_type": "pan_card", "status": "not_uploaded"},
    ]
    assert derive_onboarding_status(docs) == "rejected"


# ---------------------------------------------------------------- live API
def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN[0], "password": ADMIN[1]},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login()


def test_no_approved_employee_has_zero_verified_docs(admin_token):
    """The core integrity guarantee: nobody is 'Approved' without all required
    docs actually verified."""
    h = {"Authorization": f"Bearer {admin_token}"}
    lst = requests.get(
        f"{BASE_URL}/api/onboarding/list?status=approved", headers=h, timeout=90
    ).json()
    for rec in lst:
        emp = rec["employee_id"]
        detail = requests.get(
            f"{BASE_URL}/api/onboarding/employee/{emp}", headers=h, timeout=90
        ).json()
        docs = detail.get("documents", [])
        verified = [d for d in docs if d.get("status") == "verified"]
        assert verified, f"{rec.get('emp_name')} approved with no verified docs"
        # Sticky-APPROVED (2026-07-15) + permanent verification lock
        # (2026-07-23, EMP0125): an HR-approved employee may still have
        # pending docs; only a REJECTED required doc invalidates approval.
        assert derive_onboarding_status(docs) != "rejected"


def test_stats_consistent_with_list(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    stats = requests.get(f"{BASE_URL}/api/onboarding/stats", headers=h, timeout=90).json()
    not_started = requests.get(
        f"{BASE_URL}/api/onboarding/list?status=not_started", headers=h, timeout=90
    ).json()
    assert stats["not_started"] == len(not_started)
    assert stats["pending"] == 0 and stats["in_progress"] == 0
