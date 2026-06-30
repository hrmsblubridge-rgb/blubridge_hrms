"""Regression: Payroll consumes the admin With/Without-LOP decision and never
auto-marks Present without sufficient login hours (Bug 1 + Bug 2).
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
from server import calculate_payroll_for_employee, db  # noqa: E402

DAYS = {"d1": "2026-05-04", "d2": "2026-05-05", "d3": "2026-05-06", "d4": "2026-05-07"}


@pytest.fixture
async def emp():
    eid = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": eid, "custom_employee_id": f"AP-{eid[:6]}", "full_name": "Approval LOP Test",
        "employment_type": "Full-time", "employee_status": "Active",
        "department": "Support Staff",                 # full=9h, half=4.5h
        "shift_type": "Custom", "custom_login_time": "09:00", "custom_logout_time": "18:00",
        "late_grace_minutes": 0, "date_of_joining": "2026-01-01", "is_deleted": False,
    })
    yield eid
    await db.employees.delete_one({"id": eid})
    await db.attendance.delete_many({"employee_id": eid})
    await db.late_requests.delete_many({"employee_id": eid})
    await db.early_out_requests.delete_many({"employee_id": eid})


async def _att(eid, d, ci, co, dec):
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "date": d,
        "check_in_24h": ci, "check_out_24h": co, "total_hours_decimal": dec,
        "check_in": ci, "check_out": co,
    })


@pytest.mark.asyncio
async def test_late_with_and_without_lop(emp):
    eid = emp
    # Late (10:00 > 09:00) + full hours both days.
    await _att(eid, DAYS["d1"], "10:00", "20:00", 10.0)  # late approved WITHOUT LOP
    await _att(eid, DAYS["d2"], "10:00", "20:00", 10.0)  # late approved WITH LOP
    await db.late_requests.insert_one({"id": str(uuid.uuid4()), "employee_id": eid, "date": DAYS["d1"], "status": "approved", "is_lop": False})
    await db.late_requests.insert_one({"id": str(uuid.uuid4()), "employee_id": eid, "date": DAYS["d2"], "status": "approved", "is_lop": True})
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["04-05-2026"]["status"] == "LC" and by["04-05-2026"]["lop_value"] == 0    # without LOP
    assert by["05-05-2026"]["status"] == "LC" and by["05-05-2026"]["lop_value"] == 0.5  # with LOP


@pytest.mark.asyncio
async def test_early_out_with_and_without_lop(emp):
    eid = emp
    # Half-day hours (5h: >=4.5 half, <9 full) → hours-based HD. On-time check-in.
    await _att(eid, DAYS["d3"], "09:00", "14:00", 5.0)  # early out WITHOUT LOP → excused P
    await _att(eid, DAYS["d4"], "09:00", "14:00", 5.0)  # early out WITH LOP → HD penalty
    await db.early_out_requests.insert_one({"id": str(uuid.uuid4()), "employee_id": eid, "date": DAYS["d3"], "status": "approved", "is_lop": False})
    await db.early_out_requests.insert_one({"id": str(uuid.uuid4()), "employee_id": eid, "date": DAYS["d4"], "status": "approved", "is_lop": True})
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["06-05-2026"]["status"] == "P" and by["06-05-2026"]["lop_value"] == 0     # without LOP → excused
    assert by["07-05-2026"]["status"] == "HD" and by["07-05-2026"]["lop_value"] == 0.5  # with LOP → penalty


@pytest.mark.asyncio
async def test_no_checkout_past_day_not_present(emp):
    eid = emp
    # Past day, checked in early but NO checkout → must NOT be auto-Present (Bug 2).
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "date": DAYS["d1"],
        "check_in_24h": "09:08", "check_in": "09:08 AM",
        "check_out_24h": None, "total_hours_decimal": 0.0,
    })
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["04-05-2026"]["status"] == "MP", by["04-05-2026"]
    assert by["04-05-2026"]["lop_value"] == 0  # salary-neutral until corrected
