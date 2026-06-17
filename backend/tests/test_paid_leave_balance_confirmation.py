"""Regression tests for Paid Leave balance vs Confirmation Date.

Covers the Attendance "Remaining Leaves" fix:
- Full-time: accrues 1/month from Confirmation Date (not DOJ, not update time).
- Future Confirmation Date -> 0 eligible (Case 1).
- Approved Paid Leave AFTER confirmation deducted (Case 2).
- Intern -> always 0 (Case 3).
- Paid Leave BEFORE confirmation date NOT deducted (Case 5).

These exercise the pure backend helper `calculate_paid_leave_balance`
(the single source of truth the API + Attendance modal consume), using a
throwaway employee + throwaway leaves that are fully cleaned up afterwards.
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server  # noqa: E402
from server import calculate_paid_leave_balance, db  # noqa: E402


def _iso(y, m, d):
    return date(y, m, d).strftime("%Y-%m-%d")


@pytest.fixture
async def temp_emp():
    """Create a throwaway employee; yield id; hard-delete it + its leaves."""
    emp_id = str(uuid.uuid4())
    created_leaves = []

    async def make(employment_type, date_of_joining, confirmation_date):
        await db.employees.delete_one({"id": emp_id})
        await db.employees.insert_one({
            "id": emp_id,
            "custom_employee_id": f"TST-{emp_id[:6]}",
            "full_name": "PaidLeave Test",
            "employment_type": employment_type,
            "date_of_joining": date_of_joining,
            "confirmation_date": confirmation_date,
            "is_deleted": False,
        })
        return emp_id

    async def add_leave(start, end, status="approved", leave_type="Paid Leave", split="Full Day"):
        lid = str(uuid.uuid4())
        await db.leaves.insert_one({
            "id": lid,
            "employee_id": emp_id,
            "leave_type": leave_type,
            "status": status,
            "start_date": start,
            "end_date": end,
            "leave_split": split,
        })
        created_leaves.append(lid)
        return lid

    yield make, add_leave

    await db.employees.delete_one({"id": emp_id})
    if created_leaves:
        await db.leaves.delete_many({"id": {"$in": created_leaves}})


@pytest.mark.asyncio
async def test_fulltime_accrues_from_confirmation_not_doj(temp_emp):
    make, _ = temp_emp
    eid = await make("Full-time", _iso(2026, 1, 9), _iso(2026, 6, 8))
    # Reference 2026-06-17 -> only June counts -> earned 1 (NOT from Jan DOJ).
    bal = await calculate_paid_leave_balance(eid, date(2026, 6, 17))
    assert bal["earned"] == 1.0, bal
    assert bal["used"] == 0.0, bal
    assert bal["balance"] == 1.0, bal


@pytest.mark.asyncio
async def test_case1_future_confirmation_date_zero(temp_emp):
    make, _ = temp_emp
    eid = await make("Full-time", _iso(2026, 1, 9), _iso(2099, 1, 1))
    bal = await calculate_paid_leave_balance(eid, date(2026, 6, 17))
    assert bal["earned"] == 0.0, bal
    assert bal["balance"] == 0.0, bal


@pytest.mark.asyncio
async def test_case2_approved_paid_after_confirmation_deducted(temp_emp):
    make, add_leave = temp_emp
    eid = await make("Full-time", _iso(2026, 1, 1), _iso(2026, 3, 1))
    # As of 2026-06-17: earned = Mar..Jun = 4.
    await add_leave(_iso(2026, 4, 10), _iso(2026, 4, 10))  # 1 approved Paid day after conf
    bal = await calculate_paid_leave_balance(eid, date(2026, 6, 17))
    assert bal["earned"] == 4.0, bal
    assert bal["used"] == 1.0, bal
    assert bal["balance"] == 3.0, bal


@pytest.mark.asyncio
async def test_case3_intern_always_zero(temp_emp):
    make, add_leave = temp_emp
    eid = await make("Intern", _iso(2026, 1, 1), None)
    await add_leave(_iso(2026, 5, 5), _iso(2026, 5, 5))  # even if a paid leave exists
    bal = await calculate_paid_leave_balance(eid, date(2026, 6, 17))
    assert bal["earned"] == 0.0, bal
    assert bal["used"] == 0.0, bal
    assert bal["balance"] == 0.0, bal


@pytest.mark.asyncio
async def test_case5_paid_leave_before_confirmation_not_deducted(temp_emp):
    make, add_leave = temp_emp
    eid = await make("Full-time", _iso(2026, 1, 1), _iso(2026, 6, 8))
    # Approved Paid Leave BEFORE confirmation (08-Jun) -> must NOT be deducted.
    await add_leave(_iso(2026, 4, 15), _iso(2026, 4, 15))
    bal = await calculate_paid_leave_balance(eid, date(2026, 6, 17))
    assert bal["earned"] == 1.0, bal  # June only
    assert bal["used"] == 0.0, bal  # pre-confirmation leave ignored
    assert bal["balance"] == 1.0, bal


@pytest.mark.asyncio
async def test_straddling_leave_counts_only_after_confirmation(temp_emp):
    make, add_leave = temp_emp
    eid = await make("Full-time", _iso(2026, 1, 1), _iso(2026, 6, 8))
    # Leave 2026-06-06 -> 2026-06-10 straddles confirmation 06-08:
    # only 08,09,10 = 3 days on/after eligibility should count.
    await add_leave(_iso(2026, 6, 6), _iso(2026, 6, 10))
    bal = await calculate_paid_leave_balance(eid, date(2026, 6, 17))
    assert bal["earned"] == 1.0, bal
    assert bal["used"] == 3.0, bal
    assert bal["balance"] == -2.0 or bal["balance"] == round(1.0 - 3.0, 1), bal
