"""
Warning module — Leave & Attendance Policy Non-Compliance Framework.

MVP scope (single-file router, no separate migrations — MongoDB collections
created on first use, indexes ensured at import time):
  • Single collection `warning_cases` with embedded attachments, approvals,
    audit log entries and acknowledgement — keeps the surface small and
    consistent with the existing HRMS monolith style.
  • Endpoints for dashboard stats, list (with filters), create draft, update
    draft, submit for approval, approve/reject, send email (uses existing
    send_email_notification), acknowledge (employee), close, revoke, timeline,
    and CSV export.
  • Role gating: only HR/system_admin can create/approve/send/revoke/close.
    Employees see only their own issued warnings.
  • Sequential reference numbers WARN/YYYY/MM/0001 assigned atomically at
    approval time.
  • Full audit log per case — every action appends an entry with actor + role +
    timestamp + optional status transition.

Phase 2 (not in MVP, tracked in ROADMAP): PDF generation, follow-ups sub-tab,
CC/BCC recipient config, Excel export, escalation-creates-linked-case, in-app
notifications feed.
"""
import io, csv, uuid, asyncio
from datetime import datetime, timezone
from fastapi import HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

# These names are all pulled from server.py's global scope at import time.
from server import (
    api_router, db, get_current_user, get_ist_now, serialize_doc,
    log_audit, send_email_notification, UserRole, ADMIN_ROLES,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WARNING_LEVELS = {
    "first":  {"code": "first",  "label": "Warning Notice 1"},
    "final":  {"code": "final",  "label": "Warning Notice 2 – Final Warning"},
    "termination": {"code": "termination", "label": "Termination of Employment/Internship"},
}
CASE_STATUSES = [
    "draft", "pending_approval", "approved", "rejected",
    "issued", "sent", "email_failed",
    "awaiting_ack", "acknowledged", "response_received",
    "under_review", "closed", "revoked", "cancelled",
]
# Statuses that count as "valid issued warnings" (drive the escalation logic).
VALID_INSTANCE_STATUSES = {
    "issued", "sent", "awaiting_ack", "acknowledged",
    "response_received", "under_review", "closed",
}

INCIDENT_CATEGORIES = [
    "leave_late", "leave_wrong_category", "leave_docs_missing",
    "medical_cert_missing", "leave_email_missing", "leave_email_late",
    "leave_not_in_hrms", "hrms_request_late", "wrong_comm_format",
    "manager_not_informed", "unauthorized_absence", "regularization_missing",
    "missed_punch_not_reported", "repeated_late_arrival", "repeated_early_departure",
    "attendance_comm_failure", "other_leave_policy", "other_attendance_policy",
]


def _now():
    return get_ist_now().isoformat()


async def _is_hr(user):
    return user.get("role") in ADMIN_ROLES


async def _ensure_indexes():
    try:
        await db.warning_cases.create_index("employee_id")
        await db.warning_cases.create_index("warning_reference", unique=True, sparse=True)
        await db.warning_cases.create_index("status")
        await db.warning_cases.create_index("warning_level")
        await db.warning_cases.create_index("incident_date")
        await db.warning_cases.create_index("created_at")
        await db.warning_email_templates.create_index("level", unique=True)
    except Exception:
        pass  # Idempotent on restarts
    await _seed_default_templates()


# ---------------------------------------------------------------------------
# Editable email templates — one row per warning level, with placeholders like
# {{employee_name}}, {{warning_reference}}, {{incident_date}}, etc. Kept in a
# tiny dedicated collection so HR can edit heading + description without a
# code change. Defaults are seeded once on startup.
# ---------------------------------------------------------------------------

DEFAULT_EMAIL_TEMPLATES = {
    "first": {
        "level": "first",
        "level_label": "Warning Notice 1",
        "subject": "Warning Notice 1 – Leave and Attendance Policy Non-Compliance – {{employee_name}}",
        "heading": "Warning Notice 1 – Leave and Attendance Policy Non-Compliance",
        "body_html": (
            "<p>Dear {{employee_name}},</p>"
            "<p>This email is to formally notify you of a recorded instance of non-compliance "
            "with the company's <b>Leave and Attendance Policy</b>. This constitutes "
            "<b>Warning Notice 1 (First Warning)</b> under our escalation framework.</p>"
            "<p>Please treat this notice as an opportunity for course correction. Continued "
            "non-compliance will result in a <b>Final Warning</b>, followed by <b>Termination "
            "of Employment/Internship</b> as per policy.</p>"
        ),
    },
    "final": {
        "level": "final",
        "level_label": "Final Warning",
        "subject": "Final Warning – Leave and Attendance Policy Non-Compliance – {{employee_name}}",
        "heading": "Final Warning – Leave and Attendance Policy Non-Compliance",
        "body_html": (
            "<p>Dear {{employee_name}},</p>"
            "<p>This email is a <b>Final Warning</b> regarding continued non-compliance with the "
            "company's <b>Leave and Attendance Policy</b>. A prior Warning Notice 1 was already "
            "issued for a similar concern.</p>"
            "<p>Please treat this as a <b>final opportunity</b> for corrective action. Any further "
            "instance of non-compliance will lead to <b>Termination of Employment/Internship</b> "
            "without additional notice, in accordance with our escalation framework.</p>"
        ),
    },
    "termination": {
        "level": "termination",
        "level_label": "Termination of Employment/Internship",
        "subject": "Termination Action – Leave and Attendance Policy Non-Compliance – {{employee_name}}",
        "heading": "Termination of Employment/Internship – Leave and Attendance Policy Non-Compliance",
        "body_html": (
            "<p>Dear {{employee_name}},</p>"
            "<p>Despite prior Warning Notice 1 and Final Warning issued to you for non-compliance "
            "with the company's <b>Leave and Attendance Policy</b>, the pattern of non-compliance "
            "has continued.</p>"
            "<p>Accordingly, this email is to formally communicate the initiation of "
            "<b>Termination of your Employment/Internship</b>. HR will be in touch regarding "
            "exit formalities, final settlement, and handover.</p>"
        ),
    },
}


async def _seed_default_templates():
    try:
        for lvl, tpl in DEFAULT_EMAIL_TEMPLATES.items():
            existing = await db.warning_email_templates.find_one({"level": lvl})
            if not existing:
                await db.warning_email_templates.insert_one({
                    **tpl, "created_at": _now(), "updated_at": _now(),
                    "updated_by": None, "updated_by_name": None,
                })
    except Exception:
        pass


def _apply_placeholders(text: str, ctx: dict) -> str:
    if not text: return text
    for k, v in ctx.items():
        text = text.replace("{{" + k + "}}", str(v if v is not None else "—"))
    return text


def _build_email_context(case: dict) -> dict:
    emp = case.get("employee_snapshot") or {}
    return {
        "employee_name": emp.get("full_name") or "",
        "employee_id": emp.get("emp_id") or "",
        "department": emp.get("department") or "",
        "designation": emp.get("designation") or "",
        "official_email": emp.get("official_email") or "",
        "warning_reference": case.get("warning_reference") or "—",
        "warning_level_label": WARNING_LEVELS.get(case.get("warning_level"), {}).get("label", ""),
        "incident_date": case.get("incident_date") or "",
        "warning_issue_date": case.get("warning_issue_date") or "",
        "acknowledgement_due_date": case.get("acknowledgement_due_date") or "",
        "incident_category": (case.get("incident_category") or "").replace("_", " ").title(),
        "incident_description": case.get("incident_description") or "",
        "corrective_action": case.get("corrective_action") or "",
        "issued_by": case.get("approved_by_name") or case.get("created_by_name") or "HR Admin",
        "company": "BluBridge Technologies",
    }



async def _append_audit(case_id, actor, action, prev_status=None, new_status=None,
                        description=None, metadata=None):
    entry = {
        "id": str(uuid.uuid4()),
        "action": action,
        "previous_status": prev_status,
        "new_status": new_status,
        "description": description,
        "performed_by": actor.get("id") if actor else None,
        "performed_by_name": (actor or {}).get("name") or (actor or {}).get("full_name"),
        "performed_by_role": (actor or {}).get("role"),
        "created_at": _now(),
        "metadata": metadata or {},
    }
    await db.warning_cases.update_one(
        {"id": case_id},
        {"$push": {"audit_log": entry}, "$set": {"updated_at": _now()}},
    )
    # Mirror into system-wide audit trail too.
    if actor:
        try:
            await log_audit(actor["id"], f"warning_{action}", "warning_case", case_id, description or "")
        except Exception:
            pass
    return entry


async def _count_valid_prior(employee_id):
    return await db.warning_cases.count_documents({
        "employee_id": employee_id,
        "status": {"$in": list(VALID_INSTANCE_STATUSES)},
    })


def _suggest_level_from_prior(prior_count):
    if prior_count == 0:
        return "first"
    if prior_count == 1:
        return "final"
    return "termination"


async def _next_reference():
    """Atomic sequential reference: WARN/YYYY/MM/NNNN — bumps a counter row per month."""
    now = get_ist_now()
    key = f"warn_{now.year:04d}{now.month:02d}"
    row = await db.counters.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}, "$setOnInsert": {"created_at": _now()}},
        upsert=True, return_document=True,
    )
    return f"WARN/{now.year:04d}/{now.month:02d}/{row['seq']:04d}"


# ---------------------------------------------------------------------------
# Endpoints — Admin/HR
# ---------------------------------------------------------------------------

@api_router.get("/warnings/stats")
async def warnings_stats(current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    pipe = [{"$group": {"_id": {"level": "$warning_level", "status": "$status"}, "n": {"$sum": 1}}}]
    rows = await db.warning_cases.aggregate(pipe).to_list(1000)
    ur, w1, wf, wt, ack_pending, overdue = set(), 0, 0, 0, 0, 0
    now_iso = _now()
    for r in rows:
        k = r["_id"] or {}; lvl, st, n = k.get("level"), k.get("status"), r["n"]
        active = st in VALID_INSTANCE_STATUSES or st in ("issued", "sent", "awaiting_ack", "acknowledged", "response_received", "under_review")
        if active:
            if lvl == "first": w1 += n
            elif lvl == "final": wf += n
            elif lvl == "termination": wt += n
        if st in ("sent", "awaiting_ack"): ack_pending += n
    # Unique employees under active warning
    async for e in db.warning_cases.aggregate([
        {"$match": {"status": {"$in": ["issued","sent","awaiting_ack","acknowledged","response_received","under_review","email_failed"]}}},
        {"$group": {"_id": "$employee_id"}},
    ]):
        ur.add(e["_id"])
    # Overdue = ack_due_date < now and not yet acknowledged
    overdue = await db.warning_cases.count_documents({
        "acknowledgement_status": {"$in": ["pending", None]},
        "acknowledgement_due_date": {"$lt": now_iso[:10]},
        "status": {"$in": ["sent", "awaiting_ack"]},
    })
    return {
        "employees_under_warning": len(ur),
        "warning_notice_1": w1,
        "final_warnings": wf,
        "termination_actions": wt,
        "awaiting_acknowledgement": ack_pending,
        "overdue_followups": overdue,
    }


@api_router.get("/warnings")
async def warnings_list(
    search: str = None, status: str = None, level: str = None,
    department: str = None, page: int = 1, limit: int = 25,
    current_user: dict = Depends(get_current_user),
):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    q = {}
    if status and status != "All": q["status"] = status
    if level and level != "All": q["warning_level"] = level
    if search:
        rx = {"$regex": search, "$options": "i"}
        q["$or"] = [
            {"warning_reference": rx}, {"employee_snapshot.full_name": rx},
            {"employee_snapshot.emp_id": rx}, {"employee_snapshot.official_email": rx},
            {"employee_snapshot.department": rx},
        ]
    if department and department != "All":
        q["employee_snapshot.department"] = department
    skip = (page-1)*limit
    total, docs = await asyncio.gather(
        db.warning_cases.count_documents(q),
        db.warning_cases.find(q, {"_id": 0, "audit_log": 0, "attachments": 0})
                        .sort("created_at", -1).skip(skip).limit(limit).to_list(limit),
    )
    return {"warnings": [serialize_doc(d) for d in docs], "total": total, "page": page, "limit": limit,
            "pages": (total+limit-1)//limit}


@api_router.get("/warnings/employee-history/{employee_id}")
async def warnings_employee_history(employee_id: str, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    docs = await db.warning_cases.find(
        {"employee_id": employee_id}, {"_id": 0, "audit_log": 0, "attachments": 0}
    ).sort("created_at", -1).to_list(100)
    prior = await _count_valid_prior(employee_id)
    return {"history": [serialize_doc(d) for d in docs],
            "valid_prior_count": prior,
            "suggested_level": _suggest_level_from_prior(prior)}


@api_router.post("/warnings")
async def warnings_create(body: dict, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    emp_id = body.get("employee_id")
    if not emp_id:
        raise HTTPException(status_code=400, detail="Employee is mandatory")
    if not body.get("incident_date"):
        raise HTTPException(status_code=400, detail="Incident date is mandatory")
    if not body.get("incident_category"):
        raise HTTPException(status_code=400, detail="Incident category is mandatory")
    if not body.get("incident_description"):
        raise HTTPException(status_code=400, detail="Incident description is mandatory")
    emp = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    prior = await _count_valid_prior(emp_id)
    suggested = _suggest_level_from_prior(prior)
    level = body.get("warning_level") or suggested
    if level not in WARNING_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid warning level")
    if level != suggested and not body.get("level_override_reason"):
        raise HTTPException(status_code=400, detail="Level override requires a reason")
    now = _now()
    doc = {
        "id": str(uuid.uuid4()),
        # warning_reference is intentionally omitted for drafts so the
        # sparse unique index does NOT treat multiple `null`s as duplicates.
        # It is assigned atomically at approval time via _next_reference().
        "employee_id": emp_id,
        "employee_snapshot": {  # Locked historical snapshot
            "full_name": emp.get("full_name"),
            "emp_id": emp.get("emp_id") or emp.get("custom_employee_id"),
            "official_email": emp.get("official_email"),
            "department": emp.get("department"),
            "designation": emp.get("designation"),
            "employment_type": emp.get("employment_type"),
            "reporting_manager_id": emp.get("reporting_manager_id"),
            "avatar": emp.get("avatar"),
        },
        "incident_date": body["incident_date"],
        "reported_date": body.get("reported_date") or body["incident_date"],
        "incident_category": body["incident_category"],
        "incident_subcategory": body.get("incident_subcategory"),
        "incident_description": body["incident_description"],
        "policy_requirement": body.get("policy_requirement"),
        "expected_action": body.get("expected_action"),
        "actual_action": body.get("actual_action"),
        "impact_description": body.get("impact_description"),
        "related_module": body.get("related_module"),
        "related_record_id": body.get("related_record_id"),
        "warning_instance_number": prior + 1,
        "warning_level": level,
        "system_suggested_level": suggested,
        "level_override_reason": body.get("level_override_reason"),
        "warning_issue_date": body.get("warning_issue_date"),
        "warning_effective_date": body.get("warning_effective_date"),
        "acknowledgement_due_date": body.get("acknowledgement_due_date"),
        "employee_response_due_date": body.get("employee_response_due_date"),
        "follow_up_date": body.get("follow_up_date"),
        "corrective_action": body.get("corrective_action"),
        "employee_visible_remarks": body.get("employee_visible_remarks"),
        "internal_remarks": body.get("internal_remarks"),
        "attachments": body.get("attachments") or [],
        # Per-case email content — pre-filled from the level's default template on the
        # frontend, but editable per warning. Empty/missing means "fall back to the
        # level's default template at render time".
        "email_subject": (body.get("email_subject") or "").strip() or None,
        "email_heading": (body.get("email_heading") or "").strip() or None,
        "email_body_html": (body.get("email_body_html") or "").strip() or None,
        "status": "draft",
        "email_status": "not_sent",
        "acknowledgement_status": "not_required",
        "created_by": current_user["id"],
        "created_by_name": current_user.get("name"),
        "created_at": now,
        "updated_at": now,
        "audit_log": [],
    }
    await db.warning_cases.insert_one(doc.copy())
    await _append_audit(doc["id"], current_user, "created", None, "draft", "Warning draft created")
    return serialize_doc({k: v for k, v in doc.items() if k != "_id"})


@api_router.put("/warnings/{case_id}")
async def warnings_update(case_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Warning not found")
    if case["status"] not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="Only drafts or rejected cases can be edited")
    editable = {
        "incident_date","reported_date","incident_category","incident_subcategory",
        "incident_description","policy_requirement","expected_action","actual_action",
        "impact_description","related_module","related_record_id","warning_level",
        "level_override_reason","warning_issue_date","warning_effective_date",
        "acknowledgement_due_date","employee_response_due_date","follow_up_date",
        "corrective_action","employee_visible_remarks","internal_remarks","attachments",
        "email_subject","email_heading","email_body_html",
    }
    update = {k: v for k, v in body.items() if k in editable}
    update["updated_at"] = _now()
    await db.warning_cases.update_one({"id": case_id}, {"$set": update})
    await _append_audit(case_id, current_user, "edited", case["status"], case["status"], "Draft edited")
    return {"message": "Draft updated"}


@api_router.post("/warnings/{case_id}/submit")
async def warnings_submit(case_id: str, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    if case["status"] not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="Only drafts can be submitted")
    if not case.get("warning_issue_date"):
        raise HTTPException(status_code=400, detail="Issue date is required before approval")
    await db.warning_cases.update_one({"id": case_id}, {"$set": {"status": "pending_approval", "updated_at": _now()}})
    await _append_audit(case_id, current_user, "submitted", case["status"], "pending_approval", "Submitted for approval")
    return {"message": "Submitted for approval"}


@api_router.post("/warnings/{case_id}/approve")
async def warnings_approve(case_id: str, body: dict = None, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    body = body or {}
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    if case["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Only cases pending approval can be approved")
    ref = case.get("warning_reference") or await _next_reference()
    now = _now()
    await db.warning_cases.update_one({"id": case_id}, {"$set": {
        "warning_reference": ref, "status": "approved",
        "approved_by": current_user["id"], "approved_by_name": current_user.get("name"),
        "approved_at": now, "approval_comments": body.get("comments"),
        "acknowledgement_status": "pending", "updated_at": now,
    }})
    await _append_audit(case_id, current_user, "approved", "pending_approval", "approved", body.get("comments") or "Approved")
    return {"message": "Approved", "warning_reference": ref}


@api_router.post("/warnings/{case_id}/reject")
async def warnings_reject(case_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    if not body or not body.get("comments"):
        raise HTTPException(status_code=400, detail="Rejection requires comments")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case or case["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Only pending cases can be rejected")
    await db.warning_cases.update_one({"id": case_id}, {"$set": {
        "status": "rejected", "rejection_reason": body["comments"], "updated_at": _now(),
    }})
    await _append_audit(case_id, current_user, "rejected", "pending_approval", "rejected", body["comments"])
    return {"message": "Rejected"}


@api_router.post("/warnings/{case_id}/send-email")
async def warnings_send_email(case_id: str, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    if case["status"] not in ("approved", "email_failed"):
        raise HTTPException(status_code=400, detail="Warning must be approved first")
    if case.get("email_status") == "sending":
        raise HTTPException(status_code=409, detail="Email is already being sent")
    # Idempotency lock
    lock = await db.warning_cases.update_one(
        {"id": case_id, "email_status": {"$ne": "sending"}},
        {"$set": {"email_status": "sending", "updated_at": _now()}},
    )
    if lock.modified_count == 0:
        raise HTTPException(status_code=409, detail="Email already being processed")

    emp = case["employee_snapshot"]
    subject, body_html = await _render_warning_email(case)
    try:
        await send_email_notification(emp["official_email"], subject, body_html)
        now = _now()
        new_status = "sent" if case["status"] == "approved" else case["status"]
        await db.warning_cases.update_one({"id": case_id}, {"$set": {
            "email_status": "sent" if case.get("email_status") != "sent" else "resent",
            "email_sent_at": now, "status": "awaiting_ack",
            "acknowledgement_status": "pending", "updated_at": now,
        }, "$push": {"email_log": {
            "id": str(uuid.uuid4()), "recipient": emp["official_email"],
            "subject": subject, "sent_by": current_user["id"], "sent_at": now,
        }}})
        await _append_audit(case_id, current_user, "email_sent", case["status"], "awaiting_ack",
                            f"Sent to {emp['official_email']}")
        return {"message": "Email sent", "recipient": emp["official_email"]}
    except Exception as e:
        await db.warning_cases.update_one({"id": case_id}, {"$set": {
            "email_status": "failed", "status": "email_failed",
            "email_error": str(e)[:400], "updated_at": _now(),
        }})
        await _append_audit(case_id, current_user, "email_failed", case["status"], "email_failed", str(e)[:200])
        raise HTTPException(status_code=502, detail=f"Email send failed: {e}")


def _render_case_details_table(case, ctx):
    """The fixed 'case details' section — always appended after the editable body."""
    rows = [
        ("Warning Reference", ctx["warning_reference"]),
        ("Employee ID", ctx["employee_id"]),
        ("Department", ctx["department"]),
        ("Designation", ctx["designation"]),
        ("Incident Date", ctx["incident_date"]),
        ("Warning Issued Date", ctx["warning_issue_date"] or "—"),
        ("Incident Category", ctx["incident_category"]),
        ("Acknowledgement Due", ctx["acknowledgement_due_date"] or "—"),
    ]
    tr = "".join(f"<tr><td style='padding:6px 10px;background:#f8fafc;font-weight:600;color:#334155;border:1px solid #e2e8f0;width:220px'>{k}</td><td style='padding:6px 10px;color:#0f172a;border:1px solid #e2e8f0'>{v or '—'}</td></tr>" for k, v in rows)
    details = (f"<h4 style='margin:16px 0 8px;color:#0f172a;font-size:14px'>Details of Non-Compliance</h4>"
               f"<div style='padding:10px;background:#f1f5f9;border-radius:6px;color:#0f172a;white-space:pre-wrap'>{ctx['incident_description']}</div>")
    if ctx["corrective_action"]:
        details += (f"<h4 style='margin:16px 0 8px;color:#0f172a;font-size:14px'>Required Corrective Action</h4>"
                    f"<div style='padding:10px;background:#fef3c7;border-radius:6px;color:#0f172a;white-space:pre-wrap'>{ctx['corrective_action']}</div>")
    signoff = (f"<p style='margin-top:20px'>Please log in to the HRMS to acknowledge receipt of this notice.</p>"
               f"<p style='margin-top:16px'>Regards,<br><b>{ctx['issued_by']}</b><br>{ctx['company']}</p>")
    return (f"<table cellpadding='0' cellspacing='0' border='0' style='border-collapse:collapse;width:100%;margin-top:12px;font-family:Arial,sans-serif;font-size:13px'>{tr}</table>"
            f"{details}{signoff}")


async def _render_warning_email(case):
    """Build (subject, full_body_html). Uses per-case fields when set; otherwise falls
    back to the editable level template. Placeholders are always substituted last so
    HR-authored per-case content can still use them."""
    tpl = await db.warning_email_templates.find_one({"level": case["warning_level"]}, {"_id": 0})
    if not tpl:
        tpl = DEFAULT_EMAIL_TEMPLATES[case["warning_level"]]
    subject_src = case.get("email_subject") or tpl["subject"]
    heading_src = case.get("email_heading") or tpl.get("heading") or tpl["subject"]
    body_src    = case.get("email_body_html") or tpl["body_html"]
    ctx = _build_email_context(case)
    subject = _apply_placeholders(subject_src, ctx)
    heading = _apply_placeholders(heading_src, ctx)
    body = _apply_placeholders(body_src, ctx)
    full = (f"<div style='font-family:Arial,sans-serif;font-size:14px;color:#0f172a;line-height:1.6'>"
            f"<h3 style='margin:0 0 12px;color:#7c2d12;border-left:4px solid #dc2626;padding-left:10px'>{heading}</h3>"
            f"{body}"
            f"{_render_case_details_table(case, ctx)}"
            f"</div>")
    return subject, full


# ---------------------------------------------------------------------------
# Email Template Management (HR-only)
# ---------------------------------------------------------------------------

@api_router.get("/warnings/email-templates")
async def get_email_templates(current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    tpls = await db.warning_email_templates.find({}, {"_id": 0}).to_list(10)
    by_lvl = {t["level"]: t for t in tpls}
    # Ensure all 3 exist in response (return defaults for any missing)
    out = []
    for lvl in ("first", "final", "termination"):
        out.append(by_lvl.get(lvl) or {**DEFAULT_EMAIL_TEMPLATES[lvl], "is_default": True})
    return {"templates": out, "placeholders": list(_build_email_context({"employee_snapshot": {}}).keys())}


@api_router.put("/warnings/email-templates/{level}")
async def update_email_template(level: str, body: dict, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    if level not in DEFAULT_EMAIL_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid warning level")
    subj = (body or {}).get("subject", "").strip()
    heading = (body or {}).get("heading", "").strip()
    body_html = (body or {}).get("body_html", "").strip()
    if not subj or not heading or not body_html:
        raise HTTPException(status_code=400, detail="Subject, heading and body are required")
    upd = {
        "level": level,
        "level_label": DEFAULT_EMAIL_TEMPLATES[level]["level_label"],
        "subject": subj, "heading": heading, "body_html": body_html,
        "updated_at": _now(),
        "updated_by": current_user["id"],
        "updated_by_name": current_user.get("name") or current_user.get("full_name"),
    }
    await db.warning_email_templates.update_one({"level": level}, {"$set": upd, "$setOnInsert": {"created_at": _now()}}, upsert=True)
    return {"message": "Template updated", "template": upd}


@api_router.post("/warnings/email-templates/{level}/reset")
async def reset_email_template(level: str, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    if level not in DEFAULT_EMAIL_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid warning level")
    d = DEFAULT_EMAIL_TEMPLATES[level]
    await db.warning_email_templates.update_one({"level": level}, {"$set": {
        **d, "updated_at": _now(), "updated_by": current_user["id"],
        "updated_by_name": current_user.get("name") or current_user.get("full_name"),
    }}, upsert=True)
    return {"message": "Reset to default", "template": d}


@api_router.get("/warnings/{case_id}/email-preview")
async def preview_warning_email(case_id: str, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    subject, body_html = await _render_warning_email(case)
    return {
        "subject": subject, "body_html": body_html,
        "recipient": case.get("employee_snapshot", {}).get("official_email"),
        "level": case["warning_level"],
        "level_label": WARNING_LEVELS.get(case["warning_level"], {}).get("label", ""),
    }





@api_router.get("/warnings/{case_id}")
async def warnings_detail(case_id: str, current_user: dict = Depends(get_current_user)):
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    # Employee can see only their own
    if not await _is_hr(current_user):
        if current_user.get("employee_id") != case["employee_id"]:
            raise HTTPException(status_code=403, detail="Permission denied")
        # Redact internal fields from employee view
        case.pop("internal_remarks", None)
        case["audit_log"] = [a for a in case.get("audit_log", [])
                             if a.get("action") not in ("edited", "email_failed")]
    return serialize_doc(case)


@api_router.post("/warnings/{case_id}/acknowledge")
async def warnings_acknowledge(case_id: str, body: dict = None, current_user: dict = Depends(get_current_user)):
    """Employee acknowledges receipt of the warning."""
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    if current_user.get("employee_id") != case["employee_id"]:
        raise HTTPException(status_code=403, detail="You can only acknowledge your own warnings")
    if case["status"] not in ("sent", "awaiting_ack", "email_failed"):
        raise HTTPException(status_code=400, detail="Warning is not in an acknowledgeable state")
    now = _now()
    await db.warning_cases.update_one({"id": case_id}, {"$set": {
        "status": "acknowledged", "acknowledgement_status": "acknowledged",
        "acknowledged_at": now, "acknowledgement_comment": (body or {}).get("comment"),
        "updated_at": now,
    }})
    await _append_audit(case_id, current_user, "acknowledged", case["status"], "acknowledged",
                        "Employee acknowledged receipt", metadata={"comment": (body or {}).get("comment")})
    return {"message": "Warning acknowledged"}


@api_router.post("/warnings/{case_id}/respond")
async def warnings_respond(case_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    """Employee submits a written response."""
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    if current_user.get("employee_id") != case["employee_id"]:
        raise HTTPException(status_code=403, detail="You can only respond to your own warnings")
    if not (body or {}).get("response_text"):
        raise HTTPException(status_code=400, detail="Response text required")
    now = _now()
    await db.warning_cases.update_one({"id": case_id}, {"$set": {
        "response_text": body["response_text"], "response_attachments": body.get("attachments") or [],
        "response_submitted_at": now, "status": "response_received",
        "acknowledgement_status": "response_submitted", "updated_at": now,
    }})
    await _append_audit(case_id, current_user, "response_submitted", case["status"], "response_received",
                        "Employee submitted a response")
    return {"message": "Response submitted"}


@api_router.post("/warnings/{case_id}/revoke")
async def warnings_revoke(case_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    if not (body or {}).get("reason"):
        raise HTTPException(status_code=400, detail="Revocation requires a reason")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    if case["status"] in ("revoked", "cancelled"):
        raise HTTPException(status_code=400, detail="Already revoked/cancelled")
    now = _now()
    await db.warning_cases.update_one({"id": case_id}, {"$set": {
        "status": "revoked", "revoked_by": current_user["id"], "revoked_at": now,
        "revocation_reason": body["reason"], "updated_at": now,
    }})
    await _append_audit(case_id, current_user, "revoked", case["status"], "revoked", body["reason"])
    return {"message": "Warning revoked"}


@api_router.post("/warnings/{case_id}/close")
async def warnings_close(case_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    if not (body or {}).get("comments"):
        raise HTTPException(status_code=400, detail="Closure comments required")
    case = await db.warning_cases.find_one({"id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Warning not found")
    now = _now()
    await db.warning_cases.update_one({"id": case_id}, {"$set": {
        "status": "closed", "closed_by": current_user["id"], "closed_at": now,
        "closure_comments": body["comments"], "updated_at": now,
    }})
    await _append_audit(case_id, current_user, "closed", case["status"], "closed", body["comments"])
    return {"message": "Case closed"}


@api_router.get("/warnings/export/csv")
async def warnings_export_csv(current_user: dict = Depends(get_current_user)):
    if not await _is_hr(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    docs = await db.warning_cases.find({}, {"_id": 0, "audit_log": 0, "attachments": 0}).sort("created_at", -1).to_list(5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Reference","Employee","EmpID","Department","Level","Incident Category","Incident Date",
                "Issue Date","Status","Email Status","Ack Status","Created By","Approved By"])
    for d in docs:
        e = d.get("employee_snapshot", {})
        w.writerow([d.get("warning_reference",""), e.get("full_name",""), e.get("emp_id",""),
                    e.get("department",""), WARNING_LEVELS.get(d.get("warning_level",""),{}).get("label",""),
                    d.get("incident_category",""), d.get("incident_date",""), d.get("warning_issue_date",""),
                    d.get("status",""), d.get("email_status",""), d.get("acknowledgement_status",""),
                    d.get("created_by_name",""), d.get("approved_by_name","")])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=warnings.csv"})


# ---------------------------------------------------------------------------
# Employee self-service
# ---------------------------------------------------------------------------

@api_router.get("/employee/warnings/me")
async def employee_warnings_me(current_user: dict = Depends(get_current_user)):
    emp_id = current_user.get("employee_id")
    if not emp_id:
        return {"warnings": []}
    docs = await db.warning_cases.find(
        {"employee_id": emp_id, "status": {"$in": ["sent","awaiting_ack","acknowledged","response_received","closed","revoked","under_review","email_failed","issued"]}},
        {"_id": 0, "internal_remarks": 0}
    ).sort("created_at", -1).to_list(50)
    return {"warnings": [serialize_doc(d) for d in docs]}


# Ensure indexes at import time
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(_ensure_indexes())
    else:
        loop.run_until_complete(_ensure_indexes())
except Exception:
    pass
