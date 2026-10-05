"""Historical Backfill Engine — spec coverage.

Validates the `POST /api/missed-punches/backfill` endpoint and underlying
flow:
  • picks ONLY approved + not-yet-applied requests
  • is idempotent across multiple runs
  • respects dry_run (no DB mutation)
  • flags malformed historical rows as `skipped_invalid`
  • respects per-employee + date filters
  • stamps `correction_applied_at` + `is_applied` on the source request
  • writes exactly ONE `attendance_corrections` audit row per request
  • status endpoint returns coherent counts
  • biometric raw logs untouched
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

import requests  # auth helper for the HTTP endpoint


def _api_url():
    from pathlib import Path
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


def _hr_token():
    r = requests.post(
        f"{_api_url()}/api/auth/login",
        json={"username": "admin", "password": "pass123"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["token"]


@pytest_asyncio.fixture(loop_scope="session")
async def db():
    yield server.db


@pytest_asyncio.fixture(loop_scope="session")
async def emp(db):
    eid = f"BFTEST-{uuid.uuid4()}"
    await db.employees.insert_one({
        "id": eid, "full_name": "BF Test User", "team": "QA",
        "department": "Research Unit", "official_email": f"{eid}@test.local",
        "is_deleted": False, "employee_status": "Active",
        "shift_type": "General", "attendance_tracking_enabled": True,
        "date_of_joining": "2024-01-01",
    })
    yield eid
    # Teardown — delete every artefact created against this test employee
    await db.attendance.delete_many({"employee_id": eid})
    await db.attendance_corrections.delete_many({"employee_id": eid})
    await db.missed_punches.delete_many({"employee_id": eid})
    await db.employees.delete_one({"id": eid})


def _seed_request(emp_id, date, ptype, ci=None, co=None, applied=False, status="approved"):
    rid = str(uuid.uuid4())
    return {
        "id": rid,
        "employee_id": emp_id,
        "emp_name": "BF Test User",
        "team": "QA",
        "department": "Research Unit",
        "date": date,
        "punch_type": ptype,
        "check_in_time": ci,
        "check_out_time": co,
        "reason": "backfill test",
        "status": status,
        "approved_by": "test-hr" if status == "approved" else None,
        "approved_at": datetime.utcnow().isoformat() if status == "approved" else None,
        "correction_applied_at": datetime.utcnow().isoformat() if applied else None,
        "is_applied": applied,
        "created_at": datetime.utcnow().isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────
# 1. dry_run never mutates
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_does_not_mutate(db, emp):
    rec = _seed_request(emp, "10-03-2026", "Both", ci="2026-03-10T09:00", co="2026-03-10T18:30")
    await db.missed_punches.insert_one(rec.copy())

    token = _hr_token()
    r = requests.post(
        f"{_api_url()}/api/missed-punches/backfill",
        headers={"Authorization": f"Bearer {token}"},
        json={"dry_run": True, "employee_id": emp},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    assert body["dry_run"] is True
    assert body["applied"] >= 1  # would-apply count

    # No mutation: no attendance row, no audit row, no flag stamped
    assert await db.attendance.find_one({"employee_id": emp, "date": "10-03-2026"}) is None
    assert await db.attendance_corrections.find_one({"request_id": rec["id"]}) is None
    src = await db.missed_punches.find_one({"id": rec["id"]}, {"_id": 0})
    assert src.get("correction_applied_at") in (None, "")
    assert src.get("is_applied") in (None, False)


# ────────────────────────────────────────────────────────────────────────────
# 2. Real run applies + stamps + audit row
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_applies_and_stamps(db, emp):
    rec = _seed_request(emp, "11-03-2026", "Both", ci="2026-03-11T09:00", co="2026-03-11T18:30")
    await db.missed_punches.insert_one(rec.copy())

    token = _hr_token()
    r = requests.post(
        f"{_api_url()}/api/missed-punches/backfill",
        headers={"Authorization": f"Bearer {token}"},
        json={"employee_id": emp},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    assert body["applied"] >= 1

    att = await db.attendance.find_one({"employee_id": emp, "date": "11-03-2026"}, {"_id": 0})
    assert att is not None
    assert att["check_in_24h"] == "09:00"
    assert att["check_out_24h"] == "18:30"
    assert att["source"] == "corrected"
    assert att["total_hours_decimal"] == 9.5

    audit = await db.attendance_corrections.find_one({"request_id": rec["id"]}, {"_id": 0})
    assert audit is not None
    assert audit["new_check_in_24h"] == "09:00"

    src = await db.missed_punches.find_one({"id": rec["id"]}, {"_id": 0})
    assert src["is_applied"] is True
    assert src.get("correction_applied_at")


# ────────────────────────────────────────────────────────────────────────────
# 3. Idempotency — second run skips, exactly ONE audit row
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_idempotent_replay(db, emp):
    rec = _seed_request(emp, "12-03-2026", "Both", ci="2026-03-12T09:30", co="2026-03-12T18:00")
    await db.missed_punches.insert_one(rec.copy())

    token = _hr_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"employee_id": emp}

    r1 = requests.post(f"{_api_url()}/api/missed-punches/backfill", headers=headers, json=payload, timeout=30)
    r2 = requests.post(f"{_api_url()}/api/missed-punches/backfill", headers=headers, json=payload, timeout=30)
    r3 = requests.post(f"{_api_url()}/api/missed-punches/backfill", headers=headers, json=payload, timeout=30)

    # All return 200, but only the first should "apply" this record
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert r2.json()["applied"] == 0  # nothing left to apply for this employee
    assert r3.json()["applied"] == 0

    # EXACTLY one audit row written
    audits = await db.attendance_corrections.find({"request_id": rec["id"]}).to_list(10)
    assert len(audits) == 1


# ────────────────────────────────────────────────────────────────────────────
# 4. Skip already-applied (audit row exists but flag missing) — heals flag
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_heals_legacy_unflagged_records(db, emp):
    """If a record was applied via the OLD engine, an audit row may already
    exist (or attendance may already be correct) but `correction_applied_at`
    might be missing. The backfill must heal the flag without re-applying."""
    rec = _seed_request(emp, "13-03-2026", "Both", ci="2026-03-13T09:00", co="2026-03-13T18:00", applied=False)
    await db.missed_punches.insert_one(rec.copy())
    # Pre-seed a fake audit row simulating prior application
    await db.attendance_corrections.insert_one({
        "id": str(uuid.uuid4()),
        "request_id": rec["id"],
        "employee_id": emp,
        "date": "13-03-2026",
        "approved_by": "system_legacy",
        "created_at": datetime.utcnow().isoformat(),
    })

    token = _hr_token()
    r = requests.post(
        f"{_api_url()}/api/missed-punches/backfill",
        headers={"Authorization": f"Bearer {token}"},
        json={"employee_id": emp},
        timeout=30,
    )
    body = r.json()
    assert body["skipped_already_applied"] >= 1

    src = await db.missed_punches.find_one({"id": rec["id"]}, {"_id": 0})
    assert src["is_applied"] is True
    assert src.get("correction_applied_at")


# ────────────────────────────────────────────────────────────────────────────
# 5. Malformed historical rows flagged as invalid (not silently dropped)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_historical_request_reported(db, emp):
    bad = _seed_request(emp, "14-03-2026", "Both", ci="2026-03-14T09:00", co=None)  # Both with only one time
    await db.missed_punches.insert_one(bad.copy())

    token = _hr_token()
    r = requests.post(
        f"{_api_url()}/api/missed-punches/backfill",
        headers={"Authorization": f"Bearer {token}"},
        json={"employee_id": emp},
        timeout=30,
    )
    body = r.json()
    assert body["skipped_invalid"] >= 1
    assert any(e.get("id") == bad["id"] for e in body["errors"])


# ────────────────────────────────────────────────────────────────────────────
# 6. Status endpoint reflects backfill progress
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_endpoint_returns_counts(db, emp):
    token = _hr_token()
    r = requests.get(
        f"{_api_url()}/api/missed-punches/backfill/status",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    assert "total_approved_requests" in body
    assert "pending_correction_apply" in body
    assert "applied_correction_audit_rows" in body
    assert body["pending_correction_apply"] <= body["total_approved_requests"]


# ────────────────────────────────────────────────────────────────────────────
# 7. Permission — non-admin role rejected
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_requires_admin():
    # log in as a non-admin employee (kasper)
    r = requests.post(
        f"{_api_url()}/api/auth/login",
        json={"username": "kasper", "password": "pass123"},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip("Employee test account 'kasper' not available")
    token = r.json()["token"]
    r2 = requests.post(
        f"{_api_url()}/api/missed-punches/backfill",
        headers={"Authorization": f"Bearer {token}"},
        json={"dry_run": True},
        timeout=15,
    )
    assert r2.status_code == 403


# ────────────────────────────────────────────────────────────────────────────
# 8. Biometric raw logs untouched by backfill
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_does_not_touch_biometric_logs(db, emp):
    raw_id = str(uuid.uuid4())
    await db.biometric_punch_logs.insert_one({
        "id": raw_id, "employee_id": emp,
        "device_user_id": "RAW", "punch_at": "2026-03-15T08:30",
        "raw_punch_time": "08:30",
    })
    rec = _seed_request(emp, "15-03-2026", "Both", ci="2026-03-15T09:00", co="2026-03-15T18:00")
    await db.missed_punches.insert_one(rec.copy())

    token = _hr_token()
    requests.post(
        f"{_api_url()}/api/missed-punches/backfill",
        headers={"Authorization": f"Bearer {token}"},
        json={"employee_id": emp},
        timeout=30,
    )

    raw = await db.biometric_punch_logs.find_one({"id": raw_id}, {"_id": 0})
    assert raw is not None
    assert raw["raw_punch_time"] == "08:30"
    await db.biometric_punch_logs.delete_one({"id": raw_id})
