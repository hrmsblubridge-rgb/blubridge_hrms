"""Seed/cleanup TEST_PL_ records in the LOCAL test DB. Usage: python seed_paid_leave_test_data.py [seed|cleanup]"""
import hashlib
import sys
import uuid
from datetime import datetime, timezone

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["test_database"]
TAG = "TEST_PL_"
PWD = hashlib.sha256("Test@123".encode()).hexdigest()

EMPS = [
    ("fulltime2", "Full-time", "2025-01-01", 2.0, "Active"),
    ("fulltime0", "Full-time", "2025-01-01", 0.0, "Active"),
    ("halfbal", "Full-time", "2025-01-01", 0.5, "Active"),
    ("intern", "Intern", None, 0.0, "Active"),
    ("advzero", "Full-time", "2025-01-01", 0.0, "Active"),
    ("unconfirmed", "Full-time", None, 0.0, "Active"),
    ("inactive", "Full-time", "2025-01-01", 1.0, "Inactive"),
    ("negative", "Full-time", "2025-01-01", -1.0, "Active"),
]


def cleanup():
    ids = [e["id"] for e in db.employees.find({"full_name": {"$regex": f"^{TAG}"}}, {"id": 1})]
    for coll in ("leaves", "paid_leave_history", "leave_change_history", "notifications"):
        db[coll].delete_many({"employee_id": {"$in": ids}})
    db.users.delete_many({"username": {"$regex": f"^{TAG.lower()}"}})
    db.employees.delete_many({"full_name": {"$regex": f"^{TAG}"}})
    db.paid_leave_generation.delete_many({"test_tag": TAG})
    print("cleaned", len(ids))


def seed():
    cleanup()
    for key, etype, conf, bal, status in EMPS:
        eid = str(uuid.uuid4())
        db.employees.insert_one({
            "id": eid, "full_name": f"{TAG}{key}", "team": "QA", "department": "QA",
            "employment_type": etype, "confirmation_date": conf, "date_of_joining": "2024-06-01",
            "available_paid_leave": bal, "employee_status": status, "is_deleted": False,
            "official_email": f"{key}@example.invalid", "custom_employee_id": f"{TAG}{key}",
            "attendance_tracking_enabled": False,
        })
        db.users.insert_one({
            "id": str(uuid.uuid4()), "username": f"{TAG.lower()}{key}", "email": f"{key}@example.invalid",
            "password_hash": PWD, "name": f"{TAG}{key}", "role": "employee", "employee_id": eid,
            "onboarding_status": "completed", "is_first_login": False, "is_active": True,
            "password_updated_at": datetime.now(timezone.utc).isoformat(),
        })
        print(key, eid)


if __name__ == "__main__":
    (cleanup if (sys.argv[1:] or ["seed"])[0] == "cleanup" else seed)()
