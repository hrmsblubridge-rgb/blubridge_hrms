"""Production Missed-Punch Approval Engine — full spec coverage.

Validates every numbered behavior in the user's spec by directly invoking
`_update_attendance_from_missed_punch` with seeded fixtures and asserting on
the resulting `attendance` and `attendance_corrections` documents.

Run:  cd /app/backend && python -m pytest tests/test_missed_punch_engine.py -v
"""
import os
import uuid
import pytest
import pytest_asyncio
from datetime import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402


@pytest_asyncio.fixture(loop_scope="session")
async def db():
    """Reuse the SAME Motor client / db that `server` already opened, so all
    awaits run on a single event loop. Creating a fresh AsyncIOMotorClient
    inside the test would bind to a different loop and trigger the classic
    'Future attached to a different loop' error."""
    yield server.db


@pytest_asyncio.fixture(loop_scope="session")
async def emp(db):
    """Seed a throw-away employee + clean up everything created against it."""
    eid = f"TEST-MP-{uuid.uuid4()}"
    await db.employees.insert_one({
        "id": eid,
        "full_name": "MP Test User",
        "team": "QA",
        "department": "Research Unit",
        "official_email": f"{eid}@test.local",
        "is_deleted": False,
        "employee_status": "Active",
        "shift_type": "General",
        "attendance_tracking_enabled": True,
        "date_of_joining": "2024-01-01",
    })
    yield eid
    # Teardown
    await db.attendance.delete_many({"employee_id": eid})
    await db.attendance_corrections.delete_many({"employee_id": eid})
    await db.employees.delete_one({"id": eid})


def _request(emp_id, date, punch_type, ci=None, co=None, request_id=None):
    return {
        "id": request_id or str(uuid.uuid4()),
        "employee_id": emp_id,
        "date": date,
        "punch_type": punch_type,
        "check_in_time": ci,
        "check_out_time": co,
        "approved_by": "test-hr",
        "approved_at": datetime.utcnow().isoformat(),
        "status": "approved",
    }


# ────────────────────────────────────────────────────────────────────────────
# 1. Type semantics
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_in_only_replaces_in_field_keeps_out(db, emp):
    """Check-in correction REPLACES check_in only, leaves check_out intact."""
    date = "10-02-2026"
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": emp, "emp_name": "MP Test User",
        "team": "QA", "department": "Research Unit", "date": date,
        "check_in": "10:30 AM", "check_in_24h": "10:30",
        "check_out": "07:00 PM", "check_out_24h": "19:00",
        "status": "Present", "source": "biometric",
    })
    req = _request(emp, date, "Check-in", ci="2026-02-10T09:15")
    await server._update_attendance_from_missed_punch(req)

    rec = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert rec["check_in_24h"] == "09:15"      # REPLACED
    assert rec["check_in"] == "09:15 AM"
    assert rec["check_out_24h"] == "19:00"     # untouched
    assert rec["source"] == "corrected"
    assert rec["missed_punch_corrected"] is True


@pytest.mark.asyncio
async def test_check_out_only_replaces_out_field_keeps_in(db, emp):
    date = "11-02-2026"
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": emp, "emp_name": "MP Test User",
        "team": "QA", "department": "Research Unit", "date": date,
        "check_in": "09:30 AM", "check_in_24h": "09:30",
        "check_out": "06:30 PM", "check_out_24h": "18:30",
        "status": "Present", "source": "biometric",
    })
    req = _request(emp, date, "Check-out", co="2026-02-11T20:00")
    await server._update_attendance_from_missed_punch(req)

    rec = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert rec["check_in_24h"] == "09:30"      # untouched
    assert rec["check_out_24h"] == "20:00"     # REPLACED
    assert rec["check_out"] == "08:00 PM"
    assert rec["source"] == "corrected"


@pytest.mark.asyncio
async def test_both_replaces_in_and_out(db, emp):
    date = "12-02-2026"
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": emp, "emp_name": "MP Test User",
        "team": "QA", "department": "Research Unit", "date": date,
        "check_in": "10:00 AM", "check_in_24h": "10:00",
        "check_out": None, "check_out_24h": None,
        "status": "Login", "source": "biometric",
    })
    req = _request(emp, date, "Both", ci="2026-02-12T09:00", co="2026-02-12T18:30")
    await server._update_attendance_from_missed_punch(req)

    rec = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert rec["check_in_24h"] == "09:00"
    assert rec["check_out_24h"] == "18:30"


# ────────────────────────────────────────────────────────────────────────────
# 2. UPSERT: insert when no attendance row exists
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_inserts_when_no_existing_attendance(db, emp):
    date = "13-02-2026"
    assert await db.attendance.find_one({"employee_id": emp, "date": date}) is None
    req = _request(emp, date, "Both", ci="2026-02-13T09:30", co="2026-02-13T18:30")
    await server._update_attendance_from_missed_punch(req)

    rec = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert rec is not None
    assert rec["check_in_24h"] == "09:30"
    assert rec["check_out_24h"] == "18:30"
    assert rec["source"] == "corrected"
    assert rec["missed_punch_corrected"] is True


# ────────────────────────────────────────────────────────────────────────────
# 3. Total-hours recalc + cross-midnight
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_total_hours_recomputed(db, emp):
    date = "14-02-2026"
    req = _request(emp, date, "Both", ci="2026-02-14T09:00", co="2026-02-14T18:30")
    await server._update_attendance_from_missed_punch(req)
    rec = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert rec["total_hours_decimal"] == 9.5


@pytest.mark.asyncio
async def test_cross_midnight_total_hours(db, emp):
    """OUT < IN → wraps via 24h. 22:00 IN, 02:30 OUT next day = 4.5h."""
    date = "15-02-2026"
    req = _request(emp, date, "Both", ci="2026-02-15T22:00", co="2026-02-16T02:30")
    await server._update_attendance_from_missed_punch(req)
    rec = await db.attendance.find_one({"employee_id": emp, "date": date}, {"_id": 0})
    assert rec["total_hours_decimal"] == 4.5


# ────────────────────────────────────────────────────────────────────────────
# 4. Audit trail
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_record_written(db, emp):
    date = "16-02-2026"
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": emp, "emp_name": "MP Test User",
        "team": "QA", "department": "Research Unit", "date": date,
        "check_in": "10:30 AM", "check_in_24h": "10:30",
        "check_out": None, "check_out_24h": None,
        "status": "Login", "source": "biometric",
    })
    rid = str(uuid.uuid4())
    req = _request(emp, date, "Both", ci="2026-02-16T09:30", co="2026-02-16T18:30", request_id=rid)
    await server._update_attendance_from_missed_punch(req)

    audits = await db.attendance_corrections.find({"request_id": rid}, {"_id": 0}).to_list(10)
    assert len(audits) == 1
    a = audits[0]
    assert a["old_check_in_24h"] == "10:30"
    assert a["new_check_in_24h"] == "09:30"
    assert a["old_check_out_24h"] is None
    assert a["new_check_out_24h"] == "18:30"
    assert a["punch_type"] == "Both"
    assert a["approved_by"] == "test-hr"
    assert a["source_before"] == "biometric"
    assert a["source_after"] == "corrected"


# ────────────────────────────────────────────────────────────────────────────
# 5. Idempotency
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotent_replay_no_duplicate_audit(db, emp):
    date = "17-02-2026"
    rid = str(uuid.uuid4())
    req = _request(emp, date, "Both", ci="2026-02-17T09:00", co="2026-02-17T18:00", request_id=rid)
    await server._update_attendance_from_missed_punch(req)
    await server._update_attendance_from_missed_punch(req)  # replay
    audits = await db.attendance_corrections.find({"request_id": rid}).to_list(10)
    assert len(audits) == 1, "replay must NOT create a second audit row"


# ────────────────────────────────────────────────────────────────────────────
# 6. Source tracking + biometric logs untouched
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_biometric_punch_logs_untouched(db, emp):
    """Sanity check: applying a missed-punch correction must never touch
    the raw biometric_punch_logs collection."""
    date = "18-02-2026"
    raw_id = str(uuid.uuid4())
    await db.biometric_punch_logs.insert_one({
        "id": raw_id, "employee_id": emp, "device_user_id": "TEST",
        "punch_at": "2026-02-18T10:30:00", "raw_punch_time": "10:30",
    })
    req = _request(emp, date, "Both", ci="2026-02-18T09:30", co="2026-02-18T18:30")
    await server._update_attendance_from_missed_punch(req)

    raw = await db.biometric_punch_logs.find_one({"id": raw_id}, {"_id": 0})
    assert raw is not None
    assert raw["raw_punch_time"] == "10:30"  # unchanged
    # cleanup the raw row
    await db.biometric_punch_logs.delete_one({"id": raw_id})


# ────────────────────────────────────────────────────────────────────────────
# 7. Edge: malformed type / missing time silently no-op
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_in_request_without_in_time_noop(db, emp):
    date = "19-02-2026"
    req = _request(emp, date, "Check-in", ci=None)  # no IN time
    await server._update_attendance_from_missed_punch(req)
    assert await db.attendance.find_one({"employee_id": emp, "date": date}) is None


@pytest.mark.asyncio
async def test_both_with_only_one_time_rejected(db, emp):
    date = "20-02-2026"
    req = _request(emp, date, "Both", ci="2026-02-20T09:00", co=None)
    await server._update_attendance_from_missed_punch(req)
    assert await db.attendance.find_one({"employee_id": emp, "date": date}) is None
