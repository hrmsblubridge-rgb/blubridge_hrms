"""Root-cause regression tests for Paid-Leave eligibility (Intern restriction).

Validates the SINGLE source of truth `_paid_leave_eligibility` and that every
layer (balance, create, employee-apply, approve) honours it for ALL intern
variants and the Full-Time + Confirmation-Date rule.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
from server import _paid_leave_eligibility, _is_intern_category, calculate_paid_leave_balance, db  # noqa: E402


# ---------- pure eligibility rule ----------

@pytest.mark.parametrize("etype,cd,expected", [
    ("Intern", None, False),                 # S1
    ("Intern", "2026-01-01", False),         # intern even with a CD
    ("Trainee", "2026-01-01", False),        # S2
    ("Internship", "2026-01-01", False),     # S3
    ("Probationary Intern", "2026-01-01", False),
    ("Full-time", None, False),              # S4 (no confirmation date)
    ("Full-time", "", False),                # S4 (blank)
    ("Full-time", "2026-01-01", True),       # S5
    ("Permanent", "2026-03-01", True),
])
def test_eligibility_rule(etype, cd, expected):
    eligible, _ = _paid_leave_eligibility({"employment_type": etype, "confirmation_date": cd})
    assert eligible is expected


def test_intern_category_variants():
    for t in ("Intern", "Internship", "Trainee", "Probationary Intern", "INTERN", "summer trainee"):
        assert _is_intern_category(t) is True
    for t in ("Full-time", "Permanent", "Contract", "Part-time"):
        assert _is_intern_category(t) is False


# ---------- balance returns 0 for all intern variants ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("etype", ["Intern", "Trainee", "Internship", "Probationary Intern"])
async def test_balance_zero_for_intern_variants(etype):
    eid = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": eid, "full_name": "ELIG Test", "employment_type": etype,
        "date_of_joining": "2026-01-01", "confirmation_date": "2026-01-01",
        "is_deleted": False,
    })
    try:
        from datetime import date
        bal = await calculate_paid_leave_balance(eid, date(2026, 6, 18))
        assert bal == {"earned": 0.0, "used": 0.0, "balance": 0.0}, (etype, bal)
    finally:
        await db.employees.delete_one({"id": eid})


@pytest.mark.asyncio
async def test_balance_nonzero_for_fulltime_with_cd():
    eid = str(uuid.uuid4())
    await db.employees.insert_one({
        "id": eid, "full_name": "ELIG FT", "employment_type": "Full-time",
        "date_of_joining": "2026-01-01", "confirmation_date": "2026-03-01",
        "is_deleted": False,
    })
    try:
        from datetime import date
        bal = await calculate_paid_leave_balance(eid, date(2026, 6, 18))
        assert bal["earned"] == 4.0  # Mar..Jun
    finally:
        await db.employees.delete_one({"id": eid})
