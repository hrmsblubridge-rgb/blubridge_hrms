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
│   └── server.py         # Monolithic FastAPI app (>6300 lines)
├── frontend/
│   ├── public/
│   └── src/
│       ├── pages/
│       │   ├── Attendance.js    # With pagination
│       │   ├── Employees.js     # With bulk import
│       │   ├── EmployeeLeave.js # Start/End date
│       │   ├── Team.js
│       │   └── Dashboard.js
│       └── App.js
└── server/                # DEPRECATED: Old Node.js backend
```

## What's Been Implemented
- Custom Employee ID & Biometric ID fields
- Bulk Employee Import via Excel/CSV with welcome emails
- Biometric Attendance Ingestion API (atomic upserts)
- MongoDB Atlas migration with admin seeding
- Strict fixed dropdowns for Department/Team/Designation
- Leave Application: Start Date / End Date
- Team Member Count display fix
- **Attendance Module Pagination** (client-side, 10/25/50 rows per page, resets on filter change) - Mar 24, 2026

## Pending Issues
- **P1**: Cloudinary PDF Viewing (blocked on user Cloudinary settings)
- **P2**: Username collision on employee creation (silent failure)

## Backlog / Upcoming Tasks
- **P1**: Biometric Sync Dashboard (UI for sync history, unmapped devices)
- **P2**: Leave Balance Tracking endpoint (`GET /api/employee/leave-balance`)
- **P2**: Backend refactoring (decompose server.py into routers/models/services)
- **P2**: Delete deprecated Node.js backend (`/app/server`)

## Key Credentials
- Admin: `admin` / `admin` (role: super_admin)

## Key API Endpoints
- `POST /api/employees/bulk-import`
- `POST /api/attendance/import-biometric`
- `POST /api/employee/leaves/apply`
- `GET /api/attendance` (with date/filter params)
