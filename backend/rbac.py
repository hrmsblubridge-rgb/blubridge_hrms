"""Centralised Role-Based Access Control for the HRMS API.

Security model
--------------
    EMPLOYEE -> OWN HRMS RECORDS ONLY
    ADMIN    -> AUTHORISED COMPANY-WIDE HRMS RECORDS

A valid JWT proves *authentication* only. Authorisation is enforced here, on
the server, for EVERY request: any `/api/**` route that is not on the employee
allowlist below is rejected with 403 for users whose trusted (JWT) role is
`employee`. This is a deny-by-default gate, so a newly added administrative
endpoint is protected automatically instead of silently leaking data.

Endpoints that employees legitimately share with admins (attendance, leaves,
dashboard stats, teams, departments, avatars, birthdays) are allowlisted here
AND additionally row/field-scoped inside their handlers in server.py.
"""
import logging
import re
from typing import Optional

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("hrms.security")

EMPLOYEE_ROLE = "employee"

# (methods, compiled path regex). Anything not matched here is DENIED for the
# employee role. Paths are matched against the full request path (with /api).
_ALLOW_RULES: list[tuple[set[str], re.Pattern]] = [
    # --- auth / session ---
    ({"POST", "GET"}, re.compile(r"^/api/auth/(login|logout|refresh|me|change-password|forgot-password|reset-password)$")),
    # --- employee self-service (all own-data endpoints live under these) ---
    ({"GET", "POST", "PUT", "PATCH", "DELETE"}, re.compile(r"^/api/employee/")),
    ({"GET", "POST", "PUT", "PATCH", "DELETE"}, re.compile(r"^/api/employee-profile/")),
    # own avatar map (handler returns ONLY the caller's avatar for employees)
    ({"GET"}, re.compile(r"^/api/employee-avatars$")),
    # own payslip / salary slip (handlers verify ownership)
    ({"GET"}, re.compile(r"^/api/payslips/my$")),
    ({"GET"}, re.compile(r"^/api/payslips/[^/]+/pdf$")),
    ({"GET"}, re.compile(r"^/api/employees/[^/]+/payslip/[^/]+$")),
    # --- dashboard: personal stats + sanitised birthday widget ---
    ({"GET"}, re.compile(r"^/api/dashboard/(stats|birthdays)$")),
    # --- own attendance / leave (handlers force employee_id = caller) ---
    ({"GET"}, re.compile(r"^/api/attendance$")),
    ({"GET"}, re.compile(r"^/api/leaves$")),
    # --- minimal org metadata for dropdowns (handlers return id+name only) ---
    ({"GET"}, re.compile(r"^/api/(teams|departments)$")),
    # --- self-service requests (handlers scope by caller) ---
    ({"GET", "POST"}, re.compile(r"^/api/(late-requests|early-out-requests|missed-punches)$")),
    ({"PUT"}, re.compile(r"^/api/(late-requests|early-out-requests|missed-punches)/[^/]+$")),
    # --- tickets raised by the employee ---
    ({"GET", "POST"}, re.compile(r"^/api/issue-tickets$")),
    ({"GET"}, re.compile(r"^/api/issue-tickets/(categories|stats)$")),
    ({"POST", "PUT"}, re.compile(r"^/api/issue-tickets/[^/]+/(feedback|status)$")),
    # --- own warnings ---
    ({"GET"}, re.compile(r"^/api/warnings/[^/]+$")),
    ({"POST"}, re.compile(r"^/api/warnings/[^/]+/(acknowledge|respond)$")),
    # --- own onboarding / documents ---
    ({"GET", "POST"}, re.compile(r"^/api/onboarding/(my-status|upload-document|submit)$")),
    ({"GET"}, re.compile(r"^/api/documents/secure-url$")),
    ({"POST"}, re.compile(r"^/api/documents/compress-upload/(chunk|finish)$")),
    ({"GET"}, re.compile(r"^/api/cloudinary/signature$")),
    ({"POST"}, re.compile(r"^/api/upload$")),
    # --- company-wide but non-sensitive reference data ---
    ({"GET"}, re.compile(r"^/api/holidays(/upcoming)?$")),
    ({"GET"}, re.compile(r"^/api/policies$")),
    ({"GET"}, re.compile(r"^/api/policies/[^/]+$")),
    ({"POST"}, re.compile(r"^/api/policies/[^/]+/acknowledge$")),
    ({"GET"}, re.compile(r"^/api/config/")),
    ({"GET"}, re.compile(r"^/api/help/")),
    # --- own notifications (handlers scope by user_id) ---
    ({"GET", "PUT", "DELETE"}, re.compile(r"^/api/notifications")),
    # --- Operational Vigilance module (own access gated inside the module) ---
    ({"GET", "POST", "PUT", "DELETE"}, re.compile(r"^/api/vigilance/")),
    # --- public/unauthenticated helpers that may still carry a token ---
    ({"GET", "POST"}, re.compile(r"^/api/profile-upload/")),
]

DENY_BODY = {
    "success": False,
    "message": "You are not authorized to access this resource.",
    "detail": "Insufficient permissions. Admin access required.",
}


def is_employee_allowed(method: str, path: str) -> bool:
    method = method.upper()
    for methods, pattern in _ALLOW_RULES:
        if method in methods and pattern.match(path):
            return True
    return False


def is_admin_user(user: dict, admin_roles) -> bool:
    return (user or {}).get("role") in admin_roles


def enforce_self_scope(current_user: dict, requested_employee_id: Optional[str], admin_roles) -> Optional[str]:
    """Return the employee_id whose data the caller may read.

    Admins keep the requested id (or None = company-wide). Everyone else is
    silently pinned to their OWN employee_id — a client-supplied id is never
    trusted.
    """
    if is_admin_user(current_user, admin_roles):
        return requested_employee_id
    return current_user.get("employee_id") or "__none__"


def install_employee_rbac(app, jwt_secret: str, jwt_algorithm: str, deny_sink=None):
    """Register the deny-by-default employee gate as the innermost middleware.

    Register BEFORE CORSMiddleware so CORS headers still wrap 403 responses.
    """

    @app.middleware("http")
    async def _employee_rbac_gate(request: Request, call_next):
        path = request.url.path
        method = request.method.upper()
        if method == "OPTIONS" or not path.startswith("/api/"):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return await call_next(request)  # unauthenticated -> handler returns 401

        try:
            payload = jwt.decode(auth.split(" ", 1)[1].strip(), jwt_secret, algorithms=[jwt_algorithm])
        except Exception:
            return await call_next(request)  # invalid/expired -> handler returns 401

        if payload.get("role") != EMPLOYEE_ROLE:
            return await call_next(request)

        if is_employee_allowed(method, path):
            return await call_next(request)

        target = request.query_params.get("employee_id")
        logger.warning(
            "RBAC DENY 403 user_id=%s role=%s method=%s path=%s target_employee_id=%s",
            payload.get("user_id"), payload.get("role"), method, path, target,
        )
        if deny_sink:
            try:
                await deny_sink({
                    "user_id": payload.get("user_id"),
                    "role": payload.get("role"),
                    "method": method,
                    "path": path,
                    "target_employee_id": target,
                    "result": 403,
                })
            except Exception:
                pass
        return JSONResponse(status_code=403, content=DENY_BODY)

    return _employee_rbac_gate
