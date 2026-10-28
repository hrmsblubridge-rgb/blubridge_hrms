"""Payslip Module — Phase 1: templates CRUD, components, employee assignment
(effective dates + per-employee monthly pay), calculation engine preview.
Collections: payslip_templates, payslip_assignments, payslip_audit."""
import uuid
import calendar
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException, Depends, Query, Body

from server import (
    api_router, db, get_current_user, UserRole,
    calculate_payroll_for_employee,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hr_only(user):
    if user["role"] not in [UserRole.HR]:
        raise HTTPException(status_code=403, detail="Permission denied")


async def _audit(user, action, employee_id=None, ref_id=None, old=None, new=None):
    await db.payslip_audit.insert_one({
        "id": str(uuid.uuid4()), "user": user.get("username") or user.get("id"),
        "action": action, "employee_id": employee_id, "ref_id": ref_id,
        "old": old, "new": new, "ts": _now(),
    })


def _validate_components(components):
    if not isinstance(components, list) or not components:
        raise HTTPException(status_code=400, detail="Template needs at least one component")
    orders = set()
    for c in components:
        if not (c.get("name") or "").strip():
            raise HTTPException(status_code=400, detail="Component name required")
        if c.get("component_type") not in ("earning", "deduction"):
            raise HTTPException(status_code=400, detail=f"Invalid component_type for {c.get('name')}")
        if c.get("operation") not in ("add", "deduct"):
            raise HTTPException(status_code=400, detail=f"Invalid operation for {c.get('name')}")
        ct = c.get("calc_type")
        if ct not in ("percentage", "fixed", "payroll_extra_pay", "system"):
            raise HTTPException(status_code=400, detail=f"Invalid calc_type for {c.get('name')}")
        if ct == "percentage":
            pv = float(c.get("percentage_value") or 0)
            if pv <= 0 or pv > 100:
                raise HTTPException(status_code=400, detail=f"Percentage must be 0-100 for {c.get('name')}")
        if ct == "fixed" and float(c.get("fixed_amount") or 0) < 0:
            raise HTTPException(status_code=400, detail=f"Negative amount not allowed for {c.get('name')}")
        # PF-specific: base_percentage (0-100). Used when operation=deduct & the component represents PF.
        bp = c.get("base_percentage")
        if bp not in (None, ""):
            try:
                bpf = float(bp)
                if bpf < 0 or bpf > 100:
                    raise HTTPException(status_code=400, detail=f"base_percentage must be 0-100 for {c.get('name')}")
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Invalid base_percentage for {c.get('name')}")
        if c.get("max_amount") not in (None, "", 0) and float(c.get("max_amount") or 0) < 0:
            raise HTTPException(status_code=400, detail=f"max_amount cannot be negative for {c.get('name')}")
        o = int(c.get("display_order") or 0)
        if o in orders:
            raise HTTPException(status_code=400, detail=f"Duplicate display_order {o}")
        orders.add(o)
        c.setdefault("proratable", True)
        c.setdefault("active", True)
        c.setdefault("include_in_gross", c["operation"] == "add")
        c.setdefault("include_in_net", True)
        c.setdefault("category", "")


def _pf_eligible_names(components) -> list:
    """Earning components that may form the PF base (not PF/Gratuity/Extra Pay)."""
    return [(c.get("name") or "").strip() for c in components or []
            if c.get("operation") == "add" and c.get("component_type") == "earning"
            and c.get("calc_type") in ("percentage", "fixed") and c.get("active", True)
            and not _is_pf(c.get("name")) and not _is_gratuity(c.get("name"))]


def _validate_pf_config(pf, components, label="PF"):
    """Template-level configurable PF (percentage, cap, base components)."""
    if pf is None:
        return None
    if not isinstance(pf, dict):
        raise HTTPException(status_code=400, detail=f"Invalid {label} configuration")
    enabled = bool(pf.get("enabled"))
    out = {"enabled": enabled, "percentage": None, "max_amount": None, "components": []}
    if not enabled:
        return out
    cap_label = "Maximum PF Deduction" if label == "PF" else f"Maximum {label} Contribution"
    try:
        pct = float(pf.get("percentage"))
        cap = float(pf.get("max_amount"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{label} Percentage and {cap_label} must be valid numbers")
    if not (0 < pct <= 100):
        raise HTTPException(status_code=400, detail=f"{label} Percentage must be greater than 0 and at most 100")
    if cap <= 0:
        raise HTTPException(status_code=400, detail=f"{cap_label} must be greater than 0")
    names = [str(n).strip() for n in (pf.get("components") or []) if str(n).strip()]
    if not names:
        raise HTTPException(status_code=400, detail=f"Select at least one earning component for the {label} calculation")
    eligible = set(_pf_eligible_names(components))
    bad = [n for n in names if n not in eligible]
    if bad:
        raise HTTPException(status_code=400, detail=(
            f"{label} calculation component(s) not found among this template's earning components: {', '.join(bad)}. "
            f"Update the {label} component selection before saving."))
    out.update({"percentage": pct, "max_amount": cap, "components": list(dict.fromkeys(names))})
    return out


def _validate_gratuity(g, components):
    """Employer gratuity provision (employer cost — never an employee deduction)."""
    if g is None:
        return None
    if not isinstance(g, dict):
        raise HTTPException(status_code=400, detail="Invalid Gratuity configuration")
    out = {"enabled": bool(g.get("enabled")), "amount": None, "prorate": g.get("prorate", True) is not False}
    if not out["enabled"]:
        return out
    try:
        amt = float(g.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Gratuity provision amount must be a valid number")
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Gratuity provision amount must be greater than 0")
    ded = next((c for c in components if _is_gratuity(c.get("name")) and c.get("operation") == "deduct"
                and c.get("active", True)), None)
    if ded:
        raise HTTPException(status_code=400, detail=(
            f"Remove the '{ded['name']}' deduction component first — Gratuity is configured as an employer "
            "provision and must not also be deducted from the employee."))
    out["amount"] = amt
    return out


CALC_KEYS = ("components", "pf_config", "employer_pf_config", "gratuity_config", "auto_reconcile")


def _normalize_calc(cfg: dict) -> dict:
    """Validate one template version's calculation settings; returns the stored shape."""
    comps = cfg.get("components")
    _validate_components(comps)
    out = {"components": comps, "auto_reconcile": bool(cfg.get("auto_reconcile"))}
    pf = _validate_pf_config(cfg.get("pf_config"), comps)
    epf = _validate_pf_config(cfg.get("employer_pf_config"), comps, "Employer PF")
    gr = _validate_gratuity(cfg.get("gratuity_config"), comps)
    if pf is None and ((epf or {}).get("enabled") or (gr or {}).get("enabled") or out["auto_reconcile"]):
        raise HTTPException(status_code=400, detail=(
            "Turn on the configurable PF Configuration first — Employer PF, Gratuity provision and "
            "Auto Reconcile Gross Salary apply to configurable templates only."))
    for k, v in (("pf_config", pf), ("employer_pf_config", epf), ("gratuity_config", gr)):
        if v is not None:
            out[k] = v
    return out


def _valid_month(m) -> bool:
    try:
        return isinstance(m, str) and len(m) == 7 and 1 <= int(m[5:7]) <= 12 and m[4] == "-" and int(m[:4]) > 1900
    except ValueError:
        return False


def _mlabel(m: Optional[str]) -> str:
    if not m:
        return "Ongoing"
    return datetime(int(m[:4]), int(m[5:7]), 1).strftime("%B %Y")


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _next_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"


def _resolve_version(tpl: dict, month: str) -> dict:
    """Template version in force for a payslip month (latest effective_from_month <= month; else base v1)."""
    vs = sorted([v for v in tpl.get("versions") or [] if (v.get("effective_from_month") or "9999") <= month],
                key=lambda v: v["effective_from_month"])
    src = vs[-1] if vs else tpl
    return {"version_no": src.get("version_no", 1) if vs else 1,
            "effective_from_month": src.get("effective_from_month") if vs else None,
            **{k: src.get(k) for k in CALC_KEYS}}


def _calc_kwargs(version: dict) -> dict:
    return {"components": version["components"], "pf_config": version.get("pf_config"),
            "employer_pf_config": version.get("employer_pf_config"),
            "gratuity_config": version.get("gratuity_config"),
            "auto_reconcile": bool(version.get("auto_reconcile"))}


async def _audit_config_changes(user, ref_id, old: dict, new: dict, effective_from=None):
    for key, action in (("pf_config", "pf_config_updated"), ("employer_pf_config", "employer_pf_config_updated"),
                        ("gratuity_config", "gratuity_config_updated"), ("auto_reconcile", "auto_reconcile_updated")):
        if (old or {}).get(key) != new.get(key):
            await _audit(user, action, ref_id=ref_id, old=(old or {}).get(key),
                         new={"value": new.get(key), "effective_from": effective_from or "base version"})


@api_router.post("/payslips/templates")
async def create_payslip_template(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name required")
    if await db.payslip_templates.find_one({"name": name, "is_deleted": {"$ne": True}}):
        raise HTTPException(status_code=409, detail="Template with this name already exists")
    calc = _normalize_calc({k: payload.get(k) for k in CALC_KEYS})
    doc = {
        "id": str(uuid.uuid4()), "name": name,
        "description": payload.get("description") or "",
        "status": payload.get("status") or "Active",
        **calc, "versions": [],
        "is_deleted": False, "created_at": _now(), "updated_at": _now(),
    }
    await db.payslip_templates.insert_one(dict(doc))
    doc.pop("_id", None)
    await _audit(current_user, "template_created", ref_id=doc["id"], new=name)
    return doc


@api_router.get("/payslips/templates")
async def list_payslip_templates(current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    return await db.payslip_templates.find({"is_deleted": {"$ne": True}}, {"_id": 0}).sort("name", 1).to_list(200)


@api_router.put("/payslips/templates/{template_id}")
async def update_payslip_template(template_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Edit a template. Calculation settings go to: a NEW version (new_version_from=YYYY-MM),
    an existing later version (version_no>=2), or the base version 1 (default)."""
    _hr_only(current_user)
    tpl = await db.payslip_templates.find_one({"id": template_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    upd = {k: payload[k] for k in ("name", "description", "status") if k in payload}
    calc_in = {k: payload[k] for k in CALC_KEYS if k in payload}
    new_from = payload.get("new_version_from")
    vno = int(payload.get("version_no") or 1)
    versions = [dict(v) for v in tpl.get("versions") or []]
    unset, action, old_cfg, new_cfg, eff = {}, "template_edited", None, None, None
    if new_from:
        if not _valid_month(new_from):
            raise HTTPException(status_code=400, detail="New version Effective From must be a month (YYYY-MM)")
        if any(v.get("effective_from_month") == new_from for v in versions):
            raise HTTPException(status_code=409, detail=f"A version effective from {_mlabel(new_from)} already exists — edit that version instead")
        base = _resolve_version(tpl, new_from)
        new_cfg = _normalize_calc({**{k: base.get(k) for k in CALC_KEYS}, **calc_in})
        old_cfg, eff = base, new_from
        versions.append({"version_no": max([1] + [int(v.get("version_no") or 1) for v in versions]) + 1,
                         "effective_from_month": new_from, **new_cfg,
                         "created_by": current_user.get("username"), "created_at": _now()})
        versions.sort(key=lambda v: v["effective_from_month"])
        upd["versions"] = versions
        action = "template_version_created"
    elif calc_in and vno == 1:
        old_cfg = {k: tpl.get(k) for k in CALC_KEYS}
        new_cfg = _normalize_calc({**old_cfg, **calc_in})
        upd.update(new_cfg)
        unset = {k: "" for k in ("pf_config", "employer_pf_config", "gratuity_config") if k not in new_cfg and k in tpl}
    elif calc_in:
        idx = next((i for i, v in enumerate(versions) if int(v.get("version_no") or 0) == vno), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"Template version {vno} not found")
        old_cfg = {k: versions[idx].get(k) for k in CALC_KEYS}
        new_cfg = _normalize_calc({**old_cfg, **calc_in})
        keep = {k: versions[idx].get(k) for k in ("version_no", "effective_from_month", "created_by", "created_at")}
        versions[idx] = {**keep, **new_cfg, "updated_by": current_user.get("username"), "updated_at": _now()}
        upd["versions"] = versions
        action, eff = "template_version_updated", versions[idx]["effective_from_month"]
    upd["updated_at"] = _now()
    await db.payslip_templates.update_one({"id": template_id}, {"$set": upd, **({"$unset": unset} if unset else {})})
    await _audit(current_user, action, ref_id=template_id, old=tpl.get("name"),
                 new={"name": upd.get("name") or tpl.get("name"), "effective_from": eff,
                      "version_no": next((v["version_no"] for v in versions if v.get("effective_from_month") == new_from), None)
                      if new_from else vno})
    if new_cfg is not None:
        await _audit_config_changes(current_user, template_id, old_cfg, new_cfg, eff)
    return {"success": True}


@api_router.delete("/payslips/templates/{template_id}")
async def delete_payslip_template(template_id: str, current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    in_use = await db.payslip_assignments.count_documents({"template_id": template_id, "effective_to": None})
    if in_use:
        raise HTTPException(status_code=409, detail=f"Template is actively assigned to {in_use} employee(s). Reassign them first — template will be soft-deleted only.")
    await db.payslip_templates.update_one({"id": template_id}, {"$set": {"is_deleted": True, "status": "Inactive", "updated_at": _now()}})
    await _audit(current_user, "template_deleted", ref_id=template_id)
    return {"success": True}


def _assign_range(a: dict):
    """(from_month, to_month|None, superseded) for any assignment, incl. legacy records."""
    frm = a.get("effective_from_month") or (a.get("effective_from") or "")[:7]
    if "effective_to_month" in a:
        to = a.get("effective_to_month")
    elif a.get("effective_to"):
        to = _prev_month(a["effective_to"][:7])  # legacy: closed on the successor's start date
    else:
        to = None
    return frm, to, bool(a.get("superseded")) or bool(to and frm and to < frm)


def _ranges_overlap(f1, t1, f2, t2) -> bool:
    return f1 <= (t2 or "9999-12") and f2 <= (t1 or "9999-12")


def _resolve_eff_from(emp: dict, eff_type: str, value) -> tuple:
    """Effective From → (type, stored date YYYY-MM-DD, month YYYY-MM). Uses Employee Master dates."""
    t = (eff_type or "custom_month").lower()
    if t in ("joining_date", "joining_month"):
        d = (emp.get("date_of_joining") or "")[:10]
        if not d:
            raise HTTPException(status_code=400, detail=f"{emp.get('full_name')} has no Joining Date on record")
        return "joining_month", d, d[:7]
    if t in ("confirmation_date", "confirmation_month"):
        d = (emp.get("confirmation_date") or "")[:10]
        if not d:
            raise HTTPException(status_code=400, detail=f"{emp.get('full_name')} has no Confirmation Date; pick Joining Month or Custom Month")
        return "confirmation_month", d, d[:7]
    v = str(value or "")[:10]
    if not (v and _valid_month(v[:7])):
        raise HTTPException(status_code=400, detail="Custom Month requires an Effective From month")
    return ("custom_date" if len(v) == 10 else "custom_month"), (v if len(v) == 10 else f"{v}-01"), v[:7]


def _overlap_error(other: dict):
    f, t, _ = _assign_range(other)
    raise HTTPException(status_code=409, detail=(
        f"This period overlaps the existing assignment '{other.get('template_name')}' "
        f"({_mlabel(f)} – {_mlabel(t)}). Adjust that assignment's effective period first."))


async def _create_assignment(user, emp: dict, tpl: dict, monthly_pay: float, eff_type, eff_value,
                             to_month, ewc: str, bulk: bool = False) -> dict:
    eff_type, eff_from, from_m = _resolve_eff_from(emp, eff_type, eff_value)
    if to_month and not _valid_month(to_month):
        raise HTTPException(status_code=400, detail="Effective Until must be a month (YYYY-MM)")
    if to_month and to_month < from_m:
        raise HTTPException(status_code=400, detail=(
            f"Effective Until ({_mlabel(to_month)}) cannot be before Effective From ({_mlabel(from_m)})"))
    existing = [a for a in await db.payslip_assignments.find({"employee_id": emp["id"]}, {"_id": 0}).to_list(200)
                if not _assign_range(a)[2]]
    to_close = []
    for a in existing:
        f, t, _ = _assign_range(a)
        if to_month is None and t is None and a.get("effective_to") is None and f <= from_m:
            to_close.append((a, f))  # current ongoing assignment ends the month before the new one starts
        elif _ranges_overlap(from_m, to_month, f, t):
            _overlap_error(a)
    for a, f in to_close:
        sup = f == from_m
        await db.payslip_assignments.update_one({"id": a["id"]}, {"$set": {
            "effective_to": f"{from_m}-01", "effective_from_month": f, "effective_to_month": _prev_month(from_m),
            "closed_at": _now(), **({"superseded": True} if sup else {})}})
    doc = {
        "id": str(uuid.uuid4()), "employee_id": emp["id"], "template_id": tpl["id"],
        "template_name": tpl["name"], "monthly_pay": monthly_pay,
        "effective_from": eff_from, "effective_from_type": eff_type, "effective_from_month": from_m,
        "effective_to": f"{_next_month(to_month)}-01" if to_month else None, "effective_to_month": to_month,
        "extra_work_compensation": ewc,
        "assigned_by": user.get("username"), "created_at": _now(),
    }
    await db.payslip_assignments.insert_one(dict(doc))
    doc.pop("_id", None)
    old = to_close[0][0] if to_close else None
    action = "historical_assignment_added" if to_month else ("template_assigned_bulk" if bulk else "template_assigned")
    await _audit(user, action, employee_id=emp["id"], ref_id=doc["id"], old=(old or {}).get("template_name"),
                 new={"template": tpl["name"], "monthly_pay": monthly_pay, "from": from_m, "until": to_month})
    return doc


def _parse_pay(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_ewc(payload) -> str:
    ewc = (payload.get("extra_work_compensation") or "extra_pay").lower()
    if ewc not in ("extra_pay", "comp_off", "not_applicable"):
        raise HTTPException(status_code=400, detail="Invalid Extra Work Compensation option")
    return ewc


async def _active_template(tpl_id):
    tpl = await db.payslip_templates.find_one({"id": tpl_id, "is_deleted": {"$ne": True}, "status": "Active"},
                                              {"_id": 0, "id": 1, "name": 1})
    if not tpl:
        raise HTTPException(status_code=404, detail="Active template not found")
    return tpl


@api_router.post("/payslips/assignments")
async def assign_payslip_template(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    monthly_pay = _parse_pay(payload.get("monthly_pay"))
    if monthly_pay <= 0:
        raise HTTPException(status_code=400, detail="Monthly Pay must be greater than 0")
    emp = await db.employees.find_one({"id": payload.get("employee_id"), "is_deleted": {"$ne": True}}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    tpl = await _active_template(payload.get("template_id"))
    return await _create_assignment(current_user, emp, tpl, monthly_pay, payload.get("effective_from_type"),
                                    payload.get("effective_from"), payload.get("effective_to_month") or None,
                                    _parse_ewc(payload))


@api_router.get("/payslips/assignments")
async def list_payslip_assignments(q: Optional[str] = Query(None), department: Optional[str] = Query(None),
                                   team: Optional[str] = Query(None), employee_type: Optional[str] = Query(None),
                                   current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    equery = {"is_deleted": {"$ne": True}, "employee_status": "Active"}
    if department:
        equery["department"] = department
    if team:
        equery["team"] = team
    if employee_type:
        equery["employment_type"] = employee_type
    if q:
        equery["$or"] = [{"full_name": {"$regex": q, "$options": "i"}},
                         {"custom_employee_id": {"$regex": q, "$options": "i"}},
                         {"email": {"$regex": q, "$options": "i"}}]
    emps = await db.employees.find(equery, {"_id": 0, "id": 1, "full_name": 1, "custom_employee_id": 1,
                                            "department": 1, "team": 1, "designation": 1, "employment_type": 1,
                                            "date_of_joining": 1, "confirmation_date": 1}).sort("full_name", 1).to_list(500)
    assigns = {a["employee_id"]: a for a in await db.payslip_assignments.find(
        {"effective_to": None}, {"_id": 0}).to_list(1000)}
    out = []
    for e in emps:
        a = assigns.get(e["id"])
        out.append({**e, "assignment": a})
    return out


@api_router.post("/payslips/assignments/bulk")
async def bulk_assign_payslip_template(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Assign one template to many employees at once. items=[{employee_id, monthly_pay}]"""
    _hr_only(current_user)
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="No employees selected")
    tpl = await _active_template(payload.get("template_id"))
    ewc = _parse_ewc(payload)
    eff_value = payload.get("effective_from") or _now()[:10]
    assigned, errors = 0, []
    for it in items:
        emp_id = it.get("employee_id")
        mp = _parse_pay(it.get("monthly_pay"))
        emp = await db.employees.find_one({"id": emp_id, "is_deleted": {"$ne": True}}, {"_id": 0})
        if not emp:
            errors.append({"employee_id": emp_id, "error": "Employee not found"})
            continue
        if mp <= 0:
            errors.append({"employee_id": emp_id, "name": emp["full_name"], "error": "Monthly Pay must be greater than 0"})
            continue
        try:
            await _create_assignment(current_user, emp, tpl, mp, payload.get("effective_from_type"), eff_value,
                                     payload.get("effective_to_month") or None, ewc, bulk=True)
        except HTTPException as ex:
            errors.append({"employee_id": emp_id, "name": emp["full_name"], "error": str(ex.detail)})
            continue
        assigned += 1
    return {"assigned": assigned, "errors": errors}


@api_router.get("/payslips/assignments/{employee_id}/history")
async def assignment_history(employee_id: str, current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    rows = await db.payslip_assignments.find({"employee_id": employee_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for a in rows:
        f, t, sup = _assign_range(a)
        a.update({"from_month": f, "to_month": t, "superseded": sup})
    return rows


@api_router.put("/payslips/assignments/{assignment_id}/period")
async def update_assignment_period(assignment_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Change an assignment's effective months (inclusive). Confirmed payslips keep their own snapshot."""
    _hr_only(current_user)
    a = await db.payslip_assignments.find_one({"id": assignment_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if _assign_range(a)[2]:
        raise HTTPException(status_code=400, detail="This assignment was superseded and is not used for any month")
    frm, to = payload.get("effective_from_month"), payload.get("effective_to_month") or None
    if not _valid_month(frm) or (to and not _valid_month(to)):
        raise HTTPException(status_code=400, detail="Effective From / Until must be months (YYYY-MM)")
    if to and to < frm:
        raise HTTPException(status_code=400, detail=f"Effective Until ({_mlabel(to)}) cannot be before Effective From ({_mlabel(frm)})")
    for o in await db.payslip_assignments.find({"employee_id": a["employee_id"], "id": {"$ne": assignment_id}}, {"_id": 0}).to_list(200):
        f, t, sup = _assign_range(o)
        if not sup and _ranges_overlap(frm, to, f, t):
            _overlap_error(o)
    old = dict(zip(("from", "until"), _assign_range(a)[:2]))
    await db.payslip_assignments.update_one({"id": assignment_id}, {"$set": {
        "effective_from_month": frm, "effective_from": f"{frm}-01", "effective_from_type": "custom_month",
        "effective_to_month": to, "effective_to": f"{_next_month(to)}-01" if to else None, "updated_at": _now()}})
    await _audit(current_user, "assignment_period_changed", employee_id=a["employee_id"], ref_id=assignment_id,
                 old=old, new={"from": frm, "until": to})
    return {"success": True}


async def _resolve_assignment(emp_id: str, month: str, rows: Optional[list] = None) -> Optional[dict]:
    """The single assignment covering a payslip month (latest start wins; superseded ignored)."""
    if rows is None:
        rows = await db.payslip_assignments.find({"employee_id": emp_id}, {"_id": 0}).to_list(200)
    cands = []
    for a in rows:
        f, t, sup = _assign_range(a)
        if not sup and f and f <= month and (t is None or t >= month):
            cands.append((f, a.get("created_at") or "", a))
    return max(cands, key=lambda x: (x[0], x[1]))[2] if cands else None


PF_CAP_MONTHLY = 1800.0  # Statutory PF (Employer/EPS) monthly cap on 12% of Basic


def _norm(n: str) -> str:
    return (n or "").lower().strip()


def _is_basic(n: str) -> bool:
    s = _norm(n)
    return s == "basic" or s == "basic salary"


def _is_hra(n: str) -> bool:
    s = _norm(n)
    return "hra" in s or "house rent" in s


def _is_pf(n: str) -> bool:
    s = _norm(n)
    return "pf" in s or "provident fund" in s


def _is_gratuity(n: str) -> bool:
    return "gratuity" in _norm(n)


_FLEX_KEYWORDS = ("leave travel", "phone", "bonus", "stay", "special", "food")


def _is_flex(n: str) -> bool:
    if _is_basic(n) or _is_hra(n) or _is_pf(n) or _is_gratuity(n):
        return False
    s = _norm(n)
    return any(k in s for k in _FLEX_KEYWORDS)


def _is_special(n: str) -> bool:
    s = _norm(n)
    return "special" in s and "allowance" in s


def _infer_category(n: str) -> str:
    if _is_basic(n) or _is_hra(n):
        return "Base Components (A)"
    if _is_pf(n) or _is_gratuity(n):
        return "Retirement Benefits (C)"
    return "Basket of Allowances (B)"


def _component_full_month(c: dict, monthly_pay: float, resolved: dict, per_day: float, extra_pay_days: float) -> float:
    ct = c.get("calc_type")
    if ct == "percentage":
        base_key = c.get("calc_base") or "monthly_pay"
        base = monthly_pay if base_key == "monthly_pay" else resolved.get(base_key, {}).get("monthly", 0.0)
        return base * float(c.get("percentage_value") or 0) / 100.0
    if ct == "fixed":
        return float(c.get("fixed_amount") or 0)
    if ct == "payroll_extra_pay":
        return per_day * float(extra_pay_days or 0)
    return 0.0


GRATUITY_FULL_MONTH_DEFAULT = 793.0  # Full-month reference gratuity amount (per PRD v6)


def _money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_payslip(monthly_pay: float, components: list, month: str, payable_days: float,
                    extra_pay_days: float, extra_work_compensation: str = "extra_pay",
                    pf_config: Optional[dict] = None, employer_pf_config: Optional[dict] = None,
                    gratuity_config: Optional[dict] = None, auto_reconcile: bool = False) -> dict:
    """Payroll-first calculation engine (PRD v6 · 2026-08-19).

    Sequence (do NOT change):
      1. Per-Day Salary          = monthly_pay / cal_days
      2. Attendance Payable      = per_day × payable_days       ← core salary for the month
      3. PF                       = min(attendance_payable / 2 × 12%, ₹1,800)
      4. Gratuity                 = round((gratuity_full / cal_days) × payable_days)
      5. Extra Pay                = per_day × extra_pay_days
      6. Gross Earnings           = attendance_payable + extra_pay
      7. Total Deductions         = PF + Gratuity
      8. Net Pay                  = Gross Earnings − Total Deductions
      9. Split attendance_payable into template earning components by their weights;
         rounding balance to Special Allowance so components sum to attendance_payable exactly.
      10. Extra Pay is displayed separately as "Other Allowance" — never split across components.

    PF and Gratuity are calculated BEFORE the component split and are NOT part of the
    template earnings percentage (i.e. earnings sum to 100% of attendance_payable, PF and
    Gratuity are separate deductions).
    """
    y, m = int(month[:4]), int(month[5:7])
    cal_days = calendar.monthrange(y, m)[1]
    if cal_days <= 0 or monthly_pay <= 0:
        raise HTTPException(status_code=400, detail="Invalid month or monthly pay")

    per_day = float(monthly_pay) / cal_days
    payable = max(0.0, float(payable_days or 0))
    extra_days = max(0.0, float(extra_pay_days or 0))
    if isinstance(pf_config, dict) and "enabled" in pf_config:
        return _compute_configured(monthly_pay, components, month, cal_days, payable, extra_days,
                                   (extra_work_compensation or "extra_pay").lower(), pf_config,
                                   employer_pf_config, gratuity_config, auto_reconcile)

    active = sorted([c for c in components if c.get("active", True)],
                    key=lambda x: int(x.get("display_order") or 0))

    # --- Step 1-2: Attendance payable salary ---
    attendance_payable = per_day * payable

    # --- Step 3: PF (template-driven, optional) ---
    # PF only applies when template has a PF component (name contains 'pf'/'provident').
    # base_percentage (default 100%) defines what portion of attendance_payable is the PF base.
    # percentage_value defines contribution % (default 12%). ₹1,800 cap applied unless template
    # explicitly disables it (apply_pf_cap=False).
    pf_component = next((c for c in active if _is_pf(c["name"])
                         and c.get("operation") == "deduct"
                         and c.get("active", True)), None)
    pf_final = 0.0
    pf_raw = 0.0
    pf_base = 0.0
    pf_capped = False
    pf_base_pct = None
    pf_contrib_pct = None
    if pf_component:
        pf_base_pct = float(pf_component.get("base_percentage") or 100.0)
        pf_contrib_pct = float(pf_component.get("percentage_value") or 12.0)
        pf_base = attendance_payable * pf_base_pct / 100.0
        pf_raw = pf_base * pf_contrib_pct / 100.0
        apply_cap = pf_component.get("apply_pf_cap", True) is not False
        pf_final = min(pf_raw, PF_CAP_MONTHLY) if apply_cap else pf_raw
        pf_capped = apply_cap and pf_raw > PF_CAP_MONTHLY

    # --- Step 4: Gratuity (template-driven, optional) ---
    gratuity_component = next((c for c in active if _is_gratuity(c["name"])
                               and c.get("operation") == "deduct"
                               and c.get("active", True)), None)
    gratuity_full, gratuity_raw, gratuity_final = 0.0, 0.0, 0
    if gratuity_component:
        gratuity_full, gratuity_raw, gratuity_final = _legacy_gratuity(gratuity_component, monthly_pay, cal_days, payable)

    # --- Step 5: Extra pay (only when assignment says "extra_pay") ---
    ewc = (extra_work_compensation or "extra_pay").lower()
    effective_extra_days = extra_days if ewc == "extra_pay" else 0.0
    extra_pay = round(per_day * effective_extra_days, 2)

    # --- Steps 6-8: Preliminary totals (finalized after generic deductions emit) ---
    gross_earnings = round(attendance_payable + extra_pay, 2)
    total_deductions_prelim = round(pf_final + gratuity_final, 2)

    # --- Step 9: Split attendance_payable into template earning components ---
    # Earning = add operations, not PF/Gratuity/Extra_pay.
    earning_components = [
        c for c in active
        if c.get("operation") == "add"
        and c.get("calc_type") != "payroll_extra_pay"
        and not _is_pf(c["name"])
        and not _is_gratuity(c["name"])
    ]

    # Each earning's implied full-month value (from template % or fixed).
    tmpl_full = {}
    for c in earning_components:
        ct = c.get("calc_type")
        if ct == "percentage":
            tmpl_full[c["name"]] = float(monthly_pay) * float(c.get("percentage_value") or 0) / 100.0
        elif ct == "fixed":
            tmpl_full[c["name"]] = float(c.get("fixed_amount") or 0)
        else:
            tmpl_full[c["name"]] = 0.0
    tmpl_total = sum(tmpl_full.values())

    split_amounts = {n: 0.0 for n in tmpl_full}
    if tmpl_total > 0.001 and attendance_payable > 0.001:
        special_name = next((n for n in tmpl_full if _is_special(n)), None)
        running = 0.0
        for name, val in tmpl_full.items():
            if name == special_name:
                continue
            share = round(attendance_payable * val / tmpl_total, 2)
            split_amounts[name] = share
            running += share
        if special_name is not None:
            # Special Allowance absorbs any rounding balance so sum = attendance_payable exactly.
            split_amounts[special_name] = round(attendance_payable - running, 2)
        elif earning_components:
            first_name = earning_components[0]["name"]
            split_amounts[first_name] = round(split_amounts[first_name] + (attendance_payable - running), 2)

    # --- Emit line items ---
    lines = []
    for c in active:
        name = c["name"]
        ct = c.get("calc_type")
        proratable = c.get("proratable", True)
        deduct_amount = None
        auto_note = None
        if _is_pf(name):
            monthly_amt = pf_final
            amount = round(pf_final, 2)
            deduct_amount = round(pf_final, 2)
            if pf_component:
                cap_txt = f", capped at ₹{PF_CAP_MONTHLY:,.0f}" if pf_capped else ""
                auto_note = (
                    f"{pf_contrib_pct:.2f}% of (Attendance Payable ₹{attendance_payable:,.2f} × {pf_base_pct:.2f}% = ₹{pf_base:,.2f})"
                    f" = ₹{pf_raw:,.2f}{cap_txt}"
                )
            operation = "deduct"
            include_gross = False
        elif _is_gratuity(name):
            monthly_amt = gratuity_full
            amount = float(gratuity_final)
            deduct_amount = float(gratuity_final)
            _pd = int(payable) if payable == int(payable) else payable
            if gratuity_component and gratuity_component.get("calc_type") == "fixed":
                auto_note = f"(₹{gratuity_full:,.2f} / {cal_days}) × {_pd} = ₹{gratuity_raw:,.2f} → rounded ₹{gratuity_final:,.0f}"
            elif gratuity_component:
                auto_note = f"{gratuity_component.get('percentage_value')}% of Monthly Pay = ₹{gratuity_raw:,.2f} → rounded ₹{gratuity_final:,.0f}"
            operation = "deduct"
            include_gross = False
        elif c.get("operation") == "deduct":
            monthly_amt, amount, auto_note = _generic_deduction(c, monthly_pay, attendance_payable, payable, cal_days)
            deduct_amount = amount
            operation = "deduct"
            include_gross = False
        elif ct == "payroll_extra_pay":
            monthly_amt = per_day * effective_extra_days
            amount = extra_pay
            operation = "add"
            include_gross = True
            _ed = int(effective_extra_days) if effective_extra_days == int(effective_extra_days) else effective_extra_days
            if ewc == "extra_pay":
                auto_note = f"Per-Day ₹{per_day:,.2f} × {_ed} extra day(s)"
            else:
                auto_note = f"Comp-Off mode — no monetary extra pay"
        else:
            monthly_amt = tmpl_full.get(name, 0.0)
            amount = round(split_amounts.get(name, 0.0), 2)
            pct_of_total = (tmpl_full[name] / tmpl_total * 100.0) if tmpl_total > 0 else 0.0
            auto_note = f"{pct_of_total:.2f}% of Attendance Payable ₹{attendance_payable:,.2f}"
            operation = c.get("operation", "add")
            include_gross = True
        lines.append({
            "name": name,
            "component_type": c.get("component_type"),
            "operation": operation,
            "calc_type": ct,
            "percentage_value": c.get("percentage_value"),
            "calc_base": c.get("calc_base"),
            "monthly_amount": round(monthly_amt, 2),
            "amount": amount,
            "deduct_amount": deduct_amount,
            "proratable": proratable,
            "include_in_gross": bool(include_gross),
            "category": _infer_category(name),
            "capped": _is_pf(name) and pf_capped,
            "auto_note": auto_note,
            "redistribution_adjustment": 0.0,
        })

    # Recompute totals from emitted lines so ALL configured deductions (including generic
    # TDS/PT/ESI/Other) participate — not just PF and Gratuity.
    total_deductions = round(sum((l.get("deduct_amount") if l.get("deduct_amount") is not None else 0.0)
                                 for l in lines if l["operation"] == "deduct"), 2)
    net_pay = round(gross_earnings - total_deductions, 2)
    net_pay_rounded = round(net_pay)

    # Reconciliation
    split_sum = round(sum(v for v in split_amounts.values()), 2)
    return {
        "month": month, "calendar_days": cal_days, "payable_days": payable_days,
        "extra_pay_days": effective_extra_days, "extra_pay_days_raw": extra_pay_days,
        "extra_work_compensation": ewc,
        "monthly_pay": monthly_pay,
        "per_day_salary": round(per_day, 4),
        "attendance_payable": round(attendance_payable, 2),
        "components": lines,
        "gross_earnings": gross_earnings,
        "total_deductions": total_deductions,
        "other_allowance": extra_pay,
        "net_pay": net_pay,
        "net_pay_rounded": net_pay_rounded,
        "reconciliation": {
            "per_day_salary": round(per_day, 4),
            "attendance_payable": round(attendance_payable, 2),
            "pf_base": round(pf_base, 2),
            "pf_raw": round(pf_raw, 2),
            "pf_final": round(pf_final, 2),
            "pf_capped": pf_capped,
            "gratuity_full_month": round(gratuity_full, 2),
            "gratuity_raw": round(gratuity_raw, 2),
            "gratuity_final": float(gratuity_final),
            "extra_pay": extra_pay,
            "template_split_total": split_sum,
            "template_earnings_percent_sum": round(sum(
                (c.get("percentage_value") or 0) for c in earning_components
                if c.get("calc_type") == "percentage"
            ), 4),
            "matches_attendance_payable": abs(split_sum - round(attendance_payable, 2)) < 0.02,
        },
    }


def _generic_deduction(c: dict, monthly_pay: float, attendance_payable: float, payable: float, cal_days: int):
    """Non-PF, non-Gratuity template deduction (TDS, PT, ESI, Other) → (monthly, amount, note)."""
    ct = c.get("calc_type")
    proratable = c.get("proratable", True)
    if ct == "percentage":
        base_key = c.get("calc_base") or "monthly_pay"
        base_val = attendance_payable if base_key in ("attendance_payable", "payable_amount") else float(monthly_pay)
        monthly_amt = base_val * float(c.get("percentage_value") or 0) / 100.0
        if proratable and base_key != "attendance_payable":
            monthly_amt = monthly_amt * (payable / cal_days if cal_days else 1)
        amount = round(monthly_amt, 2)
    elif ct == "fixed":
        fx = float(c.get("fixed_amount") or 0)
        monthly_amt = (fx / cal_days) * payable if (proratable and cal_days) else fx
        amount = round(monthly_amt, 2)
    else:
        monthly_amt, amount = 0.0, 0.0
    note = f"{c.get('percentage_value')}% of {c.get('calc_base') or 'monthly_pay'}" if ct == "percentage" else f"Fixed ₹{c.get('fixed_amount')}"
    return monthly_amt, amount, note


def _balance(amounts: dict, target: Decimal, keys: list) -> None:
    """Assign the paise remainder deterministically — Special Allowance, else the largest component."""
    keys = [k for k in keys if k in amounts]
    diff = target - sum(amounts.values(), Decimal("0"))
    if diff == 0 or not keys:
        return
    k = next((n for n in keys if _is_special(n)), None) or max(keys, key=lambda n: amounts[n])
    amounts[k] += diff


def _pf_calc(cfg: Optional[dict], payable_amt: dict) -> Optional[dict]:
    if not (cfg and cfg.get("enabled")):
        return None
    by_trim = {n.strip(): n for n in payable_amt}
    sel = [by_trim[n] for n in cfg.get("components") or [] if n in by_trim]
    base = sum((payable_amt[n] for n in sel), Decimal("0"))
    raw = _money(base * Decimal(str(cfg.get("percentage") or 0)) / Decimal("100"))
    cap = _money(cfg.get("max_amount") or 0)
    return {"base": base, "raw": raw, "final": min(raw, cap), "capped": raw > cap, "components": sel,
            "percentage": float(cfg.get("percentage") or 0), "max_amount": float(cfg.get("max_amount") or 0)}


def _pf_note(r: dict) -> str:
    cap_txt = f", capped at ₹{r['max_amount']:,.2f}" if r["capped"] else ""
    return (f"{r['percentage']:g}% of PF Base ₹{float(r['base']):,.2f} "
            f"({' + '.join(r['components']) or 'no components'}) = ₹{float(r['raw']):,.2f}{cap_txt}")


def _compute_configured(monthly_pay: float, components: list, month: str, cal_days: int, payable: float,
                        extra_days: float, ewc: str, pf_config: dict, employer_pf_config: Optional[dict],
                        gratuity_config: Optional[dict], auto_reconcile: bool) -> dict:
    """Configurable salary structure (template pf_config present):
    full-month breakup (strict or auto-reconciled) → prorate by Payroll payable days → PF on payable
    selected components (capped) → employer PF & gratuity reported separately → Net Pay."""
    D = Decimal
    active = sorted([c for c in components if c.get("active", True)], key=lambda x: int(x.get("display_order") or 0))
    gross = _money(monthly_pay)
    earn = [c for c in active if c.get("operation") == "add" and c.get("calc_type") in ("percentage", "fixed")
            and not _is_pf(c["name"]) and not _is_gratuity(c["name"])]
    order = [c["name"] for c in earn]
    pct = {c["name"]: D(str(c.get("percentage_value") or 0)) for c in earn if c["calc_type"] == "percentage"}
    full = {c["name"]: (_money(c.get("fixed_amount") or 0) if c["calc_type"] == "fixed" else D("0.00")) for c in earn}
    fixed_total = sum((full[n] for n in order if n not in pct), D("0"))
    if fixed_total > gross:
        raise HTTPException(status_code=400, detail=(
            f"Fixed regular earnings total ₹{fixed_total:,.2f}, which exceeds the Monthly Gross Salary ₹{gross:,.2f}. "
            "Reduce the fixed earning amounts in the template."))
    if auto_reconcile:
        remaining, psum = gross - fixed_total, sum(pct.values(), D("0"))
        if remaining > 0 and psum <= 0:
            raise HTTPException(status_code=400, detail=(
                f"₹{remaining:,.2f} of the Monthly Gross Salary is unallocated and the template has no "
                "percentage-based earning components to reconcile it. Add a percentage component or adjust the fixed amounts."))
        for n, p in pct.items():
            full[n] = _money(remaining * p / psum) if psum > 0 else D("0.00")
        _balance(full, gross, [n for n in order if n in pct])
    else:
        for n, p in pct.items():
            full[n] = _money(gross * p / D("100"))
        total = sum(full.values(), D("0"))
        if abs(total - gross) > D("1.00"):
            raise HTTPException(status_code=400, detail=(
                f"Template earning components total ₹{total:,.2f} but the Monthly Gross Salary is "
                f"₹{gross:,.2f}. Update the template so the earning components add up to the Gross Salary, "
                "or turn on Auto Reconcile Gross Salary."))
        _balance(full, gross, order)
    template_total = sum(full.values(), D("0"))

    # Prorate by Payroll payable days (LOP is applied here only — never deducted again).
    factor = D(str(payable)) / D(cal_days)
    prorate = {c["name"]: c.get("proratable", True) is not False for c in earn}
    pay, exact = {}, D("0")
    for n in order:
        if prorate[n]:
            pay[n] = _money(full[n] * factor)
            exact += full[n] * factor
        else:
            pay[n] = full[n]
    _balance(pay, _money(exact) + sum((full[n] for n in order if not prorate[n]), D("0")),
             [n for n in order if prorate[n]])
    regular_payable = sum(pay.values(), D("0"))

    per_day = D(str(monthly_pay)) / D(cal_days)
    eff_extra = extra_days if ewc == "extra_pay" else 0.0
    extra_pay = float(_money(per_day * D(str(eff_extra))))

    emp_pf = _pf_calc(pf_config, pay)
    er_pf = _pf_calc(employer_pf_config, pay)
    gr = None
    if gratuity_config and gratuity_config.get("enabled"):
        g_full = _money(gratuity_config.get("amount") or 0)
        g_prorate = gratuity_config.get("prorate", True) is not False
        gr = {"full": g_full, "amount": _money(g_full * factor) if g_prorate else g_full, "prorate": g_prorate}
    _pd = int(payable) if payable == int(payable) else payable

    pf_component = next((c for c in active if _is_pf(c["name"]) and c.get("operation") == "deduct"), None)
    rows = list(active)
    if emp_pf and not pf_component:
        rows.append({"name": "PF", "component_type": "deduction", "operation": "deduct", "calc_type": "system",
                     "active": True, "proratable": True})
    lines = []
    for c in rows:
        name, ct, proratable = c["name"], c.get("calc_type"), c.get("proratable", True)
        deduct_amount, include_gross, operation = None, False, "deduct"
        if _is_pf(name) and c.get("operation") == "deduct":
            amt = float(emp_pf["final"]) if emp_pf else 0.0
            monthly_amt, amount, deduct_amount = amt, amt, amt
            auto_note = _pf_note(emp_pf) if emp_pf else "PF disabled in template"
        elif _is_gratuity(name) and c.get("operation") == "deduct":
            if gr:
                continue  # employer provision configured — never also deducted from the employee
            g_full, g_raw, g_final = _legacy_gratuity(c, monthly_pay, cal_days, payable)
            monthly_amt, amount, deduct_amount = g_full, float(g_final), float(g_final)
            auto_note = f"Employee deduction (existing template setting) = ₹{g_raw:,.2f} → rounded ₹{g_final:,.0f}"
        elif c.get("operation") == "deduct":
            monthly_amt, amount, auto_note = _generic_deduction(c, monthly_pay, float(regular_payable), payable, cal_days)
            deduct_amount = amount
        elif ct == "payroll_extra_pay":
            monthly_amt, amount, operation, include_gross = float(per_day * D(str(eff_extra))), extra_pay, "add", True
            _ed = int(eff_extra) if eff_extra == int(eff_extra) else eff_extra
            auto_note = (f"Per-Day ₹{float(per_day):,.2f} × {_ed} extra day(s)" if ewc == "extra_pay"
                         else "Comp-Off mode — no monetary extra pay")
        elif name in full:
            monthly_amt, amount, operation, include_gross = float(full[name]), float(pay[name]), "add", True
            share = f"{pct[name]}% weight, reconciled" if (auto_reconcile and name in pct) else (
                f"{pct[name]}% of Gross" if name in pct else "Fixed")
            auto_note = (f"{share} · ₹{full[name]:,.2f} × {_pd}/{cal_days} days" if prorate[name]
                         else f"{share} · not prorated")
        else:
            monthly_amt, amount, operation, include_gross, auto_note = 0.0, 0.0, "add", True, "Not part of the salary breakup"
        lines.append({
            "name": name, "component_type": c.get("component_type"), "operation": operation, "calc_type": ct,
            "percentage_value": c.get("percentage_value"), "calc_base": c.get("calc_base"),
            "monthly_amount": round(monthly_amt, 2), "amount": amount, "deduct_amount": deduct_amount,
            "proratable": proratable, "include_in_gross": bool(include_gross), "category": _infer_category(name),
            "capped": bool(_is_pf(name) and emp_pf and emp_pf["capped"]), "auto_note": auto_note,
            "redistribution_adjustment": 0.0,
        })

    employer = []
    if er_pf:
        employer.append({"name": "Employer PF Contribution", "amount": float(er_pf["final"]), "auto_note": _pf_note(er_pf)})
    if gr:
        employer.append({"name": "Gratuity (Employer Provision)", "amount": float(gr["amount"]),
                         "auto_note": (f"₹{gr['full']:,.2f} × {_pd}/{cal_days} days" if gr["prorate"] else "Full-month provision")})
    warnings = []
    for label, r in (("Employee PF", emp_pf), ("Employer PF", er_pf)):
        if not r:
            continue
        if r["percentage"] != 12:
            warnings.append(f"{label} rate {r['percentage']:g}% differs from the standard 12% EPF rate — review statutory compliance.")
        if r["final"] < min(r["raw"], D("1800.00")):
            warnings.append(f"{label} ₹{float(r['final']):,.2f} is below ₹1,800 (12% of the ₹15,000 EPF wage ceiling) "
                            "because of the configured maximum — review statutory compliance.")

    gross_earnings = round(float(regular_payable) + extra_pay, 2)
    total_deductions = round(sum(l["deduct_amount"] or 0.0 for l in lines if l["operation"] == "deduct"), 2)
    net_pay = round(gross_earnings - total_deductions, 2)
    return {
        "month": month, "calendar_days": cal_days, "payable_days": payable,
        "extra_pay_days": eff_extra, "extra_pay_days_raw": extra_days, "extra_work_compensation": ewc,
        "monthly_pay": monthly_pay, "per_day_salary": round(float(per_day), 4),
        "attendance_payable": float(regular_payable), "regular_gross_payable": float(regular_payable),
        "lop_amount": float(gross - regular_payable) if regular_payable <= gross else 0.0,
        "components": lines, "gross_earnings": gross_earnings, "total_deductions": total_deductions,
        "other_allowance": extra_pay, "net_pay": net_pay, "net_pay_rounded": round(net_pay),
        "calc_model": "configured", "employer_contributions": employer,
        "employer_cost_total": round(sum(e["amount"] for e in employer), 2), "warnings": warnings,
        "reconciliation": {
            "pf_model": "template_config", "auto_reconcile": bool(auto_reconcile),
            "per_day_salary": round(float(per_day), 4), "attendance_payable": float(regular_payable),
            "gross_template_total": float(template_total), "matches_monthly_gross": template_total == gross,
            "pf_enabled": bool(emp_pf), "pf_percentage": pf_config.get("percentage"),
            "pf_max_amount": pf_config.get("max_amount"), "pf_components": emp_pf["components"] if emp_pf else [],
            "pf_base": float(emp_pf["base"]) if emp_pf else 0.0, "pf_raw": float(emp_pf["raw"]) if emp_pf else 0.0,
            "pf_final": float(emp_pf["final"]) if emp_pf else 0.0, "pf_capped": bool(emp_pf and emp_pf["capped"]),
            "employer_pf_final": float(er_pf["final"]) if er_pf else 0.0,
            "gratuity_final": float(gr["amount"]) if gr else 0.0,
            "extra_pay": extra_pay, "template_split_total": float(regular_payable),
            "matches_attendance_payable": True,
        },
    }


def _legacy_gratuity(c: dict, monthly_pay: float, cal_days: int, payable: float):
    """Template Gratuity *deduction* component (existing behaviour) → (full, raw, rounded)."""
    ct = c.get("calc_type")
    pr = c.get("proratable", True)
    if ct == "fixed":
        full = float(c.get("fixed_amount") or 0)
        raw = (full / cal_days) * payable if (cal_days and pr) else full
    elif ct == "percentage":
        full = float(monthly_pay) * float(c.get("percentage_value") or 0) / 100.0
        raw = full * (payable / cal_days if (cal_days and pr) else 1)
    else:
        full, raw = 0.0, 0.0
    return full, raw, round(raw)


async def _payslip_for_month(emp: dict, month: str, assign: Optional[dict], tpl_cache: dict) -> dict:
    """Shared engine for Preview, Generate and Regenerate — one calculation path for every output."""
    label = f"{emp.get('full_name')} ({emp.get('custom_employee_id') or emp.get('id')})"
    if not assign:
        raise HTTPException(status_code=400, detail=f"No Payslip Template assignment is available for Employee {label} for {_mlabel(month)}.")
    tpl = tpl_cache.get(assign["template_id"])
    if not tpl:
        raise HTTPException(status_code=400, detail=f"Assigned template '{assign.get('template_name')}' no longer exists")
    if not assign.get("monthly_pay") or float(assign["monthly_pay"]) <= 0:
        raise HTTPException(status_code=400, detail=f"No valid Monthly Gross Salary is recorded for {label} for {_mlabel(month)}.")
    version = _resolve_version(tpl, month)
    payroll = await calculate_payroll_for_employee(emp["id"], month, employee=emp)
    if not payroll:
        raise HTTPException(status_code=400, detail="No payroll data (check joining/relieving dates for this month)")
    if payroll.get("final_payable_days") is None:
        raise HTTPException(status_code=400, detail=f"Payroll payable days are missing for {label} for {_mlabel(month)}.")
    cal_days = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
    payable = float(payroll["final_payable_days"])
    if payable < 0 or payable > cal_days:
        raise HTTPException(status_code=400, detail=(
            f"Payroll payable days ({payable:g}) are outside 0–{cal_days} for {label} for {_mlabel(month)} — correct the Payroll data."))
    calc = compute_payslip(monthly_pay=float(assign["monthly_pay"]), month=month, payable_days=payable,
                           extra_pay_days=float(payroll.get("extra_pay") or 0),
                           extra_work_compensation=assign.get("extra_work_compensation") or "extra_pay",
                           **_calc_kwargs(version))
    calc["template_version"] = {"version_no": version["version_no"], "effective_from_month": version["effective_from_month"]}
    return {"calc": calc, "payroll": payroll, "tpl": tpl, "version": version}


@api_router.post("/payslips/calculate")
async def calculate_payslip_preview(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Preview calculation for one employee+month using the month's assignment, template version and Payroll."""
    _hr_only(current_user)
    emp_id = payload.get("employee_id")
    month = payload.get("month")  # YYYY-MM
    if not _valid_month(month):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    emp = await db.employees.find_one({"id": emp_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    assign = await _resolve_assignment(emp_id, month)
    tpl_cache = {}
    if assign:
        t = await db.payslip_templates.find_one({"id": assign["template_id"], "is_deleted": {"$ne": True}}, {"_id": 0})
        tpl_cache = {t["id"]: t} if t else {}
    r = await _payslip_for_month(emp, month, assign, tpl_cache)
    result = r["calc"]
    result.update({"employee_id": emp_id, "template_id": r["tpl"]["id"], "template_name": r["tpl"]["name"],
                   "monthly_pay": float(assign["monthly_pay"])})
    return result


# ============================ PHASE 2 ============================
from datetime import date
from zoneinfo import ZoneInfo
from fastapi.responses import Response
from payslip_pdf import build_payslip_pdf

IST = ZoneInfo("Asia/Kolkata")
_PAYROLL_META_KEYS = ("total_days", "working_days", "weekoff_pay", "extra_pay", "oh_pay",
                      "lop", "final_payable_days", "present_days", "leave_days", "absent_days")


def _visible_from(month: str) -> date:
    y, m = int(month[:4]), int(month[5:7])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return date(ny, nm, 5)


def _is_visible_to_employee(month: str) -> bool:
    return datetime.now(IST).date() >= _visible_from(month)


@api_router.post("/payslips/generate")
async def generate_payslips(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Generate/regenerate draft payslips for a (current or past) month using each employee's
    assignment and template version effective for THAT month. Confirmed payslips are never touched."""
    _hr_only(current_user)
    month = payload.get("month")
    if not _valid_month(month):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    only_ids = payload.get("employee_ids")
    q = {"employee_id": {"$in": list(only_ids)}} if only_ids else {}
    by_emp = {}
    for a in await db.payslip_assignments.find(q, {"_id": 0}).to_list(5000):
        by_emp.setdefault(a["employee_id"], []).append(a)
    # Employees with an assignment covering this month, or a current assignment (missing month → clear error).
    targets = {}
    for emp_id, rows in by_emp.items():
        cover = await _resolve_assignment(emp_id, month, rows)
        if cover or any(a.get("effective_to") is None for a in rows):
            targets[emp_id] = cover
    if not targets:
        raise HTTPException(status_code=400, detail=f"No employees have a payslip template assigned for {_mlabel(month)}")
    tpl_cache = {t["id"]: t for t in await db.payslip_templates.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500)}
    emps = {e["id"]: e for e in await db.employees.find(
        {"id": {"$in": list(targets)}, "is_deleted": {"$ne": True}}, {"_id": 0}).to_list(5000)}
    month_end = f"{month}-{calendar.monthrange(int(month[:4]), int(month[5:7]))[1]:02d}"
    existing = {s["employee_id"]: s for s in await db.payslips.find(
        {"month": month, "employee_id": {"$in": list(targets)}}, {"_id": 0, "employee_id": 1, "status": 1}).to_list(5000)}
    generated, regenerated, skipped_confirmed, errors = 0, 0, 0, []
    for emp_id, assign in targets.items():
        emp = emps.get(emp_id)
        if not emp:
            continue
        name = emp.get("full_name")
        if not assign and (emp.get("date_of_joining") or "")[:10] > month_end:
            continue  # joined after this month — nothing to generate
        prev = existing.get(emp_id)
        if prev and prev.get("status") == "confirmed":
            skipped_confirmed += 1
            continue
        try:
            r = await _payslip_for_month(emp, month, assign, tpl_cache)
        except HTTPException as ex:
            errors.append({"name": name, "error": str(ex.detail)})
            continue
        tpl, version, payroll = r["tpl"], r["version"], r["payroll"]
        doc = {
            "employee_id": emp_id, "month": month,
            "employee_name": name,
            "employee": {
                "full_name": name, "custom_employee_id": emp.get("custom_employee_id"),
                "designation": emp.get("designation"), "department": emp.get("department"),
                "team": emp.get("team"),
                "employment_type": emp.get("employment_type"), "date_of_joining": emp.get("date_of_joining"),
                "email": emp.get("email"),
            },
            "template_id": tpl["id"], "template_name": tpl["name"],
            "assignment_id": assign["id"],
            "template_version": r["calc"]["template_version"],
            "template_snapshot": {k: version.get(k) for k in CALC_KEYS},
            "monthly_pay": float(assign["monthly_pay"]),
            "calc": r["calc"],
            "payroll_meta": {k: payroll.get(k) for k in _PAYROLL_META_KEYS},
            "status": "draft",
            "generated_by": current_user.get("username"), "generated_at": _now(),
            "confirmed_by": None, "confirmed_at": None,
        }
        await db.payslips.update_one(
            {"employee_id": emp_id, "month": month},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
        # Re-apply any active manual adjustments on top of the fresh base calc
        # so admin's earlier adjustments survive a regeneration.
        fresh = await db.payslips.find_one({"employee_id": emp_id, "month": month}, {"_id": 0, "id": 1})
        if fresh:
            try:
                from payslip_adjustments import _recompute_slip_totals
                await _recompute_slip_totals(fresh["id"])
            except Exception:
                pass
        if prev:
            regenerated += 1
        generated += 1
    await _audit(current_user, "payslips_generated", ref_id=month,
                 new=f"generated={generated}, regenerated={regenerated}, skipped={skipped_confirmed}, errors={len(errors)}")
    return {"month": month, "generated": generated, "regenerated": regenerated,
            "skipped_confirmed": skipped_confirmed, "errors": errors}


@api_router.get("/payslips/generated")
async def list_generated_payslips(month: str = Query(...), current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    return await db.payslips.find({"month": month}, {"_id": 0}).sort("employee_name", 1).to_list(1000)


@api_router.post("/payslips/{payslip_id}/confirm")
async def confirm_payslip(payslip_id: str, current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    slip = await db.payslips.find_one({"id": payslip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if slip["status"] == "confirmed":
        return {"success": True, "already": True}
    await db.payslips.update_one({"id": payslip_id}, {"$set": {
        "status": "confirmed", "confirmed_by": current_user.get("username"), "confirmed_at": _now()}})
    await _audit(current_user, "payslip_confirmed", employee_id=slip["employee_id"], ref_id=payslip_id, new=slip["month"])
    return {"success": True}


@api_router.post("/payslips/{payslip_id}/unconfirm")
async def unconfirm_payslip(payslip_id: str, current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    slip = await db.payslips.find_one({"id": payslip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    await db.payslips.update_one({"id": payslip_id}, {"$set": {"status": "draft", "confirmed_by": None, "confirmed_at": None}})
    await _audit(current_user, "payslip_unconfirmed", employee_id=slip["employee_id"], ref_id=payslip_id, new=slip["month"])
    return {"success": True}


@api_router.post("/payslips/confirm-all")
async def confirm_all_payslips(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Bulk-confirm draft payslips.

    Two supported shapes:
      • {"month": "YYYY-MM"}                     → confirm every draft in that month
      • {"month": "YYYY-MM", "ids": [id1, id2]}  → confirm only those specific drafts
    """
    _hr_only(current_user)
    month = payload.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="month required")
    ids = payload.get("ids")
    query = {"month": month, "status": "draft"}
    if ids is not None:
        if not isinstance(ids, list) or not ids:
            raise HTTPException(status_code=400, detail="ids must be a non-empty list when provided")
        query["id"] = {"$in": [str(x) for x in ids]}
    res = await db.payslips.update_many(query, {"$set": {
        "status": "confirmed", "confirmed_by": current_user.get("username"), "confirmed_at": _now()}})
    subject = f"selected({len(ids)})" if ids is not None else "all"
    await _audit(current_user, "payslips_confirmed_bulk", ref_id=month, new=f"scope={subject}, count={res.modified_count}")
    return {"confirmed": res.modified_count}


@api_router.delete("/payslips/{payslip_id}")
async def delete_draft_payslip(payslip_id: str, current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    slip = await db.payslips.find_one({"id": payslip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if slip["status"] == "confirmed":
        raise HTTPException(status_code=409, detail="Confirmed payslips cannot be deleted. Revert to draft first.")
    await db.payslips.delete_one({"id": payslip_id})
    await _audit(current_user, "payslip_draft_deleted", employee_id=slip["employee_id"], ref_id=payslip_id, new=slip["month"])
    return {"success": True}


@api_router.get("/payslips/my")
async def my_payslips(current_user: dict = Depends(get_current_user)):
    """Employee view: confirmed payslips visible only from the 5th of the following month."""
    if current_user["role"] != UserRole.EMPLOYEE:
        raise HTTPException(status_code=403, detail="This endpoint is for employees only")
    emp_id = current_user.get("employee_id")
    if not emp_id:
        return []
    slips = await db.payslips.find({"employee_id": emp_id, "status": "confirmed"}, {"_id": 0}).sort("month", -1).to_list(100)
    return [s for s in slips if _is_visible_to_employee(s["month"])]


@api_router.get("/payslips/{payslip_id}/pdf")
async def download_payslip_pdf(payslip_id: str, current_user: dict = Depends(get_current_user)):
    slip = await db.payslips.find_one({"id": payslip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    role = current_user["role"]
    if role == UserRole.EMPLOYEE:
        if current_user.get("employee_id") != slip["employee_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        if slip["status"] != "confirmed" or not _is_visible_to_employee(slip["month"]):
            raise HTTPException(status_code=403, detail="Payslip not yet published")
    elif role != UserRole.HR:
        raise HTTPException(status_code=403, detail="Permission denied")
    pdf = build_payslip_pdf(slip)
    safe_name = (slip.get("employee_name") or "employee").replace(" ", "_")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Payslip_{safe_name}_{slip["month"]}.pdf"'})
