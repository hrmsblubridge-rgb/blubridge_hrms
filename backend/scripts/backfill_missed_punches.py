"""One-time / cron-runnable Historical Backfill Script.

Applies APPROVED missed-punch corrections that were never propagated to the
final attendance table. Reuses the production engine in `server.py` so the
behaviour matches the live approval flow exactly.

Idempotent: safe to run as many times as you want — already-applied requests
are skipped via the `correction_applied_at` flag and the
`attendance_corrections` audit collection.

Usage:
    cd /app/backend && python scripts/backfill_missed_punches.py [--dry-run]
                                                                  [--batch-size 1000]
                                                                  [--from YYYY-MM-DD]
                                                                  [--to YYYY-MM-DD]
                                                                  [--employee-id ID]
                                                                  [--force]
"""
import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

# Allow `import server` regardless of where the script is launched from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import server  # noqa: E402


async def run(args):
    db = server.db

    q = {"status": "approved"}
    if not args.force:
        q["$or"] = [
            {"correction_applied_at": {"$exists": False}},
            {"correction_applied_at": None},
        ]
    if args.employee_id:
        q["employee_id"] = args.employee_id
    if args.from_date or args.to_date:
        date_q = {}
        if args.from_date:
            date_q["$gte"] = args.from_date
        if args.to_date:
            date_q["$lte"] = args.to_date
        q["date"] = date_q

    cursor = db.missed_punches.find(q, {"_id": 0})
    candidates = await cursor.to_list(args.batch_size)

    print(f"Found {len(candidates)} approved missed-punch request(s) needing apply.")
    if args.dry_run:
        print("[DRY RUN] No mutations will be performed.")

    applied = skipped = invalid = 0
    errors = []

    for i, rec in enumerate(candidates, 1):
        rid = rec.get("id")
        ptype = (rec.get("punch_type") or "").strip()

        if not args.force and rid:
            prior = await db.attendance_corrections.find_one({"request_id": rid}, {"_id": 0})
            if prior:
                if not rec.get("correction_applied_at") and not args.dry_run:
                    await db.missed_punches.update_one(
                        {"id": rid},
                        {"$set": {
                            "correction_applied_at": prior.get("created_at") or server.get_ist_now().isoformat(),
                            "correction_applied_by": prior.get("approved_by") or "system_backfill",
                            "is_applied": True,
                        }},
                    )
                skipped += 1
                continue

        if ptype == "Check-in" and not rec.get("check_in_time"):
            invalid += 1
            errors.append((rid, "Check-in request missing check_in_time"))
            continue
        if ptype == "Check-out" and not rec.get("check_out_time"):
            invalid += 1
            errors.append((rid, "Check-out request missing check_out_time"))
            continue
        if ptype == "Both" and not (rec.get("check_in_time") and rec.get("check_out_time")):
            invalid += 1
            errors.append((rid, "Both request missing one or both times"))
            continue

        if args.dry_run:
            applied += 1
            continue

        rec_for_engine = dict(rec)
        rec_for_engine["approved_by"] = rec.get("approved_by") or "system_backfill"
        rec_for_engine["approved_at"] = rec.get("approved_at") or server.get_ist_now().isoformat()

        try:
            await server._update_attendance_from_missed_punch(rec_for_engine)
            applied += 1
        except Exception as e:
            errors.append((rid, str(e)))

        if i % 100 == 0:
            print(f"  …processed {i}/{len(candidates)}  applied={applied} skipped={skipped} invalid={invalid}")

    print()
    print(f"Done. applied={applied}  skipped_already_applied={skipped}  invalid={invalid}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for rid, reason in errors[:20]:
            print(f"  - {rid}: {reason}")
        if len(errors) > 20:
            print(f"  …{len(errors) - 20} more")


def main():
    p = argparse.ArgumentParser(description="Apply historical approved missed-punch corrections to attendance.")
    p.add_argument("--dry-run", action="store_true", help="Don't mutate anything; just print counts.")
    p.add_argument("--batch-size", type=int, default=1000, help="Max requests to process per run.")
    p.add_argument("--from", dest="from_date", default=None, help="Filter missed_punches.date >= YYYY-MM-DD.")
    p.add_argument("--to", dest="to_date", default=None, help="Filter missed_punches.date <= YYYY-MM-DD.")
    p.add_argument("--employee-id", default=None, help="Restrict to a single employee.")
    p.add_argument("--force", action="store_true", help="Re-apply even if already marked applied.")
    args = p.parse_args()
    try:
        asyncio.run(run(args))
    finally:
        # Motor leaves a background watcher task — explicit close stops the
        # script from hanging when invoked from cron / a CI runner.
        try:
            server.client.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
