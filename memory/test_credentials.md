# HRMS Test Credentials

## Admin Accounts
- **HR Admin**: `admin` / `pass123` (role: hr)
- **System Admin**: `sysadmin` / `pass123` (role: system_admin)
- **Office Admin**: `offadmin` / `pass123` (role: office_admin)


> ⚠️ **NOTE (2026-05-12 fix):** The startup seed previously force-reset `admin`'s
> password back to `pass123` on every backend restart, silently undoing any
> admin password change. This is now FIXED — admin password changes persist.
> The default seed credential `admin/pass123` only applies on a fresh install
> (or if `admin.password_hash` is somehow blank). If you change it during
> testing, you must remember the new value (or run the password-change test
> suite's cleanup, which always restores `pass123`).

## Employee Accounts
- **Employee**: `spartasolace1` / `spar@1230`
- **Employee**: `vijayan.k` / `pass123` (created 2026-04-27, onboarding approved)
- **Employee**: `kasper` / `pass123` (kasper@blubridge.com, EMP0050, reactivated 2026-04-27)
- **Employee**: `Umesh.Gana` / `pass123` (used for password-reset flow tests; restored after each suite)

## Password Reset Endpoints (added 2026-05-05)
- Admin reset: `POST /api/admin/employees/{employee_id}/reset-credentials` (HR/system_admin token; body: `{password,confirm_password,auto_generate,force_change_on_next_login}`)
- Forgot password (public): `POST /api/auth/forgot-password` body: `{identifier}`
- Validate token (public): `GET /api/auth/reset-password/validate?token=...`
- Reset password (public): `POST /api/auth/reset-password` body: `{token,new_password,confirm_password}`
- NOTE: Reset endpoint enforces min 8 chars + letter + digit. Legacy `pass123` (7 chars) is grandfathered but cannot be re-set via this endpoint.

Base URL: https://leave-code-mapper.preview.emergentagent.com
Login endpoint: POST /api/auth/login with JSON {"username": "...", "password": "..."}
