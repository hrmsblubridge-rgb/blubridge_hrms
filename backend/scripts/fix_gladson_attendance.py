"""Targeted attendance audit + correction for ONE employee.

Context
-------
`Gladson Anto` is the only employee whose `shift_type` was left as the legacy
string "General" (which resolves to the legacy 11h definition baked into
`SHIFT_DEFINITIONS`). Every other active employee was migrated to the
Settings-driven "General" shift (10h). Result: Gladson's daily ~10.2h working
hours are incorrectly flagged as `Loss of Pay` / `Early Out` because the
engine believes he owes 11 hours.

What this script does (idempotent + scope-limited):
  1. Locates the employee by name (`Gladson Anto`).
  2. Migrates his employee record to the Settings "General" shift via the
     same helper used by Add/Edit Employee — `_apply_settings_shift_to_employee_payload`.
     After this his shift_type becomes 'Custom' with custom_login_time=10:00,
     custom_total_hours=10, active_shift_name='General'.
  3. Walks every existing attendance record for this employee and re-evaluates
     it via `calculate_attendance_status` using the corrected shift timings.
     If the record's status is LOP/Early Out but the recomputed status says
     Completed/Present, it is corrected in place AND an audit row is written
     to `attendance_corrections` (re-using the same audit collection the
     missed-punch engine writes to — scoped via `source_after = 'targeted_fix'`
     so it's distinguishable from missed-punch corrections).
  4. NEVER touches any other employee's data.

Run:
    cd /app/backend && python /app/backend/scripts/fix_gladson_attendance.py [--dry-run]
"""
import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

import server  # noqa: E402

TARGET_NAME = "Gladson Anto"


async def fix(dry_run: bool):
    db = server.db

    emp = await db.employees.find_one(
        {"full_name": {"$regex": f"^{TARGET_NAME}$", "$options": "i"}, "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not emp:
        print(f"❌ Employee '{TARGET_NAME}' not found.")
        return

    emp_id = emp["id"]
    print(f"Target employee: id={emp_id}  name={emp['full_name']}")
    print(f"Current shift_type={emp.get('shift_type')}  active_shift_name={emp.get('active_shift_name')}  custom_total_hours={emp.get('custom_total_hours')}")

    # ── Step 1: migrate the employee shift to Settings-driven 'General' ──
    payload = {}
    payload = await server._apply_settings_shift_to_employee_payload(payload, "General")
    if not payload:
        print("⚠️  Settings 'General' shift not found — cannot proceed safely. Aborting.")
        return

    needs_emp_update = (
        emp.get("shift_type") != payload.get("shift_type")
        or emp.get("active_shift_id") != payload.get("active_shift_id")
        or emp.get("custom_total_hours") != payload.get("custom_total_hours")
    )
    print(f"\n[Step 1] Employee shift migration → "
          f"shift_type={payload.get('shift_type')}, "
          f"login={payload.get('custom_login_time')}, logout={payload.get('custom_logout_time')}, "
          f"total_hours={payload.get('custom_total_hours')}, "
          f"active_shift_name={payload.get('active_shift_name')}")
    if needs_emp_update and not dry_run:
        await db.employees.update_one({"id": emp_id}, {"$set": payload})
        print("  ✓ employee record updated")
    elif needs_emp_update:
        print("  [dry-run] would update employee record")
    else:
        print("  ✓ employee already migrated — no change")

    # Refresh employee object so calculate_attendance_status sees the new shift
    emp.update(payload)
    shift_timings = server.get_shift_timings(emp)
    print(f"\nShift timings used for re-eval: {shift_timings}")

    # ── Step 2: walk attendance records ──
    cursor = db.attendance.find({"employee_id": emp_id}, {"_id": 0})
    corrected = 0
    skipped_already_ok = 0
    skipped_no_in = 0
    skipped_genuine_short = 0
    audit_rows = []

    async for a in cursor:
        st = a.get("status")
        if st not in (server.AttendanceStatus.LOSS_OF_PAY, server.AttendanceStatus.EARLY_OUT):
            skipped_already_ok += 1
            continue

        check_in_24h = a.get("check_in_24h")
        check_out_24h = a.get("check_out_24h")
        if not check_in_24h:
            skipped_no_in += 1
            continue
        if not check_out_24h:
            skipped_genuine_short += 1  # genuinely no punch-out
            continue

        # Re-evaluate using the corrected shift timings
        recomputed = server.calculate_attendance_status(
            check_in_24h, check_out_24h, shift_timings or {}, attendance_date=a.get("date")
        )
        new_status = recomputed.get("status")
        new_is_lop = bool(recomputed.get("is_lop"))

        # Only correct if the recomputation says the employee is OK now
        if new_is_lop or new_status in (server.AttendanceStatus.LOSS_OF_PAY, server.AttendanceStatus.EARLY_OUT):
            skipped_genuine_short += 1
            continue

        total_decimal = float(recomputed.get("total_hours_decimal") or 0.0)
        update = {
            "status": new_status,
            "is_lop": new_is_lop,
            "lop_reason": recomputed.get("lop_reason"),
            "total_hours": server.calculate_total_hours_str(total_decimal) if total_decimal else None,
            "total_hours_decimal": round(total_decimal, 2),
            "expected_logout": recomputed.get("expected_logout"),
            "targeted_fix_at": server.get_ist_now().isoformat(),
            "targeted_fix_reason": "Shift mismatch — moved from legacy General(11h) to Settings General(10h)",
        }

        print(
            f"  ✓ {a.get('date')}: {st} → {new_status}  "
            f"({a.get('total_hours_decimal')}h, was 'is_lop={a.get('is_lop')}')"
        )

        if not dry_run:
            await db.attendance.update_one(
                {"employee_id": emp_id, "date": a.get("date")},
                {"$set": update},
            )

        audit_rows.append({
            "id": str(uuid.uuid4()),
            "request_id": None,
            "employee_id": emp_id,
            "emp_name": emp.get("full_name"),
            "date": a.get("date"),
            "punch_type": "ShiftReeval",
            "old_check_in": a.get("check_in"),
            "old_check_in_24h": check_in_24h,
            "old_check_out": a.get("check_out"),
            "old_check_out_24h": check_out_24h,
            "old_status": st,
            "new_check_in": a.get("check_in"),
            "new_check_in_24h": check_in_24h,
            "new_check_out": a.get("check_out"),
            "new_check_out_24h": check_out_24h,
            "new_status": new_status,
            "new_total_hours": update["total_hours"],
            "approved_by": "targeted_audit_script",
            "approved_at": server.get_ist_now().isoformat(),
            "source_before": a.get("source", "biometric"),
            "source_after": "targeted_fix",
            "fix_note": "Gladson-only shift mismatch fix (legacy 11h → Settings 10h)",
            "created_at": server.get_ist_now().isoformat(),
        })
        corrected += 1

    if audit_rows and not dry_run:
        await db.attendance_corrections.insert_many([r.copy() for r in audit_rows])

    print()
    print("─" * 60)
    print(f"Done.  corrected={corrected}  already_ok={skipped_already_ok}  "
          f"no_in={skipped_no_in}  genuinely_short={skipped_genuine_short}  "
          f"dry_run={dry_run}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        asyncio.run(fix(args.dry_run))
    finally:
        try:
            server.client.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
