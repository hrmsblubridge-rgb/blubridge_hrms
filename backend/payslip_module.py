"""Payslip Module — Phase 1: templates CRUD, components, employee assignment
(effective dates + per-employee monthly pay), calculation engine preview.
Collections: payslip_templates, payslip_assignments, payslip_audit."""
import uuid
import calendar
from datetime import datetime, timezone
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


@api_router.post("/payslips/templates")
async def create_payslip_template(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name required")
    if await db.payslip_templates.find_one({"name": name, "is_deleted": {"$ne": True}}):
        raise HTTPException(status_code=409, detail="Template with this name already exists")
    _validate_components(payload.get("components"))
    doc = {
        "id": str(uuid.uuid4()), "name": name,
        "description": payload.get("description") or "",
        "status": payload.get("status") or "Active",
        "components": payload["components"],
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
    _hr_only(current_user)
    tpl = await db.payslip_templates.find_one({"id": template_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    upd = {}
    for k in ("name", "description", "status"):
        if k in payload:
            upd[k] = payload[k]
    if "components" in payload:
        _validate_components(payload["components"])
        upd["components"] = payload["components"]
    upd["updated_at"] = _now()
    await db.payslip_templates.update_one({"id": template_id}, {"$set": upd})
    await _audit(current_user, "template_edited", ref_id=template_id, old=tpl.get("name"), new=upd.get("name"))
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


@api_router.post("/payslips/assignments")
async def assign_payslip_template(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    emp_id = payload.get("employee_id")
    tpl_id = payload.get("template_id")
    monthly_pay = float(payload.get("monthly_pay") or 0)
    if monthly_pay <= 0:
        raise HTTPException(status_code=400, detail="Monthly Pay must be greater than 0")
    emp = await db.employees.find_one({"id": emp_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    tpl = await db.payslip_templates.find_one({"id": tpl_id, "is_deleted": {"$ne": True}, "status": "Active"}, {"_id": 0, "name": 1})
    if not tpl:
        raise HTTPException(status_code=404, detail="Active template not found")
    # --- Effective From resolution (Joining Date / Confirmation Date / Custom Date) ---
    eff_from_type = (payload.get("effective_from_type") or "custom_date").lower()
    if eff_from_type == "joining_date":
        eff_from = (emp.get("date_of_joining") or "")[:10]
        if not eff_from:
            raise HTTPException(status_code=400, detail="Employee has no Joining Date on record")
    elif eff_from_type == "confirmation_date":
        eff_from = (emp.get("confirmation_date") or "")[:10]
        if not eff_from:
            raise HTTPException(status_code=400, detail="Employee has no Confirmation Date; pick Joining Date or Custom")
    else:
        eff_from_type = "custom_date"
        eff_from = (payload.get("effective_from") or "")[:10]
        if not eff_from:
            raise HTTPException(status_code=400, detail="Custom Date requires an Effective From date")
    # --- Extra Work Compensation ---
    ewc = (payload.get("extra_work_compensation") or "extra_pay").lower()
    if ewc not in ("extra_pay", "comp_off", "not_applicable"):
        raise HTTPException(status_code=400, detail="Invalid Extra Work Compensation option")
    old = await db.payslip_assignments.find_one({"employee_id": emp_id, "effective_to": None}, {"_id": 0})
    if old:
        await db.payslip_assignments.update_one(
            {"id": old["id"]}, {"$set": {"effective_to": eff_from, "closed_at": _now()}})
    doc = {
        "id": str(uuid.uuid4()), "employee_id": emp_id, "template_id": tpl_id,
        "template_name": tpl["name"], "monthly_pay": monthly_pay,
        "effective_from": eff_from, "effective_from_type": eff_from_type,
        "effective_to": None,
        "extra_work_compensation": ewc,
        "assigned_by": current_user.get("username"), "created_at": _now(),
    }
    await db.payslip_assignments.insert_one(dict(doc))
    doc.pop("_id", None)
    await _audit(current_user, "template_assigned", employee_id=emp_id, ref_id=doc["id"],
                 old=(old or {}).get("template_name"), new=tpl["name"])
    return doc


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
                                            "department": 1, "team": 1, "designation": 1, "employment_type": 1}).sort("full_name", 1).to_list(500)
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
    tpl_id = payload.get("template_id")
    eff_from = payload.get("effective_from") or _now()[:10]
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="No employees selected")
    tpl = await db.payslip_templates.find_one(
        {"id": tpl_id, "is_deleted": {"$ne": True}, "status": "Active"}, {"_id": 0, "name": 1})
    if not tpl:
        raise HTTPException(status_code=404, detail="Active template not found")
    assigned, errors = 0, []
    for it in items:
        emp_id = it.get("employee_id")
        try:
            mp = float(it.get("monthly_pay") or 0)
        except (TypeError, ValueError):
            mp = 0
        emp = await db.employees.find_one({"id": emp_id, "is_deleted": {"$ne": True}}, {"_id": 0, "full_name": 1})
        if not emp:
            errors.append({"employee_id": emp_id, "error": "Employee not found"})
            continue
        if mp <= 0:
            errors.append({"employee_id": emp_id, "name": emp["full_name"], "error": "Monthly Pay must be greater than 0"})
            continue
        old = await db.payslip_assignments.find_one({"employee_id": emp_id, "effective_to": None}, {"_id": 0})
        if old:
            await db.payslip_assignments.update_one(
                {"id": old["id"]}, {"$set": {"effective_to": eff_from, "closed_at": _now()}})
        doc = {
            "id": str(uuid.uuid4()), "employee_id": emp_id, "template_id": tpl_id,
            "template_name": tpl["name"], "monthly_pay": mp,
            "effective_from": eff_from, "effective_to": None,
            "assigned_by": current_user.get("username"), "created_at": _now(),
        }
        await db.payslip_assignments.insert_one(doc)
        await _audit(current_user, "template_assigned_bulk", employee_id=emp_id, ref_id=doc["id"],
                     old=(old or {}).get("template_name"), new=tpl["name"])
        assigned += 1
    return {"assigned": assigned, "errors": errors}


@api_router.get("/payslips/assignments/{employee_id}/history")
async def assignment_history(employee_id: str, current_user: dict = Depends(get_current_user)):
    _hr_only(current_user)
    return await db.payslip_assignments.find({"employee_id": employee_id}, {"_id": 0}).sort("created_at", -1).to_list(50)


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


def compute_payslip(monthly_pay: float, components: list, month: str, payable_days: float,
                    extra_pay_days: float, extra_work_compensation: str = "extra_pay") -> dict:
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
    gratuity_full = 0.0
    gratuity_raw = 0.0
    gratuity_final = 0.0
    if gratuity_component:
        ct = gratuity_component.get("calc_type")
        proratable_gr = gratuity_component.get("proratable", True)
        if ct == "fixed":
            gratuity_full = float(gratuity_component.get("fixed_amount") or 0)
            gratuity_raw = (gratuity_full / cal_days) * payable if (cal_days and proratable_gr) else gratuity_full
        elif ct == "percentage":
            gratuity_full = float(monthly_pay) * float(gratuity_component.get("percentage_value") or 0) / 100.0
            gratuity_raw = gratuity_full * (payable / cal_days if (cal_days and proratable_gr) else 1)
        else:
            gratuity_raw = 0.0
        gratuity_final = round(gratuity_raw)

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
            # Generic non-PF, non-Gratuity deduction (TDS, PT, ESI, Other) — compute from template.
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
                monthly_amt = 0.0
                amount = 0.0
            deduct_amount = amount
            auto_note = f"{c.get('percentage_value')}% of {c.get('calc_base') or 'monthly_pay'}" if ct == "percentage" else f"Fixed ₹{c.get('fixed_amount')}"
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


@api_router.post("/payslips/calculate")
async def calculate_payslip_preview(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Preview calculation for one employee+month using live Payroll data."""
    _hr_only(current_user)
    emp_id = payload.get("employee_id")
    month = payload.get("month")  # YYYY-MM
    if not (month and len(month) == 7):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    assign = await db.payslip_assignments.find_one(
        {"employee_id": emp_id, "effective_to": None}, {"_id": 0})
    if not assign:
        raise HTTPException(status_code=400, detail="No active payslip template assigned to this employee")
    tpl = await db.payslip_templates.find_one({"id": assign["template_id"], "is_deleted": {"$ne": True}}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=400, detail="Assigned template no longer exists")
    payroll = await calculate_payroll_for_employee(emp_id, month)
    if not payroll:
        raise HTTPException(status_code=400, detail="Payroll data unavailable for this employee/month")
    result = compute_payslip(
        monthly_pay=float(assign["monthly_pay"]), components=tpl["components"], month=month,
        payable_days=float(payroll.get("final_payable_days") or 0),
        extra_pay_days=float(payroll.get("extra_pay") or 0),
        extra_work_compensation=assign.get("extra_work_compensation") or "extra_pay",
    )
    result.update({"employee_id": emp_id, "template_id": tpl["id"], "template_name": tpl["name"]})
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
    """Generate/regenerate draft payslips for a month for all employees with an active assignment."""
    _hr_only(current_user)
    month = payload.get("month")
    if not (month and len(month) == 7):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    only_ids = payload.get("employee_ids")
    assigns = await db.payslip_assignments.find({"effective_to": None}, {"_id": 0}).to_list(1000)
    if only_ids:
        assigns = [a for a in assigns if a["employee_id"] in set(only_ids)]
    if not assigns:
        raise HTTPException(status_code=400, detail="No employees have an active payslip template assigned")
    tpl_cache = {t["id"]: t for t in await db.payslip_templates.find({"is_deleted": {"$ne": True}}, {"_id": 0}).to_list(200)}
    emp_ids = [a["employee_id"] for a in assigns]
    emps = {e["id"]: e for e in await db.employees.find(
        {"id": {"$in": emp_ids}, "is_deleted": {"$ne": True}}, {"_id": 0}).to_list(1000)}
    generated, skipped_confirmed, errors = 0, 0, []
    for a in assigns:
        emp = emps.get(a["employee_id"])
        if not emp:
            continue
        name = emp.get("full_name")
        existing = await db.payslips.find_one({"employee_id": a["employee_id"], "month": month}, {"_id": 0, "status": 1})
        if existing and existing.get("status") == "confirmed":
            skipped_confirmed += 1
            continue
        tpl = tpl_cache.get(a["template_id"])
        if not tpl:
            errors.append({"name": name, "error": "Assigned template no longer exists"})
            continue
        try:
            payroll = await calculate_payroll_for_employee(a["employee_id"], month, employee=emp)
            if not payroll:
                errors.append({"name": name, "error": "No payroll data (check joining/relieving dates for this month)"})
                continue
            calc = compute_payslip(
                monthly_pay=float(a["monthly_pay"]), components=tpl["components"], month=month,
                payable_days=float(payroll.get("final_payable_days") or 0),
                extra_pay_days=float(payroll.get("extra_pay") or 0),
                extra_work_compensation=a.get("extra_work_compensation") or "extra_pay")
        except HTTPException as ex:
            errors.append({"name": name, "error": str(ex.detail)})
            continue
        doc = {
            "employee_id": a["employee_id"], "month": month,
            "employee_name": name,
            "employee": {
                "full_name": name, "custom_employee_id": emp.get("custom_employee_id"),
                "designation": emp.get("designation"), "department": emp.get("department"),
                "employment_type": emp.get("employment_type"), "date_of_joining": emp.get("date_of_joining"),
                "email": emp.get("email"),
            },
            "template_id": tpl["id"], "template_name": tpl["name"],
            "monthly_pay": float(a["monthly_pay"]),
            "calc": calc,
            "payroll_meta": {k: payroll.get(k) for k in _PAYROLL_META_KEYS},
            "status": "draft",
            "generated_by": current_user.get("username"), "generated_at": _now(),
            "confirmed_by": None, "confirmed_at": None,
        }
        await db.payslips.update_one(
            {"employee_id": a["employee_id"], "month": month},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
        generated += 1
    await _audit(current_user, "payslips_generated", ref_id=month,
                 new=f"generated={generated}, skipped={skipped_confirmed}, errors={len(errors)}")
    return {"month": month, "generated": generated, "skipped_confirmed": skipped_confirmed, "errors": errors}


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
    _hr_only(current_user)
    month = payload.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="month required")
    res = await db.payslips.update_many({"month": month, "status": "draft"}, {"$set": {
        "status": "confirmed", "confirmed_by": current_user.get("username"), "confirmed_at": _now()}})
    await _audit(current_user, "payslips_confirmed_all", ref_id=month, new=f"count={res.modified_count}")
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
