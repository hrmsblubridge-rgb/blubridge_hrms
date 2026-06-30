"""Regression: Payroll Late-Coming (LC) sync.

Approved Late request  -> day shows 'LC' but is EXCUSED (0 LOP, full pay).
No/Unapproved late      -> day shows 'LC' with 0.5 LOP penalty.
Salary (LOP) for approved-late is unchanged vs the previous 'P' behaviour.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
from server import calculate_payroll_for_employee, db  # noqa: E402


@pytest.fixture
async def late_scenario():
    eid = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": eid, "custom_employee_id": f"LCT-{eid[:6]}", "full_name": "LC Test",
        "employment_type": "Full-time", "employee_status": "Active",
        "department": "Support Staff",            # full=9h, half=4.5h
        "shift_type": "Custom",
        "custom_login_time": "09:00", "custom_logout_time": "18:00",
        "late_grace_minutes": 0,
        "date_of_joining": "2026-01-01", "is_deleted": False,
    })
    # Two working days, both LATE check-in (10:00 > 09:00) with FULL hours (10h).
    for d in ("2026-05-04", "2026-05-05"):  # Mon, Tue
        await db.attendance.insert_one({
            "id": str(uuid.uuid4()), "employee_id": eid, "date": d,
            "check_in": "10:00 AM", "check_out": "08:00 PM",
            "check_in_24h": "10:00", "check_out_24h": "20:00",
            "total_hours": "10h 0m", "total_hours_decimal": 10.0,
        })
    # Approved Late request ONLY for 2026-05-04.
    late_id = str(uuid.uuid4())
    await db.late_requests.insert_one({
        "id": late_id, "employee_id": eid, "date": "2026-05-04", "status": "approved",
    })
    yield eid
    await db.employees.delete_one({"id": eid})
    await db.attendance.delete_many({"employee_id": eid})
    await db.late_requests.delete_many({"employee_id": eid})


@pytest.mark.asyncio
async def test_late_coming_sync(late_scenario):
    eid = late_scenario
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    assert pr is not None
    by_date = {row["date"]: row for row in pr["attendance_details"]}

    approved = by_date["04-05-2026"]
    assert approved["status"] == "LC", approved          # relabelled from P
    assert approved["lop_value"] == 0, approved          # EXCUSED — no penalty
    assert approved["is_lop"] is False, approved

    unapproved = by_date["05-05-2026"]
    assert unapproved["status"] == "LC", unapproved
    assert unapproved["lop_value"] == 0.5, unapproved    # penalty retained
    assert unapproved["is_lop"] is True, unapproved
