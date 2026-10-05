"""Payslip Module — additional 6-digit authorization layer (Admin side only).

Access rule enforced by this module:

    Valid HRMS login  +  Admin/Payslip RBAC  +  Payslip auth verified for THIS
    session  +  verified code version == current code version   =>  access

Design notes
------------
* The code is NEVER stored, logged, emailed-back or returned in plain text.
  Only a salted PBKDF2-SHA256 hash is persisted.
* Verification is bound to the server-side HRMS session (JWT `session_id`),
  so logout / session expiry / re-login always require the code again.
* Regenerating bumps `auth_code_version`; every previously verified session
  becomes invalid immediately (version mismatch) without forcing a logout.
* Regeneration is commit-after-send: the new hash is activated ONLY when the
  email to the fixed recipient succeeded, so an admin can never be locked out.
* CSRF: the API is stateless Bearer-token auth (no cookies / no ambient
  credentials), so a cross-site request cannot carry the admin's token.
"""
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Body, Depends, HTTPException, Request

from email_service import send_hrms_email
from server import (
    ALL_ADMIN_ROLES,
    UserRole,
    api_router,
    db,
    get_current_user,
    get_ist_now,
    log_audit,
)

CONFIG_ID = "payslip_auth"
RECIPIENT_EMAIL = "hrrecruiter@blubridge.com"
INITIAL_CODE = "082026"
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15
REGEN_COOLDOWN_MINUTES = 5
# Only this HRMS username may regenerate the code (user mandate 2026-06-09).
REGEN_USERNAME = "admin"
PBKDF2_ROUNDS = 200_000


# ------------------------------------------------------------------ helpers
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", code.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS
    ).hex()


def _new_salt() -> str:
    return os.urandom(16).hex()


def generate_code() -> str:
    """Cryptographically secure 6-digit code, zero padded (000000-999999)."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def ensure_payslip_security_seed():
    """Bootstrap the configuration with the initial code (hash only)."""
    existing = await db.payslip_security_settings.find_one({"id": CONFIG_ID})
    if existing:
        return
    salt = _new_salt()
    await db.payslip_security_settings.insert_one({
        "id": CONFIG_ID,
        "auth_code_salt": salt,
        "auth_code_hash": _hash_code(INITIAL_CODE, salt),
        "auth_code_version": 1,
        "last_regenerated_at": None,
        "last_regenerated_by": None,
        "created_at": _utc_now().isoformat(),
        "updated_at": _utc_now().isoformat(),
    })
    await db.payslip_auth_sessions.create_index("session_id", unique=True)
    await db.payslip_auth_attempts.create_index("user_id", unique=True)


async def _config() -> dict:
    cfg = await db.payslip_security_settings.find_one({"id": CONFIG_ID}, {"_id": 0})
    if not cfg:
        await ensure_payslip_security_seed()
        cfg = await db.payslip_security_settings.find_one({"id": CONFIG_ID}, {"_id": 0})
    return cfg


async def _audit(user: dict, action: str, detail: str = "", request: Optional[Request] = None):
    ip = None
    if request is not None:
        ip = request.headers.get("x-forwarded-for") or (
            request.client.host if request.client else None
        )
    await db.payslip_security_audit.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_name": user.get("full_name") or user.get("username"),
        "action": action,
        "detail": detail,
        "ip": ip,
        "timestamp": get_ist_now().isoformat(),
    })
    await log_audit(user.get("id"), action, "payslip_security", CONFIG_ID, detail)


async def is_session_verified(session_id: str) -> bool:
    """True when this HRMS session verified the CURRENT code version."""
    if not session_id:
        return False
    row = await db.payslip_auth_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not row:
        return False
    cfg = await _config()
    return int(row.get("code_version") or 0) == int(cfg["auth_code_version"])


async def _attempt_state(user_id: str) -> dict:
    row = await db.payslip_auth_attempts.find_one({"user_id": user_id}, {"_id": 0}) or {}
    locked_until = row.get("locked_until")
    if locked_until:
        try:
            if datetime.fromisoformat(locked_until) <= _utc_now():
                await db.payslip_auth_attempts.update_one(
                    {"user_id": user_id},
                    {"$set": {"failed_count": 0, "locked_until": None}},
                )
                row = {"failed_count": 0, "locked_until": None}
        except ValueError:
            pass
    return row


def _require_payslip_admin(user: dict):
    """Admin RBAC for the payslip module — knowing the code grants nothing."""
    if user.get("role") not in ALL_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    if user.get("role") != UserRole.HR:
        raise HTTPException(status_code=403, detail="Permission denied")


# ------------------------------------------------------------------ routes
@api_router.get("/payslip-security/status")
async def payslip_security_status(request: Request, current_user: dict = Depends(get_current_user)):
    """Whether THIS session may open the Payslip module."""
    _require_payslip_admin(current_user)
    cfg = await _config()
    session_id = _session_id_from_request(request)
    verified = await is_session_verified(session_id)
    st = await _attempt_state(current_user["id"])
    return {
        "enabled": True,
        "verified": verified,
        "code_version": cfg["auth_code_version"],
        "locked_until": st.get("locked_until"),
        "failed_attempts": st.get("failed_count") or 0,
        "max_attempts": MAX_FAILED_ATTEMPTS,
        "lock_minutes": LOCK_MINUTES,
        "can_regenerate": (current_user.get("username") == REGEN_USERNAME),
        "recipient_email": RECIPIENT_EMAIL,
    }


def _session_id_from_request(request: Request) -> Optional[str]:
    """Read the session id from the verified Bearer token."""
    import jwt as _jwt

    from server import JWT_ALGORITHM, JWT_SECRET
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1].strip(), JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    return payload.get("session_id")


@api_router.post("/payslip-security/verify")
async def payslip_security_verify(
    request: Request,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    _require_payslip_admin(current_user)
    code = str((payload or {}).get("code") or "").strip()

    st = await _attempt_state(current_user["id"])
    if st.get("locked_until"):
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect attempts. Payslip verification is temporarily locked.",
        )

    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Enter a valid 6-digit authorization code.")

    cfg = await _config()
    ok = hmac.compare_digest(
        _hash_code(code, cfg["auth_code_salt"]), cfg["auth_code_hash"]
    )

    if not ok:
        failed = int(st.get("failed_count") or 0) + 1
        locked_until = None
        if failed >= MAX_FAILED_ATTEMPTS:
            locked_until = (_utc_now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
        await db.payslip_auth_attempts.update_one(
            {"user_id": current_user["id"]},
            {"$set": {
                "user_id": current_user["id"],
                "failed_count": failed,
                "locked_until": locked_until,
                "updated_at": _utc_now().isoformat(),
            }},
            upsert=True,
        )
        await _audit(
            current_user,
            "payslip_auth_lockout" if locked_until else "payslip_auth_failed",
            f"failed_attempt {failed}/{MAX_FAILED_ATTEMPTS}",
            request,
        )
        if locked_until:
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect attempts. Payslip verification is temporarily locked.",
            )
        raise HTTPException(status_code=401, detail="Invalid authorization code. Please try again.")

    session_id = _session_id_from_request(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    await db.payslip_auth_sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "session_id": session_id,
            "user_id": current_user["id"],
            "code_version": cfg["auth_code_version"],
            "verified_at": _utc_now().isoformat(),
        }},
        upsert=True,
    )
    await db.payslip_auth_attempts.update_one(
        {"user_id": current_user["id"]},
        {"$set": {"failed_count": 0, "locked_until": None, "updated_at": _utc_now().isoformat()}},
        upsert=True,
    )
    await _audit(current_user, "payslip_auth_verified", f"code_version={cfg['auth_code_version']}", request)
    return {"success": True, "message": "Authorization successful.", "code_version": cfg["auth_code_version"]}


def _email_html(code: str) -> str:
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1f2937;line-height:1.6">
      <p>Hello,</p>
      <p>A new authorization code has been generated for the HRMS Payslip Module.</p>
      <p style="margin:24px 0">
        <span style="display:inline-block;font-size:28px;letter-spacing:8px;font-weight:700;
                     background:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;padding:14px 22px">
          {code}
        </span>
      </p>
      <p>This code is required for Admin access to the Payslip Module during a new HRMS login session.</p>
      <p>The previous authorization code is no longer valid.</p>
      <p>If you did not request this change, please contact the HRMS administrator immediately.</p>
      <p>Regards,<br/>HRMS</p>
    </div>
    """


@api_router.post("/payslip-security/regenerate")
async def payslip_security_regenerate(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """Generate a new code, email it, and only THEN activate it."""
    _require_payslip_admin(current_user)
    if current_user.get("username") != REGEN_USERNAME:
        raise HTTPException(status_code=403, detail="You are not authorized to regenerate the payslip authorization code.")

    cfg = await _config()
    last = cfg.get("last_regenerated_at")
    if last:
        try:
            if datetime.fromisoformat(last) > _utc_now() - timedelta(minutes=REGEN_COOLDOWN_MINUTES):
                raise HTTPException(
                    status_code=429,
                    detail="A Payslip authorization code was recently generated. Please wait before requesting another code.",
                )
        except ValueError:
            pass

    candidate = generate_code()
    sent = await send_hrms_email(
        db,
        email_type="payslip_auth_code",
        scope_key=f"payslip_auth:{_utc_now().strftime('%Y%m%dT%H%M%S%f')}",
        to_email=RECIPIENT_EMAIL,
        subject="HRMS Payslip Module Authorization Code",
        html=_email_html(candidate),
        force=True,
    )
    if not sent:
        await _audit(current_user, "payslip_auth_email_failed",
                     f"email to {RECIPIENT_EMAIL} failed; existing code kept active", request)
        raise HTTPException(
            status_code=502,
            detail="Unable to send the new authorization code. Your existing authorization code remains active.",
        )

    # Commit-after-send, guarded on the version we read (blocks concurrent regen).
    salt = _new_salt()
    updated = await db.payslip_security_settings.find_one_and_update(
        {"id": CONFIG_ID, "auth_code_version": cfg["auth_code_version"]},
        {"$set": {
            "auth_code_salt": salt,
            "auth_code_hash": _hash_code(candidate, salt),
            "auth_code_version": int(cfg["auth_code_version"]) + 1,
            "last_regenerated_at": _utc_now().isoformat(),
            "last_regenerated_by": current_user.get("full_name") or current_user.get("username"),
            "last_regenerated_by_id": current_user.get("id"),
            "updated_at": _utc_now().isoformat(),
        }},
        return_document=True,
    )
    if not updated:
        raise HTTPException(
            status_code=409,
            detail="Another regeneration completed first. Please check the authorized mailbox for the latest code.",
        )

    # Every previously verified session is invalid from now on.
    await db.payslip_auth_sessions.delete_many({})
    await _audit(current_user, "payslip_auth_code_regenerated",
                 f"Email successfully sent to {RECIPIENT_EMAIL}; version={updated['auth_code_version']}", request)
    return {
        "success": True,
        "message": f"A new authorization code has been sent to {RECIPIENT_EMAIL}.",
        "code_version": updated["auth_code_version"],
    }


@api_router.get("/payslip-security/settings")
async def payslip_security_settings(current_user: dict = Depends(get_current_user)):
    """Read-only panel data for Settings → Payslip Security. Never the code."""
    _require_payslip_admin(current_user)
    cfg = await _config()
    return {
        "status": "Enabled",
        "auth_code_configured": True,
        "auth_code_version": cfg["auth_code_version"],
        "last_regenerated_at": cfg.get("last_regenerated_at"),
        "last_regenerated_by": cfg.get("last_regenerated_by"),
        "failed_attempt_protection": True,
        "max_attempts": MAX_FAILED_ATTEMPTS,
        "lock_minutes": LOCK_MINUTES,
        "recipient_email": RECIPIENT_EMAIL,
        "can_regenerate": (current_user.get("username") == REGEN_USERNAME),
    }
