"""Centralised Payslip authorization guard (middleware).

ONE reusable gate applied to EVERY admin-side payslip route — pages, REST /
AJAX endpoints, calculation views, adjustments, exports and PDF downloads —
so no individual handler can forget the check.

Order of enforcement per request:
    valid login (handler dependency) -> admin payslip RBAC (handler) ->
    payslip session verified for the CURRENT code version (here)

Employees/interns are never touched by this gate: their own payslip access
(`/api/payslips/my`, own PDF) keeps using the existing employee rules, and the
RBAC gate in rbac.py already restricts them to those two paths.
"""
import logging
import re

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("hrms.security")

# All admin-side payslip API surface.
_PROTECTED = re.compile(r"^/api/payslips(/|$)")
# The security handshake itself must stay reachable.
_EXEMPT = re.compile(r"^/api/payslip-security/")
# Employee self-service payslip endpoints (own data, existing rules).
_EMPLOYEE_SELF = re.compile(r"^/api/payslips/my$")

DENY_BODY = {
    "success": False,
    "error": "payslip_auth_required",
    "message": "Payslip authorization required. Enter the 6-digit authorization code.",
}


def install_payslip_auth_guard(app, jwt_secret: str, jwt_algorithm: str, is_session_verified):
    """Register the guard. `is_session_verified` is an async fn(session_id)->bool."""

    @app.middleware("http")
    async def _payslip_auth_gate(request: Request, call_next):
        path = request.url.path
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if _EXEMPT.match(path) or not _PROTECTED.match(path) or _EMPLOYEE_SELF.match(path):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return await call_next(request)  # handler returns 401
        try:
            payload = jwt.decode(auth.split(" ", 1)[1].strip(), jwt_secret, algorithms=[jwt_algorithm])
        except Exception:
            return await call_next(request)  # handler returns 401

        if payload.get("role") == "employee":
            return await call_next(request)  # employee rules unchanged

        if await is_session_verified(payload.get("session_id")):
            return await call_next(request)

        logger.warning(
            "PAYSLIP AUTH REQUIRED 403 user_id=%s role=%s method=%s path=%s",
            payload.get("user_id"), payload.get("role"), request.method, path,
        )
        return JSONResponse(status_code=403, content=DENY_BODY)

    return _payslip_auth_gate
