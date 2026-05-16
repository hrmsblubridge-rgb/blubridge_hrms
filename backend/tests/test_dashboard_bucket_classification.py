"""Regression tests for Dashboard Attendance bucket classification.

Bug fixed (CHANGELOG 2026-05-14):
  The engine writes status=Loss of Pay + lop_reason="Late login..." for late
  arrivals, and the same fields for early-out / short-hours days. The dashboard
  classifier `classify_attendance_bucket` only inspected `is_lop` and so
  bucketed BOTH cases as `early_out`. A "Late Login but completed full hours"
  employee therefore appeared in BOTH the Late Login tile AND the Early Out
  tile, violating mutual exclusivity.

  Fix: when `is_lop` is true, distinguish by `lop_reason` — if the LOP is a
  Late Login, return `completed`, not `early_out`. Late Login secondary flag
  continues to pick it up.

Same classifier mirror lives in `/app/frontend/src/pages/Dashboard.js` —
keep both in sync.
"""
import pytest
import sys
import importlib.util

# Import the classifier directly from server.py without booting the app.
spec = importlib.util.spec_from_file_location("_srv", "/app/backend/server.py")


@pytest.fixture(scope="module")
def classifiers():
    """Pull `classify_attendance_bucket` and `is_late_login_record` from
    server.py by parsing only those functions — avoid full app bootstrap."""
    src = open("/app/backend/server.py").read()
    # Carve out a minimal AttendanceStatus stub + the two functions
    ns = {}
    exec(
        """
class AttendanceStatus:
    PRESENT = "Present"; LATE_LOGIN = "Late Login"; EARLY_OUT = "Early Out"
    LOSS_OF_PAY = "Loss of Pay"; NOT_LOGGED = "Not Logged"; SUNDAY = "Sunday"
    WORKED_ON_SUNDAY = "Worked on Sunday"
""", ns
    )
    # Extract the two functions verbatim from server.py
    for fname in ("classify_attendance_bucket", "is_late_login_record"):
        start = src.find(f"def {fname}(")
        assert start != -1, f"{fname} not found"
        # Find end — next top-level def or @api_router
        rest = src[start:]
        next_top = min(
            (i for i in (rest.find("\ndef ", 1), rest.find("\n@api_router", 1), rest.find("\n@app.", 1)) if i > 0),
            default=-1,
        )
        block = rest if next_top == -1 else rest[:next_top]
        exec(block, ns)
    return ns["classify_attendance_bucket"], ns["is_late_login_record"]


CASES = [
    # (label, record, expected_bucket, expected_late_flag)
    ("Late + completed full hours",
     {"check_in": "11:38 AM", "check_out": "10:40 PM", "status": "Loss of Pay",
      "is_lop": True, "lop_reason": "Late login by 98 minute(s)..."},
     "completed", True),
    ("On-time + insufficient hours",
     {"check_in": "10:00 AM", "check_out": "02:00 PM", "status": "Loss of Pay",
      "is_lop": True, "lop_reason": "Early out / short hours by 240 minute(s)..."},
     "early_out", False),
    ("On-time + full hours",
     {"check_in": "10:00 AM", "check_out": "08:00 PM", "status": "Present",
      "is_lop": False, "lop_reason": None},
     "completed", False),
    ("No punch",
     {"status": "Not Logged"},
     "no_login", False),
    ("Currently logged in",
     {"check_in": "09:55 AM", "status": "Login"},
     "logged_in", False),
    ("Late + still logged in (no OUT yet)",
     {"check_in": "11:30 AM", "status": "Login"},
     "logged_in", False),
    ("Late + short hours (engine sets late lop_reason first)",
     {"check_in": "11:30 AM", "check_out": "03:30 PM", "status": "Loss of Pay",
      "is_lop": True, "lop_reason": "Late login by 90 minute(s)..."},
     "completed", True),
    ("Worked on Sunday",
     {"check_in": "10:00 AM", "check_out": "06:00 PM",
      "status": "Worked on Sunday", "is_lop": False},
     "completed", False),
]


@pytest.mark.parametrize("label,rec,expected_bucket,expected_late", CASES,
                         ids=[c[0] for c in CASES])
def test_bucket_and_late_flag(classifiers, label, rec, expected_bucket, expected_late):
    classify, is_late = classifiers
    actual_bucket = classify(rec)
    actual_late = is_late(rec)
    assert actual_bucket == expected_bucket, f"bucket: expected {expected_bucket!r}, got {actual_bucket!r}"
    assert actual_late == expected_late, f"late_flag: expected {expected_late}, got {actual_late}"


def test_no_overlap_between_early_out_and_late_login(classifiers):
    """The MUTUAL EXCLUSIVITY rule: no single record can be classified as
    both `early_out` AND `late_login`. (Late-but-completed records bucket as
    `completed` while still raising the late_login flag — that's allowed.)"""
    classify, is_late = classifiers
    for label, rec, _eb, _el in CASES:
        bucket = classify(rec)
        late_flag = is_late(rec)
        # Rule: if bucket=='early_out' then late_flag must be False.
        if bucket == "early_out":
            assert not late_flag, f"{label!r} ended up in BOTH early_out AND late_login — violates mutual exclusivity"
