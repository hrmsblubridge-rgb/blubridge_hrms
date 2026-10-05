"""
One-time backfill: stamp a frozen shift snapshot onto existing employee_shifts
assignments that predate the snapshot feature. Uses the CURRENT linked shift
config — accurate because no shift master has been edited yet, so current ==
historical for every existing assignment. Idempotent: skips assignments that
already carry a snapshot.
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]


async def main(apply: bool):
    shifts = {s["id"]: s async for s in db.shifts.find({}, {"_id": 0})}
    total = 0
    updated = 0
    skipped = 0
    missing_shift = 0
    async for a in db.employee_shifts.find({"is_deleted": {"$ne": True}}, {"_id": 0}):
        total += 1
        if a.get("shift_start_time"):
            skipped += 1
            continue
        shift = shifts.get(a.get("shift_id"))
        if not shift:
            missing_shift += 1
            continue
        snap = {
            "shift_name": shift.get("name"),
            "shift_start_time": shift.get("start_time"),
            "shift_total_hours": float(shift.get("total_hours") or 0),
            "shift_late_grace_minutes": int(shift.get("late_grace_minutes", 0) or 0),
            "shift_early_out_grace_minutes": int(shift.get("early_out_grace_minutes", 0) or 0),
        }
        updated += 1
        if apply:
            await db.employee_shifts.update_one({"id": a["id"]}, {"$set": snap})
    print(f"{'APPLIED' if apply else 'DRY-RUN'}: total={total} snapshotted={updated} "
          f"already_had_snapshot={skipped} missing_shift={missing_shift}")


if __name__ == "__main__":
    import sys
    asyncio.run(main("--apply" in sys.argv))
