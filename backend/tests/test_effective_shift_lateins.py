"""
Validates effective-dated Late-In resolution against the REAL server helpers
(get_effective_shift_timings + calculate_attendance_status). Seeds isolated
test data, runs req #22 test cases, then removes the seed. Read-only w.r.t.
real employees/attendance.
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import server  # real app module (does NOT start schedulers on import)

load_dotenv('/app/backend/.env')
# Rebind motor client to THIS process's event loop (avoids cross-loop errors)
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
server.db = db
EFF = server.get_effective_shift_timings
CALC = server.calculate_attendance_status

EMP_A = "zz-shifttest-emp-a"
EMP_B = "zz-shifttest-emp-b"
EMP_C = "zz-shifttest-emp-c"

results = []
def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(("PASS" if cond else "FAIL"), "-", name, extra)


async def seed():
    await cleanup()
    for eid in (EMP_A, EMP_B, EMP_C):
        await db.employees.insert_one({"id": eid, "full_name": f"ZZ Test {eid[-1].upper()}",
                                       "team": "T", "department": "D", "shift_type": "General",
                                       "is_deleted": False})
    def asn(eid, ef, et, start, total=9.0):
        return {"id": f"asn-{eid}-{ef}", "employee_id": eid, "shift_id": f"sh-{start}",
                "effective_from": ef, "effective_to": et, "is_deleted": False,
                "shift_name": f"Shift {start}", "shift_start_time": start,
                "shift_total_hours": total, "shift_late_grace_minutes": 0,
                "shift_early_out_grace_minutes": 0}
    # Employee A: reassigned 10:00 -> 10:30 effective 18-09-2026
    await db.employee_shifts.insert_many([
        asn(EMP_A, "2026-01-01", "2026-09-17", "10:00"),
        asn(EMP_A, "2026-09-18", None, "10:30"),
    ])
    # Employee B: NOT reassigned — single open-ended 10:00 assignment
    await db.employee_shifts.insert_one(asn(EMP_B, "2026-01-01", None, "10:00"))
    # Employee C: multiple future changes 10:00 -> 10:30 (18-09) -> 11:00 (01-11)
    await db.employee_shifts.insert_many([
        asn(EMP_C, "2026-01-01", "2026-09-17", "10:00"),
        asn(EMP_C, "2026-09-18", "2026-10-31", "10:30"),
        asn(EMP_C, "2026-11-01", None, "11:00"),
    ])


async def cleanup():
    await db.employees.delete_many({"id": {"$in": [EMP_A, EMP_B, EMP_C]}})
    await db.employee_shifts.delete_many({"employee_id": {"$in": [EMP_A, EMP_B, EMP_C]}})


def is_late(res):
    st = res.get("status")
    reason = (res.get("lop_reason") or "").lower()
    return st == server.AttendanceStatus.LATE_LOGIN or (bool(res.get("is_lop")) and "late" in reason)


async def main():
    await seed()
    empA = await db.employees.find_one({"id": EMP_A}, {"_id": 0})
    empB = await db.employees.find_one({"id": EMP_B}, {"_id": 0})
    empC = await db.employees.find_one({"id": EMP_C}, {"_id": 0})

    # --- Effective resolution of shift start per date (req #21) ---
    async def start_on(emp, d):
        t = await EFF(emp, d)
        return (t or {}).get("login_time")

    check("A 16-09 -> 10:00", await start_on(empA, "16-09-2026") == "10:00")
    check("A 17-09 -> 10:00", await start_on(empA, "17-09-2026") == "10:00")
    check("A 18-09 -> 10:30", await start_on(empA, "18-09-2026") == "10:30")
    check("A 19-09 -> 10:30", await start_on(empA, "19-09-2026") == "10:30")
    check("B 18-09 -> 10:00 (not reassigned)", await start_on(empB, "18-09-2026") == "10:00")
    check("C 31-10 -> 10:30", await start_on(empC, "31-10-2026") == "10:30")
    check("C 01-11 -> 11:00", await start_on(empC, "01-11-2026") == "11:00")

    # Helper: run status for an employee/date/punch. check_out set to meet hours
    # so a genuine late shows as LATE_LOGIN, on-time shows PRESENT.
    async def late_result(emp, date, punch_in, punch_out="20:00"):
        t = await EFF(emp, date)
        return CALC(punch_in, punch_out, t, attendance_date=date)

    # TEST 1 & 2 — old 10:00 shift boundary (date under 10:00 window)
    check("T1 10:00 shift, 10:00 -> Not Late", not is_late(await late_result(empA, "17-09-2026", "10:00")))
    check("T2 10:00 shift, 10:01 -> Late", is_late(await late_result(empA, "17-09-2026", "10:01")))

    # TEST 3 — historical date before change uses 10:00 => 10:10 Late
    check("T3 17-09 punch 10:10 -> Late (10:00 applies)", is_late(await late_result(empA, "17-09-2026", "10:10")))

    # TEST 4 — effective date 18-09 uses 10:30 => 10:27 Not Late
    r4 = await late_result(empA, "18-09-2026", "10:27")
    check("T4 18-09 punch 10:27 -> Not Late (10:30 applies)", not is_late(r4))

    # TEST 5 & 6 — boundary at 10:30 shift
    check("T5 10:30 shift, 10:30 -> Not Late", not is_late(await late_result(empA, "18-09-2026", "10:30")))
    check("T6 10:30 shift, 10:31 -> Late", is_late(await late_result(empA, "18-09-2026", "10:31")))

    # TEST 7 — Employee B not reassigned: 18-09 punch 10:10 -> Late (10:00 still applies)
    check("T7 B 18-09 punch 10:10 -> Late (still 10:00)", is_late(await late_result(empB, "18-09-2026", "10:10")))
    #        and B punch 10:00 -> Not Late
    check("T7b B 18-09 punch 10:00 -> Not Late", not is_late(await late_result(empB, "18-09-2026", "10:00")))

    # TEST 28 — future multi-change for C (use 02-11 Monday; 01-11-2026 is Sunday)
    check("C 02-11 punch 11:00 -> Not Late", not is_late(await late_result(empC, "02-11-2026", "11:00")))
    check("C 02-11 punch 11:01 -> Late", is_late(await late_result(empC, "02-11-2026", "11:01")))
    check("C 31-10 punch 10:31 -> Late (10:30)", is_late(await late_result(empC, "31-10-2026", "10:31")))

    await cleanup()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== {passed}/{len(results)} PASSED ====")
    if passed != len(results):
        raise SystemExit(1)


asyncio.run(main())
