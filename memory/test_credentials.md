# HRMS Test Credentials

## Admin Accounts
- **HR Admin**: `admin` / `MyPermanent#2026A` (role: hr) — see note below
- **System Admin**: `sysadmin` / `pass123` (role: system_admin)
- **Office Admin**: `workforce` / `Pass@123#` (role: office_admin — renamed from `offadmin` on 2026-05-13)


> ⚠️ **NOTE (2026-05-17 TRUE ROOT CAUSE FIX):** The "admin password
> auto-reverts" bug was finally ELIMINATED at its source. The REAL
> culprit was NOT the seed/migrate/rehire logic — it was two pytest
> regression files that mutated the REAL admin user as part of their
> cleanup hooks:
>   • `test_change_password_persistence.py` — autouse `_cleanup` fixture
>     ran `_ensure_admin_pwd("pass123")` after EVERY test, cycling
>     through known passwords and force-resetting admin to `pass123`.
>   • `test_admin_rehire_collision_firewall.py` — wrote
>     `password_hash = SHA256("pass123")` directly to Mongo, bypassing
>     every firewall.
> Both files have been refactored to use a DEDICATED ephemeral test
> user. The real admin account is NEVER touched by tests anymore.
> A startup-time integrity beacon now logs a forensic alert if admin's
> hash silently reverts to the default seed.
>
> The admin password has been changed to `MyPermanent#2026A` as part
> of the verification. You may change it via Settings → Change Password
> and it will now persist forever (across restarts, deploys, test runs).

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
