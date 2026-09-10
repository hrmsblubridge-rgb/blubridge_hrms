"""One-off global repair: re-run the corrected BRSF calculation for every stored
employee + month so P01 (and the other automated criteria) reflect the fixed logic.

Uses the SAME calculation service (`brsf_stars.sync_lines`), so manual overrides,
child overrides and manual entries are preserved and no duplicate rows are created.
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

import server  # noqa: E402
import brsf_stars  # noqa: E402


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    dbx = cli[os.environ["DB_NAME"]]
    server.db = dbx
    brsf_stars.db = dbx

    pairs = await dbx.brsf_star_lines.aggregate([
        {"$group": {"_id": {"e": "$employee_id", "y": "$year", "m": "$month"}}}
    ]).to_list(None)
    print("employee/month records:", len(pairs))

    emp_cache, changed, skipped = {}, [], 0
    for i, p in enumerate(sorted(pairs, key=lambda x: (x["_id"]["y"], x["_id"]["m"]))):
        eid, month = p["_id"]["e"], f"{p['_id']['y']:04d}-{p['_id']['m']:02d}"
        if eid not in emp_cache:
            emp_cache[eid] = await dbx.employees.find_one({"id": eid}, {"_id": 0})
        emp = emp_cache[eid]
        if not emp:
            skipped += 1
            continue
        before = {d["code"]: (d.get("system_value"), d.get("final_value"))
                  async for d in dbx.brsf_star_lines.find(
                      {"employee_id": eid, "year": p["_id"]["y"], "month": p["_id"]["m"]},
                      {"_id": 0, "code": 1, "system_value": 1, "final_value": 1})}
        lines = await brsf_stars.sync_lines(emp, month)
        for ln in lines:
            b = before.get(ln["code"])
            if b and (b[0] != ln.get("system_value") or b[1] != ln.get("final_value")):
                changed.append((emp.get("full_name"), month, ln["code"],
                                b[0], ln.get("system_value"), b[1], ln.get("final_value")))
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{len(pairs)}")

    print("skipped (employee missing):", skipped)
    print("changed lines:", len(changed))
    for c in changed:
        print(f"  {c[0]:26} {c[1]}  {c[2]}  system {c[3]} -> {c[4]}   final {c[5]} -> {c[6]}")
    p01 = [c for c in changed if c[2] == "P01"]
    print("P01 lines corrected:", len(p01))

    dup = await dbx.brsf_star_lines.aggregate([
        {"$group": {"_id": {"e": "$employee_id", "y": "$year", "m": "$month", "c": "$code"},
                    "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
    ]).to_list(None)
    print("duplicate (employee, month, code) rows:", len(dup))


asyncio.run(main())
