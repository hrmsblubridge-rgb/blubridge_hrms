"""P01 Full Attendance — acceptance tests (spec 2026-09-10).

Any approved leave in the eligible window (full or half day, valid/invalid, LOP or not)
disqualifies the +2. Absence disqualifies too. P01 is only ever 0 or +2.
"""
import asyncio
import sys

sys.path.insert(0, "/app/backend")

import brsf_stars  # noqa: E402


def _run(days, month="2026-04", leaves=None, confirmation_date=None):
    """days: {'YYYY-MM-DD': (status, research_minutes)}
    leaves: list of (start_iso, end_iso, split, status, validity, is_lop)"""
    details = [{"date": f"{d[8:10]}-{d[5:7]}-{d[0:4]}", "status": v[0]} for d, v in days.items()]
    leave_docs = []
    for i, lv in enumerate(leaves or []):
        s, e, split, st, validity, lop = lv
        leave_docs.append({"id": f"lv{i}", "leave_type": "Preplanned", "leave_split": split,
                           "start_date": s, "end_date": e, "created_at": None, "reason": "",
                           "leave_validity": validity, "is_lop": lop, "status": st})

    async def fake_payroll(emp_id, m, employee=None):
        return {"attendance_details": details}

    async def fake_research(emp_id, start, end):
        return {d: v[1] for d, v in days.items() if v[1]}

    class _Cursor:
        def __init__(self, rows):
            self._rows = list(rows)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._rows:
                raise StopAsyncIteration
            return self._rows.pop(0)

    class _Coll:
        def __init__(self, rows):
            self._rows = rows

        def find(self, q=None, *a, **k):
            rows = self._rows
            if q and q.get("status") == "approved":
                rows = [r for r in rows if r.get("status") == "approved"]
            return _Cursor(rows)

    class _DB:
        def __getattr__(self, name):
            return _Coll(leave_docs if name == "leaves" else [])

    emp = {"id": "p01-test-emp", "confirmation_date": confirmation_date}
    orig = (brsf_stars.calculate_payroll_for_employee, brsf_stars._research_minutes, brsf_stars.db)
    brsf_stars.calculate_payroll_for_employee = fake_payroll
    brsf_stars._research_minutes = fake_research
    brsf_stars.db = _DB()
    try:
        return asyncio.run(brsf_stars.compute_system_values(emp, month))
    finally:
        (brsf_stars.calculate_payroll_for_employee, brsf_stars._research_minutes,
         brsf_stars.db) = orig


# April 2026: 01=Wed .. 04=Sat, 05=Sun, 06=Mon ..
ALL_PRESENT = {f"2026-04-{d:02d}": ("P", 600) for d in range(1, 31)
               if d not in (5, 12, 19, 26)}
FULL = ("Full Day", "approved", "valid", False)


def test_1_no_leave_gives_plus_two():
    out = _run(dict(ALL_PRESENT))
    assert out["P01"]["value"] == 2
    assert out["P01"]["note"] == "All applicable working days attended and no leave taken"


def test_2_one_paid_leave_stamped_present():
    """The reported bug: payroll still says "P" but an approved leave exists."""
    out = _run(dict(ALL_PRESENT), leaves=[("2026-04-13", "2026-04-13", *FULL)])
    assert out["P01"]["value"] == 0
    assert out["P01"]["note"] == "Leave taken on 13-04-2026"


def test_3_valid_leave_still_zero():
    out = _run(dict(ALL_PRESENT),
               leaves=[("2026-04-13", "2026-04-13", "Full Day", "approved", "valid", False)])
    assert out["P01"]["value"] == 0


def test_4_invalid_leave_still_zero():
    out = _run(dict(ALL_PRESENT),
               leaves=[("2026-04-13", "2026-04-13", "Full Day", "approved", "invalid", False)])
    assert out["P01"]["value"] == 0


def test_5_first_half_leave():
    out = _run(dict(ALL_PRESENT),
               leaves=[("2026-04-13", "2026-04-13", "First Half", "approved", "valid", False)])
    assert out["P01"]["value"] == 0


def test_6_second_half_leave():
    out = _run(dict(ALL_PRESENT),
               leaves=[("2026-04-13", "2026-04-13", "Second Half", "approved", "valid", False)])
    assert out["P01"]["value"] == 0


def test_7_three_leaves_screenshot_case():
    out = _run(dict(ALL_PRESENT), leaves=[("2026-04-01", "2026-04-01", *FULL),
                                          ("2026-04-13", "2026-04-13", *FULL),
                                          ("2026-04-23", "2026-04-23", *FULL)])
    assert out["P01"]["value"] == 0
    assert out["P01"]["note"] == "3 leave record(s) found during the eligible period"


def test_8_approved_no_lop_leave():
    out = _run(dict(ALL_PRESENT), leaves=[("2026-04-13", "2026-04-13", *FULL)])
    assert out["P01"]["value"] == 0


def test_9_rejected_leave_does_not_disqualify():
    out = _run(dict(ALL_PRESENT),
               leaves=[("2026-04-13", "2026-04-13", "Full Day", "rejected", "valid", False)])
    assert out["P01"]["value"] == 2


def test_10_pre_confirmation_leave_ignored():
    out = _run(dict(ALL_PRESENT), confirmation_date="2026-04-08",
               leaves=[("2026-04-01", "2026-04-01", *FULL)])
    assert out["P01"]["value"] == 2


def test_11_post_confirmation_leave_disqualifies():
    out = _run(dict(ALL_PRESENT), confirmation_date="2026-04-08",
               leaves=[("2026-04-13", "2026-04-13", *FULL)])
    assert out["P01"]["value"] == 0


def test_12_absence_disqualifies():
    days = dict(ALL_PRESENT)
    days["2026-04-13"] = ("A", 0)
    out = _run(days)
    assert out["P01"]["value"] == 0 and out["P01"]["note"] == "Absent on 13-04-2026"


def test_13_leave_status_code_disqualifies():
    days = dict(ALL_PRESENT)
    days["2026-04-13"] = ("PF", 0)
    out = _run(days)
    assert out["P01"]["value"] == 0


def test_14_multi_day_leave_counts_once():
    out = _run(dict(ALL_PRESENT), leaves=[("2026-04-13", "2026-04-15", *FULL)])
    assert out["P01"]["value"] == 0
    assert len(out["P01"]["children"]) == 3


def test_15_sunday_only_leave_does_not_disqualify():
    out = _run({**ALL_PRESENT, "2026-04-12": ("Su", 0)},
               leaves=[("2026-04-12", "2026-04-12", *FULL)])
    assert out["P01"]["value"] == 2


def test_16_no_attendance_data_is_zero():
    out = _run({})
    assert out["P01"]["value"] == 0


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
