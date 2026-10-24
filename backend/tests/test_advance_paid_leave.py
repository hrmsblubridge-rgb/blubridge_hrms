"""Next-month ADVANCE paid leave (employee login) + Admin Paid Leave Balances table.
LOCAL DB only (IST today assumed 2026-10-24 -> target month 2026-11). Cleans up all data.
"""
import os
import subprocess
import concurrent.futures as cf
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
db = MongoClient("mongodb://localhost:27017")["test_database"]
SEED = "/app/backend/tests/seed_paid_leave_test_data.py"
REASON = "TEST_PL_ advance reason text"
_tokens = {}

INIT = {"fulltime2": 2.0, "fulltime0": 0.0, "halfbal": 0.5, "intern": 0.0, "advzero": 0.0,
        "unconfirmed": 0.0, "inactive": 1.0, "negative": -1.0}


@pytest.fixture(scope="module", autouse=True)
def seed():
    subprocess.run(["python3", SEED, "seed"], check=True)
    db.paid_leave_generation.delete_many({"year": 2026, "month": {"$in": [10, 11]}})
    yield
    _cleanup_generation()
    subprocess.run(["python3", SEED, "cleanup"], check=True)
    db.notifications.delete_many({"message": {"$regex": "TEST_PL_"}})


def _cleanup_generation():
    # Revert +1 for all other employees if Nov generation happened, then delete record
    gen = db.paid_leave_generation.find_one({"year": 2026, "month": 11})
    if gen:
        hist = list(db.paid_leave_history.find({"action_type": "MONTHLY_GENERATION", "year": 2026, "month": 11}))
        for h in hist:
            db.employees.update_one({"id": h["employee_id"]}, {"$inc": {"available_paid_leave": -1}})
        db.paid_leave_history.delete_many({"action_type": "MONTHLY_GENERATION", "year": 2026, "month": 11})
    db.paid_leave_generation.delete_many({"year": 2026, "month": {"$in": [10, 11]}})


def _emp(k):
    return db.employees.find_one({"full_name": f"TEST_PL_{k}"}, {"_id": 0})


def _bal(k):
    return round(float(_emp(k).get("available_paid_leave") or 0.0), 1)


def reset(k=None):
    keys = [k] if k else list(INIT)
    for key in keys:
        e = _emp(key)
        db.leaves.delete_many({"employee_id": e["id"]})
        db.employees.update_one({"id": e["id"]}, {"$set": {"available_paid_leave": INIT[key]},
                                                 "$unset": {"paid_leave_advance_month": "", "paid_leave_advance_used": ""}})


def tok(u, p="Test@123"):
    if u not in _tokens:
        r = requests.post(f"{API}/auth/login", json={"username": u, "password": p})
        assert r.status_code == 200, r.text
        _tokens[u] = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {_tokens[u]}"}


def E(k):
    return tok(f"test_pl_{k}")


def ADM():
    return tok("admin", "pass123")


def apply(k, date, split="Full Day", paid=True):
    return requests.post(f"{API}/employee/leaves/apply", headers=E(k), json={
        "leave_type": "Emergency", "leave_split": split, "start_date": date, "end_date": date,
        "reason": REASON, "consider_as_paid_leave": paid})


def adv(k, date, split="Full Day"):
    return requests.get(f"{API}/employee/paid-leave-advance", headers=E(k),
                        params={"start_date": date, "leave_split": split}).json()


# --- Availability endpoint ---
def test_advance_availability_months():
    reset("fulltime0")
    assert adv("fulltime0", "2026-10-28")["allowed"] is False
    r = adv("fulltime0", "2026-11-05")
    assert r["allowed"] is True and r["applicable"] is True
    assert r["message"] == "Advance paid leave is available for next month. Maximum 1 day."
    assert r["target_month"] == "2026-11"
    assert adv("fulltime0", "2026-12-05")["allowed"] is False


# --- CASE1 full day -> -1 then blocked ---
def test_case1_full_day_then_blocked():
    reset("fulltime0")
    r = apply("fulltime0", "2026-11-05")
    assert r.status_code == 200, r.text
    assert _bal("fulltime0") == -1.0
    lv = db.leaves.find_one({"id": r.json()["leave_id"]}, {"_id": 0})
    assert lv["is_advance_paid_leave"] is True and lv["advance_target_month"] == "2026-11"
    assert lv["advance_settlement"] == "outstanding" and lv["paid_leave_reservation_status"] == "reserved"
    r2 = apply("fulltime0", "2026-11-06", "First Half")
    assert r2.status_code == 400 and "limit has been reached" in r2.json()["detail"], r2.text
    assert _bal("fulltime0") == -1.0
    a = adv("fulltime0", "2026-11-06", "First Half")
    assert a["allowed"] is False and "limit has been reached" in a["message"]


# --- CASE2/3 half + half ---
def test_case23_half_then_half():
    reset("fulltime0")
    assert apply("fulltime0", "2026-11-05", "First Half").status_code == 200
    assert _bal("fulltime0") == -0.5
    a = adv("fulltime0", "2026-11-06", "Second Half")
    assert a["allowed"] is True and a["message"] == "Remaining advance paid leave: 0.5 day."
    assert apply("fulltime0", "2026-11-06", "Second Half").status_code == 200
    assert _bal("fulltime0") == -1.0
    assert _emp("fulltime0")["paid_leave_advance_used"] == 1.0


# --- CASE4 half then full -> blocked ---
def test_case4_half_then_full_blocked():
    reset("fulltime0")
    assert apply("fulltime0", "2026-11-05", "First Half").status_code == 200
    r = apply("fulltime0", "2026-11-06", "Full Day")
    assert r.status_code == 400 and r.json()["detail"].startswith("Remaining advance paid leave: 0.5 day"), r.text
    assert _bal("fulltime0") == -0.5


# --- CASE5 full then half -> blocked ---
def test_case5_full_then_half_blocked():
    reset("fulltime0")
    assert apply("fulltime0", "2026-11-05").status_code == 200
    r = apply("fulltime0", "2026-11-06", "Second Half")
    assert r.status_code == 400, r.text
    assert _bal("fulltime0") == -1.0


# --- Approve does not deduct, reject restores once ---
def test_approve_then_reject_once():
    reset("fulltime0")
    lid = apply("fulltime0", "2026-11-05").json()["leave_id"]
    r = requests.put(f"{API}/leaves/{lid}/approve", headers=ADM(), json={"leave_validity": "valid"})
    assert r.status_code == 200, r.text
    assert _bal("fulltime0") == -1.0
    r = requests.put(f"{API}/leaves/{lid}/reject", headers=ADM())
    assert r.status_code == 200, r.text
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    # Spec: reject releases exactly once -> balance back to 0
    assert _bal("fulltime0") == 0.0, f"after reject of approved advance: {_bal('fulltime0')} status={lv.get('paid_leave_reservation_status')}"
    requests.put(f"{API}/leaves/{lid}/reject", headers=ADM())
    assert _bal("fulltime0") == 0.0


def test_reject_pending_restores_and_frees_allowance():
    reset("fulltime0")
    lid = apply("fulltime0", "2026-11-05").json()["leave_id"]
    assert requests.put(f"{API}/leaves/{lid}/reject", headers=ADM()).status_code == 200
    assert _bal("fulltime0") == 0.0
    requests.put(f"{API}/leaves/{lid}/reject", headers=ADM())
    assert _bal("fulltime0") == 0.0
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["advance_settlement"] == "reversed" and lv["paid_leave_reservation_status"] == "released"
    assert _emp("fulltime0")["paid_leave_advance_used"] == 0.0
    assert adv("fulltime0", "2026-11-09")["allowed"] is True


# --- Admin reset re-reserves via advance rules ---
def test_reset_rejected_advance_rereserves():
    reset("fulltime0")
    lid = apply("fulltime0", "2026-11-05").json()["leave_id"]
    requests.put(f"{API}/leaves/{lid}/reject", headers=ADM())
    assert _bal("fulltime0") == 0.0
    r = requests.post(f"{API}/leaves/{lid}/reset", headers=ADM(), json={})
    assert r.status_code == 200, r.text
    assert _bal("fulltime0") == -1.0
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["status"] == "pending" and lv["paid_leave_reservation_status"] == "reserved"
    assert lv["advance_settlement"] == "outstanding" and lv["is_advance_paid_leave"] is True
    assert _emp("fulltime0")["paid_leave_advance_used"] == 1.0


# --- Edit pending advance leave ---
def test_edit_full_to_half_then_uncheck():
    reset("fulltime0")
    lid = apply("fulltime0", "2026-11-05").json()["leave_id"]
    body = {"leave_type": "Emergency", "leave_split": "First Half", "start_date": "2026-11-05",
            "end_date": "2026-11-05", "reason": REASON, "consider_as_paid_leave": True}
    r = requests.put(f"{API}/employee/leaves/{lid}", headers=E("fulltime0"), json=body)
    assert r.status_code == 200, r.text
    assert _bal("fulltime0") == -0.5 and _emp("fulltime0")["paid_leave_advance_used"] == 0.5
    body["consider_as_paid_leave"] = False
    r = requests.put(f"{API}/employee/leaves/{lid}", headers=E("fulltime0"), json=body)
    assert r.status_code == 200, r.text
    assert _bal("fulltime0") == 0.0 and _emp("fulltime0")["paid_leave_advance_used"] == 0.0
    lv = db.leaves.find_one({"id": lid}, {"_id": 0})
    assert lv["consider_as_paid_leave"] is False and lv["advance_settlement"] == "reversed"


# --- Ineligible employees ---
def test_ineligible_intern_unconfirmed_negative():
    reset()
    for k in ("intern", "unconfirmed"):
        assert adv(k, "2026-11-05")["allowed"] is False
        r = apply(k, "2026-11-05")
        assert r.status_code in (400, 403), r.text
        assert _bal(k) == 0.0
    a = adv("negative", "2026-11-05")
    assert a["allowed"] is False
    r = apply("negative", "2026-11-05")
    assert r.status_code == 400, r.text
    assert _bal("negative") == -1.0


def test_halfbal_full_day_nov_not_advance():
    reset("halfbal")
    r = apply("halfbal", "2026-11-05")
    assert r.status_code == 400, r.text  # positive balance -> normal rules, insufficient
    assert _bal("halfbal") == 0.5


def test_positive_balance_normal_paid_leave():
    reset("fulltime2")
    r = apply("fulltime2", "2026-11-05")
    assert r.status_code == 200, r.text
    assert _bal("fulltime2") == 1.0
    lv = db.leaves.find_one({"id": r.json()["leave_id"]}, {"_id": 0})
    assert not lv.get("is_advance_paid_leave")
    r = apply("fulltime2", "2026-10-28")
    assert r.status_code == 200 and _bal("fulltime2") == 0.0


# --- Outstanding rule ---
def test_outstanding_previous_month_blocks():
    reset("advzero")
    e = _emp("advzero")
    db.employees.update_one({"id": e["id"]}, {"$set": {"available_paid_leave": -1.0,
                                                      "paid_leave_advance_month": "2026-10",
                                                      "paid_leave_advance_used": 1.0}})
    a = adv("advzero", "2026-11-05")
    assert a["allowed"] is False and "not settled yet" in a["message"], a
    r = apply("advzero", "2026-11-05")
    assert r.status_code == 400 and "not settled yet" in r.json()["detail"]
    assert _bal("advzero") == -1.0
    # previous month settled with balance 0 -> allowed
    db.employees.update_one({"id": e["id"]}, {"$set": {"available_paid_leave": 0.0}})
    db.paid_leave_generation.insert_one({"id": "TEST_PL_gen_oct", "year": 2026, "month": 10,
                                         "method": "generate", "test_tag": "TEST_PL_"})
    assert adv("advzero", "2026-11-05")["allowed"] is True
    db.paid_leave_generation.delete_many({"year": 2026, "month": 10})


# --- Concurrency ---
def test_concurrency_only_one_succeeds():
    reset("advzero")
    dates = ["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14"]
    E("advzero")
    with cf.ThreadPoolExecutor(5) as ex:
        res = list(ex.map(lambda d: apply("advzero", d), dates))
    ok = [r for r in res if r.status_code == 200]
    assert len(ok) == 1, [(r.status_code, r.text[:80]) for r in res]
    assert _bal("advzero") == -1.0


# --- Admin balances table ---
def test_admin_balances_list():
    reset()
    r = requests.get(f"{API}/admin/paid-leave/balances", headers=ADM())
    assert r.status_code == 200, r.text
    names = {x["emp_name"]: x["available_paid_leave"] for x in r.json()}
    for k in ("fulltime2", "fulltime0", "halfbal", "advzero", "negative"):
        assert f"TEST_PL_{k}" in names
    for k in ("intern", "unconfirmed", "inactive"):
        assert f"TEST_PL_{k}" not in names
    assert names["TEST_PL_negative"] == -1.0 and names["TEST_PL_fulltime0"] == 0.0
    assert requests.get(f"{API}/admin/paid-leave/balances", headers=E("fulltime0")).status_code == 403


# --- Generation offsets & settles (runs last) ---
def test_zz_generate_november_settles():
    reset()
    lid_full = apply("fulltime0", "2026-11-05").json()["leave_id"]
    assert apply("advzero", "2026-11-05", "First Half").status_code == 200
    assert _bal("fulltime0") == -1.0 and _bal("advzero") == -0.5
    r = requests.post(f"{API}/admin/paid-leave/generate", headers=ADM(), json={"year": 2026, "month": 11})
    assert r.status_code == 200, r.text
    assert _bal("fulltime0") == 0.0 and _bal("advzero") == 0.5 and _bal("fulltime2") == 3.0
    assert db.leaves.find_one({"id": lid_full})["advance_settlement"] == "settled"
    a = adv("advzero", "2026-11-06", "First Half")
    assert a["allowed"] is False  # balance positive now -> normal rules
    # zero-balance employee after generation -> generated message
    e = _emp("fulltime0")
    db.employees.update_one({"id": e["id"]}, {"$set": {"available_paid_leave": 0.0}})
    db.leaves.delete_many({"employee_id": e["id"]})
    db.employees.update_one({"id": e["id"]}, {"$unset": {"paid_leave_advance_month": "", "paid_leave_advance_used": ""}})
    a = adv("fulltime0", "2026-11-09")
    assert a["allowed"] is False and "already been generated" in a["message"], a
    names = {x["emp_name"]: x["available_paid_leave"] for x in
             requests.get(f"{API}/admin/paid-leave/balances", headers=ADM()).json()}
    assert names["TEST_PL_advzero"] == 0.5
