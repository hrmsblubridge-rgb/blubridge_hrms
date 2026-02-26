# BluBridge HRMS - Product Requirements Document

## Latest Updates (February 26, 2026)

### Issue Ticket System - COMPLETED (NEW!)
**100% Complete** - Comprehensive employee support ticket system with premium design

#### Features
- **6 Categories** with auto-assignment to departments:
  - IT & System Support → IT Admin
  - HR Support → HR Admin
  - Finance & Accounts → Finance Admin
  - Admin & Stationery → Admin Department
  - Compliance & Legal → Compliance Officer
  - Operations → Operations Manager

- **Subcategories** per category (e.g., Login Issue, Password Reset, Salary Not Credited, etc.)

- **Priority Levels**: High 🔴 | Medium 🟡 | Low ⚪

- **Status Workflow**: Open → In Progress → Waiting for Approval → On Hold → Resolved → Closed → Rejected

- **Ticket Features**:
  - Auto-generated ticket numbers (TKT-YYYYMMDD-XXX)
  - File attachments via Cloudinary
  - Status timeline with notes
  - Resolution tracking
  - Employee feedback (1-5 rating + comment)

#### Admin View (`/issue-tickets`)
- Stats dashboard: Total, Open, In Progress, Resolved
- Priority breakdown: High/Medium/Low counts
- Filters: Status, Priority, Category, Search
- Ticket list with category icons, status badges, priority indicators
- Create ticket (for self or on behalf of employee)
- Ticket detail with 3 tabs: Details, Timeline, Actions
- Update status with notes and resolution

#### Employee View (`/employee/tickets`)
- Personal stats: Total, Open, In Progress, Resolved
- "Raise New Ticket" with category card selection
- Urgency picker: Not urgent, Moderate, Very urgent
- View ticket details and timeline
- Close resolved tickets
- Submit feedback for resolved tickets

#### Backend APIs
- `GET /api/issue-tickets/categories` - List all categories with subcategories
- `GET /api/issue-tickets` - List tickets (role-filtered)
- `GET /api/issue-tickets/stats` - Comprehensive statistics
- `GET /api/issue-tickets/{id}` - Single ticket details
- `POST /api/issue-tickets` - Create ticket
- `PUT /api/issue-tickets/{id}/status` - Update status
- `PUT /api/issue-tickets/{id}/assign` - Assign to user
- `POST /api/issue-tickets/{id}/feedback` - Submit feedback

#### Testing Status
- **Testing Agent Iteration 20**: 100% Pass Rate
- Backend: 18/18 tests passed
- Frontend: 16/16 features verified

---

### Policies & Education/Experience Modules - COMPLETED
**100% Complete** - Full implementation tested and verified

#### Policies Module
- **3 Company Policies** created and accessible by both Admin and Employees:
  1. **Leave Policy** (HR, v2.0) - Leave types, entitlements, application process, restrictions, encashment
  2. **IT Team Policy** (Department, v1.5) - Working hours, code standards, equipment, security, career development
  3. **Research Unit Policy** (Department, v1.0) - Research standards, IP, funding, project management, safety

- **Features:**
  - Policy cards with category badges, version, effective date
  - Detail modal with expandable accordion sections
  - Both Admin and Employee can view policies

#### Education & Experience Module
- **Employee Side** (`/employee/education-experience`):
  - Add/Edit/Delete education qualifications (level, institution, board/university, year, percentage/CGPA)
  - Add/Edit/Delete work experience (company, designation, dates, responsibilities)
  - After verification by HR, entries become read-only

- **Admin Side** (in Employee Details dialog):
  - View employee education and experience via "Education & Experience" tab
  - Verify education details with "Verify" button
  - Verify experience details with "Verify" button
  - Verified entries show "Verified" badge

#### Backend APIs Added
- `GET /api/policies` - List all policies
- `GET /api/policies/{id}` - Get policy details
- `PUT /api/policies/{id}` - Update policy (admin only)
- `GET /api/employee-profile/education-experience` - Employee's own data
- `PUT /api/employee-profile/education-experience` - Update own data
- `GET /api/employees/{id}/education-experience` - Admin view
- `POST /api/employees/{id}/verify-education` - HR verify education
- `POST /api/employees/{id}/verify-experience` - HR verify experience

#### Testing Status
- **Testing Agent Iteration 19**: 100% Pass Rate
- Backend: 17/17 tests passed
- Frontend: 11/11 features verified

---

### Employee Onboarding Flow - COMPLETED
**100% Complete** - Full employee onboarding workflow implemented and tested

#### The Flow
1. HR creates employee → Employee receives login credentials via email
2. First login → Employee redirected to onboarding page
3. Employee uploads required documents:
   - Aadhaar Card (Required)
   - PAN Card (Required)
   - Passport
   - Voter ID
   - Education Certificates (Required)
   - Experience Certificates
   - Offer / Appointment Letter
   - Relieving Letter
   - Passport-size Photograph (Required)
4. HR reviews documents in Verification page
5. HR approves/rejects → Employee gets full HRMS access or action required
6. Onboarding becomes view-only after approval (permanently locked)

#### Cloudinary Integration
- Cloud Name: djsvuh19j
- Documents stored in: blubridge/documents/

#### New Pages Created
1. **Verification Page** (`/verification`) - HR reviews pending onboarding requests
   - Stats cards: Total Employees, Pending Verifications, Rejected Documents, Completed
   - Onboarding Queue table with search and filters
   - Document review modal with approve/reject per document
   
2. **Tickets Page** (`/tickets`) - Support ticket system
   - Stats cards: Total Tickets, Open, In Progress, Resolved
   - Create/View/Update tickets
   - Priority levels and status management
   
3. **Audit Logs Page** (`/audit-logs`) - Activity tracking
   - Stats: Total Logs, Logins Today, Changes Today, Onboarding Actions
   - Activity table with timestamp, user, action, resource, details
   - Filter by resource type
   
4. **Employee Onboarding Page** (`/employee/onboarding`) - Document upload
   - Welcome message with onboarding status badge
   - Progress bar showing completion percentage
   - Document upload cards for each required document type
   - Submit for Review button (enabled when all required docs uploaded)

#### Backend APIs Added
- `GET /api/onboarding/stats` - Onboarding statistics
- `GET /api/onboarding/list` - List all onboarding records
- `GET /api/onboarding/employee/{id}` - Get employee's onboarding details
- `GET /api/onboarding/my-status` - Get current user's onboarding status
- `POST /api/onboarding/upload-document` - Upload a document
- `POST /api/onboarding/submit` - Submit onboarding for review
- `POST /api/onboarding/verify-document` - HR verify/reject document
- `POST /api/onboarding/approve/{id}` - HR approve/reject onboarding
- `GET /api/tickets` - List tickets
- `POST /api/tickets` - Create ticket
- `PUT /api/tickets/{id}/status` - Update ticket status
- `GET /api/tickets/stats` - Ticket statistics
- `GET /api/audit-logs` - Get activity logs

#### Testing Status
- **Testing Agent Iteration 18**: 100% Pass Rate
- Backend: 13/13 tests passed
- Frontend: 8/8 features verified

### Login Page UI Enhancement - COMPLETED
- **Requirement:** Light-themed login page with animated border
- **Background:** Soft cream/off-white (#FFFDF6)
- **Card Features:**
  - Rounded rectangle with subtle shadow
  - Animated blue border (5s loop, top→right→bottom→left)
  - CSS conic-gradient rotation technique
- **Form Elements:** Username/password inputs with icons, eye toggle, blue Sign In button
- **Status:** ✅ Implemented and tested

### Pending Items:
1. **eSSL X990 Biometric Integration** - Awaiting user's integration preferences
2. **Backend Date Filtering Bug** - Dates stored as "DD-MM-YYYY" strings break MongoDB range queries
3. **Cloudinary PDF Viewing** - Admin viewing PDFs returns 401 (user needs to enable public delivery in Cloudinary settings)
4. **Username Collision on Employee Creation** - Silent failure when duplicate username generated

---

## Original Problem Statement
Build a complete Human Resource Management System (HRMS) with admin and employee modules, including:
- Employee management with CRUD operations
- Attendance tracking with check-in/out
- Leave management with approval workflows
- Star reward system for performance tracking
- Team management by departments
- Payroll with attendance-based calculations
- Reports generation and export

## Latest Update: Employee Leave Visualization (Feb 9, 2026)

### Completed: Employee Leave Detail Modal
**100% Complete** - Detailed, visual Leave Overview for individual employees when clicked from Attendance Module.

#### Features Implemented
- **Employee Header**: Shows name, Employee ID, department, designation with avatar
- **Month Navigation**: Previous/Next buttons with month/year display
- **KPI Summary Cards**: 5 cards showing Total Leaves Taken, Remaining Leaves, Approved This Month, Pending Requests, LOP Days
- **View Toggle**: Day/Week/Month view options with smooth transitions
- **Monthly Bar Chart**: Color-coded bars for each day (Present, Leave, Half Day/Late, LOP, Week Off, Absent)
- **Weekly Summary Chart**: Grouped bar chart showing weekly breakdown
- **Daily Calendar View**: 7-day grid with color-coded tiles and status labels
- **Leave Type Filter**: Dropdown to filter by leave types (Sick, Emergency, Preplanned, etc.)
- **Leave History Log Table**: Detailed table with Date, Leave Type, Duration, Reason, Status, Approved By

#### Implementation Details
- New component: `/app/frontend/src/components/EmployeeLeaveDetail.js`
- Integrated into Attendance.js with clickable chart icon per employee row
- Uses Recharts library for visualization (BarChart, ResponsiveContainer)
- Fetches data from existing APIs: /api/attendance, /api/leaves, /api/employees

#### Testing Status
- **Testing Agent**: Iteration 17 - 100% Pass Rate (13/13 features)
- All features working: modal open/close, month navigation, view toggles, filters, chart rendering

### Previous Update: Dashboard Attendance Chart Filters (Feb 5, 2026)
**100% Complete** - Filters for Attendance Overview chart implemented and tested

## Premium UI/UX Redesign (Feb 5, 2026)

### Completed: Full Visual Redesign
**100% Complete** - All pages redesigned with premium UI/UX

#### Design System
- **Color Palette**: Primary Blue (#063c88), Background (#efede5), Cards (#fffdf7)
- **Typography**: Outfit for headings, Public Sans for body, JetBrains Mono for numbers
- **Components**: Glassmorphism sidebar, Bento grid layouts, Premium stat cards
- **Charts**: Recharts integration for data visualization

#### Pages Redesigned
1. **Login** - Premium split layout with blue gradient branding
2. **Admin Layout** - Glassmorphism sidebar with active states, search bar, notifications
3. **Employee Layout** - Simplified employee navigation with emerald/teal accent
4. **Dashboard** - Bento grid with stats, Weekly Attendance chart, Attendance Distribution
5. **Employees** - Stats cards, advanced filters, premium table, tabbed forms
6. **Attendance** - Quick stats, sortable table, status badges with icons, Employee Leave Detail modal
7. **Leave** - Request/History tabs, approve/reject workflows
8. **Star Reward** - Amber/gold theme, employees/teams tabs, grid/table views
9. **Team** - Department tabs, team cards grid, member modals
10. **Payroll** - Summary cards, salary chart, attendance/salary view tabs
11. **Reports** - Leave/Attendance report filters and export
12. **Admin Profile** - Premium gradient header with editable fields
13. **Change Password** - Security-focused with password strength indicator
14. **Employee Dashboard** - Clock in/out with working hours chart
15. **Employee Attendance** - Personal attendance history
16. **Employee Leave** - Leave balance and application
17. **Employee Profile** - Personal information display

## Technology Stack
- **Frontend**: React 18, Tailwind CSS, Shadcn/UI, Recharts
- **Backend**: FastAPI, Python
- **Database**: MongoDB
- **Authentication**: JWT tokens

## User Personas
1. **Admin/HR Manager** - Full access to all modules
2. **Team Lead** - Department-level access, approve leaves
3. **Employee** - Personal dashboard, attendance, leave requests

## Core Features (All Implemented)
1. ✅ Authentication with role-based access
2. ✅ Employee CRUD with advanced search/filters
3. ✅ Attendance tracking with check-in/out
4. ✅ Leave management with approval workflow
5. ✅ Star reward system with weekly tracking
6. ✅ Team dashboard by departments
7. ✅ Payroll with LOP calculations
8. ✅ CSV export for reports
9. ✅ Employee Leave Visualization
10. ✅ Employee Onboarding Flow (NEW)
11. ✅ Support Tickets System (NEW)
12. ✅ Audit Logs Tracking (NEW)

## Future Enhancements (Backlog)
- P1: eSSL X990 Biometric Device Integration (research done, awaiting user decision)
- P2: Backend Date Filtering Bug Fix (dates stored as "DD-MM-YYYY" strings)
- P2: Email notifications for leave approvals
- P3: Performance review module
- P3: Document management

## File Structure
```
/app/frontend/src/
├── components/
│   ├── Layout.js              # Admin layout with premium sidebar
│   ├── EmployeeLayout.js      # Employee layout
│   ├── EmployeeLeaveDetail.js # Employee leave visualization modal
│   └── ui/                    # Shadcn components
├── contexts/
│   └── AuthContext.js         # Auth with needsOnboarding() function
├── pages/
│   ├── Login.js               # Premium login page
│   ├── Dashboard.js           # Admin dashboard with charts
│   ├── Employees.js           # Employee management
│   ├── Attendance.js          # Attendance tracking + Leave Detail modal
│   ├── Leave.js               # Leave management
│   ├── StarReward.js          # Star rewards (amber theme)
│   ├── Team.js                # Team dashboard
│   ├── Payroll.js             # Payroll management
│   ├── Reports.js             # Report generation
│   ├── Verification.js        # NEW: HR onboarding verification
│   ├── Tickets.js             # NEW: Support tickets
│   ├── AuditLogs.js           # NEW: Activity audit logs
│   ├── AdminProfile.js        # Admin profile
│   ├── ChangePassword.js      # Password change
│   ├── EmployeeDashboard.js
│   ├── EmployeeAttendance.js
│   ├── EmployeeLeave.js
│   ├── EmployeeProfile.js
│   └── EmployeeOnboarding.js  # NEW: Employee document upload
└── index.css                  # Global premium styles
```

## Test Credentials
- **Admin**: admin / admin
- **Employee (needs onboarding)**: onboardtest / onbo@6655
