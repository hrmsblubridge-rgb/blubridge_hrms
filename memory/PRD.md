# HRMS Application - Product Requirements Document

## Original Problem Statement
Build and enhance a premium HRMS web application with modules for employee onboarding, attendance tracking, leave management, payroll, teams, tickets, and more.

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
│   │   │   ├── Attendance.js          # Admin attendance (with pagination)
│   │   │   ├── EmployeeAttendance.js  # Employee attendance (period/status filters, pagination)
│   │   │   ├── Leave.js              # Admin leave (LOP approval, apply for employee)
│   │   │   ├── EmployeeLeave.js      # Employee leave (split, doc upload, edit)
│   │   │   ├── AdminLateRequests.js   # Admin late request management
│   │   │   ├── AdminEarlyOut.js       # Admin early out management
│   │   │   ├── AdminMissedPunch.js    # Admin missed punch management
│   │   │   ├── EmployeeLateRequest.js # Employee late request
│   │   │   ├── EmployeeEarlyOut.js    # Employee early out
│   │   │   ├── EmployeeMissedPunch.js # Employee missed punch
│   │   │   ├── Dashboard.js           # Admin dashboard
│   │   │   ├── Employees.js           # Employee CRUD + bulk import
│   │   │   ├── Holidays.js            # Holiday management (deduped)
│   │   │   └── Team.js
│   │   ├── components/
│   │   │   ├── Layout.js             # Admin sidebar (updated)
│   │   │   └── EmployeeLayout.js     # Employee sidebar (updated)
│   │   └── App.js                     # All routes
└── server/                            # DEPRECATED
```

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

### Phase 2 (Apr 8, 2026) - Current Session
**Bug Fixes:**
- Holiday duplicate entries fixed (upsert + unique index + dedup on startup)
- Dashboard attendance stats fixed (Python-side DD-MM-YYYY filtering instead of broken MongoDB string comparison)
- Employee attendance date filter fixed (from_date/to_date params now properly handled)

**Leave Module Enhancements:**
- Leave Split: Full Day / First Half / Second Half (backend + both frontends)
- Document upload on leave application form
- Edit pending leave requests (employee side)
- LOP/No_LOP selection on admin approval
- Admin: Apply leave for employee with optional auto-approve + LOP

**3 New Modules (Late Request, Early Out, Missed Punch):**
- Full backend CRUD + approve/reject APIs for all 3 modules
- Employee-side pages: Apply form + data view + edit pending
- Admin-side pages: Manage, approve/reject with LOP, apply for employee
- Missed Punch: Conditional fields based on punch type (Check-in/Check-out/Both)
- All modules added to sidebar navigation for both roles
- All routes wired in App.js

**Employee Attendance Enhancement:**
- Period quick-filters (This Week, Last Week, This Month, Last Month, Custom Range)
- Status filter dropdown
- Pagination controls

## Pending Issues
- **P1**: Cloudinary PDF Viewing (blocked on user Cloudinary settings)
- **P2**: Username collision on employee creation

## Backlog / Future Tasks
- **P1**: Biometric Sync Dashboard (UI for sync history, unmapped devices)
- **P2**: Leave Balance Tracking endpoint (`GET /api/employee/leave-balance`)
- **P2**: Backend refactoring (decompose server.py into routers/models/services)
- **P2**: Delete deprecated Node.js backend (`/app/server`)
- **P3**: Leave History redesign (ref: blubridge.ai style)

## Key DB Collections
- `employees`, `users`, `attendance`, `leaves`, `holidays`
- `late_requests`, `early_out_requests`, `missed_punches` (NEW)
- `biometric_punch_logs`

## Key API Endpoints
- `POST /api/late-requests` / `GET /api/late-requests`
- `PUT /api/late-requests/{id}/approve` / `PUT /api/late-requests/{id}/reject`
- `POST /api/early-out-requests` / `GET /api/early-out-requests`
- `PUT /api/early-out-requests/{id}/approve` / `PUT /api/early-out-requests/{id}/reject`
- `POST /api/missed-punches` / `GET /api/missed-punches`
- `PUT /api/missed-punches/{id}/approve` / `PUT /api/missed-punches/{id}/reject`
- `POST /api/leaves` (with leave_split, auto_approve, is_lop)
- `PUT /api/leaves/{id}/approve` (with is_lop, lop_remark)

## Credentials
- Admin: `admin` / `admin` (role: super_admin)
