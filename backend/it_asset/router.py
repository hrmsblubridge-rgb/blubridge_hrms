"""IT Asset & Infrastructure Management — Phase 1 (Core Asset Foundation).

Additive, isolated module. Reuses the existing HRMS employee master, auth,
RBAC (deny-by-default employee gate), and audit logging. Collections:
  it_assets, it_asset_categories, it_asset_history
Nothing here modifies existing HRMS collections.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import Depends, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import StreamingResponse

STATUSES = ["Ordered", "Received", "In Stock", "Available", "Assigned",
            "Temporarily Assigned", "Under Repair", "Under Maintenance",
            "Returned", "Lost", "Damaged", "Retired", "Disposed", "Scrapped"]
CONDITIONS = ["New", "Good", "Fair", "Poor", "Damaged"]
SOURCES = ["Newly Purchased", "Existing / Legacy Asset", "Opening Inventory",
           "Employee Return", "Internal Transfer", "Replacement", "Donation", "Other"]

DEFAULT_CATEGORIES = [
    ("Laptop", "LAP", "Hardware", ["Processor", "RAM", "Storage", "Storage Type", "Operating System", "OS Version", "Hostname", "MAC Address", "IP Address", "Graphics", "Display Size"]),
    ("Desktop", "DES", "Hardware", ["Processor", "RAM", "Storage", "Storage Type", "Operating System", "OS Version", "Hostname", "MAC Address", "IP Address"]),
    ("Workstation", "WKS", "Hardware", ["Processor", "RAM", "Storage", "Operating System"]),
    ("Monitor", "MON", "Hardware", ["Screen Size", "Resolution", "Panel Type", "Refresh Rate"]),
    ("Mobile Phone", "PH", "Hardware", ["IMEI 1", "IMEI 2", "Mobile Number", "SIM Number", "SIM Provider", "Operating System", "OS Version"]),
    ("Tablet", "TAB", "Hardware", ["IMEI 1", "Operating System", "OS Version"]),
    ("Server", "SRV", "Hardware", ["Server Name", "Physical / Virtual", "CPU", "RAM", "Storage", "Operating System", "IP Address", "Environment", "Datacenter", "Rack", "Rack Unit"]),
    ("Printer", "PRN", "Hardware", ["Type", "IP Address"]),
    ("Scanner", "SCN", "Hardware", []),
    ("Projector", "PRJ", "Hardware", []),
    ("UPS", "UPS", "Hardware", ["Capacity"]),
    ("Storage Device", "STG", "Hardware", ["Capacity", "Type"]),
    ("Keyboard", "KBD", "Hardware", []),
    ("Mouse", "MOU", "Hardware", []),
    ("Headset", "HST", "Hardware", []),
    ("Docking Station", "DCK", "Hardware", []),
    ("Charger/Adapter", "CHG", "Hardware", []),
    ("Router", "RTR", "Network", ["IP Address", "MAC Address", "Firmware Version", "Management IP", "Rack", "Port"]),
    ("Switch", "SWT", "Network", ["IP Address", "MAC Address", "Firmware Version", "Rack", "Port"]),
    ("Firewall", "FW", "Network", ["IP Address", "Firmware Version", "Management IP"]),
    ("Access Point", "AP", "Network", ["IP Address", "MAC Address", "Firmware Version"]),
    ("CCTV", "CAM", "Security", ["IP Address", "Location"]),
    ("Biometric Device", "BIO", "Security", ["IP Address", "Location"]),
    ("Other", "AST", "Hardware", []),
]

IMPORT_COLUMNS = ["asset_id", "category", "name", "asset_tag", "brand", "model",
                  "serial_number", "status", "condition", "source", "location",
                  "department", "purchase_date", "purchase_cost", "vendor",
                  "invoice_number", "remarks"]


def register(api_router, deps: dict):
    db = deps["db"]
    get_current_user = deps["get_current_user"]
    log_audit = deps["log_audit"]
    get_ist_now = deps["get_ist_now"]
    ADMIN_ROLES = deps["ADMIN_ROLES"]

    from .assignment_history import (
        open_asset_assignment, close_asset_assignment, sync_components_on_asset_reassign,
    )

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _clean(doc: dict) -> dict:
        doc = dict(doc)
        doc.pop("_id", None)
        return doc

    async def _require_admin(user: dict):
        if user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="IT Management is restricted to administrators.")

    async def _ensure_categories():
        if await db.it_asset_categories.count_documents({}) == 0:
            for name, prefix, group, fields in DEFAULT_CATEGORIES:
                await db.it_asset_categories.insert_one({
                    "id": str(uuid.uuid4()), "name": name, "prefix": prefix,
                    "group": group, "fields": fields, "is_active": True,
                    "created_at": _now(),
                })

    async def _next_asset_id(prefix: str) -> str:
        # Highest existing numeric suffix for this prefix + 1
        rx = {"$regex": f"^{prefix}-\\d+$"}
        top = await db.it_assets.find_one({"asset_id": rx}, sort=[("asset_id", -1)], projection={"asset_id": 1})
        n = 0
        if top:
            try:
                n = int(top["asset_id"].split("-")[-1])
            except Exception:
                n = 0
        # Guard against gaps/dupes by scanning count too
        cnt = await db.it_assets.count_documents({"asset_id": rx})
        n = max(n, cnt)
        return f"{prefix}-{n + 1:04d}"

    async def _prefix_for(category: str) -> str:
        c = await db.it_asset_categories.find_one({"name": category})
        return (c or {}).get("prefix") or "AST"

    async def _history(asset_id: str, action: str, user: dict, note: str = "", extra: dict = None):
        entry = {
            "id": str(uuid.uuid4()), "asset_id": asset_id, "action": action,
            "note": note, "by_user_id": user.get("id"), "by_name": user.get("name") or user.get("username"),
            "at": _now(),
        }
        if extra:
            entry.update(extra)
        await db.it_asset_history.insert_one(entry)

    async def _emp_snapshot(employee_id: str) -> dict:
        emp = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}},
                                          {"_id": 0, "id": 1, "full_name": 1, "emp_id": 1,
                                           "department": 1, "designation": 1, "team": 1, "location": 1})
        if not emp:
            raise HTTPException(status_code=400, detail=f"Employee {employee_id} not found in HRMS Employee Master.")
        return {"employee_id": emp["id"], "employee_name": emp.get("full_name"),
                "emp_code": emp.get("emp_id"), "department": emp.get("department"),
                "designation": emp.get("designation"), "location": emp.get("location") or emp.get("team")}

    async def _emp_snapshot_active(employee_id: str) -> dict:
        """Snapshot that additionally requires the employee to be currently Active.
        Used by the optional assign-on-create shortcut."""
        emp = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}},
                                          {"_id": 0, "id": 1, "employee_status": 1})
        if not emp:
            raise HTTPException(status_code=400, detail="Selected employee was not found in the HRMS Employee Master.")
        if (emp.get("employee_status") or "Active") != "Active":
            raise HTTPException(status_code=400,
                                detail="Selected employee is no longer active. Please select another employee.")
        return await _emp_snapshot(employee_id)

    # ---------------- META / CATEGORIES ----------------
    @api_router.get("/it/meta")
    async def it_meta(current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        await _ensure_categories()
        cats = [_clean(c) async for c in db.it_asset_categories.find({"is_active": {"$ne": False}}).sort("name", 1)]
        return {"statuses": STATUSES, "conditions": CONDITIONS, "sources": SOURCES,
                "categories": cats, "import_columns": IMPORT_COLUMNS}

    @api_router.post("/it/categories")
    async def it_add_category(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        name = (payload.get("name") or "").strip()
        prefix = (payload.get("prefix") or "").strip().upper()
        if not name or not prefix:
            raise HTTPException(status_code=400, detail="Category name and prefix are required.")
        if await db.it_asset_categories.find_one({"name": name}):
            raise HTTPException(status_code=400, detail="Category already exists.")
        doc = {"id": str(uuid.uuid4()), "name": name, "prefix": prefix,
               "group": payload.get("group") or "Hardware",
               "fields": payload.get("fields") or [], "is_active": True, "created_at": _now()}
        await db.it_asset_categories.insert_one(doc)
        await log_audit(current_user["id"], "it_category_created", "it_category", doc["id"])
        return _clean(doc)

    # ---------------- ASSET LIST ----------------
    @api_router.get("/it/assets")
    async def it_list_assets(
        search: Optional[str] = None, category: Optional[str] = None,
        status: Optional[str] = None, condition: Optional[str] = None,
        location: Optional[str] = None, department: Optional[str] = None,
        employee_id: Optional[str] = None, source: Optional[str] = None,
        page: int = 1, page_size: int = 25,
        current_user: dict = Depends(get_current_user),
    ):
        await _require_admin(current_user)
        q: dict = {"is_deleted": {"$ne": True}}
        if category and category != "All":
            q["category"] = category
        if status and status != "All":
            q["status"] = status
        if condition and condition != "All":
            q["condition"] = condition
        if location and location != "All":
            q["location"] = location
        if department and department != "All":
            q["department"] = department
        if source and source != "All":
            q["source"] = source
        if employee_id:
            q["assigned_to.employee_id"] = employee_id
        if search:
            import re as _re
            rx = {"$regex": _re.escape(search.strip()), "$options": "i"}
            q["$or"] = [{"asset_id": rx}, {"name": rx}, {"brand": rx}, {"model": rx},
                        {"serial_number": rx}, {"asset_tag": rx}, {"assigned_to.employee_name": rx}]
        total = await db.it_assets.count_documents(q)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        cur = db.it_assets.find(q, {"_id": 0}).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
        items = [d async for d in cur]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ---------------- CREATE ----------------
    @api_router.post("/it/assets")
    async def it_create_asset(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        await _ensure_categories()
        category = (payload.get("category") or "").strip()
        if not category:
            raise HTTPException(status_code=400, detail="Asset Category is required.")
        status = (payload.get("status") or "").strip() or "In Stock"
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'.")
        asset_id = (payload.get("asset_id") or "").strip()
        if asset_id:
            if await db.it_assets.find_one({"asset_id": asset_id}):
                raise HTTPException(status_code=400, detail=f"Asset ID {asset_id} already exists.")
        else:
            asset_id = await _next_asset_id(await _prefix_for(category))
        serial = (payload.get("serial_number") or "").strip() or None
        if serial and await db.it_assets.find_one({"serial_number": serial, "is_deleted": {"$ne": True}}):
            raise HTTPException(status_code=400, detail=f"Serial Number {serial} already exists.")
        doc = {
            "asset_id": asset_id, "category": category, "name": payload.get("name") or None,
            "asset_tag": payload.get("asset_tag") or None, "brand": payload.get("brand") or None,
            "model": payload.get("model") or None, "serial_number": serial,
            "status": status, "condition": payload.get("condition") or None,
            "source": payload.get("source") or None, "location": payload.get("location") or None,
            "department": payload.get("department") or None, "remarks": payload.get("remarks") or None,
            "purchase": payload.get("purchase") or {}, "warranty": payload.get("warranty") or {},
            "specs": payload.get("specs") or {}, "assigned_to": None, "assigned_date": None,
            "assigned_by": None, "is_deleted": False, "created_at": _now(), "updated_at": _now(),
            "created_by": current_user.get("id"),
        }
        await db.it_assets.insert_one(doc)
        await _history(asset_id, "Created", current_user, f"Asset created with status {status}")
        await log_audit(current_user["id"], "it_asset_created", "it_asset", asset_id)

        # OPTIONAL assign-on-create shortcut — reuses the same assignment logic/history.
        assign_emp = (payload.get("assign_employee_id") or "").strip()
        if assign_emp:
            snap = await _emp_snapshot_active(assign_emp)
            assigned_date = payload.get("assigned_date") or get_ist_now().strftime("%d-%m-%Y")
            by_name = current_user.get("name") or current_user.get("username")
            await db.it_assets.update_one({"asset_id": asset_id}, {"$set": {
                "assigned_to": snap, "assigned_date": assigned_date, "assigned_by": by_name,
                "status": "Assigned", "updated_at": _now(),
            }})
            await _history(asset_id, "Assigned", current_user,
                           f"Assigned to {snap['employee_name']} ({snap.get('emp_code') or snap['employee_id']}) on creation",
                           {"employee_id": snap["employee_id"]})
            await open_asset_assignment(db, asset_id, snap, "Assigned on creation", by_name)
            await sync_components_on_asset_reassign(db, asset_id, snap, "Asset assigned on creation", by_name)
            await log_audit(current_user["id"], "it_asset_assigned", "it_asset", asset_id)
            doc = await db.it_assets.find_one({"asset_id": asset_id}, {"_id": 0})
        return _clean(doc)

    # ---------------- DETAIL ----------------
    @api_router.get("/it/assets/{asset_id}")
    async def it_get_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        doc = await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Asset not found.")
        history = [_clean(h) async for h in db.it_asset_history.find({"asset_id": asset_id}).sort("at", 1)]
        return {"asset": doc, "history": history}

    # ---------------- UPDATE ----------------
    @api_router.put("/it/assets/{asset_id}")
    async def it_update_asset(asset_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        existing = await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}})
        if not existing:
            raise HTTPException(status_code=404, detail="Asset not found.")
        # asset_id is immutable
        editable = ["category", "name", "asset_tag", "brand", "model", "serial_number",
                    "status", "condition", "source", "location", "department", "remarks",
                    "purchase", "warranty", "specs"]
        updates = {}
        for k in editable:
            if k in payload:
                updates[k] = payload[k]
        if "status" in updates and updates["status"] not in STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status.")
        new_serial = (updates.get("serial_number") or "").strip() if "serial_number" in updates else None
        if new_serial and new_serial != existing.get("serial_number"):
            if await db.it_assets.find_one({"serial_number": new_serial, "is_deleted": {"$ne": True}, "asset_id": {"$ne": asset_id}}):
                raise HTTPException(status_code=400, detail=f"Serial Number {new_serial} already exists.")
        updates["updated_at"] = _now()
        await db.it_assets.update_one({"asset_id": asset_id}, {"$set": updates})
        note = ""
        if "status" in updates and updates["status"] != existing.get("status"):
            note = f"Status: {existing.get('status')} → {updates['status']}"
        await _history(asset_id, "Updated", current_user, note or "Asset details updated")
        await log_audit(current_user["id"], "it_asset_updated", "it_asset", asset_id)
        return {"success": True}

    # ---------------- EMPLOYEE ASSETS (employees + current asset counts) ----------------
    @api_router.get("/it/employee-assets")
    async def it_employee_assets(
        search: Optional[str] = None, department: Optional[str] = None,
        has_assets: Optional[str] = None, page: int = 1, page_size: int = 25,
        current_user: dict = Depends(get_current_user),
    ):
        await _require_admin(current_user)
        counts = {}
        async for row in db.it_assets.aggregate([
            {"$match": {"is_deleted": {"$ne": True}, "assigned_to.employee_id": {"$ne": None}}},
            {"$group": {"_id": "$assigned_to.employee_id", "n": {"$sum": 1}}},
        ]):
            if row["_id"]:
                counts[row["_id"]] = row["n"]
        q = {"is_deleted": {"$ne": True}, "employee_status": "Active"}
        if department and department != "All":
            q["department"] = department
        if search:
            rx = {"$regex": re.escape(search.strip()), "$options": "i"}
            q["$or"] = [{"full_name": rx}, {"emp_id": rx}, {"department": rx}, {"designation": rx}]
        if has_assets == "with":
            q["id"] = {"$in": list(counts.keys())}
        elif has_assets == "without":
            q["id"] = {"$nin": list(counts.keys())}
        total = await db.employees.count_documents(q)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        cur = db.employees.find(q, {"_id": 0, "id": 1, "full_name": 1, "emp_id": 1, "department": 1,
                                    "designation": 1, "location": 1, "team": 1, "employee_status": 1}) \
            .sort("full_name", 1).skip((page - 1) * page_size).limit(page_size)
        items = [{**e, "asset_count": counts.get(e["id"], 0)} async for e in cur]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    @api_router.get("/it/employee-assets/{employee_id}")
    async def it_employee_asset_detail(employee_id: str, current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        assets = [_clean(a) async for a in db.it_assets.find(
            {"assigned_to.employee_id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0}).sort("asset_id", 1)]
        return {"employee_id": employee_id, "assets": assets}

    # ---------------- ASSIGN ----------------
    @api_router.post("/it/assets/{asset_id}/assign")
    async def it_assign_asset(asset_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        asset = await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found.")
        if asset.get("assigned_to") and not payload.get("override"):
            raise HTTPException(status_code=400, detail="Asset is already assigned. Use Transfer or Return first.")
        snap = await _emp_snapshot(payload.get("employee_id"))
        assigned_date = payload.get("assigned_date") or get_ist_now().strftime("%d-%m-%Y")
        await db.it_assets.update_one({"asset_id": asset_id}, {"$set": {
            "assigned_to": snap, "assigned_date": assigned_date,
            "assigned_by": current_user.get("name") or current_user.get("username"),
            "status": "Assigned", "condition": payload.get("condition") or asset.get("condition"),
            "updated_at": _now(),
        }})
        await _history(asset_id, "Assigned", current_user,
                       f"Assigned to {snap['employee_name']} ({snap.get('emp_code') or snap['employee_id']})",
                       {"employee_id": snap["employee_id"]})
        by_name = current_user.get("name") or current_user.get("username")
        await open_asset_assignment(db, asset_id, snap, "Assigned", by_name)
        await sync_components_on_asset_reassign(db, asset_id, snap, "Asset assigned", by_name)
        await log_audit(current_user["id"], "it_asset_assigned", "it_asset", asset_id)
        return {"success": True}

    # ---------------- RETURN ----------------
    @api_router.post("/it/assets/{asset_id}/return")
    async def it_return_asset(asset_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        asset = await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found.")
        if not asset.get("assigned_to"):
            raise HTTPException(status_code=400, detail="Asset is not currently assigned.")
        prev = asset["assigned_to"]
        new_status = payload.get("status") or "Available"
        if new_status not in STATUSES:
            raise HTTPException(status_code=400, detail="Invalid return status.")
        await db.it_assets.update_one({"asset_id": asset_id}, {"$set": {
            "assigned_to": None, "assigned_date": None, "assigned_by": None,
            "status": new_status, "condition": payload.get("condition") or asset.get("condition"),
            "updated_at": _now(),
        }})
        note = f"Returned from {prev.get('employee_name')} → status {new_status}"
        if payload.get("remarks"):
            note += f". {payload['remarks']}"
        await _history(asset_id, "Returned", current_user, note, {"employee_id": prev.get("employee_id")})
        by_name = current_user.get("name") or current_user.get("username")
        await close_asset_assignment(db, asset_id, "Returned", by_name)
        await sync_components_on_asset_reassign(db, asset_id, None, "Asset returned", by_name)
        await log_audit(current_user["id"], "it_asset_returned", "it_asset", asset_id)
        return {"success": True}

    # ---------------- TRANSFER ----------------
    @api_router.post("/it/assets/{asset_id}/transfer")
    async def it_transfer_asset(asset_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        asset = await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found.")
        snap = await _emp_snapshot(payload.get("employee_id"))
        prev = asset.get("assigned_to")
        await db.it_assets.update_one({"asset_id": asset_id}, {"$set": {
            "assigned_to": snap, "assigned_date": payload.get("assigned_date") or get_ist_now().strftime("%d-%m-%Y"),
            "assigned_by": current_user.get("name") or current_user.get("username"),
            "status": "Assigned", "updated_at": _now(),
        }})
        frm = prev.get("employee_name") if prev else (asset.get("location") or "Stock")
        await _history(asset_id, "Transferred", current_user,
                       f"Transferred from {frm} → {snap['employee_name']}", {"employee_id": snap["employee_id"]})
        by_name = current_user.get("name") or current_user.get("username")
        await close_asset_assignment(db, asset_id, "Transferred", by_name)
        await open_asset_assignment(db, asset_id, snap, "Transferred", by_name)
        await sync_components_on_asset_reassign(db, asset_id, snap, "Asset transferred", by_name)
        await log_audit(current_user["id"], "it_asset_transferred", "it_asset", asset_id)
        return {"success": True}

    # ---------------- SOFT DELETE / ARCHIVE ----------------
    @api_router.delete("/it/assets/{asset_id}")
    async def it_delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        asset = await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found.")
        await db.it_assets.update_one({"asset_id": asset_id}, {"$set": {
            "is_deleted": True, "archived": True, "status": "Archived", "updated_at": _now(),
        }})
        await _history(asset_id, "Archived", current_user, "Asset archived (soft delete)")
        await log_audit(current_user["id"], "it_asset_archived", "it_asset", asset_id)
        return {"success": True}

    # ---------------- DASHBOARD ----------------
    @api_router.get("/it/dashboard")
    async def it_dashboard(current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        base = {"is_deleted": {"$ne": True}}
        total = await db.it_assets.count_documents(base)
        by_status = {}
        async for row in db.it_assets.aggregate([{"$match": base}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            by_status[row["_id"] or "Unknown"] = row["n"]
        by_category = {}
        async for row in db.it_assets.aggregate([{"$match": base}, {"$group": {"_id": "$category", "n": {"$sum": 1}}}]):
            by_category[row["_id"] or "Unknown"] = row["n"]
        today = get_ist_now().strftime("%Y-%m-%d")
        soon = (get_ist_now().replace(hour=0, minute=0)).strftime("%Y-%m-%d")
        # Warranty/AMC alerts (string ISO date comparisons within 30 days)
        from datetime import timedelta
        in30 = (get_ist_now() + timedelta(days=30)).strftime("%Y-%m-%d")
        warranty_expiring = await db.it_assets.count_documents({**base, "warranty.warranty_end": {"$gte": today, "$lte": in30}})
        warranty_expired = await db.it_assets.count_documents({**base, "warranty.warranty_end": {"$lt": today, "$ne": None}})
        amc_expiring = await db.it_assets.count_documents({**base, "warranty.amc_end": {"$gte": today, "$lte": in30}})
        under_repair = by_status.get("Under Repair", 0) + by_status.get("Under Maintenance", 0)
        return {
            "total": total,
            "summary": {
                "Assigned": by_status.get("Assigned", 0),
                "Available": by_status.get("Available", 0),
                "In Stock": by_status.get("In Stock", 0),
                "Under Repair": under_repair,
                "Damaged": by_status.get("Damaged", 0),
                "Lost": by_status.get("Lost", 0),
                "Disposed": by_status.get("Disposed", 0) + by_status.get("Scrapped", 0),
            },
            "by_category": by_category,
            "by_status": by_status,
            "alerts": {
                "warranty_expiring": warranty_expiring,
                "warranty_expired": warranty_expired,
                "amc_expiring": amc_expiring,
                "under_repair": under_repair,
                "lost": by_status.get("Lost", 0),
            },
        }

    # ---------------- IMPORT TEMPLATE ----------------
    @api_router.get("/it/import/template")
    async def it_import_template(current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(IMPORT_COLUMNS)
        w.writerow(["", "Laptop", "Dell Latitude", "TAG-1", "Dell", "Latitude 5420", "ABC123",
                    "Available", "Good", "Existing / Legacy Asset", "Chennai", "IT", "", "", "", "", "Legacy asset - purchase info unknown"])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=it_asset_import_template.csv"})

    def _parse_upload(filename: str, content: bytes) -> List[dict]:
        name = (filename or "").lower()
        rows: List[dict] = []
        if name.endswith(".xlsx"):
            try:
                import openpyxl
            except Exception:
                raise HTTPException(status_code=400, detail="XLSX support unavailable; please upload CSV.")
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            headers = None
            for r in ws.iter_rows(values_only=True):
                if headers is None:
                    headers = [str(c).strip().lower() if c is not None else "" for c in r]
                    continue
                if all(c is None or str(c).strip() == "" for c in r):
                    continue
                rows.append({headers[i]: ("" if r[i] is None else str(r[i]).strip()) for i in range(min(len(headers), len(r)))})
        else:
            text = content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            for r in reader:
                rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in r.items()})
        return rows

    async def _validate_rows(rows: List[dict]):
        cats = {c["name"].lower(): c async for c in db.it_asset_categories.find({})}
        seen_ids, seen_serials = set(), set()
        existing_ids = set()
        # Preload existing asset_ids to detect duplicates efficiently
        async for a in db.it_assets.find({"is_deleted": {"$ne": True}}, {"_id": 0, "asset_id": 1, "serial_number": 1}):
            existing_ids.add(a["asset_id"])
        out = []
        for idx, r in enumerate(rows, start=2):  # header is row 1
            errors, warnings = [], []
            category = (r.get("category") or "").strip()
            status = (r.get("status") or "").strip() or "In Stock"
            aid = (r.get("asset_id") or "").strip()
            serial = (r.get("serial_number") or "").strip()
            if not category:
                errors.append("Category is missing.")
            elif category.lower() not in cats:
                errors.append(f"Invalid category '{category}'.")
            if status not in STATUSES:
                errors.append(f"Invalid status '{status}'.")
            if aid:
                if aid in existing_ids:
                    errors.append(f"Asset ID {aid} already exists.")
                if aid in seen_ids:
                    errors.append(f"Duplicate Asset ID {aid} within file.")
                seen_ids.add(aid)
            if serial:
                if serial in seen_serials:
                    errors.append(f"Duplicate Serial Number {serial} within file.")
                seen_serials.add(serial)
            else:
                warnings.append("Serial number missing.")
            if not (r.get("purchase_date") or "").strip():
                warnings.append("Purchase date missing.")
            if not (r.get("vendor") or "").strip():
                warnings.append("Vendor missing.")
            out.append({"row": idx, "data": r, "errors": errors, "warnings": warnings,
                        "valid": len(errors) == 0})
        return out

    @api_router.post("/it/import/preview")
    async def it_import_preview(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        await _ensure_categories()
        content = await file.read()
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 8MB).")
        rows = _parse_upload(file.filename, content)
        if not rows:
            raise HTTPException(status_code=400, detail="No data rows found in file.")
        validated = await _validate_rows(rows)
        return {
            "total": len(validated),
            "valid": sum(1 for v in validated if v["valid"]),
            "errors": sum(1 for v in validated if v["errors"]),
            "warnings": sum(1 for v in validated if v["warnings"]),
            "rows": validated[:1000],
        }

    @api_router.post("/it/import/confirm")
    async def it_import_confirm(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        rows = payload.get("rows") or []
        validated = await _validate_rows([r.get("data", r) for r in rows])
        created, skipped = 0, 0
        for v in validated:
            if not v["valid"]:
                skipped += 1
                continue
            r = v["data"]
            category = r["category"].strip()
            aid = (r.get("asset_id") or "").strip() or await _next_asset_id(await _prefix_for(category))
            doc = {
                "asset_id": aid, "category": category, "name": r.get("name") or None,
                "asset_tag": r.get("asset_tag") or None, "brand": r.get("brand") or None,
                "model": r.get("model") or None, "serial_number": (r.get("serial_number") or "").strip() or None,
                "status": (r.get("status") or "In Stock").strip(), "condition": r.get("condition") or None,
                "source": r.get("source") or "Existing / Legacy Asset", "location": r.get("location") or None,
                "department": r.get("department") or None, "remarks": r.get("remarks") or None,
                "purchase": {k: r.get(k) for k in ("purchase_date", "purchase_cost", "vendor", "invoice_number") if r.get(k)},
                "warranty": {}, "specs": {}, "assigned_to": None, "assigned_date": None, "assigned_by": None,
                "is_deleted": False, "created_at": _now(), "updated_at": _now(), "created_by": current_user.get("id"),
            }
            try:
                await db.it_assets.insert_one(doc)
                await _history(aid, "Created", current_user, "Imported from file")
                created += 1
            except Exception:
                skipped += 1
        await log_audit(current_user["id"], "it_asset_bulk_import", "it_asset", f"created={created}")
        return {"created": created, "skipped": skipped}

    # ---------------- EXPORT ----------------
    @api_router.get("/it/export")
    async def it_export(
        search: Optional[str] = None, category: Optional[str] = None, status: Optional[str] = None,
        condition: Optional[str] = None, location: Optional[str] = None, department: Optional[str] = None,
        source: Optional[str] = None, current_user: dict = Depends(get_current_user),
    ):
        await _require_admin(current_user)
        q: dict = {"is_deleted": {"$ne": True}}
        for field, val in [("category", category), ("status", status), ("condition", condition),
                           ("location", location), ("department", department), ("source", source)]:
            if val and val != "All":
                q[field] = val
        if search:
            import re as _re
            rx = {"$regex": _re.escape(search.strip()), "$options": "i"}
            q["$or"] = [{"asset_id": rx}, {"name": rx}, {"brand": rx}, {"model": rx}, {"serial_number": rx}]
        buf = io.StringIO()
        w = csv.writer(buf)
        cols = ["asset_id", "category", "name", "brand", "model", "serial_number", "status",
                "condition", "source", "location", "department", "assigned_employee", "assigned_date"]
        w.writerow(cols)
        async for a in db.it_assets.find(q, {"_id": 0}).sort("asset_id", 1):
            at = a.get("assigned_to") or {}
            w.writerow([a.get("asset_id"), a.get("category"), a.get("name"), a.get("brand"), a.get("model"),
                        a.get("serial_number"), a.get("status"), a.get("condition"), a.get("source"),
                        a.get("location"), a.get("department"), at.get("employee_name"), a.get("assigned_date")])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=it_assets_export.csv"})

    # ---------------- EMPLOYEE SELF-SERVICE ----------------
    @api_router.get("/employee/it-assets")
    async def it_my_assets(current_user: dict = Depends(get_current_user)):
        emp_id = current_user.get("employee_id")
        if not emp_id:
            return {"items": []}
        cur = db.it_assets.find({"assigned_to.employee_id": emp_id, "is_deleted": {"$ne": True}},
                                {"_id": 0, "asset_id": 1, "category": 1, "name": 1, "brand": 1,
                                 "model": 1, "serial_number": 1, "status": 1, "condition": 1, "assigned_date": 1})
        items = [d async for d in cur]
        return {"items": items}

    return {"ok": True}
