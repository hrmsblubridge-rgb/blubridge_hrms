# BRSF Late Days summary column + Finalize/Reopen month lock (LOCAL DB only; self-seeds & cleans)
import io
import os
import subprocess
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
MONTH = "2026-09"
TAG = "TEST_N09_"
LOCK_MSG = "September 2026 is finalized. Reopen the month to change stars."
mdb = MongoClient("mongodb://localhost:27017")["test_database"]
SEED = "/app/backend/tests/seed_brsf_late_test_data.py"


def _seed(cmd):
    subprocess.run(["python3", SEED, cmd], cwd="/app/backend", check=True, capture_output=True)


def _login(u, p):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": u, "password": p})
    if r.status_code != 200:
        return None
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module", autouse=True)
def seeded():
    _seed("seed")
    yield
    mdb.brsf_import_batches.delete_many({"month": MONTH, "file_name": {"$regex": "TEST_"}})
    _seed("cleanup")


@pytest.fixture(scope="module")
def s():
    sess = _login("admin", "pass123")
    if not sess:
        pytest.skip("admin login failed")
    return sess


def _eid(k):
    return mdb.employees.find_one({"full_name": f"{TAG}{k}"})["id"]


def _summary(s):
    r = s.get(f"{BASE_URL}/api/brsf/summary", params={"month": MONTH})
    assert r.status_code == 200, r.text
    return r.json()


def _row(data, k):
    return next(r for r in data["rows"] if r["id"] == _eid(k))


def _stars(s, k):
    r = s.get(f"{BASE_URL}/api/brsf/stars", params={"employee_id": _eid(k), "month": MONTH})
    assert r.status_code == 200, r.text
    return r.json()


def _line(data, code):
    return next(l for l in data["lines"] if l["code"] == code)


def _assert_locked(r):
    assert r.status_code == 400, f"{r.status_code} {r.text}"
    assert r.json()["detail"] == LOCK_MSG


# --- Late Days in summary
def test_01_summary_before_calc_null(s):
    d = _summary(s)
    assert d["finalized"] is None
    assert _row(d, "example")["late_count"] is None
    assert _row(d, "three")["late_count"] is None
    assert _row(d, "example")["calculated"] is False


def test_02_summary_after_recalc(s):
    r = s.post(f"{BASE_URL}/api/brsf/recalculate", json={"month": MONTH})
    assert r.status_code == 200, r.text
    d = _summary(s)
    assert _row(d, "example")["late_count"] == 4
    assert _row(d, "three")["late_count"] == 3


# --- Finalize + lock enforcement
def test_03_finalize_and_double(s):
    r = s.post(f"{BASE_URL}/api/brsf/finalize", json={"month": MONTH, "note": "TEST sign-off"})
    assert r.status_code == 200, r.text
    lk = r.json()["finalized"]
    assert lk["finalized"] is True and lk["note"] == "TEST sign-off"
    assert _summary(s)["finalized"]["finalized"] is True
    _assert_locked(s.post(f"{BASE_URL}/api/brsf/finalize", json={"month": MONTH}))


def test_04_locked_mutations(s):
    d = _stars(s, "example")
    assert d["finalized"] and d["finalized"]["finalized"] is True
    n09, p02 = _line(d, "N09"), _line(d, "P02")
    _assert_locked(s.post(f"{BASE_URL}/api/brsf/recalculate", json={"month": MONTH}))
    _assert_locked(s.post(f"{BASE_URL}/api/brsf/recalculate", json={"month": MONTH, "employee_id": _eid("example")}))
    _assert_locked(s.put(f"{BASE_URL}/api/brsf/stars/{n09['id']}/override", json={"value": 0, "reason": "x"}))
    _assert_locked(s.post(f"{BASE_URL}/api/brsf/stars/{n09['id']}/reset-override"))
    _assert_locked(s.put(f"{BASE_URL}/api/brsf/stars/{p02['id']}/manual", json={"entry_mode": "monthly", "monthly_value": 1}))
    inst_line = next((l for l in d["lines"] if l["code"] in ("P01", "N07", "N08", "P06") and l["type"] == "manual"), None)
    any_line = inst_line or n09
    _assert_locked(s.post(f"{BASE_URL}/api/brsf/stars/{any_line['id']}/instances", json={"value": 1, "date": "2026-09-10"}))
    _assert_locked(s.put(f"{BASE_URL}/api/brsf/stars/{any_line['id']}/instances/x", json={"value": 1}))
    _assert_locked(s.delete(f"{BASE_URL}/api/brsf/stars/{any_line['id']}/instances/x"))
    _assert_locked(s.put(f"{BASE_URL}/api/brsf/stars/{n09['id']}/child-override", json={"key": "k", "value": 0}))
    _assert_locked(s.post(f"{BASE_URL}/api/brsf/stars/{n09['id']}/child-override/reset", json={"key": "k"}))
    csv_bytes = "Employee Name\nTEST_N09_example\n".encode()
    r = s.post(f"{BASE_URL}/api/brsf/import/preview", data={"month": MONTH},
               files={"file": ("TEST_import.csv", io.BytesIO(csv_bytes), "text/csv")})
    _assert_locked(r)
    # confirm with fake batch stored in DB
    bid = str(uuid.uuid4())
    mdb.brsf_import_batches.insert_one({"id": bid, "month": MONTH, "changes": [], "applied": False,
                                        "file_name": "TEST_fake.csv"})
    try:
        _assert_locked(s.post(f"{BASE_URL}/api/brsf/import/confirm", json={"batch_id": bid}))
    finally:
        mdb.brsf_import_batches.delete_one({"id": bid})


def test_05_export_allowed(s):
    r = s.get(f"{BASE_URL}/api/brsf/export", params={"month": MONTH, "format": "csv"})
    assert r.status_code == 200
    assert "TEST_N09_example" in r.content.decode("utf-8-sig")
    r = s.get(f"{BASE_URL}/api/brsf/export", params={"month": MONTH})
    assert r.status_code == 200 and r.content[:2] == b"PK"


# --- Frozen values while finalized
def test_06_frozen_values(s):
    eid = _eid("three")
    mdb.attendance.insert_one({
        "id": f"{TAG}extra", "employee_id": eid, "emp_name": f"{TAG}three", "team": "QA",
        "department": "Research Unit", "date": "30-09-2026", "check_in_24h": "10:45",
        "check_in": "10:45 AM", "status": "Late Login"})
    d = _stars(s, "three")
    assert _line(d, "N09")["final_value"] == 0
    assert len(d["lines"]) == 15
    assert _row(_summary(s), "three")["late_count"] == 3


def test_07_permissions(s):
    for u, p in (("user", "pass123"), ("sysadmin", "pass123")):
        o = _login(u, p)
        if not o:
            continue
        assert o.post(f"{BASE_URL}/api/brsf/finalize", json={"month": MONTH}).status_code == 403
        assert o.post(f"{BASE_URL}/api/brsf/reopen", json={"month": MONTH, "reason": "x"}).status_code == 403


# --- Reopen
def test_08_reopen_requires_reason(s):
    for body in ({"month": MONTH}, {"month": MONTH, "reason": "   "}):
        r = s.post(f"{BASE_URL}/api/brsf/reopen", json=body)
        assert r.status_code == 400 and "reason" in r.json()["detail"].lower()
    r = s.post(f"{BASE_URL}/api/brsf/reopen", json={"month": MONTH, "reason": "TEST fix late data"})
    assert r.status_code == 200, r.text
    assert _summary(s)["finalized"] is None
    r = s.post(f"{BASE_URL}/api/brsf/reopen", json={"month": MONTH, "reason": "again"})
    assert r.status_code == 400
    doc = mdb.brsf_month_locks.find_one({"year": 2026, "month": 9})
    acts = [h["action"] for h in doc["history"]]
    assert acts == ["finalize", "reopen"]
    assert doc["history"][1]["note"] == "TEST fix late data"


def test_09_after_reopen_recalc_updates(s):
    r = s.post(f"{BASE_URL}/api/brsf/recalculate", json={"month": MONTH})
    assert r.status_code == 200, r.text
    assert _line(_stars(s, "three"), "N09")["final_value"] == -1
    assert _row(_summary(s), "three")["late_count"] == 4
    # editable again: override then reset
    n09 = _line(_stars(s, "three"), "N09")
    r = s.put(f"{BASE_URL}/api/brsf/stars/{n09['id']}/override", json={"value": 0, "reason": "TEST"})
    assert r.status_code == 200, r.text
    r = s.post(f"{BASE_URL}/api/brsf/stars/{n09['id']}/reset-override")
    assert r.status_code == 200


# --- Finalize snapshots never-calculated employees
def test_10_finalize_snapshots_uncalculated(s):
    _seed("seed")
    ids = [_eid("example"), _eid("three")]
    assert mdb.brsf_star_lines.count_documents({"employee_id": {"$in": ids}}) == 0
    r = s.post(f"{BASE_URL}/api/brsf/finalize", json={"month": MONTH})
    assert r.status_code == 200, r.text
    for i in ids:
        assert mdb.brsf_star_lines.count_documents({"employee_id": i, "year": 2026, "month": 9}) == 15
    d = _summary(s)
    assert _row(d, "example")["late_count"] == 4
    assert _row(d, "example")["calculated"] is True
    doc = mdb.brsf_month_locks.find_one({"year": 2026, "month": 9})
    assert [h["action"] for h in doc["history"]] == ["finalize"]
    assert s.post(f"{BASE_URL}/api/brsf/reopen", json={"month": MONTH, "reason": "TEST"}).status_code == 200
