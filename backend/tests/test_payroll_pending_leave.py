"""Regression: a PENDING/REJECTED leave must NOT mask real attendance in payroll.

Reproduces the Kota Dhanakumar bug: a pending Sick Leave on a day with a
corrected 3h13m punch was showing Present. The day must fall through to the
hours-based engine (A, since 3.22h < half-day requirement). Approved leaves
still show their code (without LOP) or LOP (with LOP).
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
from server import calculate_payroll_for_employee, db  # noqa: E402


@pytest.fixture
async def emp():
    eid = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": eid, "custom_employee_id": f"PL-{eid[:6]}", "full_name": "Pending Leave Test",
        "employment_type": "Full-time", "employee_status": "Active",
        "department": "Research Unit",                 # full=11h, half=6h
        "shift_type": "Custom", "custom_login_time": "10:00", "custom_logout_time": "21:00",
        "date_of_joining": "2026-01-01", "is_deleted": False,
    })
    yield eid
    await db.employees.delete_one({"id": eid})
    await db.attendance.delete_many({"employee_id": eid})
    await db.leaves.delete_many({"employee_id": eid})


async def _att(eid, d, dec):
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "date": d,
        "check_in_24h": "09:42", "check_out_24h": "12:55", "total_hours_decimal": dec,
        "check_in": "09:42 AM", "check_out": "12:55 PM", "total_hours": "3h 13m",
        "source": "corrected",
    })


@pytest.mark.asyncio
async def test_pending_leave_does_not_force_present(emp):
    eid = emp
    await _att(eid, "2026-05-04", 3.22)  # 3h13m, below half (6h)
    await db.leaves.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "leave_type": "Sick",
        "leave_split": "Full Day", "start_date": "2026-05-04", "end_date": "2026-05-04",
        "status": "pending",
    })
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["04-05-2026"]["status"] == "A", by["04-05-2026"]   # NOT Present
    assert by["04-05-2026"]["lop_value"] == 1


@pytest.mark.asyncio
async def test_approved_leave_with_attendance_shows_code_or_lop(emp):
    eid = emp
    await _att(eid, "2026-05-05", 3.22)  # approved Sick WITHOUT LOP -> SF
    await _att(eid, "2026-05-06", 3.22)  # approved Sick WITH LOP   -> LOP
    await db.leaves.insert_one({"id": str(uuid.uuid4()), "employee_id": eid, "leave_type": "Sick",
        "leave_split": "Full Day", "start_date": "2026-05-05", "end_date": "2026-05-05",
        "status": "approved", "is_lop": False})
    await db.leaves.insert_one({"id": str(uuid.uuid4()), "employee_id": eid, "leave_type": "Sick",
        "leave_split": "Full Day", "start_date": "2026-05-06", "end_date": "2026-05-06",
        "status": "approved", "is_lop": True})
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["05-05-2026"]["status"] == "SF" and by["05-05-2026"]["lop_value"] == 0
    assert by["06-05-2026"]["status"] == "LOP" and by["06-05-2026"]["lop_value"] == 1
