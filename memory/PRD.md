# BluBridge HRMS - Product Requirements Document

## Original Problem Statement
Premium Employee Issue Ticket System, Offer Letter Management, Salary Management, Payslip PDF, Login Page Redesign, Application Branding, and now Employee Management enhancements with custom Employee ID, Biometric ID, and Bulk Employee Import.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn UI (port 3000)
- **Backend:** Python FastAPI monolith (port 8001)
- **Database:** MongoDB
- **File Storage:** Cloudinary
- **PDF Generation:** jsPDF + html2canvas

## What's Been Implemented

### Phase 1 - Core HRMS (Complete)
- Employee onboarding & management
- Admin verification workflow
- Holidays & policies management
- Education module
- Attendance tracking
- Leave management
- Star rewards system
- Team management
- Payroll module

### Phase 2 - Premium Features (Complete)
- Issue Ticket System (full CRUD, categories, priorities)
- Offer Letter Management (Cloudinary uploads)
- Salary Management System (CTC breakdown, components)
- Payslip PDF download (clean, no browser headers)

### Phase 3 - UI/Branding (Complete)
- Login page redesign (centered premium layout)
- Meta title: "BluBridge HRMS - Complete HR System"
- Global favicon

### Phase 4 - Employee Management Enhancements (Complete - Feb 2026)
- **Custom Employee ID field:** Added to Employee creation/edit forms (Employment section), unique, required, displayed in employee list table, view dialog, and searchable
- **Biometric ID field:** Added to Employee creation/edit forms (System section), unique, required, for external biometric device mapping, displayed in list and view
- **Bulk Employee Import:** Excel (.xlsx) and CSV upload support, flexible column name mapping, comprehensive validation (required fields, uniqueness), batch processing with detailed error reporting (row-by-row), downloadable sample template with instructions sheet, date parsing (MM/DD/YYYY, YYYY-MM-DD, DD-MM-YYYY, Excel numeric/datetime)

### Phase 5 - Biometric Attendance Ingestion (Complete - Feb 2026)
- **POST /api/attendance/import-biometric:** Secure endpoint accepting JSON array of biometric punches from external device sync service
- **Employee Mapping:** Maps `deviceUserId` → `Employee.biometric_id`, reports unmapped IDs
- **Punch Grouping:** Groups all punches per employee per day, computes IN (earliest) and OUT (latest) times
- **Upsert Logic:** Merges chunked data — IN = MIN(existing, new), OUT = MAX(existing, new) — ensures idempotent chunked imports
- **Attendance Status:** Calculates LOP, late login, total hours using existing shift rules
- **Audit Trail:** Stores raw punch logs in `biometric_punch_logs` collection for debugging
- **Response:** Returns `{totalRecords, processed, skipped, unmapped, unmappedDeviceUserIds}`
- **Performance:** Handles 500+ records per batch, tested with 50+ records
- **Backend:** Updated Employee/EmployeeCreate/EmployeeUpdate models, uniqueness validation, search support, GET /api/employees/import-template, POST /api/employees/bulk-import
- **Frontend:** Updated form state, Add/Edit dialogs, employee list table columns, View dialog profile tab, Bulk Import dialog with file upload, template download, and results display

## Pending Issues
1. **Cloudinary PDF Viewing (P1 - BLOCKED):** Admin can't view PDFs in browser (401), needs Cloudinary account setting change
2. **Username collision (P2):** Silent failure when employee email username already exists in users collection
3. **Backend date filtering (P2, recurring):** Attendance dates stored as DD-MM-YYYY strings, need migration to ISODate

## Upcoming Tasks
- **Biometric Device Integration (P1):** eSSL X990 device research and integration plan
- **Refactor Backend (P2):** Decompose server.py into routers/models/services
- **Delete deprecated Node.js backend (P2):** Remove /app/server directory

## Key API Endpoints
- POST /api/auth/login
- GET/POST /api/employees
- GET/PUT/DELETE /api/employees/{employee_id}
- GET /api/employees/import-template (downloads .xlsx template)
- POST /api/employees/bulk-import (multipart file upload)
- POST /api/attendance/import-biometric (JSON array of biometric punches)
- GET/POST /api/tickets
- GET/POST /api/employees/{employee_id}/documents
- GET/POST /api/employees/{employee_id}/salary

## Key DB Schema
- **employees:** { emp_id (auto), custom_employee_id (admin-set), biometric_id, full_name, official_email, department, team, designation, ... }
- **users:** { email, password, role, employee_id, ... }
- **tickets:** { ticket_id, employee_id, category, status, priority, ... }
- **salaries:** { employee_id, annual_ctc, components, adjustments }
- **attendances:** { employee_id, date (DD-MM-YYYY), check_in, check_out, check_in_24h, check_out_24h, status, source ("biometric"|null), device_ip }
- **biometric_punch_logs:** { imported_at, imported_by, total_punches, logs: [{deviceUserId, recordTime, ip, status, employee_id, date}] }

## 3rd Party Integrations
- Cloudinary (file uploads)
- jsPDF & html2canvas (PDF generation)
- openpyxl (Excel parsing for bulk import)

## Test Credentials
- **Admin:** admin / admin
- **Employee:** test.employee2@blubridge.com / password
