"""
End-to-end test for SAME-DAY effective-dated shift assignment recalculation.
Reproduces the reported bug: an employee already marked Late today under the
old shift must become Not-Late immediately after a new shift effective TODAY is
assigned — via the real /settings/shifts/assign endpoint — while previous days
stay unchanged. Also covers still-late, bulk, and future-effective cases.
Seeds isolated data and cleans up.
"""
import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
API = "http://localhost:8001"
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

IST = ZoneInfo("Asia/Kolkata")
now = datetime.now(IST)
TODAY_ISO = now.strftime("%Y-%m-%d")
TODAY_DDMM = now.strftime("%d-%m-%Y")
YEST = now - timedelta(days=1)
YEST_ISO = YEST.strftime("%Y-%m-%d")
YEST_DDMM = YEST.strftime("%d-%m-%Y")
FUTURE_ISO = (now + timedelta(days=5)).strftime("%Y-%m-%d")

EMP1 = "zz-sameday-emp-1"
EMP2 = "zz-sameday-emp-2"
EMP3 = "zz-sameday-emp-3"  # future-effective employee
results = []
def check(name, cond, extra=""):
    results.append(cond); print(("PASS" if cond else "FAIL"), "-", name, extra)


async def cleanup():
    await db.employees.delete_many({"id": {"$in": [EMP1, EMP2, EMP3]}})
    await db.employee_shifts.delete_many({"employee_id": {"$in": [EMP1, EMP2, EMP3]}})
    await db.attendance.delete_many({"employee_id": {"$in": [EMP1, EMP2, EMP3]}})
    await db.shifts.delete_many({"name": {"$in": ["ZZSAMEDAY_1030"]}})


async def seed_emp(eid, name, today_in, today_out="20:00"):
    await db.employees.insert_one({"id": eid, "full_name": name, "team": "T", "department": "D",
                                   "shift_type": "General", "is_deleted": False, "employee_status": "active"})
    # OLD 10:00 assignment, open-ended (snapshot)
    await db.employee_shifts.insert_one({
        "id": f"asnold-{eid}", "employee_id": eid, "shift_id": "sh-old-1000",
        "effective_from": "2026-01-01", "effective_to": None, "is_deleted": False,
        "shift_name": "Old 10:00", "shift_start_time": "10:00", "shift_total_hours": 9.0,
        "shift_late_grace_minutes": 0, "shift_early_out_grace_minutes": 0})
    # Existing attendance rows computed under OLD 10:00 => Late Login
    for d in (YEST_DDMM, TODAY_DDMM):
        await db.attendance.insert_one({
            "id": f"att-{eid}-{d}", "employee_id": eid, "date": d, "emp_name": name,
            "check_in": today_in, "check_in_24h": today_in, "check_out": today_out,
            "check_out_24h": today_out, "status": "Late Login", "is_lop": False,
            "lop_reason": "Late by 20 minute(s)", "source": "biometric",
            "expected_login": "10:00", "shift_type": "General"})


async def main():
    await cleanup()
    await seed_emp(EMP1, "ZZ SameDay One", "10:20")   # will become NOT late under 10:30
    await seed_emp(EMP2, "ZZ SameDay Two", "10:45")   # stays late under 10:30
    # EMP3: future-effective — today must NOT change
    await db.employees.insert_one({"id": EMP3, "full_name": "ZZ Future", "team": "T", "department": "D",
                                   "shift_type": "General", "is_deleted": False, "employee_status": "active"})
    await db.employee_shifts.insert_one({
        "id": f"asnold-{EMP3}", "employee_id": EMP3, "shift_id": "sh-old-1000",
        "effective_from": "2026-01-01", "effective_to": None, "is_deleted": False,
        "shift_name": "Old 10:00", "shift_start_time": "10:00", "shift_total_hours": 9.0,
        "shift_late_grace_minutes": 0, "shift_early_out_grace_minutes": 0})
    await db.attendance.insert_one({
        "id": f"att-{EMP3}-{TODAY_DDMM}", "employee_id": EMP3, "date": TODAY_DDMM, "emp_name": "ZZ Future",
        "check_in_24h": "10:20", "check_out_24h": "20:00", "status": "Late Login", "is_lop": False,
        "lop_reason": "Late by 20 minute(s)", "source": "biometric", "expected_login": "10:00"})

    async with httpx.AsyncClient(base_url=API, timeout=40) as c:
        tok = (await c.post("/api/auth/login", json={"username": "sysadmin", "password": "pass123"})).json()["token"]
        H = {"Authorization": f"Bearer {tok}"}

        # Create new 10:30 shift
        r = await c.post("/api/settings/shifts", headers=H,
                         json={"name": "ZZSAMEDAY_1030", "start_time": "10:30", "total_hours": 9})
        check("create 10:30 shift", r.status_code == 200, r.text[:120])
        new_shift = r.json()["id"]

        # BULK assign to EMP1 + EMP2 effective TODAY
        r = await c.post("/api/settings/shifts/assign", headers=H,
                         json={"employee_ids": [EMP1, EMP2], "shift_id": new_shift, "effective_from": TODAY_ISO})
        check("assign effective today (bulk)", r.status_code == 200, r.text[:160])
        recalc = r.json().get("recalc", {})
        check("recalc ran for 2 employees", recalc.get("employees") == 2, str(recalc))

        # Assign to EMP3 effective FUTURE (must NOT recalc today)
        r = await c.post("/api/settings/shifts/assign", headers=H,
                         json={"employee_ids": [EMP3], "shift_id": new_shift, "effective_from": FUTURE_ISO})
        check("assign future-effective", r.status_code == 200, r.text[:120])
        check("future assign recalculated 0", r.json().get("recalc", {}).get("recalculated", -1) == 0, str(r.json().get("recalc")))

    # Verify DB state
    a1_today = await db.attendance.find_one({"employee_id": EMP1, "date": TODAY_DDMM}, {"_id": 0})
    a1_yest = await db.attendance.find_one({"employee_id": EMP1, "date": YEST_DDMM}, {"_id": 0})
    a2_today = await db.attendance.find_one({"employee_id": EMP2, "date": TODAY_DDMM}, {"_id": 0})
    a3_today = await db.attendance.find_one({"employee_id": EMP3, "date": TODAY_DDMM}, {"_id": 0})

    # TEST 1/2/6 — EMP1 today: was Late(10:00), now Not-Late under 10:30
    check("EMP1 today status not Late Login", a1_today["status"] != "Late Login", str(a1_today.get("status")))
    check("EMP1 today not LOP", a1_today["is_lop"] is False)
    check("EMP1 today expected_login=10:30", a1_today.get("expected_login") == "10:30", str(a1_today.get("expected_login")))

    # TEST 5 — previous day unchanged (still Late under old 10:00)
    check("EMP1 yesterday STILL Late Login", a1_yest["status"] == "Late Login", str(a1_yest.get("status")))
    check("EMP1 yesterday expected_login unchanged 10:00", a1_yest.get("expected_login") == "10:00")

    # TEST 3 — EMP2 still late under 10:30 (punch 10:45)
    check("EMP2 today STILL Late (10:45 > 10:30)", a2_today["status"] == "Late Login", str(a2_today.get("status")))

    # TEST 7 — EMP3 future-effective: today unchanged
    check("EMP3 today unchanged (future effective)", a3_today["status"] == "Late Login", str(a3_today.get("status")))
    check("EMP3 today expected_login unchanged 10:00", a3_today.get("expected_login") == "10:00")

    await cleanup()
    passed = sum(results)
    print(f"\n==== {passed}/{len(results)} PASSED ====")
    if passed != len(results):
        raise SystemExit(1)


asyncio.run(main())
