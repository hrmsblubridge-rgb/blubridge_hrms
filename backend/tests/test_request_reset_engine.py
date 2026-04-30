"""Universal Request Reset Engine — spec coverage.

Validates POST .../{id}/reset endpoints across 4 modules:
  • Leave
  • Late Request
  • Early Out
  • Missed Punch (full attendance rollback)

Plus: idempotency, audit row in `request_resets`, RBAC.
"""
import os
import uuid
import pytest
import pytest_asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import requests


def _api_url():
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


def _hr_token():
    r = requests.post(f"{_api_url()}/api/auth/login",
                      json={"username": "admin", "password": "pass123"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


@pytest_asyncio.fixture(loop_scope="session")
async def db():
    yield server.db


@pytest_asyncio.fixture(loop_scope="session")
async def emp(db):
    eid = f"RST-TEST-{uuid.uuid4()}"
    await db.employees.insert_one({
        "id": eid, "full_name": "Reset Test User", "team": "QA",
        "department": "Research Unit", "official_email": f"{eid}@test.local",
        "is_deleted": False, "employee_status": "Active",
        "shift_type": "General", "attendance_tracking_enabled": True,
        "date_of_joining": "2024-01-01",
    })
    yield eid
    await db.attendance.delete_many({"employee_id": eid})
    await db.attendance_corrections.delete_many({"employee_id": eid})
    await db.missed_punches.delete_many({"employee_id": eid})
    await db.leaves.delete_many({"employee_id": eid})
    await db.late_requests.delete_many({"employee_id": eid})
    await db.early_out_requests.delete_many({"employee_id": eid})
    await db.request_resets.delete_many({})
    await db.employees.delete_one({"id": eid})


# ────────────────────────────────────────────────────────────────────────────
# 1. Leave reset
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_leave_reset_clears_approval_and_lop(db, emp):
    leave_id = str(uuid.uuid4())
    await db.leaves.insert_one({
        "id": leave_id, "employee_id": emp, "emp_name": "Reset Test User",
        "team": "QA", "department": "Research Unit",
        "leave_type": "Sick", "leave_split": "Full Day",
        "start_date": "2027-05-10", "end_date": "2027-05-10",
        "duration": "1 day(s)", "reason": "test", "status": "rejected",
        "is_lop": True, "lop_remark": "test", "approved_by": "old-hr",
        "approved_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    })

    token = _hr_token()
    r = requests.post(f"{_api_url()}/api/leaves/{leave_id}/reset",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"reason": "spec test"}, timeout=15)
    r.raise_for_status()
    body = r.json()
    assert body["status"] == "pending"
    assert "approved_by" not in body or body.get("approved_by") in (None, "")
    assert "is_lop" not in body or body.get("is_lop") is None

    audit = await db.request_resets.find_one({"request_type": "leave", "request_id": leave_id}, {"_id": 0})
    assert audit is not None
    assert audit["previous_status"] == "rejected"


@pytest.mark.asyncio
async def test_leave_reset_idempotent(db, emp):
    """Resetting an already-pending leave should be a safe no-op."""
    leave_id = str(uuid.uuid4())
    await db.leaves.insert_one({
        "id": leave_id, "employee_id": emp, "emp_name": "Reset Test User",
        "team": "QA", "department": "Research Unit",
        "leave_type": "Sick", "leave_split": "Full Day",
        "start_date": "2027-05-11", "end_date": "2027-05-11",
        "duration": "1 day(s)", "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    })
    token = _hr_token()
    r1 = requests.post(f"{_api_url()}/api/leaves/{leave_id}/reset",
                       headers={"Authorization": f"Bearer {token}"}, json={}, timeout=15)
    r2 = requests.post(f"{_api_url()}/api/leaves/{leave_id}/reset",
                       headers={"Authorization": f"Bearer {token}"}, json={}, timeout=15)
    assert r1.status_code == 200 and r2.status_code == 200
    # No audit row should be written for a no-op reset (already pending + no approver)
    audits = await db.request_resets.find({"request_type": "leave", "request_id": leave_id}).to_list(10)
    assert len(audits) == 0


# ────────────────────────────────────────────────────────────────────────────
# 2. Late Request reset
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_late_request_reset(db, emp):
    rid = str(uuid.uuid4())
    await db.late_requests.insert_one({
        "id": rid, "employee_id": emp, "emp_name": "Reset Test User",
        "team": "QA", "department": "Research Unit",
        "date": "2027-05-12", "expected_time": "09:30", "actual_time": "10:15",
        "reason": "traffic", "status": "approved", "is_lop": False,
        "lop_remark": "ok", "approved_by": "old-hr",
        "approved_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    })
    token = _hr_token()
    r = requests.post(f"{_api_url()}/api/late-requests/{rid}/reset",
                      headers={"Authorization": f"Bearer {token}"}, json={}, timeout=15)
    r.raise_for_status()
    body = r.json()
    assert body["status"] == "pending"
    assert body.get("is_lop") is None
    assert body.get("approved_by") in (None, "")


# ────────────────────────────────────────────────────────────────────────────
# 3. Early Out reset
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_early_out_reset(db, emp):
    rid = str(uuid.uuid4())
    await db.early_out_requests.insert_one({
        "id": rid, "employee_id": emp, "emp_name": "Reset Test User",
        "team": "QA", "department": "Research Unit",
        "date": "2027-05-13", "expected_time": "18:30", "actual_time": "16:00",
        "reason": "appointment", "status": "rejected", "is_lop": True,
        "approved_by": "old-hr",
        "created_at": datetime.utcnow().isoformat(),
    })
    token = _hr_token()
    r = requests.post(f"{_api_url()}/api/early-out-requests/{rid}/reset",
                      headers={"Authorization": f"Bearer {token}"}, json={}, timeout=15)
    r.raise_for_status()
    body = r.json()
    assert body["status"] == "pending"
    assert body.get("is_lop") is None


# ────────────────────────────────────────────────────────────────────────────
# 4. Missed Punch reset — restores attendance from audit row
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missed_punch_reset_restores_attendance(db, emp):
    """End-to-end: apply correction → reset → attendance MUST roll back to
    the original biometric values captured in `attendance_corrections`."""
    date = "21-05-2027"
    # Seed original attendance (biometric source)
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": emp, "emp_name": "Reset Test User",
        "team": "QA", "department": "Research Unit", "date": date,
        "check_in": "10:30 AM", "check_in_24h": "10:30",
        "check_out": "07:00 PM", "check_out_24h": "19:00",
        "status": "Present", "source": "biometric",
    })
    # Apply a correction via the engine
    rid = str(uuid.uuid4())
    rec = {
        "id": rid, "employee_id": emp, "date": date,
        "punch_type": "Both",
        "check_in_time": "2027-05-21T09:00", "check_out_time": "2027-05-21T18:30",
        "approved_by": "test-hr",
        "approved_at": datetime.utcnow().isoformat(),
    }
    await db.missed_punches.insert_one({
        **rec, "emp_name": "Reset Test User", "team": "QA",
        "department": "Research Unit", "reason": "test", "status": "approved",
        "created_at": datetime.utcnow().isoformat(),
    })
    await server._update_attendance_from_missed_punch(rec)
    att_after = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert att_after["check_in_24h"] == "09:00"
    assert att_after["source"] == "corrected"

    # Reset the request
    token = _hr_token()
    r = requests.post(f"{_api_url()}/api/missed-punches/{rid}/reset",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"reason": "rollback test"}, timeout=15)
    r.raise_for_status()
    body = r.json()
    assert body["status"] == "pending"
    assert "approved_by" not in body or body.get("approved_by") in (None, "")
    # Attendance restored to biometric values
    att_rolled = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert att_rolled["check_in_24h"] == "10:30"
    assert att_rolled["check_out_24h"] == "19:00"
    assert att_rolled["source"] == "biometric"
    assert att_rolled.get("missed_punch_corrected") is False
    # Audit row marked reverted, not deleted
    aud = await db.attendance_corrections.find_one({"request_id": rid}, {"_id": 0})
    assert aud is not None
    assert aud.get("reverted_at")
    # request_resets entry written
    reset_audit = await db.request_resets.find_one(
        {"request_type": "missed_punch", "request_id": rid}, {"_id": 0}
    )
    assert reset_audit is not None
    assert reset_audit["attendance_rollback"]["action"] == "restored"


@pytest.mark.asyncio
async def test_missed_punch_reset_then_reapprove_works(db, emp):
    """After reset → request is back to pending → re-approval triggers a
    fresh correction without stacking effects (engine remains idempotent)."""
    date = "22-05-2027"
    rid = str(uuid.uuid4())
    rec = {
        "id": rid, "employee_id": emp, "emp_name": "Reset Test User",
        "team": "QA", "department": "Research Unit", "date": date,
        "punch_type": "Both",
        "check_in_time": "2027-05-22T09:30", "check_out_time": "2027-05-22T18:00",
        "approved_by": "test-hr", "approved_at": datetime.utcnow().isoformat(),
        "reason": "test", "status": "approved",
        "created_at": datetime.utcnow().isoformat(),
    }
    await db.missed_punches.insert_one(rec.copy())
    await server._update_attendance_from_missed_punch(rec)

    # Reset
    token = _hr_token()
    requests.post(f"{_api_url()}/api/missed-punches/{rid}/reset",
                  headers={"Authorization": f"Bearer {token}"}, json={}, timeout=15)

    # Re-approve via the same engine — should produce the same final state
    rec2 = await db.missed_punches.find_one({"id": rid}, {"_id": 0})
    rec2["approved_by"] = "test-hr-2"
    rec2["approved_at"] = datetime.utcnow().isoformat()
    await server._update_attendance_from_missed_punch(rec2)

    att = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert att["check_in_24h"] == "09:30"
    assert att["check_out_24h"] == "18:00"
    assert att["source"] == "corrected"


# ────────────────────────────────────────────────────────────────────────────
# 5. RBAC — non-admin denied
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_requires_admin():
    r = requests.post(f"{_api_url()}/api/auth/login",
                      json={"username": "kasper", "password": "pass123"}, timeout=15)
    if r.status_code != 200:
        pytest.skip("Employee test account 'kasper' not available")
    token = r.json()["token"]
    r2 = requests.post(f"{_api_url()}/api/leaves/some-id/reset",
                       headers={"Authorization": f"Bearer {token}"}, json={}, timeout=15)
    assert r2.status_code == 403
