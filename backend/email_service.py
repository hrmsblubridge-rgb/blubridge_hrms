"""Centralized HRMS email send + audit + dedup engine.

Everything goes through `send_hrms_email()`:
  • Global preflight (valid email, employee active/not terminated).
  • Idempotency (email_audit_logs unique on email_type + scope_key).
  • Retry counter + failure logging.
  • Deep-link helper for employee action URLs.

The jobs module is the ONLY caller; no API routes touch this directly.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

import resend
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("hrms.email")

FRONTEND_BASE = os.environ.get("FRONTEND_BASE_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
ADMIN_REPORT_RECIPIENT = os.environ.get("ADMIN_REPORT_RECIPIENT", "hrmsblubridge@gmail.com")

EXCLUDED_EMPLOYEE_STATUSES = {"Inactive", "Terminated", "Resigned", "Exited"}


def generate_employee_action_link(route: str, date_str: Optional[str] = None) -> str:
    """Build a deep-link URL to the employee portal.

    Example: generate_employee_action_link('/employee/late-request', '02-05-2026')
    """
    base = FRONTEND_BASE.rstrip("/")
    url = f"{base}{route}"
    if date_str:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}date={date_str}"
    return url


async def _is_email_eligible(emp: dict) -> bool:
    if not emp:
        return False
    if emp.get("is_deleted"):
        return False
    if emp.get("employee_status") in EXCLUDED_EMPLOYEE_STATUSES:
        return False
    email = emp.get("official_email") or emp.get("email")
    if not email or "@" not in email:
        return False
    return True


async def _already_sent(db: AsyncIOMotorDatabase, email_type: str, scope_key: str) -> bool:
    existing = await db.email_audit_logs.find_one(
        {"email_type": email_type, "scope_key": scope_key, "status": "sent"},
        {"_id": 0, "id": 1},
    )
    return existing is not None


async def _record_audit(
    db: AsyncIOMotorDatabase,
    *,
    email_type: str,
    scope_key: str,
    recipient_email: str,
    employee_id: Optional[str],
    status: str,
    error: Optional[str] = None,
    provider_id: Optional[str] = None,
    retry_count: int = 0,
) -> None:
    doc = {
        "email_type": email_type,
        "scope_key": scope_key,
        "recipient_email": recipient_email,
        "employee_id": employee_id,
        "status": status,
        "error": error,
        "provider_id": provider_id,
        "retry_count": retry_count,
        "sent_at": datetime.utcnow().isoformat(),
    }
    try:
        await db.email_audit_logs.insert_one(doc)
    except Exception as e:  # never let audit breakage block sends
        logger.warning("email audit insert failed: %s", e)


async def send_hrms_email(
    db: AsyncIOMotorDatabase,
    *,
    email_type: str,
    scope_key: str,
    to_email: str,
    subject: str,
    html: str,
    employee_id: Optional[str] = None,
    cc: Optional[list] = None,
    max_retries: int = 2,
    force: bool = False,
) -> bool:
    """Send an HRMS email with dedup + retry + audit.

    scope_key uniquely identifies the "thing" this email is about — e.g.
    "admin_summary:02-05-2026" or f"{employee_id}:02-05-2026". If an earlier
    send for the same (email_type, scope_key) succeeded, we skip.

    `cc` (optional): list of additional email addresses copied via CC. Failure
    to attach CC NEVER blocks delivery — the primary `to_email` always goes.

    `force=True`: bypass dedup (used by the admin "Run Now" trigger). The
    scope_key is suffixed with a timestamp so the unique audit index never
    collides with prior sends.
    """
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set — skipping %s", email_type)
        return False

    if force:
        scope_key = f"{scope_key}:manual:{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}"
    elif await _already_sent(db, email_type, scope_key):
        return False

    # Sanitize CC: dedupe, drop the primary recipient if present, drop blanks.
    cc_clean: list = []
    seen = {to_email.lower().strip()}
    if cc:
        for raw in cc:
            if not raw:
                continue
            e = str(raw).strip()
            if not e or "@" not in e:
                continue
            key = e.lower()
            if key in seen:
                continue
            seen.add(key)
            cc_clean.append(e)

    attempt = 0
    last_err: Optional[str] = None
    provider_id: Optional[str] = None
    cc_to_use = cc_clean
    cc_dropped_reason: Optional[str] = None
    while attempt <= max_retries:
        try:
            params = {"from": SENDER_EMAIL, "to": [to_email], "subject": subject, "html": html}
            if cc_to_use:
                params["cc"] = cc_to_use
            result: Any = await asyncio.to_thread(resend.Emails.send, params)
            provider_id = (result or {}).get("id") if isinstance(result, dict) else None
            await _record_audit(
                db,
                email_type=email_type,
                scope_key=scope_key,
                recipient_email=to_email,
                employee_id=employee_id,
                status="sent",
                provider_id=provider_id,
                retry_count=attempt,
                error=cc_dropped_reason,  # surfaces "cc dropped after rejection: ..." if applicable
            )
            if cc_dropped_reason:
                logger.warning("email sent WITHOUT cc due to provider rejection (%s) type=%s scope=%s", cc_dropped_reason, email_type, scope_key)
            else:
                logger.info("email sent type=%s scope=%s to=%s cc=%d id=%s", email_type, scope_key, to_email, len(cc_to_use or []), provider_id)
            return True
        except Exception as e:
            last_err = str(e)
            # FAIL-SAFE: if the failure was while CC was attached, drop CC and
            # retry once so the PRIMARY recipient still gets the email. CC
            # issues must NEVER block delivery to the primary `to_email`.
            if cc_to_use:
                logger.warning("send failed with CC (%s) — retrying without CC type=%s scope=%s", e, email_type, scope_key)
                cc_dropped_reason = f"cc dropped after rejection: {e}"
                cc_to_use = []
                # don't increment attempt — give primary a clean retry without CC
                continue
            attempt += 1
            await asyncio.sleep(1.5 * attempt)

    await _record_audit(
        db,
        email_type=email_type,
        scope_key=scope_key,
        recipient_email=to_email,
        employee_id=employee_id,
        status="failed",
        error=last_err,
        retry_count=attempt,
    )
    logger.error("email failed type=%s scope=%s err=%s", email_type, scope_key, last_err)
    return False


async def send_hrms_email_multi(
    db: AsyncIOMotorDatabase,
    *,
    email_type: str,
    base_scope_key: str,
    recipients: list,
    subject: str,
    html: str,
    employee_id: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Fan out a single logical HRMS email to MULTIPLE recipients, sending each
    one as its OWN Resend message (no CC). This isolates per-recipient bounce/
    suppression failures so one bad address never blocks delivery to others.

    Each recipient is given a unique audit scope: `{base_scope_key}:{email_lower}`.
    Returns a summary dict { sent: int, skipped: int, failed: int, total: int }.
    """
    seen: set = set()
    clean_recipients: list = []
    for raw in recipients or []:
        if not raw:
            continue
        e = str(raw).strip()
        if not e or "@" not in e:
            continue
        k = e.lower()
        if k in seen:
            continue
        seen.add(k)
        clean_recipients.append(e)

    sent = skipped = failed = 0
    for rcpt in clean_recipients:
        scope = f"{base_scope_key}:{rcpt.lower()}"
        before_already = (not force) and await _already_sent(db, email_type, scope)
        ok = await send_hrms_email(
            db,
            email_type=email_type,
            scope_key=scope,
            to_email=rcpt,
            subject=subject,
            html=html,
            employee_id=employee_id,
            cc=None,  # NEVER use CC — per-recipient isolation is the whole point
            force=force,
        )
        if ok:
            sent += 1
        elif before_already:
            skipped += 1
        else:
            failed += 1
    logger.info(
        "fanout email_type=%s base_scope=%s total=%d sent=%d skipped=%d failed=%d",
        email_type, base_scope_key, len(clean_recipients), sent, skipped, failed,
    )
    return {"total": len(clean_recipients), "sent": sent, "skipped": skipped, "failed": failed}


async def ensure_email_indexes(db: AsyncIOMotorDatabase) -> None:
    try:
        await db.email_audit_logs.create_index(
            [("email_type", 1), ("scope_key", 1)],
            unique=True,
            partialFilterExpression={"status": "sent"},
            name="unique_email_type_scope_sent",
        )
        await db.email_audit_logs.create_index([("sent_at", -1)])
    except Exception as e:
        logger.warning("email_audit_logs index setup: %s", e)


async def ensure_cron_settings_seed(db: AsyncIOMotorDatabase, job_names: list[str]) -> None:
    """Seed `cron_settings` with each known job at `enabled: true` if absent.
    Never overwrites existing rows — admin toggles persist across restarts."""
    try:
        await db.cron_settings.create_index([("job_name", 1)], unique=True, name="cron_settings_job_unique")
    except Exception as e:
        logger.warning("cron_settings index setup: %s", e)
    for jn in job_names:
        try:
            await db.cron_settings.update_one(
                {"job_name": jn},
                {"$setOnInsert": {"job_name": jn, "enabled": True, "last_run_at": None, "last_result": None, "last_error": None}},
                upsert=True,
            )
        except Exception as e:
            logger.warning("cron_settings seed for %s failed: %s", jn, e)
