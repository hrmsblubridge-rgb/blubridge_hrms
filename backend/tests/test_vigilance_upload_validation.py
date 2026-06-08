"""Regression tests for the Vigilance template-upload validation fixes.

FIX 1: System/reference columns (Name, Email-id, Team, Date, Punch-In, Punch-Out,
       Total Hours) must NEVER block an upload — renamed / reordered / missing /
       tampered values are ignored and reconstructed from the DB. Mapping falls
       back from Email-id to Name (+ Date).
FIX 2: Zero durations (00:00 / 00:00:00 / numeric 0) are VALID and must upload.
"""
import io
import os
import sys
from datetime import time as dtime, datetime

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vigilance import service as svc  # noqa: E402

EMP = {
    "id": "emp-1", "full_name": "Madhan S", "official_email": "madhan.s@blubridge.com",
    "team": "Vigilance", "department": "Ops", "designation": "Vigilance",
}
BY_EMAIL = {EMP["official_email"].lower(): EMP}
BY_NAME = {EMP["full_name"].lower(): EMP}
UP = {"employee_id": "uploader-9", "name": "Uploader"}

DEFAULT_BREAKS = ["Morning Break", "Lunch Break", "Evening Break", "Extra-Break1", "Extra-Break2"]


def _make_xlsx(header1, header2, data_rows):
    wb = Workbook()
    ws = wb.active
    ws.append(header1)
    ws.append(header2)
    for r in data_rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _std_headers(break_labels=DEFAULT_BREAKS):
    """Mimic the generated template: 11 fixed cols + break groups (3 cols each)."""
    h1 = list(svc.FIXED_COLS)  # 11
    h2 = [""] * len(svc.FIXED_COLS)
    for lbl in break_labels:
        h1 += [lbl, "", ""]
        h2 += ["From", "To", "Total"]
    return h1, h2


def _std_row(email="madhan.s@blubridge.com", name="Madhan S", date="06-Jun-2026",
             login="09:30", logout="18:00", research="08:00", break_hours="01:00",
             breaks=None, n_break_labels=len(DEFAULT_BREAKS)):
    row = [name, email, "Vigilance", date, "09:30 AM", "06:30 PM", "08:30",
           login, logout, research, break_hours]
    breaks = breaks or {}
    for i in range(n_break_labels):
        f, t, tot = breaks.get(i, ("", "", ""))
        row += [f, t, tot]
    return row


# ----------------------------------------------------------- unit: zero durations
@pytest.mark.parametrize("val", ["00:00", "00:00:00", 0, 0.0, dtime(0, 0), dtime(0, 0, 0),
                                 datetime(1899, 12, 30, 0, 0, 0)])
def test_norm_duration_accepts_zero(val):
    ok, norm = svc.norm_duration(val)
    assert ok is True
    assert norm == "00:00:00"


@pytest.mark.parametrize("val,exp", [("01:15", "01:15:00"), ("01:15:20", "01:15:20"),
                                     ("10:00", "10:00:00"), ("24:30", "24:30:00"),
                                     ("100:15", "100:15:00"), (0.4375, "10:30:00")])
def test_norm_duration_accepts_valid(val, exp):
    ok, norm = svc.norm_duration(val)
    assert ok is True and norm == exp


@pytest.mark.parametrize("val", ["25:99", "12:70", "10::30", "10-30", "AA:BB"])
def test_norm_duration_rejects_malformed(val):
    ok, _ = svc.norm_duration(val)
    assert ok is False


def test_norm_clock_accepts_numeric_zero():
    ok, norm = svc.norm_clock(0)
    assert ok is True and norm == "12:00 AM"


# --------------------------------------------------- Scenario C/D/E: zero durations upload
def test_zero_durations_upload_succeeds():
    h1, h2 = _std_headers()
    row = _std_row(research="00:00", break_hours="00:00:00",
                   breaks={3: ("", "", "00:00")})  # Extra-Break1 Total = 00:00
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    assert len(entries) == 1
    e = entries[0]
    assert e["total_research_hours"] == "00:00:00"
    assert e["total_break_hours"] == "00:00:00"
    # zero-duration extra break is preserved
    assert any(b["total"] == "00:00:00" for b in e["breaks"])


def test_numeric_zero_cells_upload_succeeds():
    h1, h2 = _std_headers()
    row = _std_row(research=0, break_hours=0.0)  # Excel numeric zeros
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    assert entries[0]["total_research_hours"] == "00:00:00"


# --------------------------------------------------- Scenario A: modified system cols
def test_modified_system_columns_are_ignored():
    h1, h2 = _std_headers()
    row = _std_row()
    # Tamper Name/Team/Punch/Total Hours — these must be ignored & rebuilt from DB
    row[0] = "WRONG NAME"
    row[2] = "WRONG TEAM"
    row[4] = "garbage"
    row[5] = "garbage"
    row[6] = "garbage"
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    assert entries[0]["target_employee_name"] == "Madhan S"   # from DB, not sheet
    assert entries[0]["target_team"] == "Vigilance"


# --------------------------------------------------- Scenario B: missing system cols
def test_missing_system_columns_still_imports():
    # Only Email, Date + editable columns present (Name/Team/Punch/TotalHours removed)
    h1 = ["Email-id", "Date", "System Login", "System Logout",
          "Total Research Hours", "Total Break Hours"]
    h2 = ["", "", "", "", "", ""]
    row = ["madhan.s@blubridge.com", "06-Jun-2026", "09:30", "18:00", "08:00", "01:00"]
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    assert entries[0]["target_employee_id"] == "emp-1"
    assert entries[0]["total_research_hours"] == "08:00:00"


# --------------------------------------------------- reordered + renamed columns
def test_reordered_and_renamed_columns_still_imports():
    # Date first, Email renamed to 'Email', research renamed slightly, breaks moved before scalars
    h1 = ["Date", "Email", "Morning Break", "", "", "System Login",
          "System Logout", "Research", "Total Break Hours"]
    h2 = ["", "", "From", "To", "Total", "", "", "", ""]
    row = ["06-Jun-2026", "madhan.s@blubridge.com", "10:00", "10:15", "00:15",
           "09:30", "18:00", "08:00", "01:00"]
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    e = entries[0]
    assert e["total_research_hours"] == "08:00:00"
    assert any(b["label"] == "Morning Break" and b["total"] == "00:15:00" for b in e["breaks"])


# --------------------------------------------------- Scenario: Name fallback mapping
def test_name_fallback_when_email_blank():
    h1, h2 = _std_headers()
    row = _std_row(email="")  # no email — must map by Name
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    assert entries[0]["target_employee_id"] == "emp-1"


# --------------------------------------------------- Scenario F: only vigilance cols + standard happy path
def test_standard_template_happy_path():
    h1, h2 = _std_headers()
    row = _std_row(breaks={0: ("09:00", "09:15", "00:15"), 1: ("13:00", "13:45", "00:45")})
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors == [], errors
    e = entries[0]
    assert e["system_login"] == "09:30 AM"
    assert e["system_logout"] == "06:00 PM"
    assert e["total_research_hours"] == "08:00:00"
    labels = {b["label"] for b in e["breaks"]}
    assert {"Morning Break", "Lunch Break"} <= labels


# --------------------------------------------------- still rejects genuinely bad editable values
def test_malformed_editable_value_is_rejected():
    h1, h2 = _std_headers()
    row = _std_row(research="25:99")  # invalid duration
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [row]), BY_EMAIL, BY_NAME, UP)
    assert errors and any("Research" in e["message"] for e in errors)


# --------------------------------------------------- empty rows skipped, unknown employee errors
def test_empty_rows_skipped_and_unknown_employee_errors():
    h1, h2 = _std_headers()
    empty = _std_row(email="madhan.s@blubridge.com", login="", logout="", research="",
                     break_hours="")
    unknown = _std_row(email="ghost@x.com", name="Ghost", research="08:00")
    entries, errors = svc.parse_upload(_make_xlsx(h1, h2, [empty, unknown]), BY_EMAIL, BY_NAME, UP)
    assert len(entries) == 0
    assert any("Could not match" in e["message"] for e in errors)
