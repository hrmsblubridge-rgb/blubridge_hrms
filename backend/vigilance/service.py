"""
Vigilance service layer — pure(ish) helpers operating on the injected Motor `db`.

Sections:
  * Formatting / validation (dates, clock times, durations)
  * Data sources (date-aware active employees, attendance snapshot) — READ ONLY
  * Template generation (streaming xlsx)
  * Upload parsing (dynamic break detection + strict validation)
  * Repository (upsert/CRUD on `vigilance_entries`)
  * Aggregation (vigilance own-view, admin merged-view, attendance integration)

Storage model — collection `vigilance_entries`, one doc per
(target_employee_id + date + uploaded_by_employee_id):
  {
    id, target_employee_id, target_employee_name, target_email,
    target_team, target_department, target_designation,
    date (ISO yyyy-mm-dd),
    uploaded_by_employee_id, uploaded_by_name,
    system_login, system_logout,            # editable clock times "HH:MM AM/PM"
    total_research_hours, total_break_hours, # editable durations "HH:MM"
    breaks: [ {label, from, to, total} ],    # DYNAMIC, ordered, unlimited
    created_at, updated_at
  }
"""
import io
import re
import uuid
from datetime import datetime, date, timezone, time as dtime

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FIXED_COLS = [
    "Name", "Email-id", "Team", "Date", "Punch-In", "Punch-Out", "Total Hours",
    "System Login", "System Logout", "Total Research Hours", "Total Break Hours",
]
N_FIXED = len(FIXED_COLS)                       # 11
ATT_SYSTEM_COLS = ["Name", "Email-id", "Team", "Date", "Punch-In", "Punch-Out", "Total Hours"]  # non-editable, attendance-derived
DEFAULT_BREAK_LABELS = ["Morning Break", "Lunch Break", "Evening Break", "Extra-Break1", "Extra-Break2"]
BREAK_SUBS = ["From", "To", "Total"]

VIGILANCE_DESIGNATION = "vigilance"

CLOCK_RE = re.compile(r"^(\d{1,2}):([0-5]\d)\s*(AM|PM)$", re.IGNORECASE)
TWENTYFOUR_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DUR_RE = re.compile(r"^(\d{1,3}):([0-5]\d)$")


# ----------------------------------------------------------------------------
# Formatting / validation
# ----------------------------------------------------------------------------
def to_iso(value):
    """Normalise any supported date representation to ISO 'YYYY-MM-DD' or None.

    Accepts: ISO, DD-MM-YYYY (attendance store), DD-MMM-YYYY (display), datetime/date.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", s)            # DD-MM-YYYY
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    try:
        return datetime.strptime(s, "%d-%b-%Y").strftime("%Y-%m-%d")  # DD-MMM-YYYY
    except ValueError:
        return None


def iso_to_display(iso):
    """ISO 'YYYY-MM-DD' -> 'DD-MMM-YYYY' (universal HRMS format)."""
    if not iso:
        return ""
    try:
        d = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
        return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"
    except ValueError:
        return ""


def parse_display_date_strict(value):
    """Strict 'DD-MMM-YYYY' -> ISO. Returns None on any deviation (for validation)."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    try:
        return datetime.strptime(str(value).strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _hm_to_12h(h, mm):
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12:02d}:{mm} {ampm}"


def norm_clock(value):
    """Validate a clock time entered as EITHER 24-hour (13:45) OR 12-hour
    (01:45 PM) and normalise to canonical 12-hour 'HH:MM AM/PM' for storage.
    Returns (ok, normalised|''). Blank allowed.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return True, ""
    if isinstance(value, dtime):
        return True, _hm_to_12h(value.hour, f"{value.minute:02d}")
    if isinstance(value, datetime):
        return True, _hm_to_12h(value.hour, f"{value.minute:02d}")
    s = re.sub(r"\s+", " ", str(value).strip())
    m = CLOCK_RE.match(s)               # 12-hour with AM/PM
    if m:
        h = int(m.group(1))
        if h < 1 or h > 12:
            return False, None
        return True, f"{h:02d}:{m.group(2)} {m.group(3).upper()}"
    m = TWENTYFOUR_RE.match(s)          # 24-hour
    if m:
        return True, _hm_to_12h(int(m.group(1)), m.group(2))
    return False, None


def to_24h(value):
    """Convert a stored 12-hour (or already-24h) clock string to 24-hour 'HH:MM'.
    Blank stays blank. Used for the Vigilance-user download/export format.
    """
    if value is None or str(value).strip() == "":
        return ""
    if isinstance(value, dtime):
        return f"{value.hour:02d}:{value.minute:02d}"
    s = re.sub(r"\s+", " ", str(value).strip())
    m = CLOCK_RE.match(s)
    if m:
        h = int(m.group(1)) % 12
        if m.group(3).upper() == "PM":
            h += 12
        return f"{h:02d}:{m.group(2)}"
    m = TWENTYFOUR_RE.match(s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return str(value).strip()


def norm_duration(value):
    """Validate/normalise a duration HH:MM (no AM/PM). Returns (ok, normalised|''). Blank allowed."""
    if value is None or str(value).strip() == "":
        return True, ""
    s = str(value).strip()
    m = DUR_RE.match(s)
    if not m:
        return False, None
    return True, f"{int(m.group(1)):02d}:{m.group(2)}"


def att_total_hours_to_duration(att):
    """Convert attendance total_hours ('11h 36m' / decimal) to 'HH:MM' duration."""
    th = att.get("total_hours")
    if th:
        m = re.match(r"(\d+)\s*h\s*(\d+)\s*m", str(th))
        if m:
            return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    d = att.get("total_hours_decimal")
    if d is not None:
        try:
            h = int(d)
            mn = round((float(d) - h) * 60)
            if mn == 60:
                h, mn = h + 1, 0
            return f"{h:02d}:{mn:02d}"
        except (ValueError, TypeError):
            return ""
    return ""


# ----------------------------------------------------------------------------
# Data sources (READ ONLY — never mutate attendance / employees)
# ----------------------------------------------------------------------------
async def get_active_employees(db, iso_from, iso_to, *, employee_ids=None):
    """Return employees that were active at any point within [iso_from, iso_to].

    Date-aware: an employee is active on day D when joining<=D and
    (no inactive_date OR D<=inactive_date). ISO date strings compare lexically.
    """
    query = {}
    if employee_ids is not None:
        query["id"] = {"$in": employee_ids}
    proj = {
        "_id": 0, "id": 1, "full_name": 1, "official_email": 1, "team": 1,
        "department": 1, "designation": 1, "date_of_joining": 1, "inactive_date": 1,
        "employee_status": 1,
    }
    emps = await db.employees.find(query, proj).to_list(100000)
    out = []
    for e in emps:
        doj = to_iso(e.get("date_of_joining"))
        if not doj or doj > iso_to:
            continue
        inactive = to_iso(e.get("inactive_date"))
        if inactive and inactive < iso_from:
            continue
        e["_doj_iso"] = doj
        e["_inactive_iso"] = inactive
        out.append(e)
    out.sort(key=lambda x: (x.get("full_name") or "").lower())
    return out


def is_active_on(emp, iso_day):
    if emp["_doj_iso"] > iso_day:
        return False
    if emp["_inactive_iso"] and iso_day > emp["_inactive_iso"]:
        return False
    return True


async def get_attendance_map(db, employee_ids, iso_from, iso_to):
    """Map (employee_id, iso_date) -> {punch_in, punch_out, total_hours} from attendance.

    Attendance `date` is stored as 'DD-MM-YYYY'; we normalise to ISO for keys.
    """
    cur = db.attendance.find(
        {"employee_id": {"$in": employee_ids}},
        {"_id": 0, "employee_id": 1, "date": 1, "check_in": 1, "check_out": 1,
         "total_hours": 1, "total_hours_decimal": 1},
    )
    out = {}
    async for a in cur:
        iso = to_iso(a.get("date"))
        if iso and iso_from <= iso <= iso_to:
            out[(a["employee_id"], iso)] = {
                "punch_in": a.get("check_in") or "",
                "punch_out": a.get("check_out") or "",
                "total_hours": att_total_hours_to_duration(a),
            }
    return out


def daterange_iso(iso_from, iso_to):
    d0 = datetime.strptime(iso_from, "%Y-%m-%d").date()
    d1 = datetime.strptime(iso_to, "%Y-%m-%d").date()
    days = []
    cur = d0
    while cur <= d1:
        days.append(cur.strftime("%Y-%m-%d"))
        cur = date.fromordinal(cur.toordinal() + 1)
    return days


# ----------------------------------------------------------------------------
# Template generation (streaming xlsx)
# ----------------------------------------------------------------------------
_HDR_FONT = Font(bold=True, size=11, color="1F2937")
_SYS_FILL = PatternFill("solid", fgColor="DCE6F1")        # attendance/system (do not edit)
_EDIT_FILL = PatternFill("solid", fgColor="FFF2CC")       # editable scalar fields
_BREAK_FILL = PatternFill("solid", fgColor="E2EFDA")      # break group columns
_SUB_FILL = PatternFill("solid", fgColor="F2F2F2")
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_THIN = Side(style="thin", color="D0D0D0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _hcell(ws, value, fill):
    c = WriteOnlyCell(ws, value=value)
    c.font = _HDR_FONT
    c.fill = fill
    c.alignment = _CENTER
    c.border = _BORDER
    return c


def build_template_workbook(prefill_rows, break_labels=None):
    """Return BytesIO of a styled .xlsx (write_only/streaming) with 2-row header.

    `prefill_rows`: list of dicts with keys name,email,team,date_display,
    punch_in,punch_out,total_hours (system columns prefilled).
    """
    break_labels = break_labels or list(DEFAULT_BREAK_LABELS)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Vigilance")

    total_cols = N_FIXED + len(break_labels) * len(BREAK_SUBS)
    # Column widths (set before append in write_only)
    from openpyxl.utils import get_column_letter
    widths = [22, 28, 16, 14, 13, 13, 13, 14, 14, 18, 16] + [12] * (total_cols - N_FIXED)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "E3"   # lock 2 header rows + Name/Email/Team/Date columns

    # Header row 1
    row1 = []
    for idx, label in enumerate(FIXED_COLS):
        fill = _SYS_FILL if label in ATT_SYSTEM_COLS else _EDIT_FILL
        row1.append(_hcell(ws, label, fill))
    for label in break_labels:
        row1.append(_hcell(ws, label, _BREAK_FILL))
        row1.append(_hcell(ws, None, _BREAK_FILL))
        row1.append(_hcell(ws, None, _BREAK_FILL))
    ws.append(row1)

    # Header row 2 (sub headers)
    row2 = []
    for label in FIXED_COLS:
        fill = _SYS_FILL if label in ATT_SYSTEM_COLS else _EDIT_FILL
        row2.append(_hcell(ws, None, fill))
    for _ in break_labels:
        for sub in BREAK_SUBS:
            row2.append(_hcell(ws, sub, _SUB_FILL))
    ws.append(row2)

    # Data rows — system columns prefilled as plain strings (stored as text cells)
    n_break_cells = len(break_labels) * len(BREAK_SUBS)
    for r in prefill_rows:
        values = [
            r.get("name", ""), r.get("email", ""), r.get("team", ""),
            r.get("date_display", ""), r.get("punch_in", ""), r.get("punch_out", ""),
            r.get("total_hours", ""),
            "", "", "", "",                      # System Login/Logout, Research, Break Hours (blank, editable)
        ] + [""] * n_break_cells
        ws.append(values)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ----------------------------------------------------------------------------
# Upload parsing (dynamic break detection + strict validation)
# ----------------------------------------------------------------------------
def _norm_header(v):
    return re.sub(r"\s+", " ", str(v).strip()).lower() if v is not None else ""


def parse_upload(file_bytes, employees_by_email, uploaded_by):
    """Parse an uploaded .xlsx. Returns (entries, errors).

    `employees_by_email`: {lower_email: employee_dict}
    `uploaded_by`: {'employee_id','name'}
    All-or-nothing: caller must reject the whole upload if errors is non-empty.
    """
    errors = []
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception:
        return [], [{"row": 0, "message": "File is not a valid .xlsx workbook."}]
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return [], [{"row": 0, "message": "Template is empty or missing header rows."}]
    header1 = list(rows[0])
    header2 = list(rows[1])

    # Validate fixed/system columns (exact order, names)
    for i, expected in enumerate(FIXED_COLS):
        actual = _norm_header(header1[i]) if i < len(header1) else ""
        if actual != expected.lower():
            return [], [{"row": 1, "message": f"Mandatory column #{i + 1} must be '{expected}' (found '{header1[i] if i < len(header1) else ''}'). Do not rename/reorder system columns."}]

    # Detect break groups dynamically (columns after the 11 fixed)
    groups = []   # [{label, from_idx, to_idx, total_idx}]
    i = N_FIXED
    current = None
    while i < len(header1):
        label = header1[i]
        sub = _norm_header(header2[i]) if i < len(header2) else ""
        if label not in (None, ""):
            current = {"label": str(label).strip(), "From": None, "To": None, "Total": None}
            groups.append(current)
        if current is not None and sub in ("from", "to", "total"):
            current[sub.capitalize()] = i
        i += 1
    # Keep only well-formed groups (must have at least From/To/Total mapping)
    groups = [g for g in groups if g["From"] is not None or g["To"] is not None or g["Total"] is not None]

    IDX = {name: idx for idx, name in enumerate(FIXED_COLS)}
    entries = []
    seen = set()
    for rnum in range(2, len(rows)):          # data rows (0-based row index 2 == excel row 3)
        excel_row = rnum + 1
        row = list(rows[rnum])

        def cell(name):
            idx = IDX[name]
            return row[idx] if idx < len(row) else None

        email_raw = cell("Email-id")
        date_raw = cell("Date")
        # Editable scalars
        sys_login_raw = cell("System Login")
        sys_logout_raw = cell("System Logout")
        research_raw = cell("Total Research Hours")
        break_hours_raw = cell("Total Break Hours")

        # Gather break cell values
        break_vals = []
        for g in groups:
            f = row[g["From"]] if g["From"] is not None and g["From"] < len(row) else None
            t = row[g["To"]] if g["To"] is not None and g["To"] < len(row) else None
            tot = row[g["Total"]] if g["Total"] is not None and g["Total"] < len(row) else None
            break_vals.append((g["label"], f, t, tot))

        # Skip fully-empty rows (employee row left blank by vigilance user)
        has_any_editable = any(str(x).strip() for x in [sys_login_raw, sys_logout_raw, research_raw, break_hours_raw] if x is not None)
        has_any_break = any(str(v).strip() for (_, f, t, tot) in break_vals for v in (f, t, tot) if v is not None)
        if not has_any_editable and not has_any_break:
            continue

        # Resolve employee (mandatory)
        if email_raw is None or str(email_raw).strip() == "":
            errors.append({"row": excel_row, "message": "Email-id is required to identify the employee."})
            continue
        emp = employees_by_email.get(str(email_raw).strip().lower())
        if not emp:
            errors.append({"row": excel_row, "message": f"No employee found for Email-id '{email_raw}'."})
            continue

        iso = parse_display_date_strict(date_raw)
        if not iso:
            errors.append({"row": excel_row, "message": f"Invalid Date '{date_raw}'. Use DD-MMM-YYYY (e.g. 06-Jun-2026)."})
            continue

        key = (emp["id"], iso, uploaded_by["employee_id"])
        if key in seen:
            errors.append({"row": excel_row, "message": f"Duplicate row for {emp.get('full_name')} on {iso_to_display(iso)} within the file."})
            continue

        # Validate editable clock/duration fields
        ok, sys_login = norm_clock(sys_login_raw)
        if not ok:
            errors.append({"row": excel_row, "message": f"System Login '{sys_login_raw}' must be HH:MM AM/PM (e.g. 09:45 AM)."})
            continue
        ok, sys_logout = norm_clock(sys_logout_raw)
        if not ok:
            errors.append({"row": excel_row, "message": f"System Logout '{sys_logout_raw}' must be HH:MM AM/PM."})
            continue
        ok, research = norm_duration(research_raw)
        if not ok:
            errors.append({"row": excel_row, "message": f"Total Research Hours '{research_raw}' must be a duration HH:MM (e.g. 10:00)."})
            continue
        ok, break_hours = norm_duration(break_hours_raw)
        if not ok:
            errors.append({"row": excel_row, "message": f"Total Break Hours '{break_hours_raw}' must be a duration HH:MM."})
            continue

        breaks = []
        row_has_break_error = False
        for (label, f, t, tot) in break_vals:
            okf, nf = norm_clock(f)
            okt, nt = norm_clock(t)
            okv, nv = norm_duration(tot)
            if not okf:
                errors.append({"row": excel_row, "message": f"'{label} From' = '{f}' must be HH:MM AM/PM."})
                row_has_break_error = True
            if not okt:
                errors.append({"row": excel_row, "message": f"'{label} To' = '{t}' must be HH:MM AM/PM."})
                row_has_break_error = True
            if not okv:
                errors.append({"row": excel_row, "message": f"'{label} Total' = '{tot}' must be a duration HH:MM."})
                row_has_break_error = True
            if okf and okt and okv and (nf or nt or nv):
                breaks.append({"label": label, "from": nf, "to": nt, "total": nv})
        if row_has_break_error:
            continue

        seen.add(key)
        entries.append({
            "target_employee_id": emp["id"],
            "target_employee_name": emp.get("full_name"),
            "target_email": emp.get("official_email"),
            "target_team": emp.get("team"),
            "target_department": emp.get("department"),
            "target_designation": emp.get("designation"),
            "date": iso,
            "system_login": sys_login,
            "system_logout": sys_logout,
            "total_research_hours": research,
            "total_break_hours": break_hours,
            "breaks": breaks,
        })

    return entries, errors


# ----------------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def upsert_entry(db, entry, uploaded_by):
    """Upsert by (target_employee_id, date, uploaded_by_employee_id)."""
    key = {
        "target_employee_id": entry["target_employee_id"],
        "date": entry["date"],
        "uploaded_by_employee_id": uploaded_by["employee_id"],
    }
    set_fields = {
        **entry,
        "uploaded_by_employee_id": uploaded_by["employee_id"],
        "uploaded_by_name": uploaded_by["name"],
        "updated_at": now_iso(),
    }
    res = await db.vigilance_entries.update_one(
        key,
        {"$set": set_fields, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now_iso()}},
        upsert=True,
    )
    return res


def _clean(doc):
    doc.pop("_id", None)
    return doc


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------
def _build_filter(filters):
    q = {}
    if filters.get("from_iso") and filters.get("to_iso"):
        q["date"] = {"$gte": filters["from_iso"], "$lte": filters["to_iso"]}
    elif filters.get("from_iso"):
        q["date"] = {"$gte": filters["from_iso"]}
    elif filters.get("to_iso"):
        q["date"] = {"$lte": filters["to_iso"]}
    if filters.get("employee_name"):
        q["target_employee_name"] = {"$regex": re.escape(filters["employee_name"]), "$options": "i"}
    if filters.get("department") and filters["department"] != "All":
        q["target_department"] = filters["department"]
    if filters.get("designation") and filters["designation"] != "All":
        q["target_designation"] = filters["designation"]
    if filters.get("team") and filters["team"] != "All":
        q["target_team"] = filters["team"]
    return q


async def list_own_rows(db, uploaded_by_employee_id, filters):
    """Vigilance user view: only own entries, each enriched with live attendance."""
    q = _build_filter(filters)
    q["uploaded_by_employee_id"] = uploaded_by_employee_id
    docs = [_clean(d) async for d in db.vigilance_entries.find(q).sort([("date", 1), ("target_employee_name", 1)])]
    emp_ids = list({d["target_employee_id"] for d in docs})
    att = await get_attendance_map(db, emp_ids, filters.get("from_iso") or "0000-01-01", filters.get("to_iso") or "9999-12-31") if emp_ids else {}
    break_labels = []
    for d in docs:
        a = att.get((d["target_employee_id"], d["date"]), {})
        d["punch_in"] = a.get("punch_in", "")
        d["punch_out"] = a.get("punch_out", "")
        d["total_hours"] = a.get("total_hours", "")
        d["date_display"] = iso_to_display(d["date"])
        for b in d.get("breaks", []):
            if b["label"] not in break_labels:
                break_labels.append(b["label"])
    return {"rows": docs, "break_labels": _ordered_break_labels(break_labels)}


async def list_admin_merged(db, filters):
    """Admin view: one row per (employee, date) merging all vigilance uploaders."""
    q = _build_filter(filters)
    docs = [_clean(d) async for d in db.vigilance_entries.find(q).sort([("date", 1), ("target_employee_name", 1)])]
    emp_ids = list({d["target_employee_id"] for d in docs})
    att = await get_attendance_map(db, emp_ids, filters.get("from_iso") or "0000-01-01", filters.get("to_iso") or "9999-12-31") if emp_ids else {}

    merged = {}
    uploaders = {}
    break_labels = []
    for d in docs:
        gkey = (d["target_employee_id"], d["date"])
        if gkey not in merged:
            a = att.get(gkey, {})
            merged[gkey] = {
                "key": f"{d['target_employee_id']}__{d['date']}",
                "target_employee_id": d["target_employee_id"],
                "target_employee_name": d.get("target_employee_name"),
                "target_email": d.get("target_email"),
                "target_team": d.get("target_team"),
                "target_department": d.get("target_department"),
                "target_designation": d.get("target_designation"),
                "date": d["date"],
                "date_display": iso_to_display(d["date"]),
                "punch_in": a.get("punch_in", ""),
                "punch_out": a.get("punch_out", ""),
                "total_hours": a.get("total_hours", ""),
                "submissions": [],
            }
        merged[gkey]["submissions"].append({
            "id": d["id"],
            "uploaded_by_employee_id": d["uploaded_by_employee_id"],
            "uploaded_by_name": d.get("uploaded_by_name"),
            "system_login": d.get("system_login", ""),
            "system_logout": d.get("system_logout", ""),
            "total_research_hours": d.get("total_research_hours", ""),
            "total_break_hours": d.get("total_break_hours", ""),
            "breaks": d.get("breaks", []),
        })
        uploaders[d["uploaded_by_employee_id"]] = d.get("uploaded_by_name")
        for b in d.get("breaks", []):
            if b["label"] not in break_labels:
                break_labels.append(b["label"])

    rows = sorted(merged.values(), key=lambda r: (r["date"], (r["target_employee_name"] or "").lower()))
    uploader_list = [{"employee_id": k, "name": v} for k, v in uploaders.items()]
    uploader_list.sort(key=lambda u: (u["name"] or "").lower())
    return {
        "rows": rows,
        "uploaders": uploader_list,
        "break_labels": _ordered_break_labels(break_labels),
    }


def _ordered_break_labels(labels):
    """Default breaks first (in canonical order), then any dynamic ones sorted."""
    ordered = [lbl for lbl in DEFAULT_BREAK_LABELS if lbl in labels]
    extras = sorted([lbl for lbl in labels if lbl not in DEFAULT_BREAK_LABELS])
    return ordered + extras


async def attendance_integration_map(db, employee_ids, iso_from, iso_to):
    """For admin Attendance module: (emp_id,iso_date) -> [{uploaded_by_name, research, break}].

    Real-time read of vigilance_entries (no cache). Frontend-only consumer.
    """
    q = {"date": {"$gte": iso_from, "$lte": iso_to}}
    if employee_ids:
        q["target_employee_id"] = {"$in": employee_ids}
    out = {}
    async for d in db.vigilance_entries.find(q, {"_id": 0}):
        k = f"{d['target_employee_id']}__{d['date']}"
        out.setdefault(k, []).append({
            "uploaded_by_name": d.get("uploaded_by_name"),
            "total_research_hours": d.get("total_research_hours", ""),
            "total_break_hours": d.get("total_break_hours", ""),
        })
    return out


# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------
def build_export_workbook(rows, break_labels, *, admin_mode, clock_24h=False):
    """Build a filtered-results export. Admin mode flattens per-uploader columns.

    clock_24h: when True (Vigilance-user download), editable clock fields
    (System Login/Logout + break From/To) are rendered in 24-hour 'HH:MM'.
    Punch-In/Out (attendance-derived) ALWAYS stay 12-hour; durations stay HH:MM.
    """
    fc = (lambda v: to_24h(v)) if clock_24h else (lambda v: v or "")
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Vigilance Report")
    from openpyxl.utils import get_column_letter

    if admin_mode:
        # Collect uploader names across rows for stable columns
        uploaders = []
        for r in rows:
            for s in r.get("submissions", []):
                if s.get("uploaded_by_name") not in uploaders:
                    uploaders.append(s.get("uploaded_by_name"))
        base = ["Name", "Email-id", "Team", "Department", "Date", "Punch-In", "Punch-Out", "Total Hours"]
        header1 = list(base)
        header2 = [""] * len(base)
        per_uploader_fields = ["System Login", "System Logout", "Total Research Hours", "Total Break Hours"]
        for up in uploaders:
            for f in per_uploader_fields:
                header1.append(f"{f} ({up})")
                header2.append("")
            for bl in break_labels:
                for sub in BREAK_SUBS:
                    header1.append(f"{bl} {sub} ({up})")
                    header2.append("")
        ws.append([_hcell(ws, h, _SYS_FILL) for h in header1])
        for r in rows:
            sub_by_up = {s.get("uploaded_by_name"): s for s in r.get("submissions", [])}
            vals = [
                r.get("target_employee_name", ""), r.get("target_email", ""),
                r.get("target_team", ""), r.get("target_department", ""),
                r.get("date_display", ""), r.get("punch_in", ""),
                r.get("punch_out", ""), r.get("total_hours", ""),
            ]
            for up in uploaders:
                s = sub_by_up.get(up, {})
                vals += [s.get("system_login", ""), s.get("system_logout", ""),
                         s.get("total_research_hours", ""), s.get("total_break_hours", "")]
                bmap = {b["label"]: b for b in s.get("breaks", [])}
                for bl in break_labels:
                    b = bmap.get(bl, {})
                    vals += [b.get("from", ""), b.get("to", ""), b.get("total", "")]
            ws.append(vals)
    else:
        base = ["Name", "Email-id", "Team", "Date", "Punch-In", "Punch-Out", "Total Hours",
                "System Login", "System Logout", "Total Research Hours", "Total Break Hours"]
        header1 = list(base)
        for bl in break_labels:
            for sub in BREAK_SUBS:
                header1.append(f"{bl} {sub}")
        ws.append([_hcell(ws, h, _SYS_FILL) for h in header1])
        for r in rows:
            vals = [
                r.get("target_employee_name", ""), r.get("target_email", ""),
                r.get("target_team", ""), r.get("date_display", ""),
                r.get("punch_in", ""), r.get("punch_out", ""), r.get("total_hours", ""),
                fc(r.get("system_login", "")), fc(r.get("system_logout", "")),
                r.get("total_research_hours", ""), r.get("total_break_hours", ""),
            ]
            bmap = {b["label"]: b for b in r.get("breaks", [])}
            for bl in break_labels:
                b = bmap.get(bl, {})
                vals += [fc(b.get("from", "")), fc(b.get("to", "")), b.get("total", "")]
            ws.append(vals)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
