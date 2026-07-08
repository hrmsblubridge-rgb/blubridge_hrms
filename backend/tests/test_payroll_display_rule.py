"""Regression: Payroll attendance STATUS DISPLAY rule (HR spec 2026-06).

Approved WITHOUT LOP  -> display "P" (fully payable day, 0 LOP).
Approved WITH LOP     -> display the actual approved leave code (SF/SH/PA/...).
Generic "LOP" is never displayed for an approved leave.
Payroll math (lop_value / payable days / net salary) is unchanged.
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
        "id": eid, "custom_employee_id": f"DR-{eid[:6]}", "full_name": "Display Rule Test",
        "employment_type": "Full-time", "employee_status": "Active",
        "department": "Support Staff", "shift_type": "General",
        "date_of_joining": "2026-01-01", "monthly_salary": 31000, "is_deleted": False,
    })
    yield eid
    await db.employees.delete_one({"id": eid})
    await db.attendance.delete_many({"employee_id": eid})
    await db.leaves.delete_many({"employee_id": eid})


async def _leave(eid, d, ltype, split, is_lop):
    await db.leaves.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "leave_type": ltype,
        "leave_split": split, "start_date": d, "end_date": d,
        "status": "approved", "is_lop": is_lop,
    })


@pytest.mark.asyncio
async def test_sick_without_lop_displays_P(emp):
    await _leave(emp, "2026-05-04", "Sick", "Full Day", False)
    pr = await calculate_payroll_for_employee(emp, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    row = by["04-05-2026"]
    assert row["status"] == "P", row
    assert row["lop_value"] == 0 and row["is_lop"] is False


@pytest.mark.asyncio
async def test_with_lop_displays_actual_code_never_generic_lop(emp):
    cases = [
        ("2026-05-04", "Sick", "Full Day", "SF"),
        ("2026-05-05", "Sick", "First Half", "SH"),
        ("2026-05-06", "Pre-Planned", "Full Day", "PF"),
        ("2026-05-07", "Emergency", "Full Day", "EF"),
        ("2026-05-08", "Paid Leave", "Full Day", "PA"),
        ("2026-05-11", "Optional", "Full Day", "OH"),
    ]
    for d, lt, split, _ in cases:
        await _leave(emp, d, lt, split, True)
    pr = await calculate_payroll_for_employee(emp, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    for d, _, split, expected in cases:
        dd = f"{d[8:10]}-{d[5:7]}-{d[0:4]}"
        row = by[dd]
        assert row["status"] == expected, (dd, row)
        assert row["status"] != "LOP"
        assert row["lop_value"] == (0.5 if "Half" in split else 1)


@pytest.mark.asyncio
async def test_without_lop_full_pay_math_unchanged(emp):
    # Without-LOP leave day: 0 LOP on that row; summary reconciles from rows.
    await _leave(emp, "2026-05-04", "Emergency", "Full Day", False)
    pr = await calculate_payroll_for_employee(emp, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["04-05-2026"]["status"] == "P" and by["04-05-2026"]["lop_value"] == 0
    assert pr["final_payable_days"] == max(
        0, pr["working_days"] + pr["weekoff_pay"] + pr["oh_pay"] - pr["lop"]
    )
