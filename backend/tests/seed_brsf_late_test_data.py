"""Seed/cleanup TEST_N09_ records in the LOCAL test DB (BRSF late-arrival rule).
Usage: python seed_brsf_late_test_data.py [seed|cleanup]"""
import sys
import uuid

from pymongo import MongoClient

db = MongoClient("mongodb://localhost:27017")["test_database"]
TAG = "TEST_N09_"

# (date YYYY-MM-DD, punch HH:MM, late request (created_at iso, status) | None, first-half leave status | None)
SEPT_EXAMPLE = [
    ("2026-09-03", "10:20", ("2026-09-03T09:00:00+05:30", "approved"), None),   # excluded
    ("2026-09-07", "10:30", ("2026-09-07T09:45:00+05:30", "approved"), None),   # count
    ("2026-09-10", "10:15", None, None),                                         # count
    ("2026-09-14", "10:25", None, "pending"),                                    # excluded (FH)
    ("2026-09-18", "10:15", None, None),                                         # not late (10:30)
    ("2026-09-21", "10:45", ("2026-09-21T09:00:00+05:30", "rejected"), None),   # count
    ("2026-09-24", "10:50", None, "approved"),                                   # excluded (FH)
    ("2026-09-25", "10:20", None, None),                                         # not late
    ("2026-09-28", "10:40", ("2026-09-28T10:00:00+05:30", "approved"), None),   # count
]
THREE_ONLY = [
    ("2026-09-08", "10:20", None, None),
    ("2026-09-09", "10:20", None, None),
    ("2026-09-22", "10:45", None, None),
    ("2026-09-23", "10:45", ("2026-09-22T18:00:00+05:30", "pending"), None),    # earlier-day request → excluded
    ("2026-09-29", "10:31", ("2026-09-29T09:29:59+05:30", "pending"), "rejected"),  # FH rejected, timely request → excluded
]


def cleanup():
    ids = [e["id"] for e in db.employees.find({"full_name": {"$regex": f"^{TAG}"}}, {"id": 1})]
    for c in ("attendance", "leaves", "late_requests", "brsf_star_lines", "brsf_star_audit", "notifications"):
        db[c].delete_many({"employee_id": {"$in": ids}})
    db.employees.delete_many({"full_name": {"$regex": f"^{TAG}"}})
    db.brsf_month_locks.delete_many({"year": 2026, "month": 9})  # local test DB only
    print("cleaned", len(ids))


def _emp(key):
    eid = str(uuid.uuid4())
    db.employees.insert_one({
        "id": eid, "full_name": f"{TAG}{key}", "team": "QA", "department": "Research Unit",
        "employment_type": "Full-time", "confirmation_date": "2025-01-01", "date_of_joining": "2024-06-01",
        "employee_status": "Active", "is_deleted": False, "official_email": f"{key}@example.invalid",
        "custom_employee_id": f"{TAG}{key}", "attendance_tracking_enabled": False,
    })
    return eid


def _load(eid, key, rows):
    for ymd, punch, lr, fh in rows:
        y, m, d = ymd.split("-")
        h, mi = map(int, punch.split(":"))
        db.attendance.insert_one({
            "id": str(uuid.uuid4()), "employee_id": eid, "emp_name": f"{TAG}{key}", "team": "QA",
            "department": "Research Unit", "date": f"{d}-{m}-{y}", "check_in_24h": punch,
            "check_in": f"{(h % 12) or 12:02d}:{mi:02d} {'PM' if h >= 12 else 'AM'}", "status": "Late Login",
        })
        if lr:
            db.late_requests.insert_one({
                "id": str(uuid.uuid4()), "employee_id": eid, "emp_name": f"{TAG}{key}", "team": "QA",
                "department": "Research Unit", "date": ymd, "reason": "test late request",
                "status": lr[1], "created_at": lr[0],
            })
        if fh:
            db.leaves.insert_one({
                "id": str(uuid.uuid4()), "employee_id": eid, "emp_name": f"{TAG}{key}", "team": "QA",
                "department": "Research Unit", "leave_type": "Sick", "leave_split": "First Half",
                "start_date": ymd, "end_date": ymd, "duration": "0.5 day(s)", "reason": "test first half",
                "status": fh, "created_at": f"{ymd}T07:00:00+05:30",
            })


def seed():
    cleanup()
    a = _emp("example")
    _load(a, "example", SEPT_EXAMPLE)
    b = _emp("three")
    _load(b, "three", THREE_ONLY)
    print("example", a)
    print("three", b)


if __name__ == "__main__":
    cleanup() if (sys.argv[1:] or ["seed"])[0] == "cleanup" else seed()
