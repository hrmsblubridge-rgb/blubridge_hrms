"""N04 Short Research Duration — weekly average acceptance tests (spec 2026-09-04).

Leave days are excluded from BOTH numerator and denominator. Absence (A/LOP) days
stay in the denominator at 0 minutes (user decision). Zero eligible days => 0 stars.
"""
import asyncio
import sys
from datetime import date

sys.path.insert(0, "/app/backend")

import brsf_stars  # noqa: E402

EMP = {"id": "n04-test-emp", "confirmation_date": None}


def _run(days, month="2026-08"):
    """days: {'YYYY-MM-DD': (status, research_minutes)}"""
    details = [{"date": f"{d[8:10]}-{d[5:7]}-{d[0:4]}", "status": v[0]} for d, v in days.items()]

    async def fake_payroll(emp_id, m, employee=None):
        return {"attendance_details": details}

    async def fake_research(emp_id, start, end):
        return {d: v[1] for d, v in days.items() if v[1]}

    class _Cursor:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class _Coll:
        def find(self, *a, **k):
            return _Cursor()

    class _DB:
        def __getattr__(self, name):
            return _Coll()

    orig = (brsf_stars.calculate_payroll_for_employee, brsf_stars._research_minutes, brsf_stars.db)
    brsf_stars.calculate_payroll_for_employee = fake_payroll
    brsf_stars._research_minutes = fake_research
    brsf_stars.db = _DB()
    try:
        out = asyncio.run(brsf_stars.compute_system_values(EMP, month))
    finally:
        (brsf_stars.calculate_payroll_for_employee, brsf_stars._research_minutes,
         brsf_stars.db) = orig
    return out["N04"], out["P05"]


# Aug 2026: 3rd=Mon .. 7th=Fri (week 1), 10th=Mon .. 14th=Fri (week 2)
W1 = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]


def _week1(n04):
    return next(c for c in n04["children"] if c["start"] == "2026-08-03")


def test_1_two_leaves_average_above_threshold():
    days = {W1[0]: ("PF", 0), W1[1]: ("PF", 0), W1[2]: ("P", 580),
            W1[3]: ("P", 590), W1[4]: ("P", 600)}
    n04, _ = _run(days)
    c = _week1(n04)
    assert c["applicable_days"] == 5 and c["leave_days"] == 2 and c["eligible_days"] == 3
    assert c["total_minutes"] == 1770 and c["avg_minutes"] == 590.0
    assert c["avg_hhmm"] == "09:50" and c["value"] == 0


def test_2_two_leaves_average_below_threshold():
    days = {W1[0]: ("PF", 0), W1[1]: ("SF", 0), W1[2]: ("P", 550),
            W1[3]: ("P", 560), W1[4]: ("P", 565)}
    c = _week1(_run(days)[0])
    assert c["eligible_days"] == 3 and c["total_minutes"] == 1675
    assert round(c["avg_minutes"], 2) == 558.33 and c["value"] == -1


def test_3_all_days_valid_leave_gives_zero():
    days = {W1[0]: ("PF", 0), W1[1]: ("PF", 0), W1[2]: ("SF", 0)}
    c = _week1(_run(days)[0])
    assert c["applicable_days"] == 3 and c["leave_days"] == 3
    assert c["eligible_days"] == 0 and c["avg_hhmm"] is None and c["value"] == 0


def test_5_exact_930_is_zero():
    days = {W1[0]: ("P", 570), W1[1]: ("P", 570)}
    assert _week1(_run(days)[0])["value"] == 0


def test_6_929_is_minus_one():
    days = {W1[0]: ("P", 569), W1[1]: ("P", 569)}
    c = _week1(_run(days)[0])
    assert c["avg_minutes"] == 569.0 and c["value"] == -1


def test_7_one_leave_divides_by_four():
    days = {W1[0]: ("PH", 0), W1[1]: ("P", 600), W1[2]: ("P", 600),
            W1[3]: ("P", 600), W1[4]: ("P", 600)}
    c = _week1(_run(days)[0])
    assert c["leave_days"] == 1 and c["eligible_days"] == 4
    assert c["total_minutes"] == 2400 and c["avg_minutes"] == 600.0 and c["value"] == 0


def test_8_partial_week_one_leave():
    days = {W1[0]: ("P", 580), W1[1]: ("EF", 0), W1[2]: ("P", 600)}
    c = _week1(_run(days)[0])
    assert c["applicable_days"] == 3 and c["eligible_days"] == 2
    assert c["total_minutes"] == 1180 and c["avg_minutes"] == 590.0 and c["value"] == 0


def test_9_absence_stays_in_denominator():
    """A / LOP is NOT a leave — it stays in the N04 denominator at 0 minutes."""
    days = {W1[0]: ("A", 0), W1[1]: ("P", 600), W1[2]: ("P", 600)}
    n04, p05 = _run(days)
    c = _week1(n04)
    assert c["absent_days"] == 1 and c["leave_days"] == 0 and c["eligible_days"] == 3
    assert c["avg_minutes"] == 400.0 and c["value"] == -1
    # P05 denominator untouched: absence excluded there
    p = next(x for x in p05["children"] if x["start"] == "2026-08-03")
    assert p["eligible_days"] == 2 and p["avg_minutes"] == 600.0 and p["value"] == 1


def test_10_zero_research_on_present_day_counts():
    days = {W1[0]: ("P", 0), W1[1]: ("P", 600), W1[2]: ("P", 600)}
    c = _week1(_run(days)[0])
    assert c["eligible_days"] == 3 and c["value"] == -1


def test_11_non_working_days_never_counted():
    days = {"2026-08-02": ("Su", 0), W1[0]: ("H", 0), W1[1]: ("P", 600), W1[2]: ("WO", 0)}
    c = _week1(_run(days)[0])
    assert c["applicable_days"] == 1 and c["eligible_days"] == 1 and c["value"] == 0


def test_12_parent_is_sum_of_weeks():
    days = {W1[0]: ("P", 400), W1[1]: ("P", 400),
            "2026-08-10": ("P", 600), "2026-08-11": ("P", 600)}
    n04, _ = _run(days)
    assert n04["value"] == -1
    days2 = dict(days)
    days2["2026-08-10"] = ("P", 100)
    days2["2026-08-11"] = ("P", 100)
    n04b, _ = _run(days2)
    assert n04b["value"] == -2


if __name__ == "__main__":
    import traceback
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception:
                fails += 1
                print("FAIL", name)
                traceback.print_exc()
    print("failures:", fails)
