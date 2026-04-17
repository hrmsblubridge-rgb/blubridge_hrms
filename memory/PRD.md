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

- **Payroll Weekoff Fix for Active + Inactive (Apr 17)**: Fixed critical bug where future Sundays/holidays were NOT counting as weekoff_pay for active employees, making active and inactive employees show identical weekoff. Now: Active employees count ALL Sundays/holidays in the month (e.g., April=6), inactive employees stop at inactive_date (e.g., Apr 14=4). Future working days also counted in working_days for active employees (April=24).
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
