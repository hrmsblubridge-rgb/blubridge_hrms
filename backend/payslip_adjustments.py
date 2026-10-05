"""Payslip Manual Adjustments — Additions & Deductions applied AFTER the base
monthly payslip is generated. Adjustments are:
  • Editable / deletable while the payslip is in DRAFT
  • LOCKED once the payslip is CONFIRMED (must unconfirm first to edit)
  • Soft-deleted — history is preserved
  • Automatically reflected in `slip.calc` (manual_additions_total,
    manual_deductions_total, gross_earnings, total_deductions, net_pay)

The base template-driven calculation is NEVER touched — adjustments are a
post-processing layer only.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, Depends, Body, Query
from pydantic import BaseModel, Field

from server import api_router, db, get_current_user, ALL_ADMIN_ROLES, log_audit


ADJ_ADDITION = "ADDITION"
ADJ_DEDUCTION = "DEDUCTION"
_VALID_TYPES = {ADJ_ADDITION, ADJ_DEDUCTION}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(user):
    if user.get("role") not in ALL_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")


async def _recompute_slip_totals(payslip_id: str):
    """Re-apply active adjustments on top of the base calc snapshot and persist."""
    slip = await db.payslips.find_one({"id": payslip_id}, {"_id": 0})
    if not slip:
        return
    calc = dict(slip.get("calc") or {})

    # Preserve the ORIGINAL base numbers the first time we touch this slip
    base_gross = calc.get("base_gross_earnings")
    base_deds = calc.get("base_total_deductions")
    if base_gross is None:
        base_gross = float(calc.get("gross_earnings") or 0)
        base_deds = float(calc.get("total_deductions") or 0)
        calc["base_gross_earnings"] = base_gross
        calc["base_total_deductions"] = base_deds

    # Sum active adjustments
    add_total = 0.0
    ded_total = 0.0
    async for a in db.payslip_adjustments.find(
        {"payslip_id": payslip_id, "status": "active"}, {"_id": 0}
    ):
        if a["adjustment_type"] == ADJ_ADDITION:
            add_total += float(a.get("amount") or 0)
        elif a["adjustment_type"] == ADJ_DEDUCTION:
            ded_total += float(a.get("amount") or 0)

    calc["manual_additions_total"] = round(add_total, 2)
    calc["manual_deductions_total"] = round(ded_total, 2)
    calc["gross_earnings"] = round(base_gross + add_total, 2)
    calc["total_deductions"] = round(base_deds + ded_total, 2)
    calc["net_pay"] = round(calc["gross_earnings"] - calc["total_deductions"], 2)

    await db.payslips.update_one({"id": payslip_id}, {"$set": {"calc": calc}})


class AdjustmentCreate(BaseModel):
    payslip_ids: List[str] = Field(..., min_length=1)
    adjustment_type: str
    amount: float
    description: str
    remarks: Optional[str] = ""


class AdjustmentUpdate(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    remarks: Optional[str] = None


@api_router.post("/payslips/adjustments")
async def create_adjustments(body: AdjustmentCreate, current_user: dict = Depends(get_current_user)):
    """Create one adjustment record per payslip_id (individually tracked).
    A shared `batch_id` links bulk operations for reporting."""
    _require_admin(current_user)
    if body.adjustment_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail="adjustment_type must be ADDITION or DEDUCTION")
    if body.amount is None or float(body.amount) <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")
    if not body.description or not body.description.strip():
        raise HTTPException(status_code=400, detail="description required")

    slips = await db.payslips.find(
        {"id": {"$in": body.payslip_ids}}, {"_id": 0, "id": 1, "employee_id": 1, "month": 1, "status": 1}
    ).to_list(len(body.payslip_ids))
    slip_by_id = {s["id"]: s for s in slips}

    created = []
    errors = []
    batch_id = f"ADJ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}" if len(body.payslip_ids) > 1 else None

    for pid in body.payslip_ids:
        s = slip_by_id.get(pid)
        if not s:
            errors.append({"payslip_id": pid, "error": "Payslip not found"}); continue
        if s.get("status") == "confirmed":
            errors.append({"payslip_id": pid, "error": "Payslip is confirmed — cannot add adjustment"}); continue
        doc = {
            "id": str(uuid.uuid4()),
            "payslip_id": pid,
            "employee_id": s["employee_id"],
            "month": s["month"],
            "adjustment_type": body.adjustment_type,
            "amount": round(float(body.amount), 2),
            "description": body.description.strip(),
            "remarks": (body.remarks or "").strip(),
            "status": "active",
            "batch_id": batch_id,
            "created_by": current_user.get("username"),
            "created_by_id": current_user.get("id"),
            "created_at": _now(),
            "updated_by": None, "updated_at": None,
            "deleted_by": None, "deleted_at": None,
        }
        await db.payslip_adjustments.insert_one(dict(doc))
        doc.pop("_id", None)
        # Log per-adjustment for audit trail
        await db.payslip_adjustment_history.insert_one({
            "id": str(uuid.uuid4()),
            "adjustment_id": doc["id"],
            "payslip_id": pid,
            "action": "created",
            "old_amount": None,
            "new_amount": doc["amount"],
            "old_description": None,
            "new_description": doc["description"],
            "actor": current_user.get("username"),
            "actor_id": current_user.get("id"),
            "at": _now(),
        })
        await _recompute_slip_totals(pid)
        created.append(doc)

    await log_audit(
        current_user["id"], "payslip_adjustment_bulk_create", "payslip_adjustment",
        batch_id or (created[0]["id"] if created else ""),
        f"type={body.adjustment_type}, amt={body.amount}, count={len(created)}, errors={len(errors)}",
    )
    return {"created": created, "errors": errors, "batch_id": batch_id}


@api_router.get("/payslips/{payslip_id}/adjustments")
async def list_adjustments_for_slip(payslip_id: str, include_deleted: bool = Query(False), current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    q = {"payslip_id": payslip_id}
    if not include_deleted:
        q["status"] = "active"
    rows = await db.payslip_adjustments.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return rows


@api_router.get("/payslips/{payslip_id}/adjustments/history")
async def adjustment_history_for_slip(payslip_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    rows = await db.payslip_adjustment_history.find({"payslip_id": payslip_id}, {"_id": 0}).sort("at", -1).to_list(2000)
    return rows


@api_router.patch("/payslips/adjustments/{adj_id}")
async def update_adjustment(adj_id: str, body: AdjustmentUpdate, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    adj = await db.payslip_adjustments.find_one({"id": adj_id}, {"_id": 0})
    if not adj:
        raise HTTPException(status_code=404, detail="Adjustment not found")
    if adj["status"] != "active":
        raise HTTPException(status_code=400, detail="Adjustment is not active (deleted)")
    slip = await db.payslips.find_one({"id": adj["payslip_id"]}, {"_id": 0, "status": 1})
    if not slip or slip.get("status") == "confirmed":
        raise HTTPException(status_code=409, detail="Payslip is confirmed — unconfirm to edit adjustments")

    update = {}
    old_amount = adj["amount"]
    old_desc = adj.get("description")
    if body.amount is not None:
        if float(body.amount) <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")
        update["amount"] = round(float(body.amount), 2)
    if body.description is not None:
        if not body.description.strip():
            raise HTTPException(status_code=400, detail="description cannot be empty")
        update["description"] = body.description.strip()
    if body.remarks is not None:
        update["remarks"] = body.remarks.strip()
    if not update:
        raise HTTPException(status_code=400, detail="No changes provided")

    update["updated_by"] = current_user.get("username")
    update["updated_at"] = _now()
    await db.payslip_adjustments.update_one({"id": adj_id}, {"$set": update})

    await db.payslip_adjustment_history.insert_one({
        "id": str(uuid.uuid4()),
        "adjustment_id": adj_id,
        "payslip_id": adj["payslip_id"],
        "action": "updated",
        "old_amount": old_amount,
        "new_amount": update.get("amount", old_amount),
        "old_description": old_desc,
        "new_description": update.get("description", old_desc),
        "actor": current_user.get("username"),
        "actor_id": current_user.get("id"),
        "at": _now(),
    })
    await _recompute_slip_totals(adj["payslip_id"])
    await log_audit(current_user["id"], "payslip_adjustment_update", "payslip_adjustment", adj_id, str(update))
    return await db.payslip_adjustments.find_one({"id": adj_id}, {"_id": 0})


@api_router.delete("/payslips/adjustments/{adj_id}")
async def delete_adjustment(adj_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    adj = await db.payslip_adjustments.find_one({"id": adj_id}, {"_id": 0})
    if not adj:
        raise HTTPException(status_code=404, detail="Adjustment not found")
    if adj["status"] != "active":
        raise HTTPException(status_code=400, detail="Already deleted")
    slip = await db.payslips.find_one({"id": adj["payslip_id"]}, {"_id": 0, "status": 1})
    if not slip or slip.get("status") == "confirmed":
        raise HTTPException(status_code=409, detail="Payslip is confirmed — unconfirm to delete adjustments")

    await db.payslip_adjustments.update_one(
        {"id": adj_id},
        {"$set": {
            "status": "deleted",
            "deleted_by": current_user.get("username"),
            "deleted_at": _now(),
        }},
    )
    await db.payslip_adjustment_history.insert_one({
        "id": str(uuid.uuid4()),
        "adjustment_id": adj_id,
        "payslip_id": adj["payslip_id"],
        "action": "deleted",
        "old_amount": adj["amount"],
        "new_amount": None,
        "old_description": adj.get("description"),
        "new_description": None,
        "actor": current_user.get("username"),
        "actor_id": current_user.get("id"),
        "at": _now(),
    })
    await _recompute_slip_totals(adj["payslip_id"])
    await log_audit(current_user["id"], "payslip_adjustment_delete", "payslip_adjustment", adj_id, "")
    return {"success": True}


@api_router.get("/payslips/adjustments/summary")
async def adjustments_summary_by_month(month: str = Query(...), current_user: dict = Depends(get_current_user)):
    """Bulk summary: per-payslip active additions & deductions totals for a month.
    Used by the Monthly Payslips grid to render inline pill counts."""
    _require_admin(current_user)
    pipeline = [
        {"$match": {"month": month, "status": "active"}},
        {"$group": {
            "_id": {"payslip_id": "$payslip_id", "type": "$adjustment_type"},
            "total": {"$sum": "$amount"},
            "count": {"$sum": 1},
        }},
    ]
    by_slip = {}
    async for r in db.payslip_adjustments.aggregate(pipeline):
        pid = r["_id"]["payslip_id"]; t = r["_id"]["type"]
        entry = by_slip.setdefault(pid, {"payslip_id": pid, "additions_total": 0, "additions_count": 0,
                                          "deductions_total": 0, "deductions_count": 0})
        if t == ADJ_ADDITION:
            entry["additions_total"] = round(r["total"], 2); entry["additions_count"] = r["count"]
        else:
            entry["deductions_total"] = round(r["total"], 2); entry["deductions_count"] = r["count"]
    return list(by_slip.values())
