# HRMS Application - Product Requirements Document

## Original Problem Statement
Build and enhance a premium enterprise-grade HRMS web application with role-based access control, onboarding workflow, and notification system. The system must be scalable, modular, and production-ready with modules for employee onboarding, attendance tracking, leave management, payroll, teams, tickets, and more.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn UI
- **Backend**: Python, FastAPI, openpyxl
- **Database**: MongoDB Atlas
- **File Storage**: Cloudinary API
- **Emails**: Resend API

## Code Architecture
```
/app
├── backend/
│   ├── .env
│   ├── requirements.txt
│   └── server.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.js
│   │   │   ├── Employees.js
│   │   │   ├── Attendance.js / EmployeeAttendance.js
│   │   │   ├── Leave.js / EmployeeLeave.js
│   │   │   ├── AdminLateRequests.js / EmployeeLateRequest.js
│   │   │   ├── AdminEarlyOut.js / EmployeeEarlyOut.js
│   │   │   ├── AdminMissedPunch.js / EmployeeMissedPunch.js
│   │   │   ├── RoleManagement.js (NEW)
│   │   │   ├── Holidays.js / Policies.js
│   │   │   ├── StarReward.js / Team.js
│   │   │   ├── Payroll.js / Reports.js
│   │   │   ├── AuditLogs.js / Verification.js
│   │   │   └── Employee*.js (portal pages)
│   │   ├── components/
│   │   │   ├── Layout.js (role-based nav)
│   │   │   ├── EmployeeLayout.js
│   │   │   └── NotificationBell.js (NEW)
│   │   ├── contexts/
│   │   │   └── AuthContext.js
│   │   └── App.js (role-based routing)
└── server/ (DEPRECATED)
```

## RBAC System (Implemented Apr 8, 2026)

### Roles & Access Matrix
| Module | HR Team | System Admin | Office Admin | Employee |
|--------|---------|-------------|-------------|----------|
| Dashboard | Full | View | View | Employee Portal |
| Employees | Full CRUD | View Only | View Only | Self-Service |
| Attendance | Full + Approve | View | View | Self-Service |
| Leave | Full + Approve | View | View | Apply/Edit |
| Late/Early/Missed | Full + Approve | View | View | Apply/Edit |
| Holidays | Full CRUD | - | View | View |
| Policies | Full CRUD | - | - | View |
| Star Reward | Full | - | - | - |
| Team | Full | - | - | - |
| Payroll | Full | - | - | View |
| Issue Tickets | Full | - | - | Submit |
| Reports | Full + Export | - | - | - |
| Role Management | Full | View | - | - |
| Audit Logs | View | View | - | - |

### Credentials
- HR: `admin` / `pass123`
- System Admin: `sysadmin` / `pass123`
- Office Admin: `offadmin` / `pass123`
- Employee: `user` / `user`

## Notification System (Implemented Apr 8, 2026)
- In-app notification bell with dropdown
- Unread count badge with polling (30s interval)
- Mark as read (single/all)
- Delete notifications
- Triggers:
  - Employee created → HR notified
  - Leave request submitted → HR notified
  - Leave approved/rejected → Employee notified
  - Role changed → User notified
  - Employee created → Office Admin notified for operational setup
  - All checklist items completed → HR notified

## Operational Checklist (Implemented Apr 8, 2026)
Office Admin tracks workplace readiness per employee with 8 checklist items across 5 categories:
- **Infrastructure**: Workstation Ready (desk, chair, system/laptop)
- **Stationery**: Stationery & Supplies Issued, ID Card Issued
- **Access**: Attendance Device Configured, Access Card / Entry Permissions
- **IT**: System Access Created & Verified, Role-based Access Confirmed
- **Coordination**: HR Coordination for Joining Readiness

Status flow: Pending → In Progress → Completed
Auto-created on employee creation + backfilled for existing employees on startup.

## What's Been Implemented

### Phase 1 (Previous Sessions)
- Custom Employee ID & Biometric ID fields
- Bulk Employee Import via Excel/CSV with welcome emails
- Biometric Attendance Ingestion API
- MongoDB Atlas migration + Admin seeding
- Strict dropdowns for Department/Team/Designation
- Leave Application: Start Date / End Date
- Team Member Count display fix
- Attendance Module Pagination

### Phase 2 (Apr 8, 2026)
**Bug Fixes:**
- Holiday duplicate entries fixed (upsert + unique index + dedup on startup)
- Dashboard attendance stats fixed
- Employee attendance date filter fixed

**Leave Module Enhancements:**
- Leave Split: Full Day / First Half / Second Half
- Document upload on leave application form
- Edit pending leave requests
- LOP/No_LOP selection on admin approval
- Admin: Apply leave for employee

**3 New Modules (Late Request, Early Out, Missed Punch):**
- Full CRUD + approve/reject APIs
- Employee + Admin pages with LOP support

### Phase 3 (Apr 8, 2026) - Current Session
**RBAC Overhaul:**
- 4 roles: HR, System Admin, Office Admin, Employee
- Permission-based middleware (ADMIN_ROLES, ALL_ADMIN_ROLES, SYSTEM_ROLES)
- Role migration from old roles on startup
- Role-based sidebar navigation filtering
- Conditional UI elements (edit/approve/delete buttons)

**Notification System:**
- Notification model + CRUD endpoints
- NotificationBell component with unread badge
- Notification triggers for key actions
- Integrated in Layout + EmployeeLayout

**Role Management UI:**
- Permission matrix view
- User roles table with search/filter
- Edit role dialog (HR only)
- Role count overview cards

### Phase 4 (Apr 9, 2026) - 7 Jobs
**JOB 1**: Missed punch forms use datetime-local (YYYY-MM-DDTHH:mm) instead of time-only
**JOB 2**: Admin missed punch page: date range filters, status dropdown, employee search, server-side pagination
**JOB 3**: Approved missed punch → auto-updates attendance (first_punch/last_punch/status)
**JOB 4**: Duplicate prevention: missed punch, late request, early out, leave (per employee+date)
**JOB 5**: Fixed "Failed to apply leave" bug (NameError: `emp` → `employee`)
**JOB 6**: Leave rules: Sick=past/current only, Casual=4+ working days (excl Sundays), Emergency=any
**JOB 7**: Single leave per day enforcement (blocks duplicate dates, suggests edit instead)
- **P1**: Cloudinary PDF Viewing (blocked on user settings)
- **P2**: Username collision on employee creation - **FIXED Apr 10, 2026**

### Phase 5 (Apr 10, 2026) - Payslip UI & Bug Fixes
- **Salary Slip / Payslip UI**: Professional payslip dialog with company logo (BluBridge Technologies), full compensation breakdown (Base, Allowances, Retirement, Variable, CTC), Insurance Coverage, Employee Deductions, Net Salary, and Print/Download PDF functionality. Component: `SalarySlip.js` (forwardRef for printing)
- **Payslip Redesign**: Redesigned to match reference PDF design - navy blue header banner with BluBridge logo (logo-black.webp inverted to white), employee info card, lettered section badges (A-F), clean single-column monthly tables, red deductions section, gradient net salary card
- **Username Collision Fix**: Auto-appends numeric suffix (e.g., user1, user2) when creating employees with duplicate email prefixes
- **CTC Calculation Fix**: Special Allowance is now the true balancing figure (Fixed + Variable = CTC exactly). Previous bug had total exceeding CTC. Verified against reference salary table.
- **Missed Punch → Attendance Fix (Apr 15)**: Fixed critical bug where `_update_attendance_from_missed_punch` wrote to wrong fields (`first_punch`/`last_punch` instead of `check_in`/`check_out`/`check_in_24h`/`check_out_24h`). Also fixed employee attendance API date format mismatch (`dd-MM-yyyy` vs `yyyy-MM-dd` query). Now correctly populates attendance with 12h+24h formats, recalculates `total_hours`, and logs audit trail. Migrated 5 old corrupted records.
- **Research Designation CTC Formula**: New `calculate_salary_structure_research()` function for Research employees — uses B-percentage allocation (LTA=5.6%B, Bonus=9.9%B, Stay=30%B), no Medical/Conveyance, PF fixed at ₹1,800. Non-Research employees unchanged. Designation-based routing via `get_salary_calculator()`.
- **Employee Deactivation Enhancement (Apr 16)**: Replaced simple confirmation with structured form modal (Type: Relieved/Terminated/Completed Internship, Date, Reason, Last Day Payable). Added Inactive Type column + filter to employee list. Extended bulk upload to support deactivation fields. Backend stores inactive_type, inactive_date, inactive_reason, last_day_payable.
- **Soft Delete Fix (Apr 16)**: Removed `is_deleted: True` from deactivation flow — now only sets `employee_status: "Inactive"`. Inactive employees naturally appear in list filters. Fixed login check order to show "Your account is deactivated. Contact admin." before password check. Migrated 5 previously hard-deleted records back to soft-inactive.

### Phase 6 (Apr 16, 2026) - Payroll Engine Compliance Update
- **Complete Payroll Engine Rewrite**: Aligned payroll calculation 100% with strict payroll specification
  - Department-based work hours: Research Unit=11h/6h, Business & Product=10h/5h, Support Staff=9h/4.5h
  - Holiday handling: Holidays loaded from DB and excluded from working days; OH/PF/PH for holidays
  - Sunday/Holiday Weekoff Pay +1 always; Extra Pay +1/+0.5 when worked full/half
  - Working day classification cross-references: attendance, leaves, late_requests, missed_punches
  - New status codes: PF (Present Full), PH (Present Half), PA (Present Approved Leave), WO (Week Off), OH (Office Holiday), LC (Late Coming), MP (Missed Punch), A (Absent), R (Relieved), BLANK (Before Joining), LOP, Su/H/NA (Future)
  - LOP rules: A=1 day, LC=0.5, PH(working day)=0.5, pending/LOP leave
  - Formula: Payable Days = (Working Days - LOP) + Weekoff Pay + Extra Pay
  - Relieved employee adjustment: if last_day_payable=False → subtract 1 day
  - Employee eligibility: Active + Inactive(relieved within period), join before payroll end
  - Future dates: Su for Sundays, H for holidays, NA for others
- **Batch Query Optimization**: Reduced ~250 DB queries to ~5 batch queries for all employees (30x faster, 74s→2.5s)
- **Frontend Status Display**: Updated getStatusDisplay() and legend to handle all new payroll codes
- **Backward Compatibility**: Kept present_days, lop_days, absent_days, leave_days for existing consumers

- **Weekoff = Sundays ONLY, Holidays → Extra Pay (Apr 17)**: Separated Sunday and Holiday logic completely. Weekoff_pay counts ONLY Sundays. Holidays: if worked → Extra Pay, if not → OH (no weekoff contribution). Verified: Active April=4 weekoff (4 Sundays), Inactive Apr 14=2 weekoff (2 Sundays before inactive_date).
- **Payroll Weekoff Fix for Active + Inactive (Apr 17)**: Fixed bug where future Sundays were NOT counted for active employees. Active employees now count ALL Sundays in the month. Inactive employees stop at inactive_date.
- **Employee Reactivation (Apr 17)**: New `PUT /api/employees/{id}/reactivate` endpoint restores Inactive employees to Active status, re-enables login (is_active=True), preserves deactivation history (inactive_type, inactive_date, reason kept). Frontend shows green Activate button (UserCheck icon) for inactive employees in table, and 'Reactivate Employee' button in employee detail view.
- **Inactive Details Display (Apr 17)**: Employee detail Profile tab now shows 'Deactivation Details' section with inactive_type, inactive_date, reason, and last_day_payable. Only visible for employees with inactive history.
- **Global Employee Autocomplete (Apr 17)**: Created reusable `EmployeeAutocomplete` component (`/app/frontend/src/components/EmployeeAutocomplete.js`) with 350ms debounce, dropdown suggestions (Name|EMP ID|Email|Dept), click-outside-to-close. Applied to 5 modules: Employees, Attendance, Leave, Late Requests, Early Out.
- **Payroll Sticky Header (Apr 17)**: Made Attendance View table header fixed during vertical scroll (`position:sticky; top:0; z-index:20`). Table body scrolls within `max-h-[65vh]` container while header stays visible.
- **Inactive Employee Payroll Fix (Apr 17)**: Inactive employees without `inactive_date` are now excluded from payroll calculation (returns None). Employees WITH `inactive_date` only have payroll calculated up to that date — days after show "R" status and are excluded from Working Days, Weekoff Pay, Extra Pay, and LOP.
- **Payroll Attendance View Column Labels & Top Scroll (Apr 17)**: Expanded summary column headers from abbreviations (TD/WD/WP/EP/Pay) to full text (Total Days, Working Days, Weekoff Pay, Extra Pay, Payable Days). Added synchronized top horizontal scrollbar above the table.
- **Payroll Attendance View Summary Columns (Apr 17)**: Added 6 summary columns to the Attendance View tab: Total Days (TD), Working Days (WD), Weekoff Pay (WP), Extra Pay (EP), LOP, Payable Days (Pay). Values sourced directly from backend payroll engine. CSV export updated to include new columns.
- **Employee Search Autocomplete (Apr 17)**: Converted plain search box to autocomplete with dropdown suggestions showing Name | EMP ID | Email | Department. Backend `GET /api/employees/autocomplete?q=` endpoint with case-insensitive regex, max 10 results. Frontend 350ms debounce, "No matches found" for empty, click-outside-to-close.

## Backlog / Future Tasks
- **P1**: Biometric Sync Dashboard
- **P2**: Leave Balance Tracking endpoint
- **P2**: Backend refactoring (decompose server.py ~7000 lines)
- **P2**: Delete deprecated Node.js backend
- **P2**: Onboarding & Induction Workflow (5-step process with induction scheduling)
- **P2**: Reports & Analytics with PDF/Excel export
- **P3**: WebSocket real-time notifications
- **P3**: Rate limiting & API hardening

## Key DB Collections
- `users`, `employees`, `attendance`, `leaves`, `holidays`
- `late_requests`, `early_out_requests`, `missed_punches`
- `notifications` (NEW), `audit_logs`
- `biometric_punch_logs`, `departments`, `teams`

## Key API Endpoints (New)
- `GET/PUT/DELETE /api/notifications` - Notification CRUD
- `GET /api/notifications/unread-count` - Unread count
- `PUT /api/notifications/mark-all-read` - Mark all read
- `GET /api/roles/users` - List users with roles
- `PUT /api/roles/users/{id}/role` - Update user role
- `GET /api/roles/permissions` - Permission matrix
- `GET /api/help/download` - Download role-specific User Guide PDF (HR / SysAdmin / OfficeAdmin / Employee)

## Changelog
- **2026-05-07 (Bug fix — Rows-per-page in Employee Attendance)** Fixed `ReferenceError: setRowsPerPage is not defined` crash on `/employee/attendance`.
  - Root cause: `rowsPerPage` was declared as a `const = 10` in `EmployeeAttendance.js` (line 25) but the `PageSizeSelector`'s `onChange` handler called `setRowsPerPage(v)`, which didn't exist. Picking any value from the rows-per-page dropdown triggered the full React error overlay.
  - Fix: replaced the const with a `useState(10)` hook — `const [rowsPerPage, setRowsPerPage] = useState(10);`.
  - Verified via Playwright: dropdown opens (12 size options 25/50/75…500), value change fires **with 0 JS runtime errors captured**. Audited siblings (`Attendance.js`, `AdminMissedPunch.js`, `StarReward.js`, `Employees.js`) — all already use stateful pagination, no recurrence elsewhere.
- **2026-05-07 (Payroll Attendance Code Mapping — HR-defined leave entry codes)** Re-mapped the Payroll → Attendance View grid status codes so leave entries surface their leave-type and split directly in each cell. Old generic codes (Present Full / Present Half / Present + Approved Leave / Office Holiday) were renamed so the new HR-mandated abbreviations have no collision.
  - **Backend** (`server.py`): new module-level `_leave_code_for_status(leave_type, leave_split)` helper deterministically maps each (canonical leave type, split) to the user-facing code. Sections 5A / 5B / 6A / 6B / 6C / 6D of the payroll attendance engine were updated:
    - Worked-day codes renamed: `PF → P`, `PH → HD`. `OH (Office Holiday)` renamed to `H` (matches the future-date code, no longer split between past/future).
    - Approved-non-LOP leave days now route through `_leave_code_for_status`, producing per-row codes — **PF / PH** (Pre-Planned), **SF / SH** (Sick), **EF / EH** (Emergency), **PA / PP** (Paid Leave bucket — Casual / Earned / Annual / Maternity / Paternity / Bereavement / General), **OH** (Optional).
    - `R / LC / MP / WO / LOP / A / Su / NA / BLANK` semantics unchanged. `R` clarified as "Resigned / Terminated", `LC` extended to cover "Late Coming / Early Leaving".
    - `present_count` / `leave_count` derived counters updated to recognise the new codes (no payroll-amount regression — `final_payable_days` is still computed from `working_days - lop + weekoff_pay + extra_pay`).
  - **Frontend** (`Payroll.js`): `getStatusDisplay` rewritten with the new code → color/bg map (purple/rose/red/cyan/emerald per leave bucket) and the legend grid expanded to 19 entries covering every code. Legacy fallback retained for historical rows. CSV export auto-picks up the new codes via the same display path.
  - **Verified end-to-end**: `/api/payroll?month=2026-04` returns the new distribution (P 841 · HD 47 · H 64 · WO 195 · LOP 67 · LC 13 · MP 1 · A 284 · BLANK 282 · R 154 · PF 1 (Jenifa D, 06-Apr Pre-Planned) · EF 1 (Venkata Chaithanya Y, 04-Apr Emergency)). Live grid screenshot confirms the legend and per-cell rendering. **27/27 pytest cases** in `tests/test_payroll_leave_codes.py` green covering every (leave_type, split) combination including edge cases.
- **2026-05-07 (Leave Policy replaced with "Notice – List of Holidays" 2026)** Replaced the legacy Leave Policy content with the new official Holiday Notice issued for calendar year 2026.
  - **Backend** (`server.py`): rewrote the `policy_leave` seed → name `"Notice – List of Holidays"`, `version=2026.1`, `applicable_to="All Employees & Interns"`. New sections — `Operating Framework` (text), `A. Standard Holidays` (6-row table: New Year's Day, Republic Day, Tamil New Year, May Day, Independence Day, Gandhi Jayanthi), `B. Optional Festival Holiday Bucket` (10-row table with 4-day cap note + lunar calendar footer), `Mid-Year Joiner Eligibility` (text + pro-rated 4/3/2/1 day table), and `Important Clarification` (text). Live MongoDB document migrated in-place via a one-shot `update_one`.
  - **Visibility**: Policy is in neither `HIDDEN_POLICIES` nor `DEPARTMENT_RESTRICTED_POLICIES`, so it is visible to **all admins (HR / SysAdmin / OfficeAdmin) and all employees** — matching the user requirement of visibility on Admin and All Employee logins.
  - **Frontend**: no UI change required — the rich-text renderer (text + table + footer) shipped earlier today renders the entire document including both tables natively. Verified via screenshot that the `kasper` employee (System Engineer) can open the policy and see the 6-row Standard Holidays table.
- **2026-05-07 (Research Publication Bonus Policy + IT Team Policy hidden)** Replaced legacy "Research Unit Policy" content with the new "Research Publication Bonus Policy" and globally hid "IT Team Policy".
  - **Backend** (`server.py`): rewrote the `policy_research` seed with the new structure (Objective, Scope, Bonus Structure with 4-column table, Eligibility & Conditions, Effective Date, Appendix A with venue table) and ran an in-place `db.policies.update_one` so the production document was migrated atomically without re-seeding side-effects. Renamed the policy to **Research Publication Bonus Policy** (effective `2025-12-15`, `applicable_to = "All interns and employees in the Research Unit"`).
  - **Hide IT Team Policy**: new `HIDDEN_POLICIES = {"policy_it"}` set checked first in `_is_policy_visible_to_user`. `GET /api/policies` no longer lists it for ANY role and `GET /api/policies/policy_it` returns `403`. Re-enabling later is a one-line removal from the set; the underlying document is preserved in MongoDB.
  - **Frontend** (`Policies.js`): extended the section renderer to support three optional, composable fields per section — `text` (paragraph, `whitespace-pre-line`), `table` (`{headers, rows}` rendered as a styled bordered table with multi-line cells preserved), and `footer` (italic note below). Existing `items` (bullet list & leave-style table) rendering kept intact for backward compatibility. Same component now handles structured rich-text policies cleanly.
  - **Verified**: HR sees 2 policies (Leave + Research Publication Bonus), `policy_it` returns 403, modal renders Bonus Structure 4-column table with multi-line citation tier cells (`1-9 / 10-19 / 20+ citations`) and Appendix A 11-row venues table. 8/8 pytest cases green in `tests/test_policy_visibility.py` (added `test_hidden_policy_invisible_to_everyone`).
- **2026-05-07 (Department-Based Policy Visibility — Research Unit restriction)** Restricted "Research Unit Policy" to relevant audience only.
  - **Backend** (`server.py`): new `DEPARTMENT_RESTRICTED_POLICIES = {"policy_research": {"Research Unit"}}` config + async `_is_policy_visible_to_user(policy_id, current_user)` helper. `GET /api/policies` now post-filters the document list per-user; `GET /api/policies/{id}` raises `403` for unauthorized employees while admins still get all policies. Logic: admins (`hr`, `system_admin`, `office_admin`) see everything; other employees only see a department-restricted policy when their `employees.department` matches the allowlist. Non-restricted policies (`policy_leave`, `policy_it`) remain universally visible.
  - **Frontend**: no UI changes required — the existing `Policies.js` page renders only what the API returns, so the entry naturally disappears for non-Research employees.
  - **Verified**: HR/admin token receives 3 policies, Aparna A (Research Unit) receives 3, Kasper (System Engineer) receives 2 (Research Unit Policy excluded). Direct `/api/policies/policy_research` returns 200 for admin & Research employees, 403 for others.
  - **Tests**: 7 new pytest cases in `/app/backend/tests/test_policy_visibility.py` (HR sees, system_admin sees, office_admin sees, research employee sees, non-research employee blocked, non-restricted policies always visible, employee without `employee_id` blocked). All pass against live MongoDB Atlas.
- **2026-04-30 (Targeted Fix — Gladson Anto attendance)** Resolved an employee-specific LOP / Early-Out mis-flagging.
  - **Root cause**: Gladson's `shift_type` was the legacy string `"General"` which resolves to `SHIFT_DEFINITIONS["General"]` = **11 hours** (10:00 → 21:00). All other active employees were already linked to the Settings-driven `"General"` shift = **10 hours**. He alone fell back to the 11h legacy definition and his real ~10.2h working days were tagged as `Loss of Pay`.
  - **Fix**: new idempotent script `/app/backend/scripts/fix_gladson_attendance.py` (1) migrates his employee record to the Settings shift via `_apply_settings_shift_to_employee_payload(...)`, (2) re-evaluates every existing attendance record using `calculate_attendance_status` with the corrected shift_timings, (3) flips records where `worked_hours ≥ required_hours - early_grace` from `Loss of Pay`/`Early Out` → `Present`, (4) writes a row per correction to `attendance_corrections` with `source_after="targeted_fix"` for full traceability.
  - **Production result**: 3 wrong records corrected (28-Apr 10.25h, 29-Apr 10.18h, 30-Apr 10.13h, all `LOP → Present`). The genuine LOP (29-04-2026 with 20:05 IN, no OUT — 605min late) was correctly preserved. Re-running yields `corrected=0` (idempotent). Zero attendance rows on any other employee carry the `targeted_fix_at` flag — scope strictly contained.
- **2026-04-30 (Shift Dropdown — Dynamic from Settings)** Removed hardcoded shifts in Add / Edit Employee.
  - **Backend** (`server.py`): new `_apply_settings_shift_to_employee_payload(payload, shift_identifier)` helper. Whenever an employee is created or updated with a `shift_type` matching a Settings shift (by id or name), the payload is auto-expanded to `shift_type='Custom'`, `custom_login_time`, `custom_logout_time`, `custom_total_hours`, `late_grace_minutes`, `early_out_grace_minutes`, `active_shift_id`, `active_shift_name` so the existing attendance engine and `get_shift_timings` continue to work unchanged. Picking plain "Custom" clears the `active_shift_*` binding so the employee is correctly attributed to manual config. Wired into `POST /api/employees`, the create reactivation path, and `PUT /api/employees/{id}`.
  - **Frontend** (`Employees.js`): new `settingsShifts` state + `fetchSettingsShifts()` from `GET /api/settings/shifts` (refreshed on mount and on opening Add / Edit modals). New `renderShiftOptions()` helper renders dynamic `<SelectItem>`s in format `"Name (HH:MM, Xh Ym)"` for every active Settings shift, plus a `Custom (one-off)` option. Empty-state message: *"No shifts available — create one in Settings → Shifts"*. Edit-flow safety: if the employee currently points to an inactive / removed Settings shift, that name is still rendered (disabled) so historical assignments stay visible without being re-pickable. All hardcoded `General/Morning/Evening/Night/Flexible` items removed from the JSX.
  - **Verified end-to-end via curl**: create with `shift_type="AI Research Unit"` resolves to `(login=10:00, logout=21:00, total=11.0, active_shift_name="AI Research Unit")`. Update to `"Morning shift"` flips to `(10:00, 19:00, 9h, "Morning shift")`. Update to `"Custom"` keeps user-supplied times and clears `active_shift_name`. Screenshot of the dropdown shows all 6 Settings shifts + Custom — no static legacy entries.
- **2026-04-30 (Universal Request Reset Engine)** Admins can now reset ANY processed request back to its initial `pending` state and reprocess it from scratch — without stacking effects.
  - **Backend** — 4 new HR-only endpoints (`POST /api/leaves|late-requests|early-out-requests|missed-punches/{id}/reset`) backed by a single `_log_request_reset` helper that writes to a new `request_resets` audit collection (`previous_status`, `previous_snapshot`, `attendance_rollback`, `reset_by`, `reset_at`, `reason`).
    - Leave / Late / Early-Out reset = clears `approved_by`, `approved_at`, `is_lop`, `lop_remark`, `rejection_reason` and flips status to `pending`. Payroll/attendance impact is computed dynamically from `is_lop` + `status`, so clearing those is sufficient to undo the effect.
    - **Missed-punch reset** is the heavy lift: pulls the most recent `attendance_corrections` audit row, restores `check_in/out` (24h + 12h) + `status` + `total_hours` (recomputed via `calculate_attendance_status`) + `source = "biometric"` (or whatever `source_before` was), unsets the correction-applied flags, marks the audit row `reverted_at` (kept for history), and clears `correction_applied_at` / `is_applied` / `approved_by` on the request.
    - **Idempotent**: resetting an already-pending unprocessed request is a safe no-op (no audit row written). Re-approving after reset re-applies cleanly because the engine itself is replay-safe.
  - **Frontend** — added a yellow "Reset" (`Undo2` icon) button on the History rows of all four admin pages (`Leave.js`, `AdminLateRequests.js`, `AdminEarlyOut.js`, `AdminMissedPunch.js`). Confirms before reset; missed-punch confirm explicitly tells HR the attendance will be rolled back.
  - **Tests**: 7 new pytest cases in `/app/backend/tests/test_request_reset_engine.py` — leave reset clears LOP/approval, leave reset is idempotent, late + early-out reset, missed-punch reset restores attendance to biometric values, reset-then-reapprove cycle works without stacking effects, RBAC denial for non-admin. All 26 backend tests across reset + missed-punch engine + backfill suites green.
- **2026-04-30 (Optional Leave Type)** Added a constraint-free `Optional` leave type across the stack.
  - **Backend**: added `Optional` to `CANONICAL_LEAVE_TYPES` so bulk-import preserves it. Leave create flow already accepted any free-text `leave_type` with no balance / quota / policy gates. Payroll/attendance reader treats `is_lop=False` (the default for Optional) as paid attendance — so Optional automatically inherits "neutral leave, no deduction". Approval/reject use the same workflow as every other type. Verified end-to-end: applied → approved with `is_lop=False`.
  - **Frontend**: `Optional` added to `Leave.js` (admin filter + apply + edit modal), `EmployeeLeave.js` (employee apply, with hint "no balance / policy restrictions — pick any date"), and `Reports.js` leave filter. Date inputs intentionally unrestricted for Optional — selecting it triggers no warnings, validations, or balance indicators.
- **2026-04-30 (Dashboard Filter Refactor)** Draft + Applied filter pattern on `/dashboard`. Date / dropdown changes update only `draftFilters` and trigger NO API call / loader. Apply Filter copies draft → `appliedFilters` which the `fetchData` `useCallback` depends on — exactly one fetch per click. Reset clears both states + reloads defaults. Network-level Playwright proof: 0 stat-API calls during draft edits, +1 on Apply, +1 on Reset.
- **2026-04-30 (Historical Backfill Engine)** Reused the production real-time engine as a bulk migration tool.
  - **NEW endpoint** `POST /api/missed-punches/backfill` (HR-only) — processes APPROVED but unapplied requests in batches. Supports `dry_run`, `batch_size`, `from_date`/`to_date`, `employee_id`, and `force` knobs. Returns `{candidates, applied, skipped_already_applied, skipped_invalid, errors, dry_run}` for easy ops monitoring.
  - **NEW status endpoint** `GET /api/missed-punches/backfill/status` returns `{total_approved_requests, pending_correction_apply, applied_correction_audit_rows, last_correction}`.
  - **Tracking flags on `missed_punches`** — every successful application stamps `correction_applied_at`, `correction_applied_by`, and `is_applied=True` directly on the source request, so dashboards / payroll / future backfills can identify processed records without joining audit rows.
  - **Three-layer idempotency**: source-flag filter, `attendance_corrections` audit-row check, and the engine itself (replay = no-op). Self-healing: if a legacy record has an audit row but no flag, the backfill stamps the flag on the way past.
  - **CLI script** `/app/backend/scripts/backfill_missed_punches.py` for cron / one-time runs, mirrors the API knobs (`--dry-run`, `--batch-size`, `--from`, `--to`, `--employee-id`, `--force`).
  - **Production run executed**: applied **84 historical approved missed-punch requests** to attendance. Status now shows `pending_correction_apply=0, applied_correction_audit_rows=90, total_approved_requests=90`. Re-running the backfill returns `applied=0, candidates=0` (true idempotency).
  - **Tests**: 8 new pytest cases in `/app/backend/tests/test_backfill_missed_punches.py` (dry-run no-op, applies + stamps, idempotent replay, legacy-flag healing, malformed-row reporting, status endpoint, RBAC denial for non-admin, biometric raw logs untouched). All 30 backend tests across the missed-punch + iter42 + backfill suites green.
- **2026-04-30 (later)** Production Missed-Punch Approval Engine.
  - Replaced `_update_attendance_from_missed_punch` (`server.py`) with a spec-compliant engine: type-targeted **hard replace** (Check-in / Check-out / Both), atomic UPSERT keyed on (employee_id, date), shift-aware status recompute via `calculate_attendance_status` (Present / Loss of Pay / Login / cross-midnight aware), `total_hours` recalculated decimal + display string, `source: "corrected"` set on every modified row, and idempotent replay-safe (same request_id + same target values = no-op).
  - **NEW audit collection `attendance_corrections`** — every approval writes `old_check_in/out`, `new_check_in/out`, `old_status`, `new_status`, `approved_by`, `approved_at`, `request_id`, `source_before/after`. Indexed by `request_id`, `(employee_id, date)`, and `created_at`.
  - **Raw biometric logs (`biometric_punch_logs`) are NEVER touched** — verified via dedicated test.
  - **11 new pytest cases** in `/app/backend/tests/test_missed_punch_engine.py` cover every numbered rule from the spec (type-targeted replace, UPSERT insert, total-hours recompute, cross-midnight 22:00→02:30 = 4.5h, audit row, idempotency, biometric isolation, malformed-request no-ops). All pass against live MongoDB Atlas.
  - **Test infra**: added `/app/backend/pytest.ini` (`asyncio_mode = auto`, session-scoped loops) so async fixtures share one event loop with `server.db` — fixes "Future attached to a different loop" failures.
- **2026-04-30** Dashboard Strict Mutually-Exclusive Buckets + HR Edit-Anywhere + Case-Insensitive Duplicate Guards.
  - **Dashboard counts vs records**: Rewrote `get_attendance_stats` (`server.py`) to use a single source of truth `classify_attendance_bucket(rec)` helper. Buckets are now strictly mutually exclusive — `logged_in` (IN, no OUT) + `logout` (Completed: IN+OUT, full hours) + `early_out` (IN+OUT, short / LOP) + `not_logged` (no IN) — and ALWAYS sum to `total_employees`. `late_login` is now a SECONDARY overlay flag (record has Late Login status or `lop_reason` mentions late login). Frontend `Dashboard.js` STATUS_PREDICATE mirrors the backend classifier so tile counts and detail tables ALWAYS match.
  - **HR/Admin edit on ANY status** (Leave / Late Request / Early Out / Missed Punch): `PUT /api/leaves/{id}` is NEW (HR-only `LeaveAdminEdit` payload — leave_type, leave_split, dates, reason; recomputes duration; approval status preserved). Existing `PUT /api/late-requests|early-out-requests|missed-punches/{id}` endpoints now bypass the "pending only" gate when the caller is in `ALL_ADMIN_ROLES`. Every edit writes `edited_by` + `edited_at` audit fields and emits an `edit` audit log entry. Employees still locked to pending-only on their own records.
  - **Frontend Edit UX**: Added pencil-icon Edit button + Edit modal on Pending AND History rows in `Leave.js`, `AdminLateRequests.js`, `AdminEarlyOut.js`, `AdminMissedPunch.js`. Modals submit to the corresponding PUT endpoint and re-fetch.
  - **Duplicate prevention** (`POST /api/employees`, `PUT /api/employees/{id}`): Email and Biometric ID checks now use case-insensitive anchored regex (e.g. existing `foo@bar.com` blocks `FOO@BAR.COM`). Error messages standardized to `Employee with this Email already exists` / `Employee with this Biometric ID already exists`.
  - **Leave page filter UI**: `From Date` and `To Date` inputs are now adjacent in the same row (grid order: Employee | From | To | Leave Type | Team | Status). Mobile-responsive layout preserved.
  - **Bug fixes (pre-existing, surfaced by testing agent)**:
    1. `RequestApproveBody` schema (server.py L810) had StarReward fields glued in — frontend POSTing `{is_lop, lop_remark}` to `/api/late-requests|early-out-requests/{id}/approve` was getting 422. Restored to `{is_lop, lop_remark}` and recreated the missing `StarReward` Pydantic model used by `add_star_reward`.
    2. `@api_router.get("/attendance/stats")` decorator was binding to the new `classify_attendance_bucket` helper instead of the actual handler. Decorator moved back above `async def get_attendance_stats(...)` — `/api/attendance/stats` once again returns proper stats JSON.
  - **Tests**: 11 pytest cases in `/app/backend/tests/test_iter42_dashboard_dup_admin_edits.py` — all pass against live MongoDB Atlas.
- **2026-04-27** Skip Onboarding for Existing Employees + Case-Insensitive Login.
  - **Migration (one-time DB update)**: All 51 Active employees + their 51 linked user accounts now have `onboarding_status = "approved"` and `is_first_login = false`. They land directly on `/employee/dashboard` after login — no onboarding gate. 49 employees and 7 orphaned `onboarding` collection records were updated.
  - **New-employee path preserved**: Default `onboarding_status = PENDING` on the `Employee` / `User` models is untouched, so any employee created via `POST /api/employees` (or bulk-import) from now on still goes through the normal onboarding flow.
  - **Inactive employees deliberately skipped** — they remain with their existing onboarding status.
  - **Case-insensitive login** (`POST /api/auth/login` in `server.py`): username is now matched case-insensitively against both `username` and `email`, and trimmed of whitespace. Fixes "Invalid credentials" when users type `Kasper` instead of `kasper`, or log in with their email. Wrong passwords still correctly rejected.
- **2026-04-27** Disabled Manual Check-in for Employees + Provisioned `vijayan.k` login.
  - `/app/frontend/src/pages/EmployeeDashboard.js`: Removed the "Clock In" / "Clock Out" buttons and the `handleClockIn` / `handleClockOut` handlers. Time Tracker card now always shows a read-only "Biometric Attendance — Your check-in/out is synced from the biometric device" panel (or "Day Completed" card when applicable). Employees can no longer manually punch attendance.
  - Backup: Admin-side attendance pages are unchanged (manual punch/edit remains available to HR/SysAdmin).
  - New employee user created via DB script: `vijayan.k` / `pass123`, role `employee`, `onboarding_status=approved`, `is_active=true`, `is_first_login=false`. Linked to new employee record `VJK001` (full_name: Vijayan K, department: Support Staff). Verified end-to-end: login returns token, lands on `/employee/dashboard`, biometric card renders, clock buttons absent.
  - `/app/memory/test_credentials.md` updated with the new credential.
- **2026-04-27** Centralized HRMS Settings Module (6 tabs: Departments, Teams, Designations, Holidays, Shifts, Assign Shifts).
  - New file `/app/backend/settings_module.py` (~990 lines) exposes all CRUD + service layer (`resolve_shift_for_employee`, `_sync_shift_to_employee`, `_apply_active_shifts_now`). Registered via `settings_module.register(api_router, deps)` in `server.py`.
  - New endpoints (prefix `/api/settings`): `departments`, `teams`, `designations`, `holidays`, `shifts`, `shifts/assign`, `shifts/bulk-assign`, `shifts/assignments`, `shifts/resolve`, `attendance/recompute`.
  - Existing `departments` / `teams` / `holidays` collections preserved (no recreation). Designations auto-seeded from existing employee values. Soft-delete for all new entities; renames propagate to child records.
  - New `shifts` collection fields: `id, name, start_time, total_hours, late_grace_minutes, early_out_grace_minutes, status, description, is_deleted`.
  - New `employee_shifts` collection fields: `id, employee_id, shift_id, effective_from, effective_to, assigned_by, is_deleted` with history + overlap handling.
  - Attendance Rule Engine updated in `server.py` (`get_shift_timings` + `calculate_attendance_status`): late = `actual > start + late_grace`; early-out uses `worked_hours < total_hours − early_grace/60` (no shift-end-time dependency). Grace=0 means any minute past start is LATE (10:01 → LATE verified).
  - `POST /api/settings/attendance/recompute` recalculates Late, Early-out, Worked Hours and Holiday flag (sets `extra_pay_flag` when worked on a holiday). Locked records (`is_manual_override` / `is_approved_correction`) are skipped.
  - Frontend `/app/frontend/src/pages/Settings.js` (~1300 lines) provides the 6-tab UI with Add/Edit/Delete dialogs, multi-chip filters on Assign Shifts, and a "Recompute Attendance" button. Sidebar entry added in `Layout.js` (roles: hr, system_admin); route wired in `App.js`.
  - 14 new pytest tests in `/app/backend/tests/test_settings_module.py` — all pass. RBAC, backward compatibility with legacy `/api/departments|teams|holidays`, bulk-assign by dept/team/designation filter, and attendance recompute all verified.

- **2026-05-06** Bulk Missed-Punch Import — Combined Date+Time + Auto-detect Punch Type (Admin → Missed Punch).
  - `In Time` / `Out Time` cells now accept combined Date+Time values (e.g., `18-03-2026 09:37`, `18/03/2026 23:30`, ISO, AM/PM, native Excel datetime).
  - `Punch Date` column is now **optional** — date is auto-extracted from In/Out Time when not provided. If both column and combined value exist, explicit Punch Date wins; falls back to In Time's date, then Out Time's.
  - `Punch Type` column is now **optional** — auto-detected from time presence: both → `Both`, only In → `Check-in`, only Out → `Check-out`.
  - Cross-midnight rows (e.g., In `18-03-2026 23:30`, Out `19-03-2026 02:15`) are anchored to In Time's date, matching the live attendance cross-midnight rule.
  - New helper `_parse_import_datetime()` in `server.py` handles 18 datetime formats. `_parse_import_time()` is now a thin wrapper.
  - 12 new unit tests in `/app/backend/tests/test_mp_combined_datetime.py` — all pass. Verified end-to-end via curl with 3 real-world rows.
  - Template Instructions sheet updated to reflect new flexibility.
- **2026-04-21** Added Role-based Help Guide PDF download.
  - New file `/app/backend/help_docs.py` with step-by-step content for all 4 roles.
  - New endpoint `GET /api/help/download` returns role-aware PDF via reportlab.
  - "Download Help Guide" added to profile dropdown in both `Layout.js` (admins) and `EmployeeLayout.js` (employees).
  - No help content rendered in UI (download-only as requested).
- **2026-05-05** Cross-Midnight Shift Handling in Attendance Processing.
  - Added `get_effective_attendance_date()` and `attendance_shift_offset()` helpers in `server.py`.
  - Punches at or before configurable threshold (default `05:00` AM, env `CROSS_MIDNIGHT_THRESHOLD_MINUTES=300`) are attributed to the PREVIOUS working day's attendance record (overnight shift OUT).
  - Punches after threshold start a NEW day (regular IN).
  - Updated `/api/attendance/import-biometric` grouping + merge logic to use shift-offset comparison so IN (earliest in shift) and OUT (latest in shift, possibly next calendar day) are always correctly identified, including across split/incremental batches.
  - Fixed total-hours calculation for cross-midnight (wraps 24h).
  - 24 unit tests added in `/app/backend/tests/test_cross_midnight_attendance.py` (all pass) + validated end-to-end via curl for 5 scenarios (normal day shift, cross-midnight OUT, new-day after 05:00, multi-punch after midnight, split-batch sync).
  - No schema changes; backward compatible with existing records.
- **2026-05-05** Configurable Page-Size Selector across Listing Pages.
  - New reusable `<PageSizeSelector>` component at `/app/frontend/src/components/PageSizeSelector.js`.
  - 12 options: 25, 50, 75, 100, 150, 200, 250, 300, 350, 400, 450, 500. Default 25.
  - Applied to: `Employees.js`, `Attendance.js`, `EmployeeAttendance.js`, `AdminMissedPunch.js`, `StarReward.js`.
- **2026-05-05** Employees Export – Full 17-column .xlsx (matches Bulk Import template).
  - New endpoint: `GET /api/employees/export` (HR / SysAdmin / OfficeAdmin) honors current list filters and exports ALL matching rows (not just current page).
  - Columns: Employee Name, Employee ID, Biometric ID, Email, Phone, Gender, DOB, DOJ, Department, Team, Designation, Employment Type, Tier Level, Work Location, Shift Type, Monthly Salary, User Role.
  - Styled header (dark-blue #063c88, white bold), frozen header row, sized columns. Round-trip compatible with `/api/employees/bulk-import`.
  - Frontend `Employees.js` Export button now calls the new endpoint with the current filters and downloads `.xlsx` (was previously CSV of only current page).
- **2026-05-05** Master Employee Data Reset (one-time migration).
  - Hard-deleted all 59 prior employees + ALL transactional data (attendance 3,718, biometric punch logs 729, audit logs 7,865, leaves 17, late/early/missed-punch requests, notifications, onboarding, salary structures, operational checklists).
  - Imported **82 employees** (90 rows from `Org of employees-2026-04-25.xlsx` minus 7 duplicate emails minus 1 NULL-dept row) via `/app/backend/scripts/seed_employees_from_excel.py`.
  - Replaced `departments` master list with: Business & Product, Research Unit, Support Staff, **System Engineer** (new).
  - Replaced `teams` master list with 20 teams (typo `Administation` → `Administration` normalized).
  - Auto-generated `custom_employee_id` (EMP100+) for rows missing Employee ID; biometric_id left blank when absent.
  - Preserved login users: `admin` (HR), `sysadmin`, `offadmin`. All employee logins removed; new employees can be activated through HR onboarding flow.
  - Distribution: Research Unit 59 · Business & Product 11 · Support Staff 10 · System Engineer 2. Full-time 69 · Intern 13.
- **2026-05-05** Bulk Leave Import (Admin → Leave Module).
  - New endpoints: `GET /api/leaves/import-template` (styled .xlsx template with Instructions sheet) and `POST /api/leaves/bulk-import` (HR / SysAdmin only).
  - Accepts `.xlsx` or `.csv` with 7 columns: Employee Email, Leave Type, From Date, To Date, Number of Days (optional), Reason (optional), Status (optional).
  - Logic: maps employee by email; fuzzy-matches Leave Type to canonical types (Sick / Casual / Earned / Maternity / Annual / Emergency / Preplanned) with `General Leave` fallback; accepts YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY date formats; auto-calculates Number of Days when blank; defaults Status to `pending`.
  - Duplicate guard: skips rows that overlap existing non-rejected leaves AND rows that overlap with another row in the same upload batch.
  - Batch insert in chunks of 500; silent (no email notifications fired); approved rows marked `applied_by_admin=true` with `approved_by` set to the admin.
  - Frontend: new "Import Leaves" button + dialog in `Leave.js` with template download, file picker, summary counters (Total / Success / Duplicates / Failed), inline error preview, and downloadable error log CSV.
  - Verified end-to-end with 8 scenarios covering valid/invalid emails, fuzzy matching, fallback, date format variants, blank fields, in-batch and DB overlap detection.
- **2026-05-05** Bulk Leave Import — Extended Column Capture (enhancement).
  - Added optional `extra_data: dict` field to `LeaveRequest` model (additive, no schema migration required for MongoDB).
  - New endpoint `POST /api/leaves/import/preview` returns detected headers classified into core/optional/extra plus first 5 sample rows so admin can verify before committing.
  - `POST /api/leaves/bulk-import` now captures any non-standard columns into `extra_data` per-row JSON; standard fields continue to map normally; rejects file only if mandatory columns missing.
  - Response now includes `extra_columns_captured` array.
  - UI: updated dialog copy ("You can upload custom sheets with additional columns…"); auto-shows preview after file selection with grouped chips (Core green / Optional blue / Extra amber) and "Ready to import" badge; submit disabled when missing core columns.
  - Verified: file with 11 cols (4 core + 3 optional + 4 extras) → all extras stored as JSON in DB; file missing core column rejected with HTTP 400.
- **2026-05-05** Bulk Leave Import — Column Alias Mapping & Value Transformation (final iteration).
  - Added `LEAVE_COLUMN_ALIASES` config (case-insensitive, whitespace-tolerant): multiple sheet headers → canonical field. Examples: `Employee Email`/`Emp Mail ID`/`Email ID` → `email`, `From Date`/`Start Date`/`Leave From` → `start_date`, `Approved By`/`Approver`/`Approving Authority` → `approved_by`, `Comments`/`Remark`/`Notes` → `comments`, etc. Unknown columns are ignored (not extra-stored).
  - Value transformations now applied during import:
    - `Approved By`: `"Admin"`/`"administrator"`/`"hr"` → current admin user ID; otherwise tries username, email, or full_name match against `users` and `employees` collections, returning resolved ID. Unresolved names preserved in `extra_data.approver_unresolved`.
    - `Status`: case-insensitive normalize → canonical lowercase `approved`/`pending`/`rejected` (matches existing system).
    - `Comments` mapped to existing `lop_remark` column (no schema change).
    - `Applied Date` and `Approval Date` parsed and stored under `extra_data` keys `applied_at`/`approved_at`.
  - Preview & Result responses now expose `column_mapping` (sheet → DB field) and `ignored_columns`. UI renders mapping as green chips and ignored columns as amber chips.
  - Template updated to use real-world friendly column names (`Emp Mail ID`, `From Date`, `To Date`, `No of Days`, etc.). Instructions sheet documents every alias.
  - Verified end-to-end with a 12-column real-world sheet (11 aliases + 1 ignored): all mapped; `"Admin"` → admin user ID; `"sysadmin"` username → sysadmin ID; `"admin@blubridge.com"` email → admin ID; `APPROVED`/`Pending`/`Approved` cases all normalized; mixed date formats parsed; unmapped column reported.
- **2026-05-05** Bulk Leave Import — Leave Split + Auto Approve (UI alignment).
  - Removed `No of Days` column from template + import logic; days are now auto-calculated from `From Date + To Date + Leave Split`.
  - Added `Leave Split` column (aliases: Split, Day Type) — accepts `Full Day` / `Half Day` (case-insensitive); maps to system values `Full Day` / `First Half`. Half-day → 0.5 × range.
  - Added `Auto Approve & Set LOP Status` column (aliases: Auto Approve, Auto Approve LOP) — accepts Yes/No, TRUE/FALSE, 1/0. When TRUE, the leave is force-approved (`status=approved`, `approved_by=current admin`, `is_lop=True`).
  - Validation: invalid Leave Split or invalid boolean values are rejected per-row with clear error messages.
  - Verified with 6 scenarios: Full Day approved, Half Day auto-approve+LOP, blank split defaulting to Full Day with TRUE auto-approve, Half Day across 2 days = 1 day total, invalid `Quarter Day` rejected, invalid `MaybeLater` rejected.
- **2026-05-05** Bulk Missed-Punch Import (Admin → Missed Punch Module).
  - New endpoints: `GET /api/missed-punches/import-template`, `POST /api/missed-punches/import/preview`, `POST /api/missed-punches/bulk-import` (HR/SysAdmin only).
  - `MP_COLUMN_ALIASES` config maps real-world headers (case-insensitive, whitespace-tolerant) to canonical fields (email, date, check_in, check_out, reason, status, applied_at, approved_by, approved_at, comments). Unknown columns ignored.
  - Approved imports auto-update attendance via `_update_attendance_from_missed_punch`.
  - Duplicate guard: DB and in-batch by (employee, date, punch_type).
  - Frontend: "Import Missed Punch" button (HR-only) + dialog with preview chips + summary counters + error log CSV.
- **2026-05-05** Bulk Missed-Punch Import — Punch Type column added (UI alignment).
  - Added `Punch Type` column to template (placed right after `Punch Date`); aliases `Type`, `Punch`. Now mandatory.
  - Accepts case-insensitive `Check-in`, `Check-out`, and `Both` (with variations like `CHECK-IN`, `check out`, `BOTH`, `checkin+checkout`). Invalid values → row rejected.
  - Business logic:
    - `Check-in` → uses In Time only; Out Time ignored.
    - `Check-out` → uses Out Time only; In Time ignored.
    - `Both` → REQUIRES both In Time and Out Time; rejects row if either missing.
  - Updated Instructions sheet to document the new column and ignore behaviour. Sample row added for `Both`.
  - Verified end-to-end with 6+ scenarios covering Both with both times, Both case-insensitive, Both missing one time, Check-in still works, Check-out still works.
  - New endpoints: `GET /api/missed-punches/import-template` (styled .xlsx with Instructions sheet), `POST /api/missed-punches/import/preview` (alias-mapping preview), `POST /api/missed-punches/bulk-import` (HR/SysAdmin only).
  - `MP_COLUMN_ALIASES` config maps real-world headers (case-insensitive, whitespace-tolerant): `Emp Mail ID`/`Employee Email` → `email`, `Punch Date`/`Date` → `date`, `In Time`/`Punch In`/`Login Time` → `check_in`, `Out Time`/`Punch Out`/`Logout Time` → `check_out`, `Reason`/`Remarks`/`Notes` → `reason`, `Status` → `status`, `Approved By`/`Approver` → `approved_by`, etc. Unknown columns are listed and ignored.
  - Validation: requires email + date + at least one of In/Out time + reason; auto-derives `punch_type` from In/Out presence (`Both`/`Check-in`/`Check-out`); accepts time formats `HH:MM`, `HH:MM:SS`, `HH:MM AM/PM`. Invalid times skipped per-row with clear errors.
  - Value transformation: `Approved By` `"Admin"`/username/email/full_name → resolved user ID; status normalized to `approved`/`pending`/`rejected`.
  - Approved imports automatically push attendance updates via existing `_update_attendance_from_missed_punch` (matches manual approval behavior).
  - Duplicate guard: skips rows that match existing non-rejected DB record AND in-batch repeats by (employee, date, punch_type).
  - Frontend: new "Import Missed Punch" button + dialog in `AdminMissedPunch.js` (HR-only) with template download, preview-after-pick (mapping chips green / ignored amber), summary counters, downloadable error log CSV.
  - Verified with 8 scenarios: Both-punch approved as Admin, In-only with AM/PM time, Out-only with sysadmin approver, invalid time rejected, missing both times rejected, missing reason rejected, unknown email rejected, in-batch duplicate caught.

- **2026-05-02** Fixed: Missed-Punch approval not reflecting in Attendance grid (BUG).
  - **Root cause:** `_update_attendance_from_missed_punch` persisted attendance rows using the raw `date` from the missed-punches collection (YYYY-MM-DD, from HTML date input). The rest of the attendance collection + `/api/attendance` filters use DD-MM-YYYY → corrected records were invisible to the frontend, so employees kept showing Absent even after HR approval.
  - **Fix (surgical):** Added a YYYY-MM-DD → DD-MM-YYYY normalizer at the top of `_update_attendance_from_missed_punch` in `backend/server.py` (existing recalculation logic untouched).
  - **One-time migration:** `backend/migrate_missed_punch_dates.py` renamed/merged 102 historical bad records (63 merged into existing DD-MM-YYYY rows — corrected values win; 39 date-renamed).
  - Verified with Krithik Sagala / 01-05-2026: attendance now returns `check_in: 09:30 AM, check_out: 08:30 PM, status: Present, source: corrected` via GET /api/attendance.

- **2026-05-02** Admin Leave module — added "Reason" column (truncated preview + hover tooltip + eye-icon opens full detail sheet) to both Pending and History tabs in `frontend/src/pages/Leave.js`. No API change; uses existing `reason` field.
- **2026-05-02** Dashboard "Leaves/No Login" — leave now wins over no-login.
  - Rewrote `GET /api/dashboard/leave-list` in `backend/server.py` to cross-reference the `leaves` collection (YYYY-MM-DD) against the queried DD-MM-YYYY date/range.
  - Employees with approved/pending leave overlapping the window are surfaced first with `leave_type`, leave date, and status `Leave` (approved) / `Pending Leave` (pending). Only employees with no attendance AND no leave now fall into the `Not Login` bucket.
  - Handles Full/Half Day, multi-day, Preplanned/Sick/Optional-Holiday leave types uniformly via `start_date <= to && end_date >= from`.
  - Added "Leave" / "Pending Leave" badge styling in `frontend/src/pages/Dashboard.js`.
  - Verified live: today returns 10 on-leave rows + 17 not-logged rows (previously all 27 were incorrectly shown as "Not Login").

- **2026-05-02** HRMS Automated Email Notification System — centralized enterprise-grade cron email engine (new, additive).
  - New modules: `backend/email_templates.py` (premium base template + 5 specialized templates with BluBridge branding, CTA buttons, mobile-responsive, footer), `backend/email_service.py` (`send_hrms_email`, dedup via `email_audit_logs` with partial unique index on `(email_type, scope_key) where status=sent`, retry with backoff, employee eligibility preflight, `generate_employee_action_link` deep-link helper), `backend/email_jobs.py` (5 APScheduler cron jobs, IST-aware, `coalesce=True, max_instances=1` to prevent overlap).
  - Schedules (IST): `adminAttendanceSummaryCron` 10:30 daily, `missedPunchCron` 09:00 daily (yesterday), `earlyOutCron` 09:15 daily (yesterday), `noLoginCron` 09:30 daily (yesterday), `lateLoginCron` Mon-Sat 10:00–13:45 every 15 min (today).
  - All jobs skip non-working days (Sunday + Holidays) and enforce per-employee guards: skip if leave/late-request/missed-punch/early-out request already applied; skip if source=`corrected`; no-login dual-CTA (Apply Leave + Apply Missed Punch).
  - Admin summary includes: Total / Logged In / Present / Not Logged / Late / Early Out / Half Day / Missed Punch / On Leave, plus Department-wise, Shift-wise, Top 5 delayed employees, attendance %.
  - New env vars: `FRONTEND_BASE_URL`, `ADMIN_REPORT_RECIPIENT` (defaults to `hrmsblubridge@gmail.com` for testing).
  - New HR-only APIs: `POST /api/email-jobs/{job_name}/run` (manual trigger with dedup still active), `GET /api/email-jobs/audit?email_type=...` (view audit log).
  - New MongoDB collection: `email_audit_logs` — tracks `email_type`, `scope_key`, `recipient_email`, `employee_id`, `status`, `error`, `provider_id`, `retry_count`, `sent_at`.
  - Verified end-to-end: admin summary delivered to `hrmsblubridge@gmail.com` via Resend (provider id recorded); second trigger for the same scope_key correctly skipped; yesterday (01-05-2026) was a May Day holiday → all yesterday-based jobs skipped with logs; scheduler boots cleanly on FastAPI startup.
  - **No changes** to attendance/payroll/leave/shift/biometric/dashboard/reports/existing APIs — purely additive.
  - Dependencies added: `apscheduler==3.11.2`, `tzlocal==5.3.1` (added to `requirements.txt`).

- **2026-05-02** Global Datatable UI Enhancement (frontend-only, additive).
  - **Sticky header** on every `.table-premium` table: `position:sticky; top:0; z-index:5;` + subtle backdrop blur + bottom shadow. Works against page-scroll & ancestor-scroll containers. No layout/column shift.
  - **Premium scrollbar** globally on `.overflow-x-auto / .overflow-y-auto / .overflow-auto / .scroll-premium`: 8 px thin track, rounded thumb, smooth scroll-behavior, theme-friendly hover state. Webkit + Firefox support.
  - **Reusable sort utility** `frontend/src/components/useTableSort.js`:
    - `useTableSort(rows, defaultField, defaultDir)` hook → returns `sortedRows, sortField, sortDir, toggleSort, resetSort`.
    - `<SortableTh>` drop-in `<th>` component with sort indicator (lucide ChevronsUpDown / Up / Down) + active-state highlight via `.sortable.sort-active` CSS.
    - Smart value coercion (numbers, DD-MM-YYYY, YYYY-MM-DD, ISO, `Hh Mm`, `HH:MM` 12/24h, strings), empty values always sort last.
  - Applied to highest-traffic admin tables: `Employees.js` (full row sort), `Attendance.js` (replaced legacy localeCompare sort with the new hook for proper date/time sorting), `AdminMissedPunch.js` (new — was unsorted previously).
  - **No backend/API/business-logic changes**; pagination, filtering, search, row actions, modals, and existing flows fully preserved. Lint clean across all touched files.
  - Remaining tables (Leave/Payroll/Holidays/Reports/etc.) continue to work as-is and can be migrated to the same hook in a follow-up — they already get the sticky header + premium scrollbar for free via CSS.

- **2026-05-02** Datatable Precision Fix — completed the global enhancement.
  - **3-state sort cycle**: `useTableSort` now cycles `asc → desc → reset (original order)` per column. When sortField is null we return the source `rows` reference unchanged, preserving original order without mutating the dataset.
  - **True body-only scroll**: `frontend/src/index.css` now applies `overflow-y: auto; max-height: calc(100vh - 280px)` automatically to every `.overflow-x-auto` that contains a `.table-premium` (via `:has()` selector — no per-table CSS class). Combined with the existing sticky `<thead th>`, only the table body scrolls inside the wrapper while the header stays pinned. Page itself no longer scrolls long tables.
  - Sort hook + SortableTh applied to: Employees, Attendance, AdminMissedPunch, AdminLateRequests, AdminEarlyOut, Leave, EmployeeAttendance, EmployeeLateRequest, EmployeeEarlyOut, EmployeeMissedPunch, EmployeeLeave, Reports.
  - Skipped intentionally (high regression risk / non-table layouts): Payroll (custom frozen-column table), Holidays (card-grid, not a table), StarReward (nested team-employees structure with its own pagination — separate follow-up).
  - All touched files lint clean; no backend / API / pagination / filtering / search / row-action changes.

- **2026-05-02** Hardened the 3-state sort cycle (`useTableSort`).
  - Replaced two split state slices (`sortField` + `sortDir`) with a single atomic state object `{ field, dir }`. The previous split version had a closure-mutation race in nested `setState` updaters that could miss the reset transition under React 18 strict mode.
  - State machine now strictly cycles `neutral → ASC → DESC → neutral → …` per column with atomic transitions. Switching to a different column always restarts at ASC.
  - `sortedRows` returns the SAME `rows` reference when neutral — guaranteeing the EXACT original API/dataset order on click-3 with zero mutation. The `slice()` only happens when actually sorting.
  - `<SortableTh>` icon already maps cleanly: `null/different field` → `ChevronsUpDown` neutral; `field=this, dir=asc` → `ChevronUp`; `field=this, dir=desc` → `ChevronDown`.
  - Removed pre-set default sort fields from `Attendance.js` and `Leave.js` so click-3 reset returns to true API order.
  - Programmatic 3-state cycle test (7 cases, neutral / asc / desc / reset / restart / switch / reset-after-switch) all pass via `node /tmp/test_sort.mjs`.
