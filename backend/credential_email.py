"""Credential Email Delivery — Permanent, reliable system for sending
new-employee login credentials.

Design:
- Runs from FastAPI `BackgroundTasks` (survives the request lifecycle) OR
  can be invoked directly (idempotent).
- 3-attempt retry with exponential back-off (2s, 4s, 8s) — total ≤ 14s.
- Persists delivery status on the employee document:
    credential_email_status         : "pending" | "sent" | "failed"
    credential_email_sent_at        : ISO timestamp (only on success)
    credential_email_attempts       : int (cumulative)
    credential_email_last_error     : short error string (on failure)
    credential_email_last_attempt_at: ISO timestamp of most recent try
- Duplicate protection: refuses to resend if `credential_email_status == "sent"`
  unless the caller passes `force=True` (used by the Resend button which
  ALSO regenerates the password).
- Admin-only `POST /api/employees/{id}/resend-credentials` regenerates a fresh
  temp password, updates the user record, and re-triggers the email.

Environment:
- RESEND_API_KEY  (mandatory in production; if missing, status → "failed"
  with a clear error so Admin sees it in the UI)
- SENDER_EMAIL    (defaults to `hrms@blubridge.ai`)
- FRONTEND_URL    (used to build the login link; defaults to
  REACT_APP_BACKEND_URL replacement)
"""
import asyncio
import logging
import os
import re
import secrets
import string
from datetime import datetime, timezone

import resend
from fastapi import Depends, HTTPException, BackgroundTasks

from server import (
    api_router, db, get_current_user, ALL_ADMIN_ROLES,
    hash_password, log_audit,
)

log = logging.getLogger("hrms.credential_email")

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = [2, 4, 8]  # index by (attempt - 1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_email(raw: str) -> str:
    """Trim + lowercase. Returns empty string on garbage input."""
    if not raw or not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def _valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email))


def _default_login_url() -> str:
    """Resolve the credential-email login button URL via the shared
    email_service.absolute_url so it stays in sync with every other outgoing
    HRMS email (single source of truth = FRONTEND_BASE_URL / FRONTEND_URL,
    with `https://blubrg.com` as the safe fallback)."""
    try:
        from email_service import absolute_url
        return absolute_url("/login")
    except Exception:
        return "https://blubrg.com/login"


def _build_welcome_html(name: str, emp_id: str, username: str, password: str, login_url: str) -> str:
    """Build the credential email body. Delegates to server.get_welcome_email
    if available, otherwise uses a minimal fallback (still safe / readable)."""
    try:
        from server import get_welcome_email
        return get_welcome_email(name, emp_id, username, password, login_url)
    except Exception:
        return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;padding:20px;color:#333">
        <h2>Welcome to BluBridge, {name}!</h2>
        <p>Your HRMS account is ready. Please use the credentials below to sign in and change your password.</p>
        <table style="border-collapse:collapse">
          <tr><td style="padding:6px 12px"><b>Login URL</b></td><td><a href="{login_url}">{login_url}</a></td></tr>
          <tr><td style="padding:6px 12px"><b>Employee ID</b></td><td>{emp_id}</td></tr>
          <tr><td style="padding:6px 12px"><b>Username</b></td><td>{username}</td></tr>
          <tr><td style="padding:6px 12px"><b>Temporary Password</b></td><td><code>{password}</code></td></tr>
        </table>
        <p style="color:#666;font-size:12px">Please change this password after your first login. If you have any questions, contact HR at hrms@blubridge.ai.</p>
        </body></html>"""


async def _persist_status(employee_id: str, status: str, error: str = "", inc_attempts: bool = True):
    update = {"$set": {
        "credential_email_status": status,
        "credential_email_last_attempt_at": _now(),
    }}
    if error:
        update["$set"]["credential_email_last_error"] = error[:500]
    if status == "sent":
        update["$set"]["credential_email_sent_at"] = _now()
        update["$set"]["credential_email_last_error"] = ""
    if inc_attempts:
        update["$inc"] = {"credential_email_attempts": 1}
    await db.employees.update_one({"id": employee_id}, update)


def _generate_temp_password(length: int = 10) -> str:
    """Cryptographically-secure temporary password — mix of letters + digits.
    No punctuation to avoid copy/paste issues from email clients."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def deliver_credential_email(
    employee_id: str,
    *,
    username: str,
    password: str,
    force: bool = False,
    triggered_by: str = "system",
) -> bool:
    """Send the credential email with retries. Returns True on success.
    Idempotent — if the employee record already has `status == 'sent'` and
    `force=False`, this is a no-op (returns True immediately)."""
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not emp:
        log.error("[cred-email] employee %s not found", employee_id)
        return False

    if not force and emp.get("credential_email_status") == "sent":
        log.info("[cred-email] already sent to %s — skipping (idempotent)", emp.get("official_email"))
        return True

    email = _normalize_email(emp.get("official_email"))
    if not _valid_email(email):
        await _persist_status(employee_id, "failed", "Invalid or missing employee email address")
        log.error("[cred-email] invalid email on employee %s: %r", employee_id, emp.get("official_email"))
        return False

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        await _persist_status(employee_id, "failed", "RESEND_API_KEY not configured on server")
        log.error("[cred-email] RESEND_API_KEY missing — cannot send to %s", email)
        return False

    resend.api_key = api_key
    sender = os.environ.get("SENDER_EMAIL", "hrms@blubridge.ai")
    login_url = _default_login_url()
    html = _build_welcome_html(
        name=emp.get("full_name") or "Colleague",
        emp_id=emp.get("emp_id") or "",
        username=username,
        password=password,
        login_url=login_url,
    )
    params = {
        "from": sender,
        "to": [email],
        "subject": f"Welcome to BluBridge — Your Login Credentials ({emp.get('emp_id', '')})",
        "html": html,
    }

    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            log.info("[cred-email] attempt %d/%d → %s", attempt, MAX_ATTEMPTS, email)
            result = await asyncio.to_thread(resend.Emails.send, params)
            # Resend returns dict with 'id'; treat presence as success.
            if result and (isinstance(result, dict) and result.get("id")):
                await _persist_status(employee_id, "sent", inc_attempts=True)
                await log_audit(
                    triggered_by if triggered_by != "system" else employee_id,
                    "credential_email_sent",
                    "employee",
                    employee_id,
                    f"delivered to {email} on attempt {attempt}",
                )
                log.info("[cred-email] ✓ delivered to %s (msg_id=%s)", email, result.get("id"))
                return True
            last_error = f"Unexpected provider response: {result!r}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            log.warning("[cred-email] attempt %d failed: %s", attempt, last_error)

        await _persist_status(employee_id, "pending", last_error, inc_attempts=True)
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])

    # All attempts failed
    await _persist_status(employee_id, "failed", last_error, inc_attempts=False)
    log.error("[cred-email] ✗ all %d attempts failed for %s: %s", MAX_ATTEMPTS, email, last_error)
    return False


def schedule_credential_email(
    background_tasks: BackgroundTasks,
    employee_id: str,
    username: str,
    password: str,
    *,
    force: bool = False,
    triggered_by: str = "system",
):
    """Queue delivery on FastAPI's BackgroundTasks. Preferred over
    `asyncio.create_task` because FastAPI awaits these before shutdown."""
    background_tasks.add_task(
        deliver_credential_email,
        employee_id,
        username=username,
        password=password,
        force=force,
        triggered_by=triggered_by,
    )


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
def _require_admin(user):
    if user.get("role") not in ALL_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")


@api_router.post("/employees/{employee_id}/resend-credentials")
async def resend_credentials(
    employee_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Admin-triggered resend. Regenerates a fresh temp password, updates the
    user record and re-sends the credential email (bypasses idempotency)."""
    _require_admin(current_user)

    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    email = _normalize_email(emp.get("official_email"))
    if not _valid_email(email):
        raise HTTPException(status_code=400, detail="Employee has no valid email address")

    user = await db.users.find_one({"employee_id": employee_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=400, detail="No user account exists for this employee")

    new_password = _generate_temp_password()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_hash": hash_password(new_password),
            "password_reset_at": _now(),
            "password_reset_by": current_user.get("username"),
        }},
    )
    await db.employees.update_one(
        {"id": employee_id},
        {"$set": {"credential_email_status": "pending",
                  "credential_email_last_error": ""}},
    )

    schedule_credential_email(
        background_tasks,
        employee_id,
        username=user["username"],
        password=new_password,
        force=True,
        triggered_by=current_user.get("id", "system"),
    )
    await log_audit(
        current_user["id"], "credential_email_resend_triggered", "employee",
        employee_id, f"resend queued to {email}",
    )
    return {"success": True, "queued_for": email}


@api_router.get("/employees/{employee_id}/credential-email-status")
async def get_credential_email_status(
    employee_id: str, current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    emp = await db.employees.find_one(
        {"id": employee_id},
        {"_id": 0, "credential_email_status": 1, "credential_email_sent_at": 1,
         "credential_email_attempts": 1, "credential_email_last_error": 1,
         "credential_email_last_attempt_at": 1, "official_email": 1, "full_name": 1},
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp
