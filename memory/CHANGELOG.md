# HRMS Changelog

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
