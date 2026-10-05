"""
One-time repair for biometric mapping bug (leading-space biometric_id).

Root cause: employees Balamanikandan S (3088), Viswanathan G (3085),
Dommaraju Kavya (3087) have a leading space in `biometric_id` (e.g. ' 3088').
The import endpoint stripped the incoming deviceUserId but NOT the bio_map key,
so their punches were stored as status="unmapped" and never produced attendance.

This script ONLY re-labels those already-captured unmapped punches to "mapped"
with the correct employee_id + effective date, so they become consistent with
normally-mapped logs. It does NOT touch any other deviceUserId, does NOT create
attendance rows directly, and does NOT modify recordTime values.

Attendance is then rebuilt via the existing /attendance/recompute-from-punches
endpoint, which by design SKIPS approved missed-punch corrections and manual
overrides — so all corrected punch times are preserved.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

IST = timezone(timedelta(hours=5, minutes=30))
THRESHOLD = int(os.environ.get("CROSS_MIDNIGHT_THRESHOLD_MINUTES", "300"))

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

# deviceUserId (as stored WITHOUT space) -> employee_id
TARGETS = {
    "3088": "6abd19de-cf4c-449e-8fbc-ea29c61e321a",  # Balamanikandan S
    "3085": "8d272a8f-6f63-44a2-b373-8f7b56ea029e",  # Viswanathan G
    "3087": "f3f94982-1acf-4411-aa2b-94d8119c97d5",  # Dommaraju Kavya
}


def effective_date(record_time: str):
    dt = datetime.fromisoformat(record_time.replace("Z", "+00:00"))
    p = dt.astimezone(IST)
    mins = p.hour * 60 + p.minute
    eff = p - timedelta(days=1) if mins <= THRESHOLD else p
    return eff.strftime("%d-%m-%Y")


async def main(apply: bool):
    docs_touched = 0
    entries_remapped = 0
    async for doc in db.biometric_punch_logs.find(
        {"logs": {"$elemMatch": {"deviceUserId": {"$in": list(TARGETS)}, "status": "unmapped"}}}
    ):
        logs = doc.get("logs", [])
        changed = False
        for entry in logs:
            duid = entry.get("deviceUserId")
            if entry.get("status") == "unmapped" and duid in TARGETS:
                entry["status"] = "mapped"
                entry["employee_id"] = TARGETS[duid]
                entry["date"] = effective_date(entry["recordTime"])
                entry["remapped_by_repair"] = "biometric_space_fix_2026_06"
                changed = True
                entries_remapped += 1
        if changed:
            docs_touched += 1
            if apply:
                await db.biometric_punch_logs.update_one(
                    {"_id": doc["_id"]}, {"$set": {"logs": logs}}
                )

    print(f"{'APPLIED' if apply else 'DRY-RUN'}: docs_touched={docs_touched} entries_remapped={entries_remapped}")


if __name__ == "__main__":
    import sys
    apply = "--apply" in sys.argv
    asyncio.run(main(apply))
