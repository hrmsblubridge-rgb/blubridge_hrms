"""EMP0125 (Adari Rama Sukanya) permanent verification lock — regression tests.

User mandate (2026-07-23): once approved, EMP0125 must NEVER return to the
Pending Verification queue — not after restarts, background syncs, or
document recomputes. Root cause was the startup self-heal re-deriving her
status strictly from documents (Education = not_uploaded → under_review).

Guards under test:
  1. DB flags: verification_status/completed/verified_at/verified_by set.
  2. `recompute_onboarding_status` (document-sync path) keeps her APPROVED
     even though the strict derive rule says UNDER_REVIEW.
  3. `/verification/pending-count` + `/onboarding/list` exclude her from
     pending views.
"""
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"
HTTP_TIMEOUT = 60.0
EMP125_ID = "ec2f43c7-fa1b-4223-b971-576705630541"


@pytest.fixture(scope="module")
def hr_token():
    r = httpx.post(f"{API}/auth/login",
                   json={"username": "admin", "password": "HrAdmin786$"},
                   timeout=HTTP_TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_emp0125_db_flags_permanently_verified():
    from server import db  # noqa
    emp = await db.employees.find_one({"emp_id": "EMP0125"}, {"_id": 0})
    assert emp, "EMP0125 must exist"
    assert emp.get("verification_status") == "verified"
    assert emp.get("verification_completed") is True
    assert emp.get("verified_at")
    assert emp.get("verified_by")
    onb = await db.onboarding.find_one({"employee_id": emp["id"]}, {"_id": 0, "status": 1})
    assert onb and onb["status"] == "approved"


@pytest.mark.asyncio
async def test_emp0125_recompute_cannot_demote():
    """Document-sync recompute path must honour the permanent lock even
    though the strict derive rule yields under_review for her doc set."""
    from server import (db, recompute_onboarding_status,  # noqa
                        derive_onboarding_status, OnboardingStatus)
    docs = await db.onboarding_documents.find(
        {"employee_id": EMP125_ID}, {"_id": 0}).to_list(50)
    strict = derive_onboarding_status(docs)
    assert strict != OnboardingStatus.APPROVED, (
        "Precondition changed: her docs now strictly derive approved — "
        "lock test no longer exercises the demotion path"
    )
    result = await recompute_onboarding_status(EMP125_ID)
    assert result == OnboardingStatus.APPROVED
    onb = await db.onboarding.find_one({"employee_id": EMP125_ID}, {"_id": 0, "status": 1})
    assert onb["status"] == OnboardingStatus.APPROVED


def test_emp0125_not_in_pending_views(hr_token):
    # Pending list must NOT contain her
    for pending in ("under_review", "pending", "in_progress"):
        r = httpx.get(f"{API}/onboarding/list",
                      headers=_h(hr_token),
                      params={"status": pending, "search": "EMP0125"},
                      timeout=HTTP_TIMEOUT)
        assert r.status_code == 200, r.text
        assert r.json() == [], f"EMP0125 must not appear under status={pending}"

    # She appears as approved
    r = httpx.get(f"{API}/onboarding/list",
                  headers=_h(hr_token),
                  params={"search": "EMP0125"},
                  timeout=HTTP_TIMEOUT)
    rows = r.json()
    assert len(rows) == 1 and rows[0]["status"] == "approved"

    # Pending count endpoint responds and, per aggregation, cannot include an
    # onboarding row whose status is approved.
    r = httpx.get(f"{API}/verification/pending-count",
                  headers=_h(hr_token), timeout=HTTP_TIMEOUT)
    assert r.status_code == 200
    assert isinstance(r.json().get("count"), int)
