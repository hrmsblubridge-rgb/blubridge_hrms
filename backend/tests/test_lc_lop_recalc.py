"""Regression test for LC/LOP payroll recalculation fix.
Seeds isolated test data (tagged), verifies payroll respects the CURRENT late
request LOP/NO_LOP status, then deletes ONLY the test records it created.
"""
import asyncio, os, uuid, json, urllib.request, urllib.parse, calendar
from datetime import date
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv('/app/backend/.env')
API = os.environ.get('EXT_API')  # injected by shell
MONGO = os.environ['MONGO_URL']
DBN = os.environ['DB_NAME']
TAG = "LCTEST_QA"

def api_get(path, token):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def login():
    return os.environ['QA_TOKEN']

async def main():
    token = login()
    c = AsyncIOMotorClient(MONGO); db = c[DBN]
    # pick an active employee with a joining date well in the past
    emp = await db.employees.find_one(
        {"is_deleted": {"$ne": True}, "employee_status": "Active"},
        {"_id": 0, "id": 1, "full_name": 1, "department": 1, "joining_date": 1})
    eid = emp['id']
    year, mon = 2026, 5  # May 2026 (fully past relative to Jun 2026)
    # find 2 weekdays with NO existing attendance & NO existing late request
    existing_att = set()
    async for a in db.attendance.find({"employee_id": eid, "date": {"$regex": f"^{year}-{mon:02d}"}}, {"_id": 0, "date": 1}):
        existing_att.add(a.get("date"))
    existing_late = set()
    async for l in db.late_requests.find({"employee_id": eid, "date": {"$regex": f"^{year}-{mon:02d}"}}, {"_id": 0, "date": 1}):
        existing_late.add(l.get("date"))
    picks = []
    for day in range(12, calendar.monthrange(year, mon)[1] + 1):
        d = date(year, mon, day)
        iso = d.strftime("%Y-%m-%d")
        if d.weekday() < 5 and iso not in existing_att and iso not in existing_late:
            picks.append(iso)
        if len(picks) == 2:
            break
    assert len(picks) == 2, "could not find 2 free weekdays"
    print("EMP", emp['full_name'], "dept", emp.get('department'), "dates", picks)

    async def seed(is_lop):
        # clean any prior test rows first
        await db.attendance.delete_many({"_lctest": TAG})
        await db.late_requests.delete_many({"lop_remark": TAG})
        for iso in picks:
            await db.attendance.insert_one({
                "id": str(uuid.uuid4()), "employee_id": eid, "date": iso,
                "check_in": "10:45 AM", "check_in_24h": "10:45",
                "check_out": "11:00 PM", "check_out_24h": "23:00",
                "total_hours": "12h 15m", "total_hours_decimal": 12.25,
                "_lctest": TAG,
            })
            await db.late_requests.insert_one({
                "id": str(uuid.uuid4()), "employee_id": eid, "emp_name": emp['full_name'],
                "date": iso, "expected_time": "10:00", "actual_time": "10:45",
                "reason": "QA late", "status": "approved", "is_lop": is_lop,
                "lop_remark": TAG,
            })

    def statuses(payroll):
        m = {}
        for d in payroll.get("attendance_details", []):
            m[d.get("date")] = (d.get("status"), d.get("lop_value"))
        return m

    picks_dd = [f"{p[8:10]}-{p[5:7]}-{p[0:4]}" for p in picks]

    # Scenario A: current status LOP -> expect LC + 0.5
    await seed(is_lop=True)
    p = api_get(f"/api/payroll/{eid}?month={year}-{mon:02d}", token)
    st = statuses(p)
    print("LOP  ->", {dd: st.get(dd) for dd in picks_dd})
    ok_lop = all(st.get(dd, (None,))[0] == "LC" and st.get(dd)[1] == 0.5 for dd in picks_dd)

    # Scenario B: admin changes to NO_LOP -> expect P (excused, full day)
    await db.late_requests.update_many({"lop_remark": TAG}, {"$set": {"is_lop": False}})
    p = api_get(f"/api/payroll/{eid}?month={year}-{mon:02d}", token)
    st = statuses(p)
    print("NOLOP->", {dd: st.get(dd) for dd in picks_dd})
    ok_nolop = all(st.get(dd, (None,))[0] == "P" for dd in picks_dd)

    # Scenario C: change back NO_LOP -> LOP -> expect LC again (recalc, not stale)
    await db.late_requests.update_many({"lop_remark": TAG}, {"$set": {"is_lop": True}})
    p = api_get(f"/api/payroll/{eid}?month={year}-{mon:02d}", token)
    st = statuses(p)
    print("LOP2 ->", {dd: st.get(dd) for dd in picks_dd})
    ok_lop2 = all(st.get(dd, (None,))[0] == "LC" and st.get(dd)[1] == 0.5 for dd in picks_dd)

    # CLEANUP — delete ONLY tagged test rows
    r1 = await db.attendance.delete_many({"_lctest": TAG})
    r2 = await db.late_requests.delete_many({"lop_remark": TAG})
    print(f"CLEANUP deleted att={r1.deleted_count} late={r2.deleted_count}")

    print("RESULT", {"LOP->LC/0.5": ok_lop, "NO_LOP->P": ok_nolop, "LOP2->LC/0.5(recalc)": ok_lop2})
    assert ok_lop and ok_nolop and ok_lop2, "LC/LOP recalculation FAILED"
    print("ALL PASS")

asyncio.run(main())
