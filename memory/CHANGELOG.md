# HRMS Changelog

## 2026-09-25 — Vigilance Edit/View: identify the submitter (Reported Employee vs Vigilance Team Member)
Fixed the ambiguity when editing a submission from the admin Vigilance Details modal.
The Edit/View dialog now clearly distinguishes two people via labelled ContextCards:
**Reported Employee** (User icon — name, email, photo) and **Vigilance Team Member**
(ShieldCheck icon, accent — the submitter, "Submitted by"), plus a Date card. Banner
title reads "Edit Vigilance Submission" with subtitle "Submitted by <member> · <date>".
The correct submission is loaded/saved per click (keyed by `submission.id`, unchanged) —
editing one member never touches another, no duplicates. After a save launched from the
modal, the detail modal auto-reopens for the same employee/day with refreshed values
(match by row.key with employee_id+date fallback). Employee photos show in the modal
header, submission cards and the dialog context cards. No backend/API/permission changes.
Verification: testing_agent iteration_88 — **100%** (per-click identity, save isolation
with data restored, reopen-after-save, avatars, 390px, permissions).

## 2026-09-25 — Vigilance admin table 3-tier header + centered detail modal (frontend-only)
Redesigned the admin Operational Vigilance table and its detail experience in
`OperationalVigilance.js`. No backend/API/DB/calculation/permission changes.
- **3-tier grouped header**: Tier1 bands = Employee | Attendance | centered light-blue
  **Vigilance Team** | Actions; Tier2 = base labels + each member's name centered
  spanning its two columns; Tier3 = Research / Break. Members are dynamic from
  `data.uploaders` (never hardcoded). New `.vig-sticky-h3` CSS + measured `--vig-h2`
  drive the 3-tier sticky header; frozen columns dropped (synced top scrollbar handles
  horizontal scroll).
- **Single View (eye) button** per employee/day row (`vig-view-detail-btn`) replaces the
  old stacked per-submission View/Edit/Delete.
- New **centered modal** (`vig-detail-modal`, not a right drawer): sticky header
  (employee/email/date•team), Attendance summary, and "Vigilance Team Submissions (N)"
  — one card per submitter with Research Hours and a **Total Break Hours accordion**
  (collapsed by default; expands to per-break From→To + Duration). Each card has its
  own Edit and Delete. Edit closes the modal and opens the pre-filled entry dialog;
  Delete opens a confirm naming employee/date/submitter. ESC + scroll-lock handled;
  collapsed accordion content marked `aria-hidden`.
Verification: testing_agent iteration_87 — **100%** of executable checks (header tiers,
dynamic members, single view, centered modal, accordion, per-submitter mapping,
edit/delete, ESC/scroll-lock, sorts, permissions, 390px). Own-view (/employee/vigilance)
not re-exercised due to vigilance-user password drift (unchanged code path).

## 2026-09-25 — Vigilance "View Entry" dialog redesign (frontend-only)
Redesigned the read-only View dialog in `OperationalVigilance.js`: avatar header,
Employee/Date info strip, four icon metric cards (System Login/Logout, Total Research,
Total Break), and a clean Breaks table (Break/From/To/Total with navy Total pills) plus
an empty-state. Edit/Add form and all handlers unchanged; no logic/API/data changes.

## 2026-09-25 — Vigilance Report table: compact dynamic per-member columns (frontend-only)
Restructured the Operational Vigilance Report data table (`OperationalVigilance.js`)
so the wide raw columns (Sys In/Out, per-break Morning/Lunch From/To/Total) are gone
from the main view. No backend/API/DB/calculation/permission changes.
- Each vigilance team member is now derived dynamically from `data.uploaders` (never
  hardcoded) and shown as a group with exactly two columns: **Research** and
  **Total Break** (dynamic count = uploaders × 2).
- Admin column order: Name (sticky, email under) · Date (sticky) · Team · Punch-In ·
  Punch-Out · Total Hours · [member: Research, Total Break]… · Actions (sticky right).
- Own view collapsed to a flat compact table: Name · Date · Team · Punch-In ·
  Punch-Out · Total Hours · Research · Total Break · Actions.
- Detailed break data is untouched and still fully accessible via the View/Edit dialog.
- Sorting on the new per-member columns + base columns preserved; per-member data is
  mapped strictly by `subByUp[uploader.employee_id]` (no cross-contamination); empty
  cells show a muted "—".
Verification: testing_agent iteration_86 — frontend **100%** (dynamic column count,
correct data mapping, detail preserved in dialog, no regressions, permission denial,
390px no overflow).

## 2026-09-24 — Vigilance Report UI/UX Redesign (frontend-only)
Redesigned `/app/frontend/src/pages/OperationalVigilance.js` (both `/vigilance` admin
and `/employee/vigilance` own-view) into a modern enterprise layout. **No** backend,
API, DB, permission, or calculation changes.

What changed (presentational only):
- Breadcrumb "Vigilance / Operational Report" + restyled page header (shield icon in
  light-blue circle, 26–28px title).
- Filter card reflowed to 2 rows of 3 (Row1: Employee Name / From / To, Row2:
  Department / Designation / Team) with a search-icon employee field + clear button,
  and a client-side **Reset** control (`vig-reset-btn`) that resets filters, sort,
  page and page-size, then reloads.
- Action toolbar with clear hierarchy (Filter = primary navy; Download Template /
  Upload / Add Entry / Export / Help Guide = secondary; Export pushed right).
- 4 **summary cards** (`vig-summary`) computed purely from already-loaded rows:
  Total Records, Employees (distinct), Date Range, Research Entries. No new API calls.
- Employee **avatars** (initials) in Name cells; email shown muted under the name.
- **Grouped headers** on the OWN view (Employee / Attendance / Vigilance-Research +
  per-break groups) via a 2-tier sticky header using existing `vig-sticky-h1/h2` CSS.
- Admin merged table: all existing multi-uploader column groups and dynamic Break
  From/To/Total columns **preserved**, just restyled (brand-tinted bands, avatars,
  cleaner icon actions).
- Icon row-actions (View/Edit/Delete) with tooltips; restyled pagination reading
  "Showing X to Y of Z records" with Previous / page-numbers / Next + rows selector.

All existing data-testids preserved (prefix `vig-`); all handlers unchanged.

Verification: testing_agent iteration_85 — frontend 98% pass. Admin, vigilance
employee (own view) and access-denial for a normal employee all verified; mobile
390px has no horizontal overflow. Fixed the one minor finding (Reset now also resets
page/page-size/sort).

Note: vigilance employee passwords (`madhan.s` / `dinesh.t`) drifted again in the
preview env and were resynced to `Vigil@123` during testing (known drift per
test_credentials.md — seed idempotency still a P2 backlog item).
