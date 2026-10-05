"""
Tests Settings -> Assign Shift employee listing:
  - default = ACTIVE only
  - name search spans active + inactive
  - one row per employee with LATEST shift assignment (history preserved)
  - unassigned active employees still appear
  - assignments list latest_per_employee dedupe
Seeds isolated data (prefix ZZLIST) and cleans up.
"""
import asyncio
import os
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
API = "http://localhost:8001"
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

A, B, C = "zzlist-a", "zzlist-b", "zzlist-c"
results = []
def check(n, c, extra=""):
    results.append(c); print(("PASS" if c else "FAIL"), "-", n, extra)


async def cleanup():
    await db.employees.delete_many({"id": {"$in": [A, B, C]}})
    await db.employee_shifts.delete_many({"employee_id": {"$in": [A, B, C]}})


async def seed():
    await cleanup()
    await db.employees.insert_many([
        {"id": A, "full_name": "ZZLIST Alpha", "emp_id": "ZZL001", "department": "Eng", "team": "T1",
         "designation": "Dev", "employee_status": "Active", "is_deleted": False},
        {"id": B, "full_name": "ZZLIST Bravo", "emp_id": "ZZL002", "department": "Eng", "team": "T1",
         "designation": "Dev", "employee_status": "Active", "is_deleted": False},
        {"id": C, "full_name": "ZZLIST Charlie", "emp_id": "ZZL003", "department": "Eng", "team": "T1",
         "designation": "Dev", "employee_status": "Inactive", "is_deleted": False},
    ])
    def asn(eid, ef, name, start, created):
        return {"id": f"{eid}-{ef}", "employee_id": eid, "shift_id": f"sh-{start}",
                "effective_from": ef, "effective_to": None, "is_deleted": False,
                "shift_name": name, "shift_start_time": start, "shift_total_hours": 9.0,
                "created_at": created}
    # A: three history records -> latest is Sep / New Shift
    await db.employee_shifts.insert_many([
        asn(A, "2026-01-01", "General Shift", "09:00", "2026-01-01T00:00:00"),
        asn(A, "2026-06-01", "Morning Shift", "08:00", "2026-06-01T00:00:00"),
        asn(A, "2026-09-18", "New Shift", "10:30", "2026-09-18T00:00:00"),
    ])
    # B: no assignment
    # C: inactive, two records -> latest is Aug
    await db.employee_shifts.insert_many([
        asn(C, "2025-01-01", "Shift A", "09:00", "2025-01-01T00:00:00"),
        asn(C, "2025-08-01", "Shift B", "10:00", "2025-08-01T00:00:00"),
    ])


async def main():
    await seed()
    async with httpx.AsyncClient(base_url=API, timeout=40) as c:
        tok = (await c.post("/api/auth/login", json={"username": "sysadmin", "password": "pass123"})).json()["token"]
        H = {"Authorization": f"Bearer {tok}"}

        # DEFAULT (no search) -> active only
        rows = (await c.get("/api/settings/shifts/assignable-employees", headers=H)).json()
        by_id = {r["id"]: r for r in rows if r["id"] in (A, B, C)}
        check("TEST1 default includes A (active)", A in by_id)
        check("TEST6 default includes B (active, unassigned)", B in by_id)
        check("TEST1 default EXCLUDES C (inactive)", C not in by_id)
        # one row per employee
        check("TEST4/7 one row per employee (A once)", sum(1 for r in rows if r["id"] == A) == 1)
        # A latest = New Shift
        check("TEST4 A latest shift = New Shift", by_id.get(A, {}).get("latest_shift_name") == "New Shift",
              str(by_id.get(A, {}).get("latest_shift_name")))
        check("TEST4 A latest effective = 2026-09-18", by_id.get(A, {}).get("latest_effective_from") == "2026-09-18")
        # B unassigned -> no latest shift
        check("TEST6 B has no latest shift", by_id.get(B, {}).get("latest_shift_name") in (None, ""),
              str(by_id.get(B, {}).get("latest_shift_name")))

        # SEARCH inactive by name -> C appears
        rows2 = (await c.get("/api/settings/shifts/assignable-employees", headers=H, params={"search": "Charlie"})).json()
        cids = {r["id"]: r for r in rows2}
        check("TEST2 search finds inactive C", C in cids)
        check("TEST5 C shows Inactive status", cids.get(C, {}).get("employee_status") == "Inactive")
        check("TEST5 C latest = Shift B (2025-08-01)", cids.get(C, {}).get("latest_shift_name") == "Shift B"
              and cids.get(C, {}).get("latest_effective_from") == "2025-08-01")
        check("TEST5 C only one row", sum(1 for r in rows2 if r["id"] == C) == 1)

        # SEARCH 'ZZLIST' -> all three (active + inactive)
        rows3 = (await c.get("/api/settings/shifts/assignable-employees", headers=H, params={"search": "ZZLIST"})).json()
        ids3 = {r["id"] for r in rows3}
        check("TEST2 search spans active+inactive (A,B,C)", {A, B, C}.issubset(ids3))

        # history preserved in DB (not deleted)
        hist = await db.employee_shifts.count_documents({"employee_id": A, "is_deleted": {"$ne": True}})
        check("TEST/history: A still has 3 assignment records", hist == 3, str(hist))

        # assignments?latest_per_employee=true -> one row per employee
        la = (await c.get("/api/settings/shifts/assignments", headers=H,
                          params={"employee_id": A, "latest_per_employee": "true"})).json()
        check("latest_per_employee: A -> 1 row", len(la) == 1 and la[0].get("shift_name") == "New Shift", str(len(la)))

    await cleanup()
    p = sum(results)
    print(f"\n==== {p}/{len(results)} PASSED ====")
    if p != len(results):
        raise SystemExit(1)


asyncio.run(main())
