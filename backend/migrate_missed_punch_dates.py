"""One-time migration: convert YYYY-MM-DD attendance records produced by the
old missed-punch engine into the canonical DD-MM-YYYY format. If a DD-MM-YYYY
record already exists for the same (employee_id, date), merge the corrected
values onto it and delete the duplicate YYYY-MM-DD row.

Safe to re-run: operates only on records whose date still matches YYYY-MM-DD.
"""
import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    bad = await db.attendance.find(
        {"date": {"$regex": r"^\d{4}-\d{2}-\d{2}$"}}, {"_id": 0}
    ).to_list(5000)

    print(f"Found {len(bad)} attendance records with YYYY-MM-DD dates")

    merged = 0
    renamed = 0
    skipped = 0

    for rec in bad:
        old_date = rec["date"]
        try:
            new_date = datetime.strptime(old_date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            skipped += 1
            continue

        emp_id = rec.get("employee_id")
        existing = await db.attendance.find_one(
            {"employee_id": emp_id, "date": new_date}, {"_id": 0}
        )

        if existing:
            # Merge: corrected record wins on the fields it set.
            merge_fields = {}
            for k in (
                "check_in", "check_in_24h", "check_out", "check_out_24h",
                "total_hours", "total_hours_decimal", "status", "is_lop",
                "lop_reason", "expected_logout", "source",
                "missed_punch_corrected", "missed_punch_request_id",
                "missed_punch_corrected_at", "missed_punch_corrected_by",
            ):
                if k in rec and rec[k] is not None:
                    merge_fields[k] = rec[k]
            if merge_fields:
                await db.attendance.update_one(
                    {"employee_id": emp_id, "date": new_date},
                    {"$set": merge_fields},
                )
            await db.attendance.delete_one({"id": rec["id"]})
            merged += 1
            print(f"  merged {emp_id} {old_date} -> {new_date}")
        else:
            # Rename the date in place
            await db.attendance.update_one(
                {"id": rec["id"]},
                {"$set": {"date": new_date}},
            )
            renamed += 1
            print(f"  renamed {emp_id} {old_date} -> {new_date}")

    print(f"\nDone. merged={merged} renamed={renamed} skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
