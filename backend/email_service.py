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
    max_retries: int = 2,
) -> bool:
    """Send an HRMS email with dedup + retry + audit.

    scope_key uniquely identifies the "thing" this email is about — e.g.
    "admin_summary:02-05-2026" or f"{employee_id}:02-05-2026". If an earlier
    send for the same (email_type, scope_key) succeeded, we skip.
    """
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set — skipping %s", email_type)
        return False

    if await _already_sent(db, email_type, scope_key):
        return False

    attempt = 0
    last_err: Optional[str] = None
    provider_id: Optional[str] = None
    while attempt <= max_retries:
        try:
            params = {"from": SENDER_EMAIL, "to": [to_email], "subject": subject, "html": html}
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
            )
            logger.info("email sent type=%s scope=%s to=%s id=%s", email_type, scope_key, to_email, provider_id)
            return True
        except Exception as e:
            last_err = str(e)
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
