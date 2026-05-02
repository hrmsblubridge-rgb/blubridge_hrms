"""HRMS automated email cron jobs.

Five jobs, all scheduled in IST, all idempotent via email_audit_logs dedup:
  1. adminAttendanceSummaryCron  — 10:30 IST daily   (today)
  2. lateLoginCron               — every 15 min, 10:00-14:00 IST, Mon-Sat
  3. missedPunchCron             — 09:00 IST daily   (yesterday)
  4. earlyOutCron                — 09:15 IST daily   (yesterday)
  5. noLoginCron                 — 09:30 IST daily   (yesterday)

Design principles:
  • AsyncIOScheduler with `max_instances=1, coalesce=True` on every job —
    prevents overlap.
  • Reuses existing attendance/leave data (no duplicate calculation).
  • Every outbound email is routed through `send_hrms_email()` which enforces
    dedup via the email_audit_logs collection + unique index.
  • Failures are logged but never block other jobs or the main API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pytz import timezone as pytz_timezone

from email_service import (
    ADMIN_REPORT_RECIPIENT,
    generate_employee_action_link,
    send_hrms_email,
)
from email_templates import (
    admin_summary_email,
    early_out_email,
    late_login_email,
    missed_punch_email,
    no_login_email,
)

logger = logging.getLogger("hrms.email.jobs")

IST = pytz_timezone("Asia/Kolkata")


def _ist_today() -> str:  # DD-MM-YYYY
    return datetime.now(IST).strftime("%d-%m-%Y")


def _ist_yesterday() -> str:  # DD-MM-YYYY
    return (datetime.now(IST) - timedelta(days=1)).strftime("%d-%m-%Y")


def _dmy_to_ymd(ds: str) -> str:
    try:
        return datetime.strptime(ds, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ds


def _dmy_to_date(ds: str) -> Optional[datetime]:
    try:
        return datetime.strptime(ds, "%d-%m-%Y")
    except ValueError:
        return None


# --- shared employee eligibility filter -------------------------------------
_EXCLUDED_STATUSES = {"Inactive", "Terminated", "Resigned", "Exited"}


async def _active_employees(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.employees.find(
        {
            "is_deleted": {"$ne": True},
            "employee_status": {"$nin": list(_EXCLUDED_STATUSES)},
            "attendance_tracking_enabled": {"$ne": False},
        },
        {"_id": 0},
    ).to_list(5000)


def _emp_email(emp: dict) -> Optional[str]:
    email = emp.get("official_email") or emp.get("email")
    if not email or "@" not in email:
        return None
    return email


# --- leave/holiday/weekoff guards -------------------------------------------
async def _has_leave_on(db: AsyncIOMotorDatabase, emp_id: str, ymd: str) -> bool:
    """Any non-rejected leave overlapping the date."""
    lv = await db.leaves.find_one(
        {
            "employee_id": emp_id,
            "status": {"$in": ["approved", "pending"]},
            "start_date": {"$lte": ymd},
            "end_date": {"$gte": ymd},
        },
        {"_id": 0, "id": 1},
    )
    return lv is not None


async def _has_late_request_on(db: AsyncIOMotorDatabase, emp_id: str, dmy: str) -> bool:
    """late_requests store date in DD-MM-YYYY or YYYY-MM-DD — check both."""
    ymd = _dmy_to_ymd(dmy)
    lr = await db.late_requests.find_one(
        {
            "employee_id": emp_id,
            "status": {"$in": ["approved", "pending"]},
            "date": {"$in": [dmy, ymd]},
        },
        {"_id": 0, "id": 1},
    )
    return lr is not None


async def _has_missed_punch_on(db: AsyncIOMotorDatabase, emp_id: str, dmy: str) -> bool:
    ymd = _dmy_to_ymd(dmy)
    mp = await db.missed_punches.find_one(
        {
            "employee_id": emp_id,
            "status": {"$in": ["approved", "pending"]},
            "date": {"$in": [dmy, ymd]},
        },
        {"_id": 0, "id": 1},
    )
    return mp is not None


async def _has_early_out_request_on(db: AsyncIOMotorDatabase, emp_id: str, dmy: str) -> bool:
    ymd = _dmy_to_ymd(dmy)
    eo = await db.early_out_requests.find_one(
        {
            "employee_id": emp_id,
            "status": {"$in": ["approved", "pending"]},
            "date": {"$in": [dmy, ymd]},
        },
        {"_id": 0, "id": 1},
    )
    return eo is not None


async def _is_non_working_day(db: AsyncIOMotorDatabase, dmy: str) -> bool:
    d = _dmy_to_date(dmy)
    if not d:
        return False
    if d.weekday() == 6:  # Sunday
        return True
    ymd = _dmy_to_ymd(dmy)
    # Holidays collection may store `date` as YYYY-MM-DD or DD-MM-YYYY
    hol = await db.holidays.find_one(
        {"date": {"$in": [dmy, ymd]}, "is_active": {"$ne": False}},
        {"_id": 0, "id": 1},
    )
    return hol is not None


# =========================================================================
# JOB 1: Daily Admin Attendance Summary
# =========================================================================
async def admin_attendance_summary_job(db: AsyncIOMotorDatabase) -> None:
    today_dmy = _ist_today()
    scope_key = f"admin_summary:{today_dmy}"
    logger.info("[cron:admin_summary] start date=%s", today_dmy)

    employees = await _active_employees(db)
    total_employees = len(employees)
    emp_by_id = {e["id"]: e for e in employees}

    attendance = await db.attendance.find({"date": today_dmy}, {"_id": 0}).to_list(5000)

    logged_in = completed = early_out = late_login = half_day = missed_punch = 0
    emp_with_in: set[str] = set()
    delayed: list[tuple[int, dict]] = []

    for a in attendance:
        emp_id = a.get("employee_id")
        if emp_id not in emp_by_id:
            continue
        has_in = bool(a.get("check_in") or a.get("check_in_24h"))
        has_out = bool(a.get("check_out") or a.get("check_out_24h"))
        status = (a.get("status") or "").strip()
        if has_in:
            emp_with_in.add(emp_id)
            if has_out:
                if status in ("Early Out", "Loss of Pay") or a.get("is_lop"):
                    early_out += 1
                else:
                    completed += 1
            else:
                logged_in += 1
        if status == "Half Day":
            half_day += 1
        if has_in != has_out:  # XOR → missed punch
            missed_punch += 1
        # Late detection: status or late_by
        late_by = a.get("late_by_minutes") or 0
        if status == "Late Login" or "late login" in (a.get("lop_reason") or "").lower() or late_by:
            late_login += 1
            if late_by:
                delayed.append((int(late_by), a))

    # Leaves count (unique employees with any leave overlap today)
    ymd = _dmy_to_ymd(today_dmy)
    leave_rows = await db.leaves.find(
        {"status": {"$in": ["approved", "pending"]}, "start_date": {"$lte": ymd}, "end_date": {"$gte": ymd}},
        {"_id": 0, "employee_id": 1},
    ).to_list(5000)
    on_leave_ids = {lv["employee_id"] for lv in leave_rows if lv.get("employee_id") in emp_by_id}
    on_leave = len(on_leave_ids)

    not_logged = len(on_leave_ids | (set(emp_by_id.keys()) - emp_with_in))
    present = completed + logged_in
    attendance_pct = round(100.0 * len(emp_with_in) / total_employees, 1) if total_employees else 0.0

    summary = {
        "total_employees": total_employees,
        "logged_in": logged_in,
        "present": present,
        "not_logged": not_logged,
        "late_login": late_login,
        "early_out": early_out,
        "half_day": half_day,
        "missed_punch": missed_punch,
        "on_leave": on_leave,
        "attendance_pct": attendance_pct,
    }

    # Department-wise
    dept_rows_map: dict[str, dict] = {}
    for emp in employees:
        d = emp.get("department") or "Unknown"
        dept_rows_map.setdefault(d, {"total": 0, "present": 0, "leave": 0, "late": 0})
        dept_rows_map[d]["total"] += 1
    for a in attendance:
        emp = emp_by_id.get(a.get("employee_id"))
        if not emp:
            continue
        d = emp.get("department") or "Unknown"
        if a.get("check_in") or a.get("check_in_24h"):
            dept_rows_map[d]["present"] += 1
        if (a.get("status") or "") == "Late Login" or a.get("late_by_minutes"):
            dept_rows_map[d]["late"] += 1
    for emp_id in on_leave_ids:
        emp = emp_by_id.get(emp_id)
        if emp:
            d = emp.get("department") or "Unknown"
            dept_rows_map.setdefault(d, {"total": 0, "present": 0, "leave": 0, "late": 0})
            dept_rows_map[d]["leave"] += 1
    dept_rows = [
        [d, v["total"], v["present"], v["leave"], v["late"], max(0, v["total"] - v["present"] - v["leave"])]
        for d, v in sorted(dept_rows_map.items())
    ]

    # Shift-wise
    shift_map: dict[str, dict] = {}
    for emp in employees:
        s = emp.get("shift_type") or "General"
        shift_map.setdefault(s, {"total": 0, "in": 0})
        shift_map[s]["total"] += 1
    for a in attendance:
        emp = emp_by_id.get(a.get("employee_id"))
        if emp and (a.get("check_in") or a.get("check_in_24h")):
            s = emp.get("shift_type") or "General"
            shift_map[s]["in"] += 1
    shift_rows = [[s, v["total"], v["in"], max(0, v["total"] - v["in"])] for s, v in sorted(shift_map.items())]

    # Top 5 delayed
    delayed.sort(key=lambda x: x[0], reverse=True)
    top_delayed = [
        [d[1].get("emp_name") or "-", d[1].get("team") or "-", d[1].get("check_in") or "-", f"{d[0]} min"]
        for d in delayed[:5]
    ]

    html = admin_summary_email(summary, dept_rows, shift_rows, top_delayed, today_dmy)
    await send_hrms_email(
        db,
        email_type="admin_summary",
        scope_key=scope_key,
        to_email=ADMIN_REPORT_RECIPIENT,
        subject=f"Daily Attendance Report — {today_dmy}",
        html=html,
    )
    logger.info("[cron:admin_summary] done date=%s", today_dmy)


# =========================================================================
# JOB 2: Late Login Email to Employee
# =========================================================================
async def late_login_job(db: AsyncIOMotorDatabase) -> None:
    today_dmy = _ist_today()
    if await _is_non_working_day(db, today_dmy):
        logger.info("[cron:late_login] non-working day, skip")
        return
    logger.info("[cron:late_login] start date=%s", today_dmy)

    # Only records with an IN punch today AND marked as late
    records = await db.attendance.find(
        {"date": today_dmy, "$or": [{"status": "Late Login"}, {"late_by_minutes": {"$gt": 0}}]},
        {"_id": 0},
    ).to_list(5000)

    employees = {e["id"]: e for e in await _active_employees(db)}
    ymd = _dmy_to_ymd(today_dmy)
    sent = 0
    for a in records:
        emp = employees.get(a.get("employee_id"))
        if not emp:
            continue
        to_email = _emp_email(emp)
        if not to_email:
            continue
        emp_id = emp["id"]
        # Guards
        if await _has_leave_on(db, emp_id, ymd):
            continue
        if await _has_late_request_on(db, emp_id, today_dmy):
            continue

        late_by = int(a.get("late_by_minutes") or 0)
        if not late_by:
            # Fallback compute from expected_login vs check_in_24h
            try:
                exp = a.get("expected_login") or "10:00"
                actual = a.get("check_in_24h") or ""
                if actual:
                    eh, em = map(int, exp.split(":"))
                    ah, am = map(int, actual.split(":"))
                    late_by = max(0, (ah * 60 + am) - (eh * 60 + em))
            except Exception:
                late_by = 0
        if late_by <= 0:
            continue

        action_url = generate_employee_action_link("/employee/late-request", today_dmy)
        html = late_login_email(
            emp.get("full_name", "Employee"),
            a.get("expected_login") or "-",
            a.get("check_in") or "-",
            late_by,
            action_url,
        )
        ok = await send_hrms_email(
            db,
            email_type="late_login",
            scope_key=f"{emp_id}:{today_dmy}",
            to_email=to_email,
            subject=f"Late Login Notification — {today_dmy}",
            html=html,
            employee_id=emp_id,
        )
        if ok:
            sent += 1
    logger.info("[cron:late_login] done sent=%d", sent)


# =========================================================================
# JOB 3: Missed Punch Email (yesterday)
# =========================================================================
async def missed_punch_job(db: AsyncIOMotorDatabase) -> None:
    dmy = _ist_yesterday()
    ymd = _dmy_to_ymd(dmy)
    if await _is_non_working_day(db, dmy):
        logger.info("[cron:missed_punch] non-working day, skip")
        return
    logger.info("[cron:missed_punch] start date=%s", dmy)

    records = await db.attendance.find({"date": dmy}, {"_id": 0}).to_list(5000)
    employees = {e["id"]: e for e in await _active_employees(db)}

    sent = 0
    for a in records:
        emp = employees.get(a.get("employee_id"))
        if not emp:
            continue
        to_email = _emp_email(emp)
        if not to_email:
            continue
        emp_id = emp["id"]

        has_in = bool(a.get("check_in") or a.get("check_in_24h"))
        has_out = bool(a.get("check_out") or a.get("check_out_24h"))
        if has_in == has_out:  # both present or both missing → handled by no-login job
            continue
        missing = "Check-Out" if has_in else "Check-In"

        if await _has_leave_on(db, emp_id, ymd):
            continue
        if await _has_missed_punch_on(db, emp_id, dmy):
            continue
        if (a.get("source") or "") == "corrected":
            continue  # already regularized

        action_url = generate_employee_action_link("/employee/missed-punch", dmy)
        html = missed_punch_email(emp.get("full_name", "Employee"), dmy, missing, action_url)
        ok = await send_hrms_email(
            db,
            email_type="missed_punch",
            scope_key=f"{emp_id}:{dmy}",
            to_email=to_email,
            subject=f"Missing Punch Detected — {dmy}",
            html=html,
            employee_id=emp_id,
        )
        if ok:
            sent += 1
    logger.info("[cron:missed_punch] done sent=%d", sent)


# =========================================================================
# JOB 4: Early Out Email (yesterday)
# =========================================================================
async def early_out_job(db: AsyncIOMotorDatabase) -> None:
    dmy = _ist_yesterday()
    ymd = _dmy_to_ymd(dmy)
    if await _is_non_working_day(db, dmy):
        logger.info("[cron:early_out] non-working day, skip")
        return
    logger.info("[cron:early_out] start date=%s", dmy)

    records = await db.attendance.find(
        {"date": dmy, "status": {"$in": ["Early Out", "Loss of Pay"]}},
        {"_id": 0},
    ).to_list(5000)
    employees = {e["id"]: e for e in await _active_employees(db)}

    sent = 0
    for a in records:
        emp = employees.get(a.get("employee_id"))
        if not emp:
            continue
        to_email = _emp_email(emp)
        if not to_email:
            continue
        emp_id = emp["id"]
        if not (a.get("check_in") and a.get("check_out")):
            continue

        if await _has_leave_on(db, emp_id, ymd):
            continue
        if await _has_early_out_request_on(db, emp_id, dmy):
            continue

        worked = a.get("total_hours") or f"{a.get('total_hours_decimal', 0)}h"
        expected = "9h 30m"  # standard shift — templates only display, no calc impact

        action_url = generate_employee_action_link("/employee/early-out", dmy)
        html = early_out_email(emp.get("full_name", "Employee"), dmy, worked, expected, action_url)
        ok = await send_hrms_email(
            db,
            email_type="early_out",
            scope_key=f"{emp_id}:{dmy}",
            to_email=to_email,
            subject=f"Early Out Detected — {dmy}",
            html=html,
            employee_id=emp_id,
        )
        if ok:
            sent += 1
    logger.info("[cron:early_out] done sent=%d", sent)


# =========================================================================
# JOB 5: No Login Email (yesterday)
# =========================================================================
async def no_login_job(db: AsyncIOMotorDatabase) -> None:
    dmy = _ist_yesterday()
    ymd = _dmy_to_ymd(dmy)
    if await _is_non_working_day(db, dmy):
        logger.info("[cron:no_login] non-working day, skip")
        return
    logger.info("[cron:no_login] start date=%s", dmy)

    employees = await _active_employees(db)
    attendance = await db.attendance.find({"date": dmy}, {"_id": 0, "employee_id": 1, "check_in": 1, "check_in_24h": 1, "check_out": 1, "check_out_24h": 1}).to_list(5000)
    emp_attendance_map = {a["employee_id"]: a for a in attendance}

    sent = 0
    for emp in employees:
        to_email = _emp_email(emp)
        if not to_email:
            continue
        emp_id = emp["id"]
        a = emp_attendance_map.get(emp_id)
        # No attendance row OR both punches missing
        if a:
            has_in = bool(a.get("check_in") or a.get("check_in_24h"))
            has_out = bool(a.get("check_out") or a.get("check_out_24h"))
            if has_in or has_out:
                continue

        if await _has_leave_on(db, emp_id, ymd):
            continue
        if await _has_missed_punch_on(db, emp_id, dmy):
            continue

        leave_url = generate_employee_action_link("/employee/leave", dmy)
        mp_url = generate_employee_action_link("/employee/missed-punch", dmy)
        html = no_login_email(emp.get("full_name", "Employee"), dmy, leave_url, mp_url)
        ok = await send_hrms_email(
            db,
            email_type="no_login",
            scope_key=f"{emp_id}:{dmy}",
            to_email=to_email,
            subject=f"No Attendance Recorded — {dmy}",
            html=html,
            employee_id=emp_id,
        )
        if ok:
            sent += 1
    logger.info("[cron:no_login] done sent=%d", sent)


# =========================================================================
# Scheduler bootstrap
# =========================================================================
_scheduler: Optional[AsyncIOScheduler] = None


def start_email_scheduler(db: AsyncIOMotorDatabase) -> AsyncIOScheduler:
    """Idempotent scheduler start — called once from FastAPI startup."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    sch = AsyncIOScheduler(timezone=IST)

    common = dict(coalesce=True, max_instances=1, misfire_grace_time=600)

    sch.add_job(
        admin_attendance_summary_job, args=[db],
        trigger=CronTrigger(hour=10, minute=30, timezone=IST),
        id="adminAttendanceSummaryCron", **common,
    )
    sch.add_job(
        late_login_job, args=[db],
        trigger=CronTrigger(day_of_week="mon-sat", hour="10-13", minute="*/15", timezone=IST),
        id="lateLoginCron", **common,
    )
    sch.add_job(
        missed_punch_job, args=[db],
        trigger=CronTrigger(hour=9, minute=0, timezone=IST),
        id="missedPunchCron", **common,
    )
    sch.add_job(
        early_out_job, args=[db],
        trigger=CronTrigger(hour=9, minute=15, timezone=IST),
        id="earlyOutCron", **common,
    )
    sch.add_job(
        no_login_job, args=[db],
        trigger=CronTrigger(hour=9, minute=30, timezone=IST),
        id="noLoginCron", **common,
    )

    sch.start()
    _scheduler = sch
    logger.info("HRMS email scheduler started with 5 jobs")
    return sch


def get_job_handlers() -> dict:
    """Expose handlers for manual trigger API."""
    return {
        "admin_summary": admin_attendance_summary_job,
        "late_login": late_login_job,
        "missed_punch": missed_punch_job,
        "early_out": early_out_job,
        "no_login": no_login_job,
    }
