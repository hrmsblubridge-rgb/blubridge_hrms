"""Policy Acknowledgement — 48-hour reminder automation.

Mirrors the architecture of `onboarding_completion.py`:
  • Pure state: `policy_ack_state` collection, one row per employee
    {employee_id, last_reminder_sent_at, reminder_count, last_pending_count,
     last_recipient_email, updated_at}
  • Reminder cadence: per-employee 48 hours; cron wakes every 6 hours.
  • PILOT mode (default): scan restricted to `pilot_email` only — no other
    employee row is touched until `enable_bulk_policy_ack_mail` is True.
  • Idempotent: when an employee has zero pending policies, no email is sent
    and the state's reminder_count is NOT incremented.

This module is intentionally thin and dependency-injects everything it needs
(db, the "pending policies for employee" resolver, the email-sending helper).
That keeps server.py as the only place that owns the policy-visibility rules
and the `_is_policy_visible_to_user` async helper.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pytz import timezone as pytz_timezone

logger = logging.getLogger("hrms.policy_ack")
IST = pytz_timezone("Asia/Kolkata")

PILOT_RECIPIENT_EMAIL = "rishi.nayak@blubridge.com"
REMINDER_INTERVAL_HOURS = 48
SETTINGS_DOC_ID = "policy_ack_mail"


def _ist_now() -> datetime:
    return datetime.now(IST)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=IST)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=IST)
    except Exception:
        return None


async def ensure_state_indexes(db: AsyncIOMotorDatabase) -> None:
    try:
        await db.policy_ack_state.create_index("employee_id", unique=True)
    except Exception as e:
        logger.warning("policy_ack_state index create failed: %s", e)


async def get_settings(db: AsyncIOMotorDatabase) -> dict:
    doc = await db.settings.find_one({"_id": SETTINGS_DOC_ID}) or {}
    return {
        "enable_bulk_policy_ack_mail": bool(doc.get("enable_bulk_policy_ack_mail", False)),
        "pilot_email": doc.get("pilot_email") or PILOT_RECIPIENT_EMAIL,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


async def _upsert_state(db: AsyncIOMotorDatabase, employee_id: str, patch: dict) -> None:
    patch = {**patch, "updated_at": _ist_now().isoformat()}
    await db.policy_ack_state.update_one(
        {"employee_id": employee_id},
        {"$set": patch, "$setOnInsert": {"employee_id": employee_id}},
        upsert=True,
    )


async def run_policy_ack_cycle(
    db: AsyncIOMotorDatabase,
    *,
    list_pending_for_employee: Callable[[str, str, str], Awaitable[list]],
    send_reminder_email: Callable[..., Awaitable[bool]],
    force: bool = False,
    target_employee_id: Optional[str] = None,
) -> dict:
    """Main entry — scans employees, dispatches reminders to anyone with
    pending policies who hasn't been pinged in the last 48 hours.

    Parameters:
        list_pending_for_employee(emp_id, role, dept) -> list[policy dict]
            Injected from server.py since policy-visibility logic lives there.
        send_reminder_email(emp, pending, to_email) -> bool
            Injected helper that builds the HTML and calls send_hrms_email.
        force=True bypasses the 48h cadence check (used by /run-now).
        target_employee_id restricts the scan to one employee.
    """
    settings = await get_settings(db)
    pilot_only = not settings["enable_bulk_policy_ack_mail"]
    pilot_email = settings["pilot_email"] or PILOT_RECIPIENT_EMAIL

    q: dict[str, Any] = {"is_deleted": {"$ne": True}, "employee_status": {"$ne": "Inactive"}}
    if target_employee_id:
        q["id"] = target_employee_id
    elif pilot_only:
        import re as _re
        # PHASE-1 SAFETY — scan limited to the pilot recipient only. Same
        # principle as onboarding_completion: no incidental spam during test.
        q["official_email"] = {"$regex": f"^{_re.escape(pilot_email)}$", "$options": "i"}

    employees = await db.employees.find(
        q,
        {"_id": 0, "id": 1, "full_name": 1, "official_email": 1, "department": 1},
    ).to_list(2000)
    if not employees:
        return {"scanned": 0, "reminders_sent": 0, "skipped": 0, "pilot_mode": pilot_only}

    emp_ids = [e["id"] for e in employees]

    # Bulk-fetch roles (single query) — minimises N+1 hits to users table.
    user_role_map: dict[str, str] = {}
    async for u in db.users.find(
        {"employee_id": {"$in": emp_ids}}, {"_id": 0, "employee_id": 1, "role": 1}
    ):
        user_role_map[u["employee_id"]] = u.get("role", "employee")

    # Bulk-fetch state.
    state_by_emp: dict[str, dict] = {}
    async for s in db.policy_ack_state.find(
        {"employee_id": {"$in": emp_ids}}, {"_id": 0}
    ):
        state_by_emp[s["employee_id"]] = s

    reminders_sent = 0
    skipped = 0

    for emp in employees:
        emp_id = emp["id"]
        role = user_role_map.get(emp_id, "employee")
        dept = emp.get("department") or ""

        try:
            pending = await list_pending_for_employee(emp_id, role, dept)
        except Exception as e:
            logger.exception("pending lookup failed emp=%s: %s", emp_id, e)
            skipped += 1
            continue

        if not pending:
            # Nothing to do — employee is fully acknowledged. We do NOT
            # touch the state here so the next run is consistent.
            skipped += 1
            continue

        state = state_by_emp.get(emp_id, {})
        if not force:
            last_sent = _parse_iso(state.get("last_reminder_sent_at"))
            if last_sent:
                delta_h = (_ist_now() - last_sent).total_seconds() / 3600.0
                if delta_h < REMINDER_INTERVAL_HOURS:
                    skipped += 1
                    continue

        to_email = pilot_email if pilot_only else (emp.get("official_email") or pilot_email)
        if not to_email:
            skipped += 1
            continue

        try:
            ok = await send_reminder_email(emp=emp, pending=pending, to_email=to_email)
        except Exception as e:
            logger.exception("send failed emp=%s: %s", emp_id, e)
            skipped += 1
            continue

        if ok:
            new_count = int(state.get("reminder_count") or 0) + 1
            await _upsert_state(db, emp_id, {
                "email": emp.get("official_email"),
                "full_name": emp.get("full_name"),
                "last_reminder_sent_at": _ist_now().isoformat(),
                "reminder_count": new_count,
                "last_pending_count": len(pending),
                "last_recipient_email": to_email,
            })
            reminders_sent += 1
            logger.info(
                "[policy_ack] reminder #%d sent emp=%s pending=%d to=%s pilot=%s",
                new_count, emp_id, len(pending), to_email, pilot_only,
            )
        else:
            skipped += 1

    return {
        "scanned": len(employees),
        "reminders_sent": reminders_sent,
        "skipped": skipped,
        "pilot_mode": pilot_only,
        "pilot_email": pilot_email,
    }
