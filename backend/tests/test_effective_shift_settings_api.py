"""
API-level test for the effective-dated shift SETTINGS flow (req #2/#3/#5/#6/#7):
  - assign captures a frozen snapshot
  - editing the shift master does NOT rewrite existing assignment history
  - reassigning with a new Effective From captures a fresh snapshot
Uses a throwaway employee inserted directly (no onboarding side effects) and
cleans everything up afterwards.
"""
import asyncio
import os
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
API = os.environ['REACT_APP_BACKEND_URL'] if False else None

with open('/app/frontend/.env') as f:
    for line in f:
        if line.startswith('REACT_APP_BACKEND_URL'):
            API = line.split('=', 1)[1].strip()
API = "http://localhost:8001"

db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
EMP = "zz-api-shift-emp"
results = []
def check(name, cond, extra=""):
    results.append(cond); print(("PASS" if cond else "FAIL"), "-", name, extra)


async def main():
    # cleanup any prior run
    await db.employees.delete_many({"id": EMP})
    await db.employee_shifts.delete_many({"employee_id": EMP})
    await db.shifts.delete_many({"name": {"$in": ["ZZEFFSHIFT"]}})
    await db.employees.insert_one({"id": EMP, "full_name": "ZZ Api Emp", "team": "T",
                                   "department": "D", "shift_type": "General", "is_deleted": False,
                                   "employee_status": "active"})

    async with httpx.AsyncClient(base_url=API, timeout=30, verify=True) as c:
        r = await c.post("/api/auth/login", json={"username": "sysadmin", "password": "pass123"})
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}

        # 1. Create shift 10:00
        r = await c.post("/api/settings/shifts", headers=H,
                         json={"name": "ZZEFFSHIFT", "start_time": "10:00", "total_hours": 9})
        check("create shift 10:00", r.status_code == 200, r.text[:120])
        shift_id = r.json()["id"]

        # 2. Assign effective 2026-01-01 (captures 10:00 snapshot)
        r = await c.post("/api/settings/shifts/assign", headers=H,
                         json={"employee_ids": [EMP], "shift_id": shift_id, "effective_from": "2026-01-01"})
        check("assign v1", r.status_code == 200, r.text[:120])
        a1 = await db.employee_shifts.find_one({"employee_id": EMP, "effective_from": "2026-01-01"}, {"_id": 0})
        check("v1 snapshot = 10:00", a1 and a1.get("shift_start_time") == "10:00")

        # 3. EDIT shift master to 10:30 — must NOT rewrite history
        r = await c.put(f"/api/settings/shifts/{shift_id}", headers=H, json={"start_time": "10:30"})
        check("edit shift -> 10:30", r.status_code == 200, r.text[:120])
        a1b = await db.employee_shifts.find_one({"id": a1["id"]}, {"_id": 0})
        check("history preserved: v1 still 10:00 after edit", a1b.get("shift_start_time") == "10:00")

        # 4. Reassign effective 2026-09-18 (captures fresh 10:30 snapshot; closes v1)
        r = await c.post("/api/settings/shifts/assign", headers=H,
                         json={"employee_ids": [EMP], "shift_id": shift_id, "effective_from": "2026-09-18"})
        check("assign v2", r.status_code == 200, r.text[:120])
        a2 = await db.employee_shifts.find_one({"employee_id": EMP, "effective_from": "2026-09-18"}, {"_id": 0})
        check("v2 snapshot = 10:30", a2 and a2.get("shift_start_time") == "10:30")
        a1c = await db.employee_shifts.find_one({"id": a1["id"]}, {"_id": 0})
        check("v1 closed at 2026-09-17", a1c.get("effective_to") == "2026-09-17")
        check("v1 snapshot STILL 10:00", a1c.get("shift_start_time") == "10:00")

        # 5. Assignment list API surfaces the frozen snapshot start time
        r = await c.get(f"/api/settings/shifts/assignments?employee_id={EMP}", headers=H)
        rows = {row["effective_from"]: row for row in r.json()}
        check("list v1 start_time=10:00 (snapshot)", rows.get("2026-01-01", {}).get("shift_start_time") == "10:00")
        check("list v2 start_time=10:30 (snapshot)", rows.get("2026-09-18", {}).get("shift_start_time") == "10:30")

        # cleanup shift + assignments (soft) and the temp employee
        await c.delete(f"/api/settings/shifts/assignments/{a1['id']}", headers=H)
        await c.delete(f"/api/settings/shifts/assignments/{a2['id']}", headers=H)

    await db.employees.delete_many({"id": EMP})
    await db.employee_shifts.delete_many({"employee_id": EMP})
    await db.shifts.delete_many({"id": shift_id})

    passed = sum(results)
    print(f"\n==== {passed}/{len(results)} PASSED ====")
    if passed != len(results):
        raise SystemExit(1)


asyncio.run(main())
