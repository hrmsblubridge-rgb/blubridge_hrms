"""Seed/cleanup TEST_DL_ records in the LOCAL test DB for dashboard leave-list tests. Usage: python seed_dashboard_leave_test_data.py [seed|cleanup] [YYYY-MM-DD]"""
import sys
import uuid
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]
TAG = "TEST_DL_"
IST = timezone(timedelta(hours=5, minutes=30))

# key -> list of (split, status, leave_type, reason)
CASES = {
    "nologin": [],
    "pending_full": [("Full Day", "pending", "Sick", "Fever")],
    "approved_full": [("Full Day", "approved", "Preplanned", "Personal work")],
    "rejected_full": [("Full Day", "rejected", "Sick", "Rejected reason")],
    "cancelled_full": [("Full Day", "cancelled", "Emergency", "Cancelled reason")],
    "first_half_pending": [("First Half", "pending", "Sick", "Half pending reason")],
    "second_half_approved": [("Second Half", "approved", "Preplanned", "Half approved reason")],
    "rejected_plus_pending": [("Full Day", "rejected", "Sick", "Old rejected"), ("Full Day", "pending", "Emergency", "Valid pending")],
    "punched_in": [("Full Day", "approved", "Preplanned", "Worked anyway")],
}


def cleanup():
    ids = [e["id"] for e in db.employees.find({"full_name": {"$regex": f"^{TAG}"}}, {"id": 1})]
    db.leaves.delete_many({"employee_id": {"$in": ids}})
    db.attendance.delete_many({"employee_id": {"$in": ids}})
    db.employees.delete_many({"full_name": {"$regex": f"^{TAG}"}})
    print("cleaned", len(ids))


def seed(ymd):
    cleanup()
    dmy = datetime.strptime(ymd, "%Y-%m-%d").strftime("%d-%m-%Y")
    for key, leaves in CASES.items():
        eid = str(uuid.uuid4())
        db.employees.insert_one({
            "id": eid, "full_name": f"{TAG}{key}", "team": "QA", "department": "QA",
            "employment_type": "Full-time", "date_of_joining": "2024-06-01",
            "employee_status": "Active", "is_deleted": False,
            "official_email": f"{key}@example.invalid", "custom_employee_id": f"{TAG}{key}",
        })
        for split, status, ltype, reason in leaves:
            db.leaves.insert_one({
                "id": str(uuid.uuid4()), "employee_id": eid, "emp_name": f"{TAG}{key}",
                "team": "QA", "department": "QA", "leave_type": ltype, "leave_split": split,
                "start_date": ymd, "end_date": ymd, "duration": "1 day(s)", "reason": reason,
                "status": status, "created_at": datetime.now(IST).isoformat(),
            })
        if key == "punched_in":
            db.attendance.insert_one({
                "id": str(uuid.uuid4()), "employee_id": eid, "emp_name": f"{TAG}{key}",
                "team": "QA", "department": "QA", "date": dmy, "check_in": "10:00 AM",
                "check_in_24h": "10:00", "status": "Login",
            })
        print(key, eid)


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["seed"])[0]
    if cmd == "cleanup":
        cleanup()
    else:
        seed(sys.argv[2] if len(sys.argv) > 2 else datetime.now(IST).strftime("%Y-%m-%d"))
