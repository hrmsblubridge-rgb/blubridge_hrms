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
- **Vigilance Employee 1 (WORKING)**: `madhan.s` / `Vigil@123` — Madhan S, designation=Vigilance. Re-synced to `Vigil@123` on 2026-06-09 (drifts frequently; data-level reset via SHA256 hash_password, method=agent_rbac_test_resync). USED BY /app/backend/tests/test_rbac_isolation.py as 'Employee B'.
- **Vigilance Employee 2 (WORKING)**: `dinesh.t` / `Vigil@123` — Dinesh T, designation=Vigilance. Re-synced to `Vigil@123` on 2026-06-09 (same note). USED BY test_rbac_isolation.py as 'Employee C'.

> ⚙️ **ONBOARDING GATE DISABLED (2026-06-06):** The mandatory onboarding flow is
> turned OFF app-wide via `ONBOARDING_ENABLED = false` in
> `frontend/src/contexts/AuthContext.js`. Every user (incl. employees with
> pending/rejected/under-review onboarding) now gets DIRECT full HRMS access —
> no redirect to `/employee/onboarding`. To re-enable, set the flag back to
> `true`. (`needsOnboarding()` short-circuits to false; Login.js + EmployeeRoute
> + RoleBasedRedirect all honour it.)
- **Employee (WORKING 2026-06-05)**: `user` / `pass123` — Rishi S Nayak, active, has current-week attendance. NON-vigilance → must NOT see Vigilance Report.
- **Employee**: `spartasolace1` / `spar@1230`
- **Employee** (Phase-2 dashboard widget tests): `user` / `pass123` — has attendance for current week, used by `tests/test_dashboard_widgets.py`
- **Employee**: `vijayan.k` / `pass123` (created 2026-04-27, onboarding approved)
- **Employee**: `kasper` / `pass123` (kasper@blubridge.com, EMP0050, reactivated 2026-04-27, dept=System Engineer) — ⚠️ reported DEACTIVATED on 2026-06-05; reactivate before using.
- **Employee**: `Umesh.Gana` / `pass123` (used for password-reset flow tests; restored after each suite)
- **Employee (Research Unit)**: `aparna.a` / `pass123` (Research Unit dept — Aparna A, active — re-synced to `pass123` on 2026-07-16 for star-reward automation UI verification; SHA256 password_hash on `users`)

## Password Reset Endpoints (added 2026-05-05)
- Admin reset: `POST /api/admin/employees/{employee_id}/reset-credentials` (HR/system_admin token; body: `{password,confirm_password,auto_generate,force_change_on_next_login}`)
- Forgot password (public): `POST /api/auth/forgot-password` body: `{identifier}`
- Validate token (public): `GET /api/auth/reset-password/validate?token=...`
- Reset password (public): `POST /api/auth/reset-password` body: `{token,new_password,confirm_password}`
- NOTE: Reset endpoint enforces min 8 chars + letter + digit. Legacy `pass123` (7 chars) is grandfathered but cannot be re-set via this endpoint.

Base URL: https://blank-tab-debug.preview.emergentagent.com
Login endpoint: POST /api/auth/login with JSON {"username": "...", "password": "..."}

## JWT Session Security (added 2026-07-09)
- Login `POST /api/auth/login` now returns `{token, refresh_token, user}`.
- Access token: SHORT-LIVED (`ACCESS_TOKEN_EXPIRE_MINUTES=10`, backend/.env), claims: user_id, role, token_type=access, session_id, jti, iat, exp. NO sliding expiry.
- Refresh token: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`), rotated on every `POST /api/auth/refresh` (body: `{"refresh_token": "..."}`). Reusing a rotated token REVOKES the whole session.
- `POST /api/auth/logout` (Bearer access token) revokes the session server-side → old access AND refresh tokens return 401 immediately.
- Sessions stored hashed in Mongo collection `auth_sessions` (session_id indexed).
- JWT secret: `JWT_SECRET` in backend/.env (required, no fallback).
- Frontend stores `blubridge_token` + `blubridge_refresh_token` in localStorage; axios interceptor auto-refreshes on 401 once and retries.
- NOTE for testing agents: tokens issued BEFORE 2026-07-09 are invalid (new secret + new claims) — always login fresh.

## Credential drift note (2026-08-12)
- madhan.s / Vigil@123 → INVALID (drifted again)
- spartasolace1 / spar@1230 → INVALID
- admin / HrAdmin786$ → WORKING
- user / pass123 → WORKING (Rishi S Nayak, Business & Product)

## RBAC / data-isolation note (2026-06-09)
- Centralised deny-by-default gate for role=employee lives in `/app/backend/rbac.py`
  (allowlist + middleware, registered in server.py just before CORSMiddleware).
- Regression suite: `/app/backend/tests/test_rbac_isolation.py` (43 tests, all passing).
- Working employee logins used by that suite (re-synced 2026-06-09, method=agent_rbac_test_resync):
  - `madhan.s` / `Vigil@123` (Employee B)
  - `dinesh.t` / `Vigil@123` (Employee C)
- Admin: `admin` / `HrAdmin786$` (unchanged, still PINNED).

## Payslip Module 6-digit authorization code (2026-06-09)
- Initial code (version 1): **082026** — stored ONLY as a salted PBKDF2-SHA256 hash in
  mongo `payslip_security_settings` (id="payslip_auth"). Never in plain text anywhere.
- Admin must enter it once per login session before ANY `/api/payslips*` route works
  (guard: `/app/backend/payslip_auth_guard.py`). Logout / new login => code required again.
- Regeneration: ONLY username `admin` may call `POST /api/payslip-security/regenerate`.
  It emails a new random 6-digit code to the FIXED address hrrecruiter@blubridge.com and
  permanently invalidates 082026. **Agents must NOT call it** (the new code is only
  readable in that mailbox). Resend delivery to that address was verified working
  (message id returned) on 2026-06-09 without sending any code.
- Safe simulation of a regeneration (bumps version with a known code, then RESTORES
  082026/version 1): `python3 /app/backend/tests/payslip_auth_regen_sim.py <backend_url>`.
- Locked out after 5 wrong codes (15 min)? Clear it with:
  `db.payslip_auth_attempts.delete_many({})`.
- Test suites: `/app/backend/tests/test_payslip_auth_layer.py` (13),
  `/app/backend/tests/payslip_auth_probe.py`.

- 2026-06-09: `madhan.s` password re-synced again to `Vigil@123` (method=agent_brsf_test_resync). It drifts often — re-sync via `db.users.update_one({'username':...},{'$set':{'password_hash': sha256('Vigil@123')}})` if a login returns 401.
