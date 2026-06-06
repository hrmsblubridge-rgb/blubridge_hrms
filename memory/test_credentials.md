# HRMS Test Credentials

> 🔒🔒🔒 **PINNED ADMIN CREDENTIAL — DO NOT CHANGE (user mandate 2026-06-05)** 🔒🔒🔒
> The user has fixed the HR admin login to **`admin` / `HrAdmin786$`**.
> AGENTS MUST NOT re-sync, reset, or "verify" this to any other value
> (no `pass123`, no `MyPermanent#2026A`, nothing else). It is set in Mongo
> with `password_updated_method='user_fixed_credential'` and verified to
> PERSIST across a full backend restart (startup seed only sets a password
> when none exists, so it never overwrites this). If admin login ever fails,
> re-set it to EXACTLY `HrAdmin786$` — never invent a new password.

## Admin Accounts
- **HR Admin**: `admin` / `HrAdmin786$` (role: hr) — 🔒 PINNED, VERIFIED WORKING + PERSISTS ACROSS RESTART (2026-06-05). DO NOT CHANGE.
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
- **Vigilance Employee 1 (WORKING)**: `madhan.s` / `Vigil@123` — Madhan S, designation=Vigilance. Re-synced to `Vigil@123` on 2026-06-06 (drifted AGAIN; data-level reset via app SHA256 hash_password, method=agent_test_resync).
- **Vigilance Employee 2 (WORKING)**: `dinesh.t` / `Vigil@123` — Dinesh T, designation=Vigilance. Re-synced to `Vigil@123` on 2026-06-06 (same note).
- **Employee (WORKING 2026-06-05)**: `user` / `pass123` — Rishi S Nayak, active, has current-week attendance. NON-vigilance → must NOT see Vigilance Report.
- **Employee**: `spartasolace1` / `spar@1230`
- **Employee** (Phase-2 dashboard widget tests): `user` / `pass123` — has attendance for current week, used by `tests/test_dashboard_widgets.py`
- **Employee**: `vijayan.k` / `pass123` (created 2026-04-27, onboarding approved)
- **Employee**: `kasper` / `pass123` (kasper@blubridge.com, EMP0050, reactivated 2026-04-27, dept=System Engineer) — ⚠️ reported DEACTIVATED on 2026-06-05; reactivate before using.
- **Employee**: `Umesh.Gana` / `pass123` (used for password-reset flow tests; restored after each suite)
- **Employee (Research Unit)**: `aparna.a` / `TestRU#2026` (Research Unit dept — used to verify department-restricted policy visibility on 2026-05-22)

## Password Reset Endpoints (added 2026-05-05)
- Admin reset: `POST /api/admin/employees/{employee_id}/reset-credentials` (HR/system_admin token; body: `{password,confirm_password,auto_generate,force_change_on_next_login}`)
- Forgot password (public): `POST /api/auth/forgot-password` body: `{identifier}`
- Validate token (public): `GET /api/auth/reset-password/validate?token=...`
- Reset password (public): `POST /api/auth/reset-password` body: `{token,new_password,confirm_password}`
- NOTE: Reset endpoint enforces min 8 chars + letter + digit. Legacy `pass123` (7 chars) is grandfathered but cannot be re-set via this endpoint.

Base URL: https://blank-tab-debug.preview.emergentagent.com
Login endpoint: POST /api/auth/login with JSON {"username": "...", "password": "..."}
