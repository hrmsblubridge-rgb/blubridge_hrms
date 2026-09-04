"""BRSF — BluBridge Research Star Framework (Phase 1: backend engine).

Scope: Research Unit + Full-time (non-intern) + CONFIRMED employees only,
eligible from the confirmation MONTH onwards (confirmation-month calculations
start at the confirmation date).

Exactly 14 parent criteria per employee/month, keyed uniquely on
(employee_id, year, month, code) so recalculation is idempotent. Every line
keeps three layers: system_calculated → manual override → final applied, plus
audit history. Automated recalculation NEVER destroys an active override.

Phase 1 automates: P01, P05, P06, N03, N04, N06.
Phase 2 will automate: N01, N02, N05 (they exist now with system value 0).
Manual criteria: P02, P03, P04 (monthly OR weekly entry), N07, N08 (instances).
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import Body, Depends, HTTPException, Request

from server import (
    UserRole,
    api_router,
    calculate_payroll_for_employee,
    db,
    get_current_user,
    get_ist_now,
)
from brsf_validation import (
    limits_for,
    line_violation,
    validate_child_override,
    validate_instance_value,
    validate_monthly_entry,
    validate_override,
    validate_weekly_entries,
)

# Eligible departments — "AI Search" is accepted as the renamed form of the
# same unit so a department rename in the employee master needs no code change.
RESEARCH_DEPARTMENTS = ["Research Unit", "AI Search"]
INTERN_TYPE = "Intern"
MONTH_LABELS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"]
# criteria whose parent value is the aggregate of its child records
CHILD_DRIVEN_CODES = {"P05", "P06", "N01", "N02", "N04", "N05"}

# code, name, sign(+1/-1), type, frequency, cap(absolute)
CRITERIA = [
    ("P01", "Full Attendance", 1, "automated", "monthly", 2),
    ("P02", "Performance", 1, "manual", "weekly", 5),
    ("P03", "Innovation", 1, "manual", "monthly", 3),
    ("P04", "Learning", 1, "manual", "weekly", 5),
    ("P05", "Research Hours Attendance", 1, "automated", "weekly", 5),
    ("P06", "Extra Effort", 1, "automated", "instance", None),
    ("N01", "Invalid Leave Request", -1, "automated", "instance", None),
    ("N02", "Emergency Leave Violation", -1, "automated", "instance", None),
    ("N03", "Frequent Emergencies", -1, "automated", "monthly", 3),
    ("N04", "Short Research Duration", -1, "automated", "weekly", None),
    ("N05", "No Proof / Verification", -1, "automated", "instance", None),
    ("N06", "Frequent Absences", -1, "automated", "monthly", 3),
    ("N07", "No Show / Unreachable", -1, "manual", "instance", None),
    ("N08", "Unsafe Conduct", -1, "manual", "instance", None),
]
CRITERIA_MAP = {c[0]: c for c in CRITERIA}
AUTOMATED_CODES = {c[0] for c in CRITERIA if c[3] == "automated"}
MANUAL_INSTANCE_CODES = {"N07", "N08"}
DEFAULT_INSTANCE_STAR = {"N07": -3, "N08": -4}

# Payroll day codes
FULL_LEAVE_CODES = {"PF", "SF", "EF", "PA", "OH"}
HALF_LEAVE_CODES = {"PH", "SH", "EH", "PP"}
ABSENT_CODES = {"A", "LOP"}
WORKED_HOLIDAY_CODES = {"FD", "HD"}
NON_REQUIRED_CODES = {"WO", "Su", "H", "R", "BLANK", "NA", ""}

RESEARCH_POSITIVE_MIN = 600  # >= 10:00 average → +1
RESEARCH_NEGATIVE_MAX = 570  # < 09:30 average → -1


# --------------------------------------------------------------- helpers
def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _require_star_admin(user: dict):
    """Only the HR admin role may create/edit/override/recalculate stars."""
    if user.get("role") != UserRole.HR:
        raise HTTPException(status_code=403, detail="You are not authorized to manage star rewards.")


def _iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _month_bounds(month: str):
    y, m = int(month[:4]), int(month[5:7])
    start = date(y, m, 1)
    end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    return start, end


def _parse_iso(s) -> Optional[date]:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _dur_to_minutes(v) -> int:
    """'HH:MM' / 'HH:MM:SS' → whole minutes (never decimal-text maths)."""
    if not v:
        return 0
    parts = str(v).split(":")
    try:
        h = int(parts[0]); mi = int(parts[1]) if len(parts) > 1 else 0
        sec = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return 0
    return h * 60 + mi + (1 if sec >= 30 else 0)


def _is_type(leave: dict, needle: str) -> bool:
    return needle in (leave.get("leave_type") or "").lower().replace("-", "").replace(" ", "")


def _applied_at(leave: dict) -> Optional[datetime]:
    """Application timestamp (HRMS local/IST as stored)."""
    try:
        return datetime.fromisoformat(str(leave.get("created_at")))
    except (TypeError, ValueError):
        return None


def _has_proof(leave: dict) -> bool:
    return bool(leave.get("supporting_document_url"))


def _leave_dates(leave: dict) -> list:
    return [leave["_start"] + timedelta(days=i)
            for i in range((leave["_end"] - leave["_start"]).days + 1)]


def _minutes_to_hhmm(mins: float) -> str:
    total = int(round(mins))
    return f"{total // 60:02d}:{total % 60:02d}"


def _week_buckets(start: date, end: date):
    """Monday–Saturday buckets cropped to [start, end]; Sundays excluded."""
    buckets, cur, idx = [], start, 1
    while cur <= end:
        monday = cur - timedelta(days=cur.weekday())
        saturday = monday + timedelta(days=5)
        b_start, b_end = max(cur, monday, start), min(saturday, end)
        days = [b_start + timedelta(days=i) for i in range((b_end - b_start).days + 1)
                if (b_start + timedelta(days=i)).weekday() != 6]
        if days:
            buckets.append({"week": idx, "start": _iso(days[0]), "end": _iso(days[-1]), "days": days})
            idx += 1
        # Always move forward — a Sunday `cur` yields a Saturday in the past,
        # so guard against a non-advancing cursor (infinite loop).
        cur = max(saturday + timedelta(days=1), cur + timedelta(days=1))
    return buckets


async def _month_eligible_employees_raw() -> list:
    """All BRSF-scope employees (any month) — used by range reports."""
    return [e async for e in db.employees.find(
        {"is_deleted": {"$ne": True}, "department": {"$in": RESEARCH_DEPARTMENTS},
         "employment_type": {"$ne": INTERN_TYPE}, "confirmation_date": {"$nin": [None, ""]}},
        {"_id": 0, "id": 1, "full_name": 1, "custom_employee_id": 1, "emp_id": 1,
         "confirmation_date": 1, "employee_status": 1, "designation": 1,
         "team": 1, "date_of_joining": 1, "email": 1, "inactive_date": 1},
    )]


def _month_eligible(e: dict, month: str) -> bool:
    """Month-effective eligibility: confirmation month .. month before inactive month."""
    year, mon = int(month[:4]), int(month[5:7])
    _, m_end = _month_bounds(month)
    conf = _parse_iso(e.get("confirmation_date"))
    if not conf or conf > m_end:
        return False
    inactive = _parse_iso(e.get("inactive_date"))
    if inactive:
        return (inactive.year, inactive.month) > (year, mon)
    return (e.get("employee_status") or "Active") == "Active"


async def eligible_employees(month: str) -> list:
    """Month-effective eligibility — the ONE source of truth for every BRSF path."""
    rows = [e for e in await _month_eligible_employees_raw() if _month_eligible(e, month)]
    rows.sort(key=lambda x: (x.get("full_name") or ""))
    return rows


def _month_is_completed(month: str) -> bool:
    now = get_ist_now()
    return (int(month[:4]), int(month[5:7])) < (now.year, now.month)


def _require_completed_month(month: str):
    """Stars exist only for months that have fully ended."""
    if not _month_is_completed(month):
        label = f"{MONTH_LABELS[int(month[5:7]) - 1]} {month[:4]}"
        raise HTTPException(
            status_code=400,
            detail=f"{label} is not a completed month. BRSF Star Rewards can only be "
                   "generated or edited after the selected month is completed.")


# --------------------------------------------------------------- engine
async def _research_minutes(employee_id: str, start: date, end: date) -> dict:
    """Per-day TOTAL research minutes from the Vigilance module.

    Multiple monitor entries for the same employee/day are de-duplicated by
    taking the highest recorded total (never summed) so a day is not
    double-counted. Break hours are excluded by design — the Vigilance module
    already stores them separately in `total_break_hours`.
    """
    out = {}
    async for v in db.vigilance_entries.find(
        {"target_employee_id": employee_id, "date": {"$gte": _iso(start), "$lte": _iso(end)}},
        {"_id": 0, "date": 1, "total_research_hours": 1},
    ):
        mins = _dur_to_minutes(v.get("total_research_hours"))
        out[v["date"]] = max(out.get(v["date"], 0), mins)
    return out


def calculate_invalid_leave_star(lv: dict) -> dict:
    """THE N01 rule for one leave record — used by Auto Calculate, UI and exports.

    1. Apply the existing HRMS timing rule for leave types that have one.
    2. Only when the application itself is late, the Leave Module's
       `leave_validity` decides: Valid Leave -> 0, Invalid Leave -> -1,
       Not Set -> the timing result.
    """
    applied = _applied_at(lv)
    split = lv.get("leave_split") or "Full Day"
    has_rule = bool(_is_type(lv, "sick") or _is_type(lv, "preplan"))
    validity = (lv.get("leave_validity") or "").strip().lower() or None

    timing_ok, timing_note = True, ""
    if has_rule:
        if not applied:
            timing_ok, timing_note = False, "No HRMS application record"
        elif _is_type(lv, "sick"):
            if split == "Second Half":
                if applied.date() > lv["_start"]:
                    timing_ok, timing_note = False, "Second-half sick leave applied after the leave date"
            else:
                deadline = datetime.combine(lv["_start"], datetime.min.time(),
                                            tzinfo=applied.tzinfo).replace(hour=7)
                if applied > deadline:
                    timing_ok = False
                    timing_note = f"Applied {applied.strftime('%d-%m-%Y %I:%M %p')} — after 07:00 AM deadline"
        else:  # pre-planned: at least 4 days in advance
            days = (lv["_start"] - applied.date()).days
            if days < 4:
                timing_ok = False
                timing_note = f"Applied only {days} day(s) in advance (4 days required)"

    if timing_ok:
        value = 0
        reason = ("Applied within the allowed time." if has_rule
                  else f"No automatic N01 timing rule for {lv.get('leave_type')} leave.")
    elif validity == "valid":
        value, reason = 0, f"Late HRMS application but approved as Valid Leave ({timing_note})."
    elif validity == "invalid":
        value, reason = -1, f"{timing_note} and Leave Validity is Invalid Leave."
    else:
        value, reason = -1, f"{timing_note}; Leave Validity not set."

    return {
        "key": f"leave:{lv['id']}", "leave_id": lv["id"],
        "date": lv["start_date"], "end_date": lv.get("end_date") or lv["start_date"],
        "leave_type": lv.get("leave_type"), "split": split,
        "applied_at": lv.get("created_at"),
        "leave_reason": (lv.get("reason") or "").strip(),
        "approval_remark": (lv.get("lop_remark") or "").strip(),
        "leave_validity": validity,
        "timing_valid": timing_ok, "has_rule": has_rule,
        "applicable": True,        # every leave is individually reviewable
        "reason": reason, "value": value,
    }


async def compute_system_values(employee: dict, month: str) -> dict:
    """Central automated calculation — the single source of truth."""
    m_start, m_end = _month_bounds(month)
    conf = _parse_iso(employee.get("confirmation_date"))
    win_start = max(m_start, conf) if conf else m_start
    if win_start > m_end:
        return {}

    payroll = await calculate_payroll_for_employee(employee["id"], month, employee=employee) or {}
    details = {}
    for d in payroll.get("attendance_details", []):
        dd, mm, yy = d["date"].split("-")
        iso = f"{yy}-{mm}-{dd}"
        if win_start <= _parse_iso(iso) <= m_end:
            details[iso] = d

    res_mins = await _research_minutes(employee["id"], win_start, m_end)
    out = {}

    # ---- P01 Full Attendance (+2 or 0) — ANY leave/absence disqualifies
    breaches = [{"date": iso, "status": d["status"]} for iso, d in sorted(details.items())
                if d["status"] in FULL_LEAVE_CODES | HALF_LEAVE_CODES | ABSENT_CODES]
    out["P01"] = {
        "value": 0 if (breaches or not details) else 2,
        "children": breaches,
        "note": ("No attendance data for this month" if not details else
                 ("Disqualified by leave/absence" if breaches else "All applicable working days attended")),
    }

    # ---- P05 / N04 weekly research averages (minute based)
    pos_children, neg_children, pos_total, neg_total = [], [], 0, 0
    for b in _week_buckets(win_start, m_end):
        eligible = [d for d in b["days"]
                    if details.get(_iso(d)) and details[_iso(d)]["status"] not in
                    (FULL_LEAVE_CODES | HALF_LEAVE_CODES | ABSENT_CODES | NON_REQUIRED_CODES)]
        if not eligible:
            total, avg = 0, 0.0
            pos, neg = 0, 0
        else:
            total = sum(res_mins.get(_iso(d), 0) for d in eligible)
            avg = total / len(eligible)
            pos = 1 if avg >= RESEARCH_POSITIVE_MIN else 0
            neg = -1 if avg < RESEARCH_NEGATIVE_MAX else 0
        capped = pos_total + pos > CRITERIA_MAP["P05"][5]
        row = {"week": b["week"], "start": b["start"], "end": b["end"],
               "key": f"week:{b['start']}",
               "eligible_days": len(eligible), "avg_minutes": round(avg, 2),
               "avg_hhmm": _minutes_to_hhmm(avg),
               "total_minutes": total, "total_hhmm": _minutes_to_hhmm(total)}
        pos_children.append({**row, "value": 0 if capped else pos,
                             "capped": bool(capped and pos)})
        neg_children.append({**row, "value": neg})
        if not capped:
            pos_total += pos
        neg_total += neg
    out["P05"] = {"value": pos_total, "children": pos_children}
    out["N04"] = {"value": neg_total, "children": neg_children}

    # ---- P06 Extra Effort (+1 per worked Sunday / fixed holiday, once per date)
    ee = []
    for iso, d in sorted(details.items()):
        if d["status"] in WORKED_HOLIDAY_CODES and (d.get("is_sunday") or d.get("is_holiday")):
            kind = "Sunday" if d.get("is_sunday") else "Fixed Holiday"
            ee.append({"date": iso, "kind": kind, "key": f"date:{iso}",
                       "work": "Full Day" if d["status"] == "FD" else "Half Day", "value": 1})
    out["P06"] = {"value": len(ee), "children": ee}

    # ---- Leaves overlapping the eligible window (single fetch, reused below)
    leaves = []
    async for lv in db.leaves.find(
        {"employee_id": employee["id"], "status": "approved"},
        {"_id": 0, "id": 1, "leave_type": 1, "leave_split": 1, "start_date": 1, "end_date": 1,
         "created_at": 1, "supporting_document_url": 1, "reason": 1,
         "leave_validity": 1, "lop_remark": 1, "is_lop": 1},
    ):
        s, e = _parse_iso(lv.get("start_date")), _parse_iso(lv.get("end_date") or lv.get("start_date"))
        if s and e and not (e < win_start or s > m_end):
            lv["_start"], lv["_end"] = s, e
            leaves.append(lv)
    leaves.sort(key=lambda x: x["_start"])

    # ---- N03 Frequent Emergencies (duration equivalent > 2.0 in the month → one -3)
    em = []
    for lv in leaves:
        if not _is_type(lv, "emergency"):
            continue
        split = lv.get("leave_split") or "Full Day"
        eq = 0.5 if split in ("First Half", "Second Half") else 1.0
        em.append({"key": f"leave:{lv['id']}", "leave_id": lv["id"], "date": lv["start_date"],
                   "split": split, "equivalent": eq, "value": 0})
    em_equiv = round(sum(c["equivalent"] for c in em), 2)
    out["N03"] = {"value": -3 if em_equiv > 2.0 else 0, "children": em,
                  "note": f"Emergency leave equivalent {em_equiv} day(s) "
                          f"(Full Day 1.0 / Half Day 0.5); up to 2.0 allowed"}

    # ---- N06 Frequent Absences (>= 4.5 absence-equivalent days → one -3)
    equiv, abs_children = 0.0, []
    for iso, d in sorted(details.items()):
        w = 1.0 if d["status"] in FULL_LEAVE_CODES | ABSENT_CODES else (
            0.5 if d["status"] in HALF_LEAVE_CODES else 0)
        if w:
            equiv += w
            abs_children.append({"date": iso, "status": d["status"], "equivalent": w, "value": 0})
    out["N06"] = {"value": -3 if equiv >= 4.5 else 0, "children": abs_children,
                  "note": f"{equiv} absence-equivalent day(s); up to 4.0 allowed"}

    # ---- N01 Invalid Leave Request (-1 max per instance)
    # Every leave record of the month is listed and individually reviewable.
    # Timing rule first; the Leave Module's Leave Validity only matters when the
    # HRMS application itself broke the timing rule.
    n01 = [calculate_invalid_leave_star(lv) for lv in leaves]
    invalid_count = sum(1 for c in n01 if c["value"])
    out["N01"] = {"value": -invalid_count, "children": n01,
                  "note": f"{invalid_count} invalid leave instance(s) "
                          f"of {len(n01)} leave record(s) this month"}

    # ---- N02 Emergency Leave Violation (-2 max per emergency instance)
    n02 = []
    for lv in leaves:
        if not _is_type(lv, "emergency"):
            continue
        applied, split = _applied_at(lv), (lv.get("leave_split") or "Full Day")
        reasons = []
        if not applied:
            reasons.append("No HRMS application/notification record")
        elif split == "Second Half":
            if applied.date() > lv["_start"]:
                reasons.append("Second-half emergency notified after the leave date")
        else:
            deadline = datetime.combine(lv["_start"], datetime.min.time(),
                                        tzinfo=applied.tzinfo).replace(hour=9)
            if applied > deadline:
                reasons.append(f"Notified {applied.strftime('%d-%b %H:%M')} — after 09:00 AM deadline")
        if not (_has_proof(lv) or (lv.get("reason") or "").strip()):
            reasons.append("No proof or justification provided within 24 hours")
        if reasons:
            n02.append({"key": f"leave:{lv['id']}", "leave_id": lv["id"],
                        "date": lv["start_date"], "split": split, "applied_at": lv.get("created_at"),
                        "leave_reason": (lv.get("reason") or "").strip(),
                        "reason": "; ".join(reasons), "value": -2})  # capped at -2 per instance
    out["N02"] = {"value": -2 * len(n02), "children": n02,
                  "note": f"{len(n02)} violating emergency leave instance(s)"}

    # ---- N05 No Proof / Verification (-3 per consecutive leave sequence)
    by_date = {}
    for lv in leaves:
        for d in _leave_dates(lv):
            if win_start <= d <= m_end:
                by_date.setdefault(d, []).append(lv)
    sequences, cur_seq = [], []
    for d in sorted(by_date):
        if cur_seq and (d - cur_seq[-1]).days > 1:
            sequences.append(cur_seq); cur_seq = []
        cur_seq.append(d)
    if cur_seq:
        sequences.append(cur_seq)
    n05 = []
    for seq in sequences:
        if len(seq) < 2:
            continue  # single-day leaves are handled by N01 / N02
        seq_leaves = {lv["id"]: lv for d in seq for lv in by_date[d]}.values()
        proof = any(_has_proof(lv) for lv in seq_leaves)
        n05.append({
            "key": f"seq:{_iso(seq[0])}",
            "start": _iso(seq[0]), "end": _iso(seq[-1]), "days": len(seq),
            "leave_types": sorted({lv.get("leave_type") for lv in seq_leaves}),
            "proof_uploaded": proof,
            "value": 0 if proof else -3,
        })
    out["N05"] = {"value": sum(c["value"] for c in n05), "children": n05,
                  "note": f"{len(n05)} consecutive leave sequence(s) checked "
                          "(one document anywhere in a sequence satisfies it)"}
    return out


def _apply_child_overrides(line: dict) -> Optional[float]:
    """Stamp system/override/final on every automated child; return the aggregate.

    Returns None for criteria whose parent is not child-driven (their children
    are informational only).
    """
    co = line.get("child_overrides") or {}
    total = 0.0
    for ch in line.get("system_children") or []:
        ch["system_value"] = ch.get("value", 0)
        ov = co.get(ch.get("key"))
        if ch.get("applicable") is False:
            ov = None   # records outside the criteria rule can never carry a penalty
        ch["override"] = ov.get("value") if ov else None
        ch["override_note"] = ov.get("note") if ov else None
        ch["override_by"] = ov.get("by") if ov else None
        ch["override_at"] = ov.get("at") if ov else None
        ch["final"] = ch["override"] if ov else ch["system_value"]
        total += ch["final"] or 0
    if line["code"] not in CHILD_DRIVEN_CODES:
        return None
    return round(total, 2)


def _resolve_final(line: dict) -> float:
    code = line["code"]
    _, _, sign, ctype, _, cap = CRITERIA_MAP[code]
    aggregate = _apply_child_overrides(line) if ctype == "automated" else None
    line["child_aggregate"] = aggregate
    if line.get("override_value") is not None:
        val = float(line["override_value"])
    elif ctype == "automated":
        val = float(aggregate if aggregate is not None else (line.get("system_value") or 0))
    elif code in MANUAL_INSTANCE_CODES:
        val = float(sum(i.get("value", 0) for i in line.get("instances", [])))
    elif line.get("entry_mode") == "weekly":
        val = float(sum(w.get("value", 0) for w in line.get("weekly", [])))
    else:
        val = float(line.get("manual_value") or 0)
    # sign + cap guards: positives never negative, negatives never positive
    val = max(val, 0) if sign > 0 else min(val, 0)
    if cap is not None:
        val = min(val, cap) if sign > 0 else max(val, -cap)
    return round(val, 2)


async def sync_lines(employee: dict, month: str) -> list:
    """Idempotent upsert of the 14 parent lines (+ automated children)."""
    system = await compute_system_values(employee, month)
    year, mon = int(month[:4]), int(month[5:7])
    lines = []
    for code, name, sign, ctype, freq, cap in CRITERIA:
        key = {"employee_id": employee["id"], "year": year, "month": mon, "code": code}
        existing = await db.brsf_star_lines.find_one(key, {"_id": 0}) or {}
        doc = {
            **key,
            "id": existing.get("id") or str(uuid.uuid4()),
            "name": name, "sign": sign, "type": ctype, "frequency": freq, "cap": cap,
            "system_value": (system.get(code, {}).get("value") if ctype == "automated" else None),
            "system_children": system.get(code, {}).get("children", []) if ctype == "automated" else [],
            "system_note": system.get(code, {}).get("note"),
            # manual/override layers are preserved as-is
            "entry_mode": existing.get("entry_mode", "monthly"),
            "manual_value": existing.get("manual_value", 0),
            "weekly": existing.get("weekly", []),
            "instances": existing.get("instances", []),
            "child_overrides": existing.get("child_overrides", {}),
            "override_value": existing.get("override_value"),
            "override_reason": existing.get("override_reason"),
            "changed_by": existing.get("changed_by"),
            "changed_at": existing.get("changed_at"),
            "created_at": existing.get("created_at") or _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        doc["final_value"] = _resolve_final(doc)
        doc["status"] = ("Manually Overridden" if doc["override_value"] is not None
                         else ("Auto" if ctype == "automated" else "Manual"))
        await db.brsf_star_lines.update_one(key, {"$set": doc}, upsert=True)
        doc["limits"] = limits_for(doc)
        doc["validation"] = line_violation(doc)
        lines.append(doc)
    return lines


async def _audit(user: dict, line: dict, prev, new, reason: str, action: str,
                 request: Optional[Request] = None):
    await db.brsf_star_audit.insert_one({
        "id": str(uuid.uuid4()),
        "employee_id": line["employee_id"], "year": line["year"], "month": line["month"],
        "code": line["code"], "criteria": line["name"], "action": action,
        "previous_value": prev, "new_value": new,
        "system_calculated_value": line.get("system_value"),
        "reason": reason,
        "updated_by": user.get("id"), "updated_by_name": user.get("full_name") or user.get("username"),
        "updated_at": get_ist_now().isoformat(),
    })


async def _get_line(line_id: str) -> dict:
    line = await db.brsf_star_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Star line not found")
    month = f"{line['year']:04d}-{line['month']:02d}"
    _require_completed_month(month)
    if not any(e["id"] == line["employee_id"] for e in await eligible_employees(month)):
        raise HTTPException(status_code=400,
                            detail="Employee is not eligible for BRSF stars in this month "
                                   "(Research Unit + confirmed full-time employees only).")
    return line


async def _save_line(line: dict) -> dict:
    line.pop("limits", None)
    line.pop("validation", None)
    line["final_value"] = _resolve_final(line)
    line["status"] = ("Manually Overridden" if line.get("override_value") is not None
                      else ("Auto" if line["type"] == "automated" else "Manual"))
    line["updated_at"] = _utc_now_iso()
    await db.brsf_star_lines.update_one({"id": line["id"]}, {"$set": line})
    line["limits"] = limits_for(line)
    line["validation"] = line_violation(line)
    return line


def _totals(lines: list) -> dict:
    pos = round(sum(x["final_value"] for x in lines if x["sign"] > 0), 2)
    neg = round(sum(x["final_value"] for x in lines if x["sign"] < 0), 2)
    return {"positive_total": pos, "negative_total": neg, "net_total": round(pos + neg, 2)}


# --------------------------------------------------------------- routes
@api_router.get("/brsf/eligible-employees")
async def brsf_eligible_employees(month: str, current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    return {"month": month, "employees": await eligible_employees(month)}


@api_router.get("/brsf/summary")
async def brsf_summary(month: str, current_user: dict = Depends(get_current_user)):
    """One row per eligible employee with positive / negative / net stars."""
    _require_star_admin(current_user)
    year, mon = int(month[:4]), int(month[5:7])
    emps = await eligible_employees(month)
    totals = {}
    async for l in db.brsf_star_lines.find(
        {"year": year, "month": mon, "employee_id": {"$in": [e["id"] for e in emps]}},
        {"_id": 0, "employee_id": 1, "sign": 1, "final_value": 1, "override_value": 1},
    ):
        t = totals.setdefault(l["employee_id"], {"positive_total": 0.0, "negative_total": 0.0,
                                                 "lines": 0, "overrides": 0})
        t["lines"] += 1
        t["positive_total" if l["sign"] > 0 else "negative_total"] += (l.get("final_value") or 0)
        if l.get("override_value") is not None:
            t["overrides"] += 1
    rows = []
    for e in emps:
        t = totals.get(e["id"])
        pos = round(t["positive_total"], 2) if t else 0.0
        neg = round(t["negative_total"], 2) if t else 0.0
        rows.append({
            **e,
            "positive_total": pos, "negative_total": neg, "net_total": round(pos + neg, 2),
            "calculated": bool(t), "overrides": t["overrides"] if t else 0,
        })
    return {"month": month, "rows": rows, "month_completed": _month_is_completed(month)}


@api_router.get("/brsf/stars")
async def brsf_stars(employee_id: str, month: str, current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    emp = next((e for e in await eligible_employees(month) if e["id"] == employee_id), None)
    if not emp:
        raise HTTPException(status_code=400,
                            detail="Employee is not eligible for BRSF stars in this month "
                                   "(Research Unit + confirmed employees only).")
    lines = await sync_lines(emp, month)
    m_start, m_end = _month_bounds(month)
    conf = _parse_iso(emp.get("confirmation_date"))
    win_start = max(m_start, conf) if conf else m_start
    weeks = [{"week": b["week"], "start": b["start"], "end": b["end"]}
             for b in _week_buckets(win_start, m_end)]
    return {"employee": emp, "month": month, "lines": lines,
            "weeks": weeks, "totals": _totals(lines),
            "month_completed": _month_is_completed(month)}


@api_router.post("/brsf/recalculate")
async def brsf_recalculate(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    month, employee_id = payload.get("month"), payload.get("employee_id")
    if not month or len(str(month)) < 7:
        raise HTTPException(status_code=400, detail="A month (YYYY-MM) is required for Auto Calculate")
    _require_completed_month(month)
    emps = await eligible_employees(month)
    if employee_id:
        emps = [e for e in emps if e["id"] == employee_id]
        if not emps:
            raise HTTPException(status_code=400,
                                detail="Employee is not eligible for BRSF stars in this month "
                                       "(Research Unit + confirmed full-time employees only).")
    done = 0
    for e in emps:
        await sync_lines(e, month)
        done += 1
    return {"success": True, "recalculated": done,
            "message": f"Auto Calculate complete for {month} — {done} employee(s) processed. "
                       "Manual entries and overrides preserved."}


@api_router.put("/brsf/stars/{line_id}/override")
async def brsf_override(line_id: str, payload: dict = Body(...),
                        current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    value = validate_override(line, payload.get("value"))
    prev = line["final_value"]
    line.update({"override_value": value, "override_reason": payload.get("reason"),
                 "changed_by": current_user.get("full_name") or current_user.get("username"),
                 "changed_at": _utc_now_iso()})
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"], payload.get("reason"), "override")
    return line


@api_router.post("/brsf/stars/{line_id}/reset-override")
async def brsf_reset_override(line_id: str, current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    prev = line["final_value"]
    line.update({"override_value": None, "override_reason": None,
                 "changed_by": current_user.get("full_name") or current_user.get("username"),
                 "changed_at": _utc_now_iso()})
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"], "Reset to system calculated value", "reset")
    return line


@api_router.put("/brsf/stars/{line_id}/child-override")
async def brsf_child_override(line_id: str, payload: dict = Body(...),
                              current_user: dict = Depends(get_current_user)):
    """Override ONE child record (a P05/N04 week, a P06 date, an N01/N02 leave, an N05 sequence).

    The system calculation is never modified — the parent simply re-aggregates.
    """
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    if line["code"] not in CHILD_DRIVEN_CODES:
        raise HTTPException(status_code=400,
                            detail="This criteria does not support child-level overrides")
    key = payload.get("key")
    child = next((c for c in line.get("system_children") or [] if c.get("key") == key), None)
    if not child:
        raise HTTPException(status_code=404, detail="Child record not found for this criteria")
    if child.get("applicable") is False:
        raise HTTPException(status_code=400,
                            detail=f"{child.get('leave_type') or 'This record'} is not covered by "
                                   f"{line['code']} — it cannot carry a penalty here")
    value = validate_child_override(line, payload.get("value"))
    prev = line["final_value"]
    co = dict(line.get("child_overrides") or {})
    co[key] = {"value": value, "note": payload.get("note"),
               "system_value": child.get("value", 0),
               "by": current_user.get("full_name") or current_user.get("username"),
               "at": _utc_now_iso()}
    line["child_overrides"] = co
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"], payload.get("note"),
                 f"child override:{key}")
    return line


@api_router.post("/brsf/stars/{line_id}/child-override/reset")
async def brsf_child_override_reset(line_id: str, payload: dict = Body(...),
                                    current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    key = payload.get("key")
    co = dict(line.get("child_overrides") or {})
    if key not in co:
        raise HTTPException(status_code=404, detail="No override on this child record")
    prev = line["final_value"]
    co.pop(key)
    line["child_overrides"] = co
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"],
                 "Child reset to system calculated value", f"child reset:{key}")
    return line


@api_router.put("/brsf/stars/{line_id}/manual")
async def brsf_manual_entry(line_id: str, payload: dict = Body(...),
                            current_user: dict = Depends(get_current_user)):
    """Monthly OR weekly manual entry for P02 / P03 / P04 (never both)."""
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    if line["type"] != "manual" or line["code"] in MANUAL_INSTANCE_CODES:
        raise HTTPException(status_code=400, detail="This criteria does not accept a manual monthly/weekly value")
    mode = payload.get("entry_mode", line.get("entry_mode") or "monthly")
    if mode not in ("monthly", "weekly"):
        raise HTTPException(status_code=400, detail="entry_mode must be 'monthly' or 'weekly'")
    if line["frequency"] == "monthly" and mode == "weekly":
        raise HTTPException(status_code=400, detail="This criteria supports monthly entry only")
    prev = line["final_value"]
    if mode == "monthly":
        line["manual_value"] = validate_monthly_entry(
            line, payload.get("monthly_value", line.get("manual_value") or 0))
    else:
        line["weekly"] = validate_weekly_entries(line, payload.get("weekly") or [])
    line["entry_mode"] = mode
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"], payload.get("reason"), f"manual:{mode}")
    return line


@api_router.post("/brsf/stars/{line_id}/instances")
async def brsf_add_instance(line_id: str, payload: dict = Body(...),
                            current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    if line["code"] not in MANUAL_INSTANCE_CODES:
        raise HTTPException(status_code=400, detail="This criteria does not accept manual instances")
    value = validate_instance_value(line, payload.get("value"))
    prev = line["final_value"]
    inst = {
        "id": str(uuid.uuid4()),
        "date": payload.get("date"), "time": payload.get("time"),
        "remarks": payload.get("remarks"), "value": value,
        "created_by": current_user.get("full_name") or current_user.get("username"),
        "created_at": _utc_now_iso(),
    }
    line.setdefault("instances", []).append(inst)
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"], payload.get("remarks"), "instance:add")
    return line


@api_router.put("/brsf/stars/{line_id}/instances/{instance_id}")
async def brsf_edit_instance(line_id: str, instance_id: str, payload: dict = Body(...),
                             current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    inst = next((i for i in line.get("instances", []) if i["id"] == instance_id), None)
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    prev = line["final_value"]
    if "value" in payload:
        inst["value"] = validate_instance_value(line, payload["value"])
    for f in ("date", "time", "remarks"):
        if f in payload:
            inst[f] = payload[f]
    inst["updated_by"] = current_user.get("full_name") or current_user.get("username")
    inst["updated_at"] = _utc_now_iso()
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"], payload.get("remarks"), "instance:edit")
    return line


@api_router.delete("/brsf/stars/{line_id}/instances/{instance_id}")
async def brsf_delete_instance(line_id: str, instance_id: str,
                               current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    line = await _get_line(line_id)
    inst = next((i for i in line.get("instances", []) if i["id"] == instance_id), None)
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    prev = line["final_value"]
    line["instances"] = [i for i in line["instances"] if i["id"] != instance_id]
    line = await _save_line(line)
    await _audit(current_user, line, prev, line["final_value"],
                 f"Deleted instance {inst.get('date')} ({inst.get('value')})", "instance:delete")
    return line


@api_router.get("/brsf/audit")
async def brsf_audit(employee_id: str, month: str, current_user: dict = Depends(get_current_user)):
    _require_star_admin(current_user)
    year, mon = int(month[:4]), int(month[5:7])
    rows = await db.brsf_star_audit.find(
        {"employee_id": employee_id, "year": year, "month": mon}, {"_id": 0}
    ).sort("updated_at", -1).to_list(500)
    return {"audit": rows}


async def ensure_brsf_indexes():
    await db.brsf_star_lines.create_index(
        [("employee_id", 1), ("year", 1), ("month", 1), ("code", 1)],
        unique=True, name="brsf_line_unique")
    await db.brsf_star_lines.create_index("id", name="brsf_line_id")
    # import previews are short-lived working data
    await db.brsf_import_batches.create_index("created_dt", name="brsf_batch_ttl",
                                              expireAfterSeconds=7 * 24 * 3600)
