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
  • Admin-controlled gatekeeper layer: each job consults `cron_settings`
    BEFORE executing. If disabled, the run is recorded as "skipped" and the
    job exits safely. Default and fail-open: missing config = ENABLED.
"""
from __future__ import annotations

import logging
import traceback
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
    send_hrms_email_multi,
)
from email_templates import (
    admin_summary_email,
    admin_summary_email_detailed,
    early_out_email,
    late_login_email,
    missed_punch_email,
    no_login_email,
)

logger = logging.getLogger("hrms.email.jobs")

IST = pytz_timezone("Asia/Kolkata")

# ---- Job metadata exposed for the admin UI --------------------------------
JOB_META: dict[str, dict] = {
    "admin_summary": {
        "label": "Admin Attendance Summary",
        "schedule": "Daily 10:30 IST",
        "scope": "today",
    },
    "late_login": {
        "label": "Late Login",
        "schedule": "Mon–Sat, every 15 min between 10:00–13:45 IST",
        "scope": "today",
    },
    "missed_punch": {
        "label": "Missed Punch",
        "schedule": "Daily 09:00 IST",
        "scope": "yesterday",
    },
    "early_out": {
        "label": "Early Out",
        "schedule": "Daily 09:15 IST",
        "scope": "yesterday",
    },
    "no_login": {
        "label": "No Login",
        "schedule": "Daily 09:30 IST",
        "scope": "yesterday",
    },
}


# ---- Admin-controlled gatekeeper -----------------------------------------
async def is_cron_enabled(db: AsyncIOMotorDatabase, job_name: str) -> bool:
    """Default fail-open: if no config or DB error, the cron RUNS."""
    try:
        doc = await db.cron_settings.find_one({"job_name": job_name}, {"_id": 0, "enabled": 1})
        if not doc:
            return True
        return bool(doc.get("enabled", True))
    except Exception as e:
        logger.warning("is_cron_enabled fallback enabled (%s): %s", job_name, e)
        return True


async def get_cron_cc(db: AsyncIOMotorDatabase, job_name: str) -> list[str]:
    """Returns the configured CC list for a cron job. Always returns a list;
    DB errors degrade silently to []."""
    try:
        doc = await db.cron_settings.find_one({"job_name": job_name}, {"_id": 0, "cc_emails": 1})
        if not doc:
            return []
        return list(doc.get("cc_emails") or [])
    except Exception as e:
        logger.warning("get_cron_cc fallback empty (%s): %s", job_name, e)
        return []


async def mark_cron_run(
    db: AsyncIOMotorDatabase,
    job_name: str,
    *,
    result: str,
    error: Optional[str] = None,
) -> None:
    """Persist the last-run snapshot for the admin UI. Never raises."""
    try:
        await db.cron_settings.update_one(
            {"job_name": job_name},
            {
                "$set": {
                    "last_run_at": datetime.now(IST).isoformat(),
                    "last_result": result,
                    "last_error": error,
                },
                "$setOnInsert": {
                    "job_name": job_name,
                    "enabled": True,
                    "created_at": datetime.now(IST).isoformat(),
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning("mark_cron_run failed (%s): %s", job_name, e)


def _gated(job_name: str):
    """Decorator: gates a job by the admin toggle + records last-run state.

    The wrapped job MUST take `db` as its first positional arg. The decorator
    is intentionally minimal so it never alters the wrapped business logic —
    it only short-circuits when disabled and records the outcome on exit.
    `force=True` bypasses the admin enabled-toggle (manual "Run Now" path)
    and is forwarded to the inner job so it can bypass dedup as well.
    """
    def deco(fn):
        async def wrapper(db: AsyncIOMotorDatabase, *args, force: bool = False, **kwargs):
            if not force and not await is_cron_enabled(db, job_name):
                logger.info("[cron:%s] disabled by admin — skipping", job_name)
                await mark_cron_run(db, job_name, result="skipped")
                return
            try:
                await fn(db, *args, force=force, **kwargs)
                await mark_cron_run(db, job_name, result="success")
            except Exception as e:
                logger.error("[cron:%s] failed: %s\n%s", job_name, e, traceback.format_exc())
                await mark_cron_run(db, job_name, result="failed", error=str(e))
                # never re-raise from a scheduled cron — keeps APScheduler healthy
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


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
async def admin_attendance_summary_job_inner(db: AsyncIOMotorDatabase, force: bool = False) -> None:
    """Daily admin attendance summary — DETAILED employee-wise report.

    Builds 4 mutually-exclusive sections:
      • Logged In        (Name, Login Time)
      • Late Login       (Name, Login Time, Late Duration) — subset of Logged In
                         shown separately per requirement
      • Not Logged In    (Name) — excludes employees on leave
      • On Leave         (Name, Date, Leave Type, Status, Reason)

    Hard-coded recipient: hr@blubridge.com. No CC.
    """
    today_dmy = _ist_today()
    logger.info("[cron:admin_summary] start date=%s force=%s", today_dmy, force)

    employees = await _active_employees(db)
    emp_by_id = {e["id"]: e for e in employees}

    attendance = await db.attendance.find({"date": today_dmy}, {"_id": 0}).to_list(5000)

    # --- Build On-Leave set FIRST (so Not Logged In can exclude them) --------
    ymd = _dmy_to_ymd(today_dmy)
    leaves_today = await db.leaves.find(
        {
            "status": {"$in": ["approved", "pending"]},
            "start_date": {"$lte": ymd},
            "end_date": {"$gte": ymd},
        },
        {"_id": 0},
    ).to_list(5000)
    on_leave_ids: set = set()
    on_leave_rows: list = []
    for lv in leaves_today:
        eid = lv.get("employee_id")
        emp = emp_by_id.get(eid)
        if not emp:
            continue
        on_leave_ids.add(eid)
        on_leave_rows.append([
            emp.get("full_name") or emp.get("emp_name") or "-",
            today_dmy,
            lv.get("leave_type") or "-",
            (lv.get("status") or "-").title(),
            (lv.get("reason") or "-")[:160],
        ])
    on_leave_rows.sort(key=lambda r: r[0].lower())

    # --- Walk attendance to build Logged-In & Late-Login lists ---------------
    logged_in_rows: list = []
    late_login_rows: list = []
    emp_with_in: set = set()

    for a in attendance:
        emp_id = a.get("employee_id")
        emp = emp_by_id.get(emp_id)
        if not emp:
            continue
        check_in = a.get("check_in") or a.get("check_in_24h") or ""
        if not check_in:
            continue
        emp_with_in.add(emp_id)
        emp_name = emp.get("full_name") or emp.get("emp_name") or "-"
        logged_in_rows.append([emp_name, check_in])

        status = (a.get("status") or "").strip()
        late_by = int(a.get("late_by_minutes") or 0)
        is_late = (status == "Late Login") or ("late login" in (a.get("lop_reason") or "").lower()) or late_by > 0
        if is_late:
            if late_by <= 0:
                # Fallback compute from expected_login vs check_in_24h
                try:
                    exp = a.get("expected_login") or "10:00"
                    actual = a.get("check_in_24h") or check_in
                    eh, em = map(int, exp.split(":"))
                    ah, am = map(int, actual.split(":"))
                    late_by = max(0, (ah * 60 + am) - (eh * 60 + em))
                except Exception:
                    late_by = 0
            late_display = f"{late_by} min" if late_by > 0 else "-"
            late_login_rows.append([emp_name, check_in, late_display])

    logged_in_rows.sort(key=lambda r: r[0].lower())
    late_login_rows.sort(key=lambda r: r[0].lower())

    # --- Not Logged In: employees with no check_in AND not on leave ----------
    not_logged_rows: list = []
    for emp in employees:
        eid = emp["id"]
        if eid in emp_with_in:
            continue
        if eid in on_leave_ids:
            continue  # on-leave employees excluded per requirement
        not_logged_rows.append([emp.get("full_name") or emp.get("emp_name") or "-"])
    not_logged_rows.sort(key=lambda r: r[0].lower())

    html = admin_summary_email_detailed(
        date_str=today_dmy,
        logged_in_rows=logged_in_rows,
        late_login_rows=late_login_rows,
        not_logged_rows=not_logged_rows,
        on_leave_rows=on_leave_rows,
    )

    # ---- HARD-CODED admin recipient; CC is DISABLED per policy --------------
    # CC functionality is intentionally commented out (see task id=r9m2kq).
    # Do NOT re-enable without explicit product approval.
    # cc_list = await get_cron_cc(db, "admin_summary")  # [DISABLED: CC removal]
    admin_recipient = "hr@blubridge.com"
    recipients = [admin_recipient]  # no CC; primary only

    await send_hrms_email_multi(
        db,
        email_type="admin_summary",
        base_scope_key=f"admin_summary:{today_dmy}",
        recipients=recipients,
        subject=f"Daily Attendance Report — {today_dmy}",
        html=html,
        force=force,
    )
    logger.info(
        "[cron:admin_summary] done date=%s force=%s logged=%d late=%d absent=%d leave=%d",
        today_dmy, force, len(logged_in_rows), len(late_login_rows),
        len(not_logged_rows), len(on_leave_rows),
    )

    # ------------------------------------------------------------------------
    # LEGACY counts-only summary (commented out per task id=8c1z7n; restore
    # here if product wants the old stat-grid format back).
    # ------------------------------------------------------------------------
    # logged_in = completed = early_out = late_login = half_day = missed_punch = 0
    # ... (original count-based aggregation preserved in git history)
    # summary = { "total_employees": ..., "logged_in": ..., ... }
    # dept_rows = [...]
    # shift_rows = [...]
    # top_delayed = [...]
    # html = admin_summary_email(summary, dept_rows, shift_rows, top_delayed, today_dmy)


# =========================================================================
# JOB 2: Late Login Email to Employee
# =========================================================================
async def late_login_job_inner(db: AsyncIOMotorDatabase, force: bool = False) -> None:
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
    # CC functionality disabled per policy (task id=r9m2kq). Keep the line
    # commented so it can be restored later without re-derivation.
    # cc_list = await get_cron_cc(db, "late_login")  # [DISABLED: CC removal]
    cc_list: list = []
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
        result = await send_hrms_email_multi(
            db,
            email_type="late_login",
            base_scope_key=f"late_login:{emp_id}:{today_dmy}",
            recipients=[to_email] + cc_list,
            subject=f"Late Login Notification — {today_dmy}",
            html=html,
            employee_id=emp_id,
            force=force,
        )
        if result["sent"] > 0:
            sent += 1
    logger.info("[cron:late_login] done sent=%d force=%s", sent, force)


# =========================================================================
# JOB 3: Missed Punch Email (yesterday)
# =========================================================================
async def missed_punch_job_inner(db: AsyncIOMotorDatabase, force: bool = False) -> None:
    dmy = _ist_yesterday()
    ymd = _dmy_to_ymd(dmy)
    if await _is_non_working_day(db, dmy):
        logger.info("[cron:missed_punch] non-working day, skip")
        return
    logger.info("[cron:missed_punch] start date=%s", dmy)

    records = await db.attendance.find({"date": dmy}, {"_id": 0}).to_list(5000)
    employees = {e["id"]: e for e in await _active_employees(db)}
    # cc_list = await get_cron_cc(db, "missed_punch")  # [DISABLED: CC removal]
    cc_list: list = []

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
        result = await send_hrms_email_multi(
            db,
            email_type="missed_punch",
            base_scope_key=f"missed_punch:{emp_id}:{dmy}",
            recipients=[to_email] + cc_list,
            subject=f"Missing Punch Detected — {dmy}",
            html=html,
            employee_id=emp_id,
            force=force,
        )
        if result["sent"] > 0:
            sent += 1
    logger.info("[cron:missed_punch] done sent=%d force=%s", sent, force)


# =========================================================================
# JOB 4: Early Out Email (yesterday)
# =========================================================================
async def early_out_job_inner(db: AsyncIOMotorDatabase, force: bool = False) -> None:
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
    # cc_list = await get_cron_cc(db, "early_out")  # [DISABLED: CC removal]
    cc_list: list = []

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
        result = await send_hrms_email_multi(
            db,
            email_type="early_out",
            base_scope_key=f"early_out:{emp_id}:{dmy}",
            recipients=[to_email] + cc_list,
            subject=f"Early Out Detected — {dmy}",
            html=html,
            employee_id=emp_id,
            force=force,
        )
        if result["sent"] > 0:
            sent += 1
    logger.info("[cron:early_out] done sent=%d force=%s", sent, force)


# =========================================================================
# JOB 5: No Login Email (yesterday)
# =========================================================================
async def no_login_job_inner(db: AsyncIOMotorDatabase, force: bool = False) -> None:
    dmy = _ist_yesterday()
    ymd = _dmy_to_ymd(dmy)
    if await _is_non_working_day(db, dmy):
        logger.info("[cron:no_login] non-working day, skip")
        return
    logger.info("[cron:no_login] start date=%s", dmy)

    employees = await _active_employees(db)
    attendance = await db.attendance.find({"date": dmy}, {"_id": 0, "employee_id": 1, "check_in": 1, "check_in_24h": 1, "check_out": 1, "check_out_24h": 1}).to_list(5000)
    emp_attendance_map = {a["employee_id"]: a for a in attendance}
    # cc_list = await get_cron_cc(db, "no_login")  # [DISABLED: CC removal]
    cc_list: list = []

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
        result = await send_hrms_email_multi(
            db,
            email_type="no_login",
            base_scope_key=f"no_login:{emp_id}:{dmy}",
            recipients=[to_email] + cc_list,
            subject=f"No Attendance Recorded — {dmy}",
            html=html,
            employee_id=emp_id,
            force=force,
        )
        if result["sent"] > 0:
            sent += 1
    logger.info("[cron:no_login] done sent=%d force=%s", sent, force)


# =========================================================================
# Public job entrypoints — gated by admin toggle, last-run tracked
# =========================================================================
admin_attendance_summary_job = _gated("admin_summary")(admin_attendance_summary_job_inner)
late_login_job = _gated("late_login")(late_login_job_inner)
missed_punch_job = _gated("missed_punch")(missed_punch_job_inner)
early_out_job = _gated("early_out")(early_out_job_inner)
no_login_job = _gated("no_login")(no_login_job_inner)


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
