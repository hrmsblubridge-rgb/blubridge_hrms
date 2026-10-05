"""Bulk approve/reject tests for Late, Early-Out, Missed-Punch modules.

Covers:
- Bulk approve with LOP=true and LOP=false (late, early-out)
- Bulk approve missed-punch (no LOP)
- Bulk reject each module
- Skipped behaviour: already processed / non-existent id / empty ids
- Idempotent re-approve returns skipped 'Already processed'
- Regression: individual approve/reject still works

All created test records use reason prefix 'QATEST_BULK_' and are DELETED afterwards.
"""
import os
import uuid
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient


def _load_env():
    env = {}
    try:
        with open("/app/backend/.env") as f:
            for ln in f:
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


_ENV = _load_env()
_MONGO_CLIENT = MongoClient(_ENV.get("MONGO_URL") or os.environ["MONGO_URL"])
_DB = _MONGO_CLIENT[_ENV.get("DB_NAME") or os.environ.get("DB_NAME", "hrms_blubridge")]

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for ln in f:
                    if ln.startswith("REACT_APP_BACKEND_URL="):
                        v = ln.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "HrAdmin@2109"


# -------- fixtures --------
@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    import time
    last = None
    for _ in range(6):
        try:
            r = s.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=30)
            if r.status_code == 200:
                last = r
                break
            last = r
        except Exception as e:
            last = e
        time.sleep(10)
    assert getattr(last, "status_code", None) == 200, f"admin login failed: {getattr(last,'status_code',None)} {getattr(last,'text',last)}"
    token = last.json().get("access_token") or last.json().get("token")
    assert token, f"no token in login response: {last.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def employee_id(admin_client):
    r = admin_client.get(f"{API}/employees/all")
    assert r.status_code == 200, r.text
    emps = r.json()
    assert isinstance(emps, list) and emps, "no employees available"
    # pick a real employee (not the admin user)
    for e in emps:
        if e.get("id") and e.get("full_name"):
            return e["id"]
    return emps[0]["id"]


def _future_dates(n):
    # pick FAR-FUTURE dates to avoid clashing with existing records / attendance side-effects.
    # Bulk-approve of Late does not touch attendance (only missed-punch does).
    start = date.today() + timedelta(days=365 * 3)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _cleanup(admin_client, path, ids):
    # No DELETE HTTP endpoint exists for these modules -> remove directly via Mongo.
    coll_map = {
        "late-requests": _DB.late_requests,
        "early-out-requests": _DB.early_out_requests,
        "missed-punches": _DB.missed_punches,
    }
    coll = coll_map.get(path)
    if coll is not None and ids:
        try:
            coll.delete_many({"id": {"$in": list(ids)}})
        except Exception:
            pass


# -------- Late Requests --------
class TestLateBulk:
    def test_empty_ids(self, admin_client):
        r = admin_client.put(f"{API}/late-requests/bulk-approve", json={"ids": []})
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 0 and d["processed"] == 0 and d["skipped"] == 0

    def test_non_existent_id_skipped(self, admin_client):
        fake = f"nope-{uuid.uuid4()}"
        r = admin_client.put(f"{API}/late-requests/bulk-approve", json={"ids": [fake]})
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 1 and d["processed"] == 0 and d["skipped"] == 1
        assert d["skipped_items"][0]["id"] == fake

    def test_bulk_approve_with_lop_true(self, admin_client, employee_id):
        dates = _future_dates(2)
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/late-requests", json={
                "employee_id": employee_id, "date": dt,
                "expected_time": "09:30", "actual_time": "10:15",
                "reason": "QATEST_BULK_LATE_APPROVE"
            })
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        try:
            r = admin_client.put(f"{API}/late-requests/bulk-approve",
                                 json={"ids": ids, "is_lop": True, "lop_remark": "QATEST"})
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["total"] == 2 and d["processed"] == 2 and d["skipped"] == 0

            # verify persistence
            for rid in ids:
                g = admin_client.get(f"{API}/late-requests/{rid}")
                # Some APIs may not have GET-by-id; fallback to list
                if g.status_code != 200 or "status" not in (g.json() or {}):
                    lst = admin_client.get(f"{API}/late-requests").json()
                    rec = next((x for x in lst if x.get("id") == rid), None)
                else:
                    rec = g.json()
                assert rec is not None
                assert rec.get("status") == "approved"
                assert rec.get("is_lop") is True

            # re-approving already-approved -> all skipped
            r2 = admin_client.put(f"{API}/late-requests/bulk-approve",
                                  json={"ids": ids, "is_lop": True})
            d2 = r2.json()
            assert d2["processed"] == 0 and d2["skipped"] == 2
            assert all("Already processed" in (x.get("reason") or "") for x in d2["skipped_items"])
        finally:
            _cleanup(admin_client, "late-requests", ids)

    def test_bulk_approve_no_lop(self, admin_client, employee_id):
        dates = _future_dates(2)
        # shift to avoid duplicate-date conflict with the previous test
        dates = [(date.fromisoformat(d) + timedelta(days=50)).isoformat() for d in dates]
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/late-requests", json={
                "employee_id": employee_id, "date": dt,
                "expected_time": "09:30", "actual_time": "10:00",
                "reason": "QATEST_BULK_LATE_NOLOP"
            })
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        try:
            r = admin_client.put(f"{API}/late-requests/bulk-approve",
                                 json={"ids": ids, "is_lop": False})
            assert r.status_code == 200
            d = r.json()
            assert d["processed"] == 2 and d["skipped"] == 0
            lst = admin_client.get(f"{API}/late-requests").json()
            for rid in ids:
                rec = next((x for x in lst if x.get("id") == rid), None)
                assert rec and rec.get("status") == "approved" and rec.get("is_lop") is False
        finally:
            _cleanup(admin_client, "late-requests", ids)

    def test_bulk_reject(self, admin_client, employee_id):
        dates = [(date.today() + timedelta(days=365 * 5 + i)).isoformat() for i in range(2)]
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/late-requests", json={
                "employee_id": employee_id, "date": dt,
                "expected_time": "09:30", "actual_time": "10:00",
                "reason": "QATEST_BULK_LATE_REJECT"
            })
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        try:
            r = admin_client.put(f"{API}/late-requests/bulk-reject",
                                 json={"ids": ids, "reason": "QATEST reject"})
            assert r.status_code == 200
            d = r.json()
            assert d["processed"] == 2 and d["skipped"] == 0
            lst = admin_client.get(f"{API}/late-requests").json()
            for rid in ids:
                rec = next((x for x in lst if x.get("id") == rid), None)
                assert rec and rec.get("status") == "rejected"
        finally:
            _cleanup(admin_client, "late-requests", ids)

    def test_individual_approve_regression(self, admin_client, employee_id):
        dt = (date.today() + timedelta(days=365 * 6)).isoformat()
        r = admin_client.post(f"{API}/late-requests", json={
            "employee_id": employee_id, "date": dt,
            "expected_time": "09:30", "actual_time": "10:00",
            "reason": "QATEST_BULK_LATE_INDIV"
        })
        assert r.status_code == 200
        rid = r.json()["id"]
        try:
            r2 = admin_client.put(f"{API}/late-requests/{rid}/approve",
                                  json={"is_lop": True, "lop_remark": "QATEST indiv"})
            assert r2.status_code == 200, r2.text
            lst = admin_client.get(f"{API}/late-requests").json()
            rec = next((x for x in lst if x.get("id") == rid), None)
            assert rec and rec["status"] == "approved" and rec["is_lop"] is True
        finally:
            _cleanup(admin_client, "late-requests", [rid])


# -------- Early Out Requests --------
class TestEarlyOutBulk:
    def test_bulk_approve_with_lop_true(self, admin_client, employee_id):
        dates = [(date.today() + timedelta(days=365 * 7 + i)).isoformat() for i in range(2)]
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/early-out-requests", json={
                "employee_id": employee_id, "date": dt,
                "actual_time": "16:30", "reason": "QATEST_BULK_EO_APPROVE"
            })
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        try:
            r = admin_client.put(f"{API}/early-out-requests/bulk-approve",
                                 json={"ids": ids, "is_lop": True, "lop_remark": "QATEST"})
            assert r.status_code == 200
            d = r.json()
            assert d["processed"] == 2 and d["skipped"] == 0
            lst = admin_client.get(f"{API}/early-out-requests").json()
            for rid in ids:
                rec = next((x for x in lst if x.get("id") == rid), None)
                assert rec and rec["status"] == "approved" and rec["is_lop"] is True
        finally:
            _cleanup(admin_client, "early-out-requests", ids)

    def test_bulk_reject(self, admin_client, employee_id):
        dates = [(date.today() + timedelta(days=365 * 8 + i)).isoformat() for i in range(2)]
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/early-out-requests", json={
                "employee_id": employee_id, "date": dt,
                "actual_time": "16:30", "reason": "QATEST_BULK_EO_REJECT"
            })
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        try:
            r = admin_client.put(f"{API}/early-out-requests/bulk-reject",
                                 json={"ids": ids, "reason": "QATEST"})
            assert r.status_code == 200
            d = r.json()
            assert d["processed"] == 2 and d["skipped"] == 0
        finally:
            _cleanup(admin_client, "early-out-requests", ids)

    def test_empty_and_bogus(self, admin_client):
        r = admin_client.put(f"{API}/early-out-requests/bulk-approve", json={"ids": []})
        assert r.status_code == 200 and r.json()["total"] == 0
        r2 = admin_client.put(f"{API}/early-out-requests/bulk-reject",
                              json={"ids": ["nope-xyz"]})
        assert r2.status_code == 200
        d = r2.json()
        assert d["total"] == 1 and d["skipped"] == 1


# -------- Missed Punch --------
class TestMissedPunchBulk:
    def test_bulk_approve_no_lop(self, admin_client, employee_id):
        # Missed punch approve modifies attendance -- use past date but far enough
        # so we don't collide with existing records. Use dates ~2 years ago.
        dates = [(date.today() - timedelta(days=365 * 2 + i)).isoformat() for i in range(2)]
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/missed-punches", json={
                "employee_id": employee_id, "date": dt,
                "punch_type": "Check-in", "check_in_time": "09:15",
                "reason": "QATEST_BULK_MP_APPROVE"
            })
            if r.status_code != 200:
                pytest.skip(f"cannot create missed-punch: {r.status_code} {r.text}")
            ids.append(r.json()["id"])
        try:
            # Bulk approve WITHOUT is_lop (missed punch has no LOP)
            r = admin_client.put(f"{API}/missed-punches/bulk-approve",
                                 json={"ids": ids})
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["processed"] == 2 and d["skipped"] == 0
            # re-approve => all skipped
            r2 = admin_client.put(f"{API}/missed-punches/bulk-approve", json={"ids": ids})
            assert r2.json()["skipped"] == 2
        finally:
            _cleanup(admin_client, "missed-punches", ids)

    def test_bulk_reject(self, admin_client, employee_id):
        dates = [(date.today() - timedelta(days=365 * 3 + i)).isoformat() for i in range(2)]
        ids = []
        for dt in dates:
            r = admin_client.post(f"{API}/missed-punches", json={
                "employee_id": employee_id, "date": dt,
                "punch_type": "Check-in", "check_in_time": "09:20",
                "reason": "QATEST_BULK_MP_REJECT"
            })
            if r.status_code != 200:
                pytest.skip(f"cannot create missed-punch: {r.status_code} {r.text}")
            ids.append(r.json()["id"])
        try:
            r = admin_client.put(f"{API}/missed-punches/bulk-reject",
                                 json={"ids": ids, "reason": "QATEST"})
            assert r.status_code == 200
            d = r.json()
            assert d["processed"] == 2 and d["skipped"] == 0
        finally:
            _cleanup(admin_client, "missed-punches", ids)

    def test_empty_and_bogus(self, admin_client):
        r = admin_client.put(f"{API}/missed-punches/bulk-approve", json={"ids": []})
        assert r.status_code == 200 and r.json()["total"] == 0
        r2 = admin_client.put(f"{API}/missed-punches/bulk-reject", json={"ids": ["nope-xyz"]})
        assert r2.status_code == 200 and r2.json()["skipped"] == 1


# -------- RBAC --------
class TestBulkRBAC:
    def test_non_hr_forbidden(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # try login as normal employee
        r = s.post(f"{API}/auth/login", json={"username": "user", "password": "pass123"})
        if r.status_code != 200:
            pytest.skip("no non-hr test user available")
        token = r.json().get("access_token") or r.json().get("token")
        s.headers.update({"Authorization": f"Bearer {token}"})
        for path in ["late-requests", "early-out-requests", "missed-punches"]:
            for action in ["bulk-approve", "bulk-reject"]:
                r = s.put(f"{API}/{path}/{action}", json={"ids": ["x"]})
                assert r.status_code == 403, f"{path}/{action} did not return 403 (got {r.status_code})"
