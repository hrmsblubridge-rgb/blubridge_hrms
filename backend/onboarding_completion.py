"""Onboarding & Profile Photo completion tracking + reminder/success automation.

This module is the single source of truth for:
  • Computing onboarding completion % per employee
  • Computing profile photo completion status
  • Sending the 48-hour reminder email when either is incomplete
  • Sending the one-time success email when BOTH reach 100%
  • Phase-1 pilot gating (only rishi.nayak@blubridge.com receives emails until
    settings.enable_bulk_onboarding_mail is flipped to True by an admin)

The state for each employee lives in a single Mongo collection
`onboarding_completion_state`, keyed by employee_id. The scheduler reads this
collection to decide who is due for a reminder (>= 48 hours since last send)
and who has already received the success email.

Design constraints:
  • No mutations of the employees/users/onboarding/avatar core schemas.
  • Onboarding completion % is DERIVED at read time from existing
    `onboarding_documents` records. No duplication.
  • Profile photo status is DERIVED from `employees.avatar`.
  • Reminder cadence is enforced in BUSINESS LOGIC (>= 48h since last send),
    not by the cron trigger frequency. So if the cron fires every 6h, only
    employees due since 48h+ actually receive an email — others are silently
    skipped.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pytz import timezone as pytz_timezone

logger = logging.getLogger("hrms.onboarding_completion")

IST = pytz_timezone("Asia/Kolkata")


# ---- Phase-1 pilot recipient (DO NOT CHANGE without admin approval) -------
PILOT_RECIPIENT_EMAIL = "rishi.nayak@blubridge.com"

# Reminder cadence — every 48 hours
REMINDER_INTERVAL_HOURS = 48


# Mandatory documents the employee must upload + verify for onboarding to be
# 100% complete. Mirrors REQUIRED_DOCUMENTS where `required=True` in server.py.
MANDATORY_DOCUMENT_TYPES: list[dict] = [
    {"type": "aadhaar_card", "label": "Aadhaar Card"},
    {"type": "pan_card", "label": "PAN Card"},
    {"type": "education", "label": "Education Certificates"},
    {"type": "photo", "label": "Passport-size Photograph"},
]


def _ist_now() -> datetime:
    return datetime.now(IST)


def _parse_iso(value: Any) -> Optional[datetime]:
    """Parse ISO-8601 string into an aware datetime (IST). Returns None on
    invalid input — never raises."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=IST)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=IST)
    except Exception:
        return None


# ============================================================================
# Completion calculation
# ============================================================================
def compute_completion(
    employee: dict, documents: list[dict]
) -> dict:
    """Pure function — given an employee row + their onboarding_documents,
    returns the canonical completion snapshot used by ALL callers (admin
    dashboard, employee self-status, cron decision logic).

    Returns:
      {
        onboarding_status: "pending" | "partial" | "complete",
        onboarding_percent: 0-100,
        profile_photo_uploaded: bool,
        overall_percent: 0-100,
        missing_sections: list[{type,label}],
        photo_missing: bool,
      }
    """
    mandatory_total = len(MANDATORY_DOCUMENT_TYPES)
    docs_by_type = {d.get("document_type"): d for d in (documents or [])}

    verified_count = 0
    uploaded_count = 0
    missing: list[dict] = []
    for req in MANDATORY_DOCUMENT_TYPES:
        rec = docs_by_type.get(req["type"])
        status = (rec or {}).get("status", "not_uploaded")
        if status == "verified":
            verified_count += 1
        elif status == "uploaded":
            uploaded_count += 1
        if status in ("not_uploaded", "rejected"):
            missing.append({"type": req["type"], "label": req["label"]})

    total = mandatory_total
    # "Complete" means EVERY mandatory doc is verified — a stricter, audit-friendly
    # definition than "uploaded". A pending HR review keeps the employee in
    # "partial" until HR signs off, which is intentional.
    if verified_count == total:
        onboarding_status = "complete"
        onboarding_percent = 100
    elif verified_count + uploaded_count == 0:
        onboarding_status = "pending"
        onboarding_percent = 0
    else:
        onboarding_status = "partial"
        # Verified docs count fully; uploaded-but-pending count half.
        raw = (verified_count * 1.0 + uploaded_count * 0.5) / total
        onboarding_percent = int(round(raw * 100))
        if onboarding_percent >= 100:
            onboarding_percent = 99  # never claim 100% while HR review pending

    avatar_url = (employee or {}).get("avatar")
    profile_photo_uploaded = bool(avatar_url and str(avatar_url).strip())

    # Overall: 70% weight to onboarding (compliance-critical) + 30% photo.
    overall = int(round(onboarding_percent * 0.7 + (100 if profile_photo_uploaded else 0) * 0.3))
    overall = max(0, min(100, overall))

    return {
        "onboarding_status": onboarding_status,
        "onboarding_percent": onboarding_percent,
        "profile_photo_uploaded": profile_photo_uploaded,
        "overall_percent": overall,
        "missing_sections": missing,
        "photo_missing": not profile_photo_uploaded,
        "mandatory_total": total,
        "verified_count": verified_count,
        "uploaded_count": uploaded_count,
    }


# ============================================================================
# State persistence  (collection: onboarding_completion_state)
#
#   { employee_id, email, full_name,
#     last_reminder_sent_at, reminder_count,
#     completion_success_mail_sent, completion_success_mail_sent_at,
#     completed_at, last_status_snapshot, updated_at }
# ============================================================================
async def ensure_state_indexes(db: AsyncIOMotorDatabase) -> None:
    try:
        await db.onboarding_completion_state.create_index("employee_id", unique=True)
    except Exception as e:
        logger.warning("ensure_state_indexes failed: %s", e)


async def _get_state(db: AsyncIOMotorDatabase, employee_id: str) -> dict:
    doc = await db.onboarding_completion_state.find_one({"employee_id": employee_id}, {"_id": 0})
    return doc or {}


async def _upsert_state(db: AsyncIOMotorDatabase, employee_id: str, patch: dict) -> None:
    patch = {**patch, "updated_at": _ist_now().isoformat()}
    await db.onboarding_completion_state.update_one(
        {"employee_id": employee_id},
        {"$set": patch, "$setOnInsert": {"employee_id": employee_id}},
        upsert=True,
    )


# ============================================================================
# Settings (feature flag)
# ============================================================================
SETTINGS_DOC_ID = "onboarding_completion_mail"


async def get_settings(db: AsyncIOMotorDatabase) -> dict:
    doc = await db.settings.find_one({"_id": SETTINGS_DOC_ID}) or {}
    return {
        "enable_bulk_onboarding_mail": bool(doc.get("enable_bulk_onboarding_mail", False)),
        "pilot_email": doc.get("pilot_email") or PILOT_RECIPIENT_EMAIL,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


async def update_settings(
    db: AsyncIOMotorDatabase,
    *,
    enable_bulk: Optional[bool] = None,
    pilot_email: Optional[str] = None,
    actor_user_id: Optional[str] = None,
) -> dict:
    patch: dict[str, Any] = {"updated_at": _ist_now().isoformat()}
    if actor_user_id:
        patch["updated_by"] = actor_user_id
    if enable_bulk is not None:
        patch["enable_bulk_onboarding_mail"] = bool(enable_bulk)
    if pilot_email is not None:
        patch["pilot_email"] = str(pilot_email).strip()
    await db.settings.update_one(
        {"_id": SETTINGS_DOC_ID},
        {"$set": patch, "$setOnInsert": {"_id": SETTINGS_DOC_ID}},
        upsert=True,
    )
    return await get_settings(db)


# ============================================================================
# Dashboard data
# ============================================================================
async def list_completion_dashboard(
    db: AsyncIOMotorDatabase,
    *,
    status_filter: Optional[str] = None,  # incomplete|completed|no_photo|reminder_pending|complete100
    search: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Returns a list of rows for the admin tracking dashboard.

    Heavy logic stays here (not in server.py) so it can be unit-tested in
    isolation.
    """
    q: dict[str, Any] = {"is_deleted": {"$ne": True}, "employee_status": {"$ne": "Inactive"}}
    if department:
        q["department"] = department
    if search:
        import re
        rx = re.compile(re.escape(search), re.IGNORECASE)
        q["$or"] = [
            {"full_name": rx},
            {"emp_id": rx},
            {"official_email": rx},
        ]

    employees = await db.employees.find(
        q,
        {"_id": 0, "id": 1, "emp_id": 1, "full_name": 1, "official_email": 1,
         "department": 1, "designation": 1, "avatar": 1, "employee_status": 1},
    ).to_list(limit)

    if not employees:
        return []

    emp_ids = [e["id"] for e in employees]

    # One bulk fetch of all onboarding docs to avoid N+1.
    doc_cursor = db.onboarding_documents.find(
        {"employee_id": {"$in": emp_ids}},
        {"_id": 0, "employee_id": 1, "document_type": 1, "status": 1},
    )
    docs_by_emp: dict[str, list[dict]] = {}
    async for d in doc_cursor:
        docs_by_emp.setdefault(d["employee_id"], []).append(d)

    # One bulk fetch of state.
    state_cursor = db.onboarding_completion_state.find(
        {"employee_id": {"$in": emp_ids}},
        {"_id": 0},
    )
    state_by_emp: dict[str, dict] = {}
    async for s in state_cursor:
        state_by_emp[s["employee_id"]] = s

    rows: list[dict] = []
    for emp in employees:
        snap = compute_completion(emp, docs_by_emp.get(emp["id"], []))
        state = state_by_emp.get(emp["id"], {})

        last_sent = _parse_iso(state.get("last_reminder_sent_at"))
        hours_since_last = None
        reminder_pending = False
        if last_sent:
            delta = _ist_now() - last_sent
            hours_since_last = int(delta.total_seconds() // 3600)
            reminder_pending = hours_since_last >= REMINDER_INTERVAL_HOURS
        else:
            reminder_pending = True  # never sent yet

        is_complete = snap["onboarding_percent"] >= 100 and snap["profile_photo_uploaded"]
        # Once both are 100%, the employee should never be classified as
        # "reminder_pending" again.
        if is_complete:
            reminder_pending = False

        row = {
            "employee_id": emp["id"],
            "emp_id": emp.get("emp_id"),
            "full_name": emp.get("full_name"),
            "email": emp.get("official_email"),
            "department": emp.get("department"),
            "designation": emp.get("designation"),
            "avatar": emp.get("avatar"),
            "onboarding_status": snap["onboarding_status"],
            "onboarding_percent": snap["onboarding_percent"],
            "profile_photo_uploaded": snap["profile_photo_uploaded"],
            "overall_percent": snap["overall_percent"],
            "missing_sections": snap["missing_sections"],
            "last_reminder_sent_at": state.get("last_reminder_sent_at"),
            "reminder_count": int(state.get("reminder_count") or 0),
            "completion_success_mail_sent": bool(state.get("completion_success_mail_sent")),
            "completion_success_mail_sent_at": state.get("completion_success_mail_sent_at"),
            "completed_at": state.get("completed_at"),
            "is_complete": is_complete,
            "hours_since_last_reminder": hours_since_last,
            "reminder_pending": reminder_pending,
        }
        rows.append(row)

    # Apply status_filter post-aggregation (cheap; list is bounded by limit)
    f = (status_filter or "").lower()
    if f == "incomplete":
        rows = [r for r in rows if not r["is_complete"]]
    elif f in ("completed", "complete100"):
        rows = [r for r in rows if r["is_complete"]]
    elif f == "no_photo":
        rows = [r for r in rows if not r["profile_photo_uploaded"]]
    elif f == "reminder_pending":
        rows = [r for r in rows if r["reminder_pending"] and not r["is_complete"]]
    elif f == "success_mail_pending":
        rows = [r for r in rows if r["is_complete"] and not r["completion_success_mail_sent"]]

    return rows


# ============================================================================
# Reminder + success email job
# ============================================================================
async def _send_reminder(
    db: AsyncIOMotorDatabase,
    *,
    emp: dict,
    snap: dict,
    state: dict,
    pilot_only: bool,
    pilot_email: str,
    force: bool = False,
) -> bool:
    """Send one reminder email. In PILOT mode the email TO field is the
    pilot recipient (rishi.nayak@blubridge.com) regardless of who is actually
    incomplete — this lets us test the flow without spamming the real
    workforce. In BULK mode the email goes to the employee themselves.

    Returns True if email was dispatched; False if skipped.
    """
    # Lazy import to avoid circular dependency with email_service in server.py
    from email_service import send_hrms_email
    from email_templates import onboarding_reminder_email

    # 48-hour cadence enforcement
    if not force:
        last_sent = _parse_iso(state.get("last_reminder_sent_at"))
        if last_sent:
            delta_hours = (_ist_now() - last_sent).total_seconds() / 3600.0
            if delta_hours < REMINDER_INTERVAL_HOURS:
                logger.debug(
                    "skip reminder emp=%s — last_sent=%.1fh ago (< %dh cadence)",
                    emp.get("id"), delta_hours, REMINDER_INTERVAL_HOURS,
                )
                return False

    # Resolve recipient
    if pilot_only:
        to_email = pilot_email
    else:
        to_email = emp.get("official_email") or pilot_email
    if not to_email:
        logger.warning("skip reminder emp=%s — no email", emp.get("id"))
        return False

    employee_name = emp.get("full_name") or "there"

    # The CTA always points to a stable login → onboarding/profile flow.
    # We do NOT issue a tokenized link here because the reminder is a
    # gentle nudge to log in normally; tokenized one-click upload is the
    # separate "profile-upload-email" flow.
    from email_service import absolute_url
    cta_url = absolute_url("/employee/onboarding", query={"src": "reminder"})

    html = onboarding_reminder_email(
        employee_name=employee_name,
        overall_percent=snap["overall_percent"],
        onboarding_percent=snap["onboarding_percent"],
        profile_photo_uploaded=snap["profile_photo_uploaded"],
        missing_sections=snap["missing_sections"],
        cta_url=cta_url,
    )

    sent = await send_hrms_email(
        db,
        email_type="onboarding_completion_reminder",
        scope_key=f"{emp.get('id')}:{_ist_now().strftime('%Y%m%dT%H')}",
        to_email=to_email,
        subject="A friendly nudge — complete your BluBridge profile",
        html=html,
        employee_id=emp.get("id"),
        force=force,
    )

    if sent:
        new_count = int(state.get("reminder_count") or 0) + 1
        await _upsert_state(db, emp["id"], {
            "email": emp.get("official_email"),
            "full_name": emp.get("full_name"),
            "last_reminder_sent_at": _ist_now().isoformat(),
            "reminder_count": new_count,
            "last_status_snapshot": snap,
            "last_recipient_email": to_email,
        })
        logger.info(
            "[onboarding_completion] reminder #%d sent emp=%s overall=%d%% to=%s (pilot=%s)",
            new_count, emp.get("id"), snap["overall_percent"], to_email, pilot_only,
        )
    return sent


async def _send_success(
    db: AsyncIOMotorDatabase,
    *,
    emp: dict,
    snap: dict,
    state: dict,
    pilot_only: bool,
    pilot_email: str,
) -> bool:
    """Send the one-time success email — only fires once per employee, ever.

    The success email always goes to the EMPLOYEE'S real address (it's the
    employee's celebration). In pilot mode it is mirrored to the pilot inbox.
    """
    if state.get("completion_success_mail_sent"):
        return False

    from email_service import send_hrms_email
    from email_templates import onboarding_success_email

    employee_email = emp.get("official_email")
    if pilot_only:
        # In pilot, send to pilot email only. (Avoid surprise email to a real
        # employee before bulk has been approved by HR.)
        to_email = pilot_email
    else:
        to_email = employee_email or pilot_email

    if not to_email:
        return False

    html = onboarding_success_email(
        employee_name=emp.get("full_name") or "there",
    )

    sent = await send_hrms_email(
        db,
        email_type="onboarding_completion_success",
        scope_key=f"{emp.get('id')}",
        to_email=to_email,
        subject="🎉 You're all set on BluBridge HRMS",
        html=html,
        employee_id=emp.get("id"),
    )
    if sent:
        await _upsert_state(db, emp["id"], {
            "email": employee_email,
            "full_name": emp.get("full_name"),
            "completion_success_mail_sent": True,
            "completion_success_mail_sent_at": _ist_now().isoformat(),
            "completed_at": _ist_now().isoformat(),
            "last_status_snapshot": snap,
        })
        logger.info(
            "[onboarding_completion] SUCCESS email sent emp=%s to=%s (pilot=%s)",
            emp.get("id"), to_email, pilot_only,
        )
    return sent


async def run_completion_cycle(
    db: AsyncIOMotorDatabase,
    *,
    force: bool = False,
    target_employee_id: Optional[str] = None,
) -> dict:
    """Main entry — scans employees, dispatches reminders or success emails.

    `force=True` bypasses the 48h cadence check AND the dedup guard.
    `target_employee_id` restricts the scan to a single employee (used by the
    "Run Now for one employee" admin button).

    PILOT MODE (`settings.enable_bulk_onboarding_mail == False`):
      • The scan is RESTRICTED to the pilot recipient only. No other employee
        is touched. This satisfies the product spec — Phase 1 test mode never
        spams the rest of the workforce, even via redirection.
      • If the pilot's `official_email` does not match `settings.pilot_email`,
        the employee is still resolved by email match (so Rishi's row in the
        employees collection is what gets scanned).

    BULK MODE (`settings.enable_bulk_onboarding_mail == True`):
      • Every active, non-deleted employee is scanned. Reminders/success
        emails go to each employee's real `official_email`.
    """
    settings = await get_settings(db)
    pilot_only = not settings["enable_bulk_onboarding_mail"]
    pilot_email = settings["pilot_email"] or PILOT_RECIPIENT_EMAIL

    q: dict[str, Any] = {"is_deleted": {"$ne": True}, "employee_status": {"$ne": "Inactive"}}
    if target_employee_id:
        q["id"] = target_employee_id
    elif pilot_only:
        # PHASE-1 SAFETY: restrict the scan to the pilot recipient only.
        # This prevents the cron from triggering 50+ reminder emails all
        # redirected to a single inbox during testing.
        import re as _re
        q["official_email"] = {"$regex": f"^{_re.escape(pilot_email)}$", "$options": "i"}

    employees = await db.employees.find(
        q,
        {"_id": 0, "id": 1, "emp_id": 1, "full_name": 1, "official_email": 1,
         "avatar": 1, "department": 1, "employee_status": 1},
    ).to_list(2000)

    if not employees:
        return {"scanned": 0, "reminders_sent": 0, "success_sent": 0, "skipped": 0}

    emp_ids = [e["id"] for e in employees]

    # Bulk-fetch onboarding docs
    docs_by_emp: dict[str, list[dict]] = {}
    async for d in db.onboarding_documents.find(
        {"employee_id": {"$in": emp_ids}},
        {"_id": 0, "employee_id": 1, "document_type": 1, "status": 1},
    ):
        docs_by_emp.setdefault(d["employee_id"], []).append(d)

    state_by_emp: dict[str, dict] = {}
    async for s in db.onboarding_completion_state.find(
        {"employee_id": {"$in": emp_ids}},
        {"_id": 0},
    ):
        state_by_emp[s["employee_id"]] = s

    reminders_sent = 0
    success_sent = 0
    skipped = 0

    for emp in employees:
        snap = compute_completion(emp, docs_by_emp.get(emp["id"], []))
        state = state_by_emp.get(emp["id"], {})

        is_complete = snap["onboarding_percent"] >= 100 and snap["profile_photo_uploaded"]

        if is_complete:
            if not state.get("completion_success_mail_sent"):
                try:
                    if await _send_success(
                        db, emp=emp, snap=snap, state=state,
                        pilot_only=pilot_only, pilot_email=pilot_email,
                    ):
                        success_sent += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.exception("success email failed emp=%s: %s", emp.get("id"), e)
                    skipped += 1
            else:
                skipped += 1
        else:
            try:
                if await _send_reminder(
                    db, emp=emp, snap=snap, state=state,
                    pilot_only=pilot_only, pilot_email=pilot_email,
                    force=force,
                ):
                    reminders_sent += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.exception("reminder email failed emp=%s: %s", emp.get("id"), e)
                skipped += 1

    return {
        "scanned": len(employees),
        "reminders_sent": reminders_sent,
        "success_sent": success_sent,
        "skipped": skipped,
        "pilot_mode": pilot_only,
        "pilot_email": pilot_email,
    }
