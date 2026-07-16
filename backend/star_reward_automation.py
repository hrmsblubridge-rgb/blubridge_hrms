"""
Star Reward Automation for BluBridge Research Unit.

Implements the policy defined in "ResearchUnit- Star System" doc:
  §3  – Leave Notification Rules
  §4  – Enforcement & Automation Logic
  §5  – Zero Uninformed Leave Policy
  §6  – Star & Attendance Credit System
  §10 – Unsafe Flag Integration

Only fully data-driven rules are automated here. Rules that need human
judgement (Innovation, Research Consistency quality, Learning Module
completion, Voluntary Sunday work, custom Recognition Framework awards)
remain manual — HR keeps awarding them via the existing UI. Manual awards
are persisted with `source: 'manual'` and are NEVER touched by re-runs of
the automation.

Auto awards are persisted with `source: 'auto'`. When HR re-runs the
computation for the same employee + range, previous auto rows in that
range are deleted first, then re-inserted. Employee total is then
recomputed as SUM of every non-deleted reward — the source of truth.
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from collections import defaultdict
import uuid


# ---------------------------------------------------------------------------
# Policy constants — mirrors the doc line-by-line so anyone can audit.
# ---------------------------------------------------------------------------

RULE_CATALOG = {
    # POSITIVE
    "monthly_full_attendance":   {"stars":  2, "category": "Attendance",           "policy_ref": "§6", "label": "Full monthly attendance (no absences)"},
    "weekly_research_excellence":{"stars":  1, "category": "Research Excellence",  "policy_ref": "§6", "label": "10+ hrs daily research average for the week"},
    # NEGATIVE
    "excess_absences":           {"stars": -4, "category": "Unsafe – Commitment",  "policy_ref": "§4",  "label": "More than 4 absences in a month"},
    "excess_emergency":          {"stars": -3, "category": "Unsafe – Irregularity","policy_ref": "§4/§10", "label": "More than 2 emergency leaves in a month"},
    "late_sick_notification":    {"stars": -1, "category": "Compliance",           "policy_ref": "§3/§4", "label": "Sick leave notified after 07:00 AM"},
    "uninformed_absence":        {"stars": -2, "category": "Unsafe – Commitment",  "policy_ref": "§5",  "label": "Uninformed absence (no approved leave)"},
    "engagement_shortfall":      {"stars": -2, "category": "Unsafe – Engagement",  "policy_ref": "§10", "label": "3 consecutive days below 11 hrs"},
    "commitment_shortfall":      {"stars": -3, "category": "Unsafe – Commitment",  "policy_ref": "§10", "label": "3 consecutive days below 9.5 hrs"},
}

RESEARCH_MIN_HOURS = 9.5          # §9 minimum active research
ENGAGEMENT_MIN_HOURS = 11.0       # §9 total working structure
EXCELLENCE_HOURS = 10.0           # §6 weekly bonus threshold
MAX_ABSENCES_MONTH = 4            # §4 threshold
MAX_EMERGENCY_MONTH = 2           # §3/§10 threshold
CONSECUTIVE_DAYS_TRIGGER = 3      # §10 sliding window

# Leave-type synonyms (case-insensitive substring match).
SICK_TYPES = {"sick", "sick leave", "medical"}
EMERGENCY_TYPES = {"emergency", "emergency leave"}
ABSENCE_STATUSES = {"absent", "no show", "no-show"}
PRESENT_STATUSES = {"present", "late", "on time", "on-time", "regularized", "regularised"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_str(s: str) -> Optional[date]:
    """Accept both DD-MM-YYYY (attendance format) and YYYY-MM-DD (leaves format)."""
    if not s: return None
    s = str(s).strip()[:10]
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: continue
    return None


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _iso_week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _leave_type_matches(leave_type: str, needles: set) -> bool:
    if not leave_type: return False
    lt = str(leave_type).lower()
    return any(n in lt for n in needles)


def _hours_of(rec: dict) -> float:
    v = rec.get("total_hours_decimal")
    if isinstance(v, (int, float)): return float(v)
    # Fallback: parse "9h 30m"
    s = str(rec.get("total_hours") or "").strip()
    if not s: return 0.0
    try:
        h, _, rest = s.partition("h")
        h = int((h or "0").strip())
        m = int((rest.replace("m", "").strip() or "0"))
        return round(h + m / 60.0, 2)
    except (ValueError, TypeError):
        return 0.0


def _classify(rec: dict) -> str:
    """Coarse-grained day classification: present / absent / unknown."""
    s = str(rec.get("status") or "").lower()
    if s in ABSENCE_STATUSES: return "absent"
    if s in PRESENT_STATUSES: return "present"
    # Heuristic — if there's a check_in, they showed up
    if rec.get("check_in") or rec.get("check_in_24h"): return "present"
    return "unknown"


# ---------------------------------------------------------------------------
# Compute engine
# ---------------------------------------------------------------------------

async def compute_auto_stars(db, employee_id: str, start_date: str, end_date: str,
                             att_docs_override=None, leaves_docs_override=None) -> dict:
    """Build the star-reward breakdown for an employee over [start_date, end_date].

    All dates are YYYY-MM-DD. Read-only — does NOT mutate the DB.

    Optional overrides let a bulk caller pre-fetch attendance & leaves for the
    entire department in one shot to avoid N round-trips.
    """
    sd = _parse_date_str(start_date)
    ed = _parse_date_str(end_date)
    if not sd or not ed or ed < sd:
        return {"error": "Invalid date range", "total_stars": 0, "breakdown": [], "counts": {}}

    if att_docs_override is not None:
        att_docs = att_docs_override
    else:
        att_docs = await db.attendance.find(
            {"employee_id": employee_id}, {"_id": 0}
        ).to_list(20000)
    att_in_range = []
    for a in att_docs:
        d = _parse_date_str(a.get("date"))
        if d and sd <= d <= ed:
            a["_date"] = d
            att_in_range.append(a)
    att_in_range.sort(key=lambda x: x["_date"])

    # Pull approved leaves that overlap the range.
    if leaves_docs_override is not None:
        leaves_docs = leaves_docs_override
    else:
        leaves_docs = await db.leaves.find(
            {"employee_id": employee_id, "status": {"$in": ["approved", "Approved"]}},
            {"_id": 0}
        ).to_list(2000)
    approved_leave_dates = set()  # dates covered by any approved leave
    emergency_leaves_by_month = defaultdict(list)   # month → list of leave docs
    late_sick_leaves = []          # sick leaves notified after 07:00 AM
    for lv in leaves_docs:
        lsd = _parse_date_str(lv.get("start_date"))
        led = _parse_date_str(lv.get("end_date")) or lsd
        if not lsd: continue
        # Enumerate covered dates
        cur = lsd
        while cur <= led:
            if sd <= cur <= ed:
                approved_leave_dates.add(cur)
            cur += timedelta(days=1)
        # Emergency count per month (only within range)
        if _leave_type_matches(lv.get("leave_type"), EMERGENCY_TYPES) and lsd and sd <= lsd <= ed:
            emergency_leaves_by_month[_month_key(lsd)].append(lv)
        # Sick — check notification time
        if _leave_type_matches(lv.get("leave_type"), SICK_TYPES) and lsd and sd <= lsd <= ed:
            created = lv.get("created_at") or (lv.get("extra_data") or {}).get("applied_at")
            try:
                if isinstance(created, str):
                    cd = datetime.fromisoformat(created.replace("Z", "+00:00")) if "T" in created else None
                else:
                    cd = created
                # Only apply penalty if application was submitted ON the leave start date and after 07:00
                if cd and cd.date() == lsd and cd.hour >= 7:
                    late_sick_leaves.append(lv)
            except (ValueError, TypeError, AttributeError):
                pass

    breakdown: List[dict] = []
    counts: Dict[str, int] = defaultdict(int)

    def _add(rule_key: str, ref_date: date, note: str = ""):
        r = RULE_CATALOG[rule_key]
        breakdown.append({
            "id": str(uuid.uuid4()),
            "rule": rule_key,
            "date": ref_date.isoformat(),
            "month": _month_key(ref_date),
            "category": r["category"],
            "event": r["label"],
            "stars": r["stars"],
            "policy_ref": r["policy_ref"],
            "remarks": note,
        })
        counts[rule_key] += 1

    # ---- Per-month rules ------------------------------------------------
    # Group attendance by month
    by_month = defaultdict(list)
    for a in att_in_range:
        by_month[_month_key(a["_date"])].append(a)

    for mkey, recs in sorted(by_month.items()):
        month_start = datetime.strptime(mkey + "-01", "%Y-%m-%d").date()
        # Count classifications
        absents = sum(1 for r in recs if _classify(r) == "absent")
        presents = sum(1 for r in recs if _classify(r) == "present")
        total_recorded = presents + absents

        # 26/26 attendance → +2 (only for FULL months present; guardrail: at
        # least 20 records to avoid awarding partial months)
        if total_recorded >= 20 and absents == 0:
            _add("monthly_full_attendance", month_start, f"{presents} present days in {mkey}")

        # >4 absences → -4
        if absents > MAX_ABSENCES_MONTH:
            _add("excess_absences", month_start, f"{absents} absences in {mkey}")

        # >2 emergency leaves → -3
        em_count = len(emergency_leaves_by_month.get(mkey, []))
        if em_count > MAX_EMERGENCY_MONTH:
            _add("excess_emergency", month_start, f"{em_count} emergency leaves in {mkey}")

    # ---- Per-instance late-sick penalty --------------------------------
    for lv in late_sick_leaves:
        lsd = _parse_date_str(lv.get("start_date"))
        if lsd: _add("late_sick_notification", lsd, f"Sick leave notified after 07:00 AM on {lsd}")

    # ---- Uninformed absence: Absent + no approved leave ---------------
    for a in att_in_range:
        if _classify(a) == "absent" and a["_date"] not in approved_leave_dates:
            _add("uninformed_absence", a["_date"], "Absent without approved leave")

    # ---- Consecutive sub-threshold hours (§10) ------------------------
    # Slide over ordered present records; count consecutive-below streaks.
    def _scan(threshold: float, rule_key: str):
        streak: List[dict] = []
        awarded_ranges: List[date] = []
        for a in att_in_range:
            if _classify(a) != "present":
                # Reset on absent/unknown
                if len(streak) >= CONSECUTIVE_DAYS_TRIGGER:
                    _apply_streak(streak, rule_key, awarded_ranges)
                streak = []
                continue
            hrs = _hours_of(a)
            if hrs and hrs < threshold:
                if streak and (a["_date"] - streak[-1]["_date"]).days == 1:
                    streak.append(a)
                else:
                    if len(streak) >= CONSECUTIVE_DAYS_TRIGGER:
                        _apply_streak(streak, rule_key, awarded_ranges)
                    streak = [a]
            else:
                if len(streak) >= CONSECUTIVE_DAYS_TRIGGER:
                    _apply_streak(streak, rule_key, awarded_ranges)
                streak = []
        if len(streak) >= CONSECUTIVE_DAYS_TRIGGER:
            _apply_streak(streak, rule_key, awarded_ranges)

    def _apply_streak(streak, rule_key, awarded_ranges):
        # For every non-overlapping 3-day chunk within the streak, one penalty.
        chunks = len(streak) // CONSECUTIVE_DAYS_TRIGGER
        for i in range(chunks):
            chunk = streak[i*CONSECUTIVE_DAYS_TRIGGER:(i+1)*CONSECUTIVE_DAYS_TRIGGER]
            _add(rule_key, chunk[-1]["_date"], f"{chunk[0]['_date']} → {chunk[-1]['_date']}")

    _scan(ENGAGEMENT_MIN_HOURS, "engagement_shortfall")
    _scan(RESEARCH_MIN_HOURS, "commitment_shortfall")

    # ---- Weekly research excellence (+1) -----------------------------
    by_week = defaultdict(list)
    for a in att_in_range:
        if _classify(a) == "present":
            by_week[_iso_week_key(a["_date"])].append(a)
    for wkey, recs in sorted(by_week.items()):
        if len(recs) < 5:  # Need at least 5 working-day records for a "full" week
            continue
        avg_hours = sum(_hours_of(r) for r in recs) / len(recs)
        if avg_hours >= EXCELLENCE_HOURS:
            week_end = max(r["_date"] for r in recs)
            _add("weekly_research_excellence", week_end,
                 f"Avg {avg_hours:.1f} hrs/day × {len(recs)} days ({wkey})")

    # ---- Sort breakdown chronologically -------------------------------
    breakdown.sort(key=lambda x: (x["date"], x["rule"]))
    total_stars = sum(x["stars"] for x in breakdown)

    return {
        "employee_id": employee_id,
        "range": {"start_date": sd.isoformat(), "end_date": ed.isoformat()},
        "total_stars": total_stars,
        "positive_stars": sum(x["stars"] for x in breakdown if x["stars"] > 0),
        "negative_stars": sum(x["stars"] for x in breakdown if x["stars"] < 0),
        "breakdown": breakdown,
        "counts": dict(counts),
        "meta": {
            "attendance_days_evaluated": len(att_in_range),
            "approved_leave_days_in_range": len(approved_leave_dates),
            "rule_catalog": RULE_CATALOG,
        },
    }


async def apply_auto_stars(db, employee_id: str, start_date: str, end_date: str,
                           awarded_by_id: str,
                           att_docs_override=None, leaves_docs_override=None) -> dict:
    """Persist the auto breakdown. Idempotent for the same range:
      1. Delete existing source='auto' rewards for this employee overlapping the range.
      2. Insert freshly-computed rows.
      3. Recompute employee.stars = SUM of every non-deleted reward.
    """
    result = await compute_auto_stars(db, employee_id, start_date, end_date,
                                       att_docs_override=att_docs_override,
                                       leaves_docs_override=leaves_docs_override)
    if result.get("error"):
        return {"error": result["error"], "applied": 0}

    sd = result["range"]["start_date"]
    ed = result["range"]["end_date"]

    # 1) Remove prior auto rows in the same window (by 'ref_date' field we set on insert).
    del_res = await db.star_rewards.delete_many({
        "employee_id": employee_id,
        "source": "auto",
        "ref_date": {"$gte": sd, "$lte": ed},
    })

    # 2) Insert the new breakdown as individual reward rows.
    now_iso = datetime.now().isoformat()
    docs_to_insert = []
    for item in result["breakdown"]:
        docs_to_insert.append({
            "id": item["id"],
            "employee_id": employee_id,
            "stars": item["stars"],
            "reason": f"[Auto · {item['policy_ref']}] {item['event']} — {item['remarks']}",
            "type": "unsafe" if item["stars"] < 0 else "performance",
            "awarded_by": awarded_by_id,
            "month": item["month"],
            "created_at": now_iso,
            "source": "auto",
            "ref_date": item["date"],
            "rule": item["rule"],
            "category": item["category"],
        })
    if docs_to_insert:
        await db.star_rewards.insert_many(docs_to_insert)

    # 3) Recompute cumulative totals from source-of-truth.
    agg = await db.star_rewards.aggregate([
        {"$match": {"employee_id": employee_id, "is_deleted": {"$ne": True}}},
        {"$group": {"_id": None,
                    "stars": {"$sum": "$stars"},
                    "unsafe": {"$sum": {"$cond": [{"$eq": ["$type", "unsafe"]}, 1, 0]}}}}
    ]).to_list(1)
    stars_total = agg[0]["stars"] if agg else 0
    unsafe_total = agg[0]["unsafe"] if agg else 0
    await db.employees.update_one(
        {"id": employee_id},
        {"$set": {
            "stars": stars_total,
            "unsafe_count": unsafe_total,
            "last_auto_star_computed_at": now_iso,
            "last_auto_star_range": {"start_date": sd, "end_date": ed},
        }},
    )

    return {
        "applied": len(docs_to_insert),
        "replaced": del_res.deleted_count,
        "total_stars": stars_total,
        "unsafe_count": unsafe_total,
        "range": result["range"],
        "breakdown": result["breakdown"],
    }
