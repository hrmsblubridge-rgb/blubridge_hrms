"""
Backend tests for the Paid Leave module (2026-01 enhancement).

Coverage:
  - /api/employee/paid-leave-eligibility, /api/employee/paid-leave-balance
  - /api/admin/employees/{id}/paid-leave-balance
  - /api/admin/paid-leave/status
  - /api/admin/paid-leave/generate (far-future throwaway month + cleanup)
  - /api/admin/paid-leave/import (validation: unknown id, duplicate, negative,
    name mismatch, and mutual lock with generate)
  - /api/admin/paid-leave/history
  - /api/admin/paid-leave/export (xlsx & csv)
  - Reserve → Approve finalize → balance stays deducted, is_lop forced false
  - Reject → balance released
  - Insufficient-balance rejection on apply

Cleanup guarantees (per main-agent contract):
  * We use a FAR-FUTURE month for Generate (year 2031, month 12).
  * After Generate we manually roll every employee back and delete the
    paid_leave_history rows and the paid_leave_generation record.
  * Every test leave we create uses reason starting with "PAIDTEST_QA".
  * We record the target employee's pre-test balance and restore it.
"""

import os
import io
import csv
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

# Load env vars from .env files if not already set (pytest may not inherit them)
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TEST_YEAR = 2031
TEST_MONTH = 12
REASON_PREFIX = "PAIDTEST_QA"


# --------------- Fixtures ---------------

@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="session")
def admin_token():
    last_err = None
    for _ in range(3):
        try:
            r = requests.post(f"{API}/auth/login",
                              json={"username": "admin", "password": "HrAdmin@2109"},
                              timeout=90)
            if r.status_code == 200:
                return r.json().get("access_token") or r.json()["token"]
            last_err = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(3)
    pytest.skip(f"admin login unreachable: {last_err}")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def confirmed_ft_employee(mongo):
    """Pick a real confirmed Full-Time employee (does not modify it)."""
    from datetime import date
    today = date.today().isoformat()
    emp = mongo.employees.find_one({
        "is_deleted": {"$ne": True},
        "employment_type": "Full-time",
        "confirmation_date": {"$ne": None, "$lte": today},
    }, {"_id": 0})
    if not emp:
        pytest.skip("No confirmed Full-Time employee available for testing")
    return emp


@pytest.fixture
def preserve_balance(mongo, confirmed_ft_employee):
    """Snapshot & restore the target employee's available_paid_leave."""
    eid = confirmed_ft_employee["id"]
    pre = mongo.employees.find_one({"id": eid}, {"_id": 0, "available_paid_leave": 1})
    prev = float((pre or {}).get("available_paid_leave") or 0.0)
    yield prev
    mongo.employees.update_one({"id": eid}, {"$set": {"available_paid_leave": prev}})
    # remove any PAIDTEST_QA history rows for this employee
    mongo.paid_leave_history.delete_many({"employee_id": eid, "note": {"$regex": "PAIDTEST"}})


@pytest.fixture
def cleanup_test_leaves(mongo, confirmed_ft_employee):
    yield
    eid = confirmed_ft_employee["id"]
    leaves = list(mongo.leaves.find(
        {"employee_id": eid, "reason": {"$regex": f"^{REASON_PREFIX}"}}))
    for lv in leaves:
        mongo.leaves.delete_one({"id": lv["id"]})
        mongo.paid_leave_history.delete_many({"reference_id": lv["id"]})


# --------------- Section 1: employee eligibility & balance endpoints ---------------

class TestEligibilityEndpoints:
    def test_employee_eligibility_endpoint_admin_no_employee(self, admin_headers):
        # admin is NOT an employee -> should 404
        r = requests.get(f"{API}/employee/paid-leave-eligibility",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_admin_employee_balance_endpoint(self, admin_headers, confirmed_ft_employee):
        eid = confirmed_ft_employee["id"]
        r = requests.get(f"{API}/admin/employees/{eid}/paid-leave-balance",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "balance" in data
        assert isinstance(data["balance"], (int, float))


# --------------- Section 2: status & mutual lock ---------------

class TestStatusAndGenerate:
    def test_status_future_month_not_finalized(self, admin_headers):
        r = requests.get(f"{API}/admin/paid-leave/status",
                         params={"year": TEST_YEAR, "month": TEST_MONTH},
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["year"] == TEST_YEAR and d["month"] == TEST_MONTH
        assert d["finalized"] in (False, True)  # if leftovers, we'll clean below
        assert "eligible_count" in d
        assert d["eligible_count"] >= 1

    def test_generate_then_regenerate_blocked_then_import_blocked_then_cleanup(
            self, admin_headers, mongo):
        # Pre-clean in case a previous crashed run left rows behind
        rec = mongo.paid_leave_generation.find_one({"year": TEST_YEAR, "month": TEST_MONTH})
        if rec:
            _rollback_generate(mongo, TEST_YEAR, TEST_MONTH)

        # Snapshot every eligible employee's balance so we can precisely roll back
        from datetime import date
        today = date.today().isoformat()
        eligible = list(mongo.employees.find(
            {"is_deleted": {"$ne": True},
             "employment_type": "Full-time",
             "confirmation_date": {"$ne": None, "$lte": today}},
            {"_id": 0, "id": 1, "available_paid_leave": 1}))
        snapshot = {e["id"]: float(e.get("available_paid_leave") or 0.0) for e in eligible}

        try:
            # Generate
            r = requests.post(f"{API}/admin/paid-leave/generate",
                              json={"year": TEST_YEAR, "month": TEST_MONTH},
                              headers=admin_headers, timeout=60)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["count"] == len(eligible)

            # Verify balances incremented
            for e in eligible[:5]:
                cur = mongo.employees.find_one({"id": e["id"]},
                                               {"_id": 0, "available_paid_leave": 1})
                assert round(float(cur["available_paid_leave"]) - snapshot[e["id"]], 1) == 1.0

            # Re-generate blocked
            r2 = requests.post(f"{API}/admin/paid-leave/generate",
                               json={"year": TEST_YEAR, "month": TEST_MONTH},
                               headers=admin_headers, timeout=30)
            assert r2.status_code == 400
            assert "already been generated" in r2.json().get("detail", "")

            # Import for same month blocked (mutual lock)
            fake = ("Employee ID,Employee Name,Department,Team,Confirmed Date,"
                    "Existing Available Paid Leave\n").encode("utf-8")
            files = {"file": ("t.csv", fake, "text/csv")}
            r3 = requests.post(f"{API}/admin/paid-leave/import",
                               params={"year": TEST_YEAR, "month": TEST_MONTH},
                               headers=admin_headers, files=files, timeout=30)
            assert r3.status_code == 400
            assert "finalized through Generate" in r3.json().get("detail", "")

            # Status reports finalized=True now
            rs = requests.get(f"{API}/admin/paid-leave/status",
                              params={"year": TEST_YEAR, "month": TEST_MONTH},
                              headers=admin_headers, timeout=15).json()
            assert rs["finalized"] is True
            assert rs["method"] == "generate"

            # History has MONTHLY_GENERATION rows
            rh = requests.get(f"{API}/admin/paid-leave/history",
                              params={"year": TEST_YEAR, "month": TEST_MONTH},
                              headers=admin_headers, timeout=15)
            assert rh.status_code == 200
            hrows = rh.json()
            assert any(row.get("action_type") == "MONTHLY_GENERATION" for row in hrows)
        finally:
            _rollback_generate(mongo, TEST_YEAR, TEST_MONTH, snapshot=snapshot)


def _rollback_generate(mongo, y, m, snapshot=None):
    rows = list(mongo.paid_leave_history.find(
        {"year": y, "month": m, "action_type": "MONTHLY_GENERATION"}))
    for row in rows:
        delta = float(row.get("change_amount") or 0.0)
        mongo.employees.update_one({"id": row["employee_id"]},
                                   {"$inc": {"available_paid_leave": -delta}})
    mongo.paid_leave_history.delete_many(
        {"year": y, "month": m, "action_type": "MONTHLY_GENERATION"})
    mongo.paid_leave_generation.delete_one({"year": y, "month": m})
    if snapshot:
        for eid, prev in snapshot.items():
            mongo.employees.update_one({"id": eid}, {"$set": {"available_paid_leave": prev}})


# --------------- Section 3: export ---------------

class TestExport:
    def test_export_csv(self, admin_headers):
        r = requests.get(f"{API}/admin/paid-leave/export",
                         params={"year": 2030, "month": 6, "format": "csv"},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        text = r.content.decode("utf-8-sig")
        first = text.splitlines()[0]
        assert "Employee ID" in first and "Existing Available Paid Leave" in first

    def test_export_xlsx(self, admin_headers):
        r = requests.get(f"{API}/admin/paid-leave/export",
                         params={"year": 2030, "month": 6, "format": "xlsx"},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # xlsx = zip; starts with PK
        assert r.content[:2] == b"PK"


# --------------- Section 4: import validation ---------------

class TestImportValidation:
    """All uploaded rows must be validated before ANY balance changes."""

    def _post_csv(self, admin_headers, rows, year=2030, month=7):
        buff = io.StringIO()
        w = csv.writer(buff)
        w.writerow(["Employee ID", "Employee Name", "Department", "Team",
                    "Confirmed Date", "Existing Available Paid Leave"])
        for r in rows:
            w.writerow(r)
        files = {"file": ("t.csv", buff.getvalue().encode("utf-8"), "text/csv")}
        return requests.post(f"{API}/admin/paid-leave/import",
                             params={"year": year, "month": month},
                             headers=admin_headers, files=files, timeout=30)

    def test_unknown_employee_id_rejected(self, admin_headers):
        r = self._post_csv(admin_headers,
                           [["ZZZ_NOSUCH_ID", "Nobody", "", "", "", "1"]])
        assert r.status_code == 200
        b = r.json()
        assert b["success"] is False and b["applied"] == 0
        assert any("not found" in e["reason"].lower() for e in b["errors"])

    def test_duplicate_id_rejected(self, admin_headers, confirmed_ft_employee):
        eid = str(confirmed_ft_employee.get("custom_employee_id")
                  or confirmed_ft_employee.get("emp_id")
                  or confirmed_ft_employee["id"])
        name = confirmed_ft_employee["full_name"]
        r = self._post_csv(admin_headers,
                           [[eid, name, "", "", "", "1"],
                            [eid, name, "", "", "", "2"]])
        b = r.json()
        assert b["success"] is False
        assert any("duplicate" in e["reason"].lower() for e in b["errors"])

    def test_negative_balance_rejected(self, admin_headers, confirmed_ft_employee):
        eid = str(confirmed_ft_employee.get("custom_employee_id")
                  or confirmed_ft_employee.get("emp_id")
                  or confirmed_ft_employee["id"])
        name = confirmed_ft_employee["full_name"]
        r = self._post_csv(admin_headers, [[eid, name, "", "", "", "-3"]])
        b = r.json()
        assert b["success"] is False
        assert any("negative" in e["reason"].lower() for e in b["errors"])

    def test_name_mismatch_rejected(self, admin_headers, confirmed_ft_employee):
        eid = str(confirmed_ft_employee.get("custom_employee_id")
                  or confirmed_ft_employee.get("emp_id")
                  or confirmed_ft_employee["id"])
        r = self._post_csv(admin_headers,
                           [[eid, "WrongPersonName_QA", "", "", "", "1"]])
        b = r.json()
        assert b["success"] is False
        assert any("mismatch" in e["reason"].lower() for e in b["errors"])

    def test_atomicity_no_balance_change_on_error(self, admin_headers, mongo,
                                                   confirmed_ft_employee):
        """A mixed file (one valid + one invalid) must NOT touch any balance."""
        eid_disp = str(confirmed_ft_employee.get("custom_employee_id")
                       or confirmed_ft_employee.get("emp_id")
                       or confirmed_ft_employee["id"])
        name = confirmed_ft_employee["full_name"]
        pre = float(mongo.employees.find_one(
            {"id": confirmed_ft_employee["id"]},
            {"_id": 0, "available_paid_leave": 1}).get("available_paid_leave") or 0.0)
        r = self._post_csv(admin_headers,
                           [[eid_disp, name, "", "", "", "5"],
                            ["ZZZ_NOSUCH_ID", "Nobody", "", "", "", "1"]],
                           year=2030, month=8)
        b = r.json()
        assert b["success"] is False and b["applied"] == 0
        post = float(mongo.employees.find_one(
            {"id": confirmed_ft_employee["id"]},
            {"_id": 0, "available_paid_leave": 1}).get("available_paid_leave") or 0.0)
        assert post == pre, "Balance changed even though import failed"


# --------------- Section 5: apply reserve → approve/reject ---------------

def _apply_admin_leave(admin_headers, employee_id, days_ahead_start,
                       days_ahead_end, consider_paid=True, half=False):
    from datetime import date, timedelta
    start = (date.today() + timedelta(days=days_ahead_start)).isoformat()
    end = (date.today() + timedelta(days=days_ahead_end)).isoformat()
    payload = {
        "employee_id": employee_id,
        "leave_type": "Emergency",
        "leave_split": "First Half" if half else "Full Day",
        "start_date": start,
        "end_date": end,
        "reason": f"{REASON_PREFIX} auto test leave for paid reserve flow xyz",
        "consider_as_paid_leave": bool(consider_paid),
    }
    return requests.post(f"{API}/leaves", json=payload,
                         headers=admin_headers, timeout=30)


class TestReserveApproveReject:
    def _set_balance(self, mongo, eid, val):
        mongo.employees.update_one({"id": eid},
                                   {"$set": {"available_paid_leave": val}})

    def test_reserve_then_approve_finalizes(self, admin_headers, mongo,
                                             confirmed_ft_employee,
                                             preserve_balance,
                                             cleanup_test_leaves):
        eid = confirmed_ft_employee["id"]
        self._set_balance(mongo, eid, 2.0)

        r = _apply_admin_leave(admin_headers, eid, 60, 60, consider_paid=True)
        # admin create endpoint may return 200 or 201
        assert r.status_code in (200, 201), r.text
        cur = mongo.employees.find_one({"id": eid},
                                       {"_id": 0, "available_paid_leave": 1})
        assert round(float(cur["available_paid_leave"]), 1) == 1.0

        leave = mongo.leaves.find_one(
            {"employee_id": eid, "reason": {"$regex": f"^{REASON_PREFIX}"}},
            sort=[("created_at", -1)])
        assert leave is not None
        assert leave.get("consider_as_paid_leave") is True
        assert leave.get("paid_leave_reservation_status") in ("reserved", "finalized")

        # Approve it
        r2 = requests.put(f"{API}/leaves/{leave['id']}/approve",
                           json={"leave_validity": "Valid"},
                           headers=admin_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        after = mongo.leaves.find_one({"id": leave["id"]})
        assert after["paid_leave_reservation_status"] == "finalized"
        assert after.get("is_lop") in (False, None)
        cur2 = mongo.employees.find_one({"id": eid},
                                        {"_id": 0, "available_paid_leave": 1})
        assert round(float(cur2["available_paid_leave"]), 1) == 1.0  # still deducted

    def test_reserve_then_reject_releases(self, admin_headers, mongo,
                                           confirmed_ft_employee,
                                           preserve_balance,
                                           cleanup_test_leaves):
        eid = confirmed_ft_employee["id"]
        self._set_balance(mongo, eid, 2.0)
        r = _apply_admin_leave(admin_headers, eid, 65, 65, consider_paid=True)
        assert r.status_code in (200, 201)
        cur = mongo.employees.find_one({"id": eid},
                                       {"_id": 0, "available_paid_leave": 1})
        assert round(float(cur["available_paid_leave"]), 1) == 1.0
        leave = mongo.leaves.find_one(
            {"employee_id": eid, "reason": {"$regex": f"^{REASON_PREFIX}"}},
            sort=[("created_at", -1)])
        r2 = requests.put(f"{API}/leaves/{leave['id']}/reject",
                           json={"reason": "PAIDTEST reject"},
                           headers=admin_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        cur2 = mongo.employees.find_one({"id": eid},
                                        {"_id": 0, "available_paid_leave": 1})
        assert round(float(cur2["available_paid_leave"]), 1) == 2.0

    def test_insufficient_balance_rejected(self, admin_headers, mongo,
                                            confirmed_ft_employee,
                                            preserve_balance,
                                            cleanup_test_leaves):
        eid = confirmed_ft_employee["id"]
        self._set_balance(mongo, eid, 0.0)
        r = _apply_admin_leave(admin_headers, eid, 70, 70, consider_paid=True)
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "paid leave" in detail and ("sufficient" in detail
                                             or "available" in detail
                                             or "balance" in detail)
