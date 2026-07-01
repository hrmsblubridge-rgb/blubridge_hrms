"""Regression: Optional Holiday (OH) approved Without LOP must reflect in payroll.

Bug: when an approved Optional Holiday (Without LOP) leave fell on a calendar
holiday, the holiday branch rendered "H" (0 pay) and swallowed the approval, so
Payable Days was 1 short. OH must render "OH" and be a payable holiday.

Also asserts the summary is recomputed strictly from the final attendance rows
(Payable = Working + Weekoff + Extra + Holiday(OH) - LOP) for every case,
including relieved employees whose last day is not payable.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
from server import calculate_payroll_for_employee, db  # noqa: E402

HOLIDAY = "2026-05-15"  # a Friday in May 2026 (non-Sunday)


@pytest.fixture
async def holiday():
    await db.holidays.insert_one({"id": str(uuid.uuid4()), "date": HOLIDAY, "name": "Test Holiday"})
    yield
    await db.holidays.delete_many({"date": HOLIDAY, "name": "Test Holiday"})


@pytest.fixture
async def emp():
    eid = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": eid, "custom_employee_id": f"OH-{eid[:6]}", "full_name": "OH Test",
        "employment_type": "Full-time", "employee_status": "Active",
        "department": "Support Staff", "shift_type": "General",
        "date_of_joining": "2026-01-01", "monthly_salary": 31000, "is_deleted": False,
    })
    yield eid
    await db.employees.delete_one({"id": eid})
    await db.attendance.delete_many({"employee_id": eid})
    await db.leaves.delete_many({"employee_id": eid})


def _reconciles(pr):
    rows = pr["attendance_details"]
    wd = sum(1 for d in rows if not d["is_sunday"] and not d["is_holiday"] and d["status"] not in ("BLANK", "R"))
    wo = sum(d.get("weekoff_value", 0) or 0 for d in rows)
    ex = sum(d.get("extra_value", 0) or 0 for d in rows)
    oh = sum(d.get("oh_value", 0) or 0 for d in rows)
    lop = sum(d.get("lop_value", 0) or 0 for d in rows)
    assert wd == pr["working_days"]
    assert abs(wo - pr["weekoff_pay"]) < 1e-6
    assert abs(ex - pr["extra_pay"]) < 1e-6
    assert abs(oh - pr["oh_pay"]) < 1e-6
    assert abs(lop - pr["lop"]) < 1e-6
    # Extra Pay is EXCLUDED from Payable Days (independent component, HR spec §8)
    assert abs(max(0, wd + wo + oh - lop) - pr["final_payable_days"]) < 1e-6


@pytest.mark.asyncio
async def test_optional_holiday_on_holiday_is_payable(emp, holiday):
    eid = emp
    await db.leaves.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "leave_type": "Optional",
        "leave_split": "Full Day", "start_date": HOLIDAY, "end_date": HOLIDAY,
        "status": "approved", "is_lop": False,
    })
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["15-05-2026"]["status"] == "OH", by["15-05-2026"]
    assert by["15-05-2026"]["oh_value"] == 1
    assert pr["oh_pay"] == 1
    _reconciles(pr)


@pytest.mark.asyncio
async def test_optional_holiday_with_lop_not_credited(emp, holiday):
    eid = emp
    await db.leaves.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "leave_type": "Optional",
        "leave_split": "Full Day", "start_date": HOLIDAY, "end_date": HOLIDAY,
        "status": "approved", "is_lop": True,
    })
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    # With LOP → not credited as a payable holiday; falls through to holiday "H"
    assert by["15-05-2026"]["status"] == "H"
    assert pr["oh_pay"] == 0
    _reconciles(pr)


@pytest.mark.asyncio
async def test_summary_reconciles_from_rows(emp):
    eid = emp
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    _reconciles(pr)


@pytest.mark.asyncio
async def test_relieved_last_day_not_payable_reconciles(emp):
    eid = emp
    await db.employees.update_one({"id": eid}, {"$set": {
        "employee_status": "Inactive", "inactive_date": "2026-05-20", "last_day_payable": False,
    }})
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    # The relieving-day row carries the 1-day deduction as LOP, and the summary
    # still reconciles with the rows (no hidden subtraction).
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["20-05-2026"]["lop_value"] >= 1
    _reconciles(pr)


async def _att(eid, d, dec):
    await db.attendance.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "date": d,
        "check_in_24h": "09:30", "check_out_24h": "19:30", "total_hours_decimal": dec,
        "check_in": "09:30 AM", "check_out": "07:30 PM", "total_hours": f"{int(dec)}h",
    })


@pytest.mark.asyncio
async def test_unpaid_holiday_is_normal_working_day(emp):
    """is_paid=False holiday = normal working day: full hours -> P, NO extra pay."""
    eid = emp
    await db.holidays.insert_one({"id": str(uuid.uuid4()), "date": "2026-05-22", "name": "Unpaid Hol", "is_paid": False})
    await _att(eid, "2026-05-22", 10.0)  # full day (Support Staff full=9h)
    try:
        pr = await calculate_payroll_for_employee(eid, "2026-05")
        by = {r["date"]: r for r in pr["attendance_details"]}
        assert by["22-05-2026"]["status"] == "P", by["22-05-2026"]
        assert by["22-05-2026"]["extra_value"] == 0  # NO extra pay on a normal working day
        assert by["22-05-2026"]["is_holiday"] is False
        _reconciles(pr)
    finally:
        await db.holidays.delete_many({"date": "2026-05-22", "name": "Unpaid Hol"})


@pytest.mark.asyncio
async def test_weekoff_full_work_is_FD_and_excluded_from_payable(emp):
    """Full-day work on a Sunday -> FD + extra pay; extra pay NOT in Payable Days."""
    eid = emp
    await _att(eid, "2026-05-17", 10.0)  # Sunday, full hours
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["17-05-2026"]["status"] == "FD"
    assert by["17-05-2026"]["extra_value"] == 1
    assert by["17-05-2026"]["weekoff_value"] == 1
    assert pr["extra_pay"] >= 1
    _reconciles(pr)  # verifies extra_pay is excluded from final_payable_days


@pytest.mark.asyncio
async def test_approved_with_lop_full_leave_shows_code_not_lop(emp):
    """Approved leave WITH LOP must display the leave code (SF), not 'LOP'."""
    eid = emp
    await db.leaves.insert_one({
        "id": str(uuid.uuid4()), "employee_id": eid, "leave_type": "Sick",
        "leave_split": "Full Day", "start_date": "2026-05-19", "end_date": "2026-05-19",
        "status": "approved", "is_lop": True,
    })
    pr = await calculate_payroll_for_employee(eid, "2026-05")
    by = {r["date"]: r for r in pr["attendance_details"]}
    assert by["19-05-2026"]["status"] == "SF"      # leave code, NOT "LOP"
    assert by["19-05-2026"]["lop_value"] == 1        # deduction still applied internally
    assert by["19-05-2026"]["is_lop"] is True
    _reconciles(pr)
