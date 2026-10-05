"""IT Asset — Component / Sub-Asset Management.

Purely ADDITIVE module. Adds Parent Asset -> Component -> Component History
tracking on top of the existing IT Asset module WITHOUT modifying any existing
asset, employee, auth, handover, maintenance or import/export behaviour.

New collections only:
  it_components            component master (unique component_id lifecycle)
  it_component_types       configurable component types (RAM, SSD, GPU, ...)
  it_component_history     per-component timeline (never overwritten)
  it_component_maintenance component-level maintenance records

A component is NEVER assigned to an employee directly: while installed in a
parent asset it INHERITS the parent asset's current employee assignment.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import StreamingResponse

from .assignment_history import (
    open_asset_assignment, close_asset_assignment,
    open_component_assignment, close_component_assignment,
    sync_components_on_asset_reassign,
    asset_assignment_history, component_assignment_history,
)

# Lifecycle states for a component
C_STATUSES = ["Available", "Installed", "Reserved", "Under Repair",
              "Damaged", "Lost", "Scrapped", "Disposed"]
# States from which a component CANNOT be installed into a parent asset
C_BLOCKED_INSTALL = {"Disposed", "Scrapped", "Lost"}
C_CONDITIONS = ["New", "Good", "Fair", "Poor", "Damaged"]
C_SOURCES = ["Newly Purchased", "Existing / Legacy Asset", "Opening Inventory",
             "Removed from Asset", "Replacement", "Donation", "Other"]

REMOVAL_REASONS = ["Hardware Failure", "Upgrade", "Replacement", "Repair",
                   "Reuse", "Disposal", "Other"]

# (name, prefix, group, trackable_default)
DEFAULT_TYPES = [
    ("CPU / Processor", "CPU", "Computer", True),
    ("Motherboard", "MB", "Computer", True),
    ("RAM", "RAM", "Computer", True),
    ("SSD", "SSD", "Computer", True),
    ("HDD", "HDD", "Computer", True),
    ("GPU", "GPU", "Computer", True),
    ("Power Supply / PSU", "PSU", "Computer", True),
    ("Cabinet", "CAB", "Computer", True),
    ("CPU Cooler", "COOL", "Computer", True),
    ("Network Card", "NIC", "Computer", True),
    ("Wi-Fi Card", "WIFI", "Computer", True),
    ("Sound Card", "SND", "Computer", False),
    ("Optical Drive", "ODD", "Computer", False),
    ("Cooling Fan", "FAN", "Computer", False),
    ("Battery", "BAT", "Computer", True),
    ("RAID Controller", "RAID", "Server", True),
    ("Storage Controller", "STC", "Server", True),
    ("Other", "CMP", "Other", True),
]

C_IMPORT_COLUMNS = ["component_id", "type", "name", "brand", "model", "serial_number",
                    "part_number", "capacity", "status", "condition", "source",
                    "location", "purchase_date", "purchase_cost", "vendor",
                    "invoice_number", "warranty_start", "warranty_end", "remarks"]

ASSEMBLY_COLUMNS = ["parent_asset_id", "component_id", "slot"]


def register(api_router, deps: dict):
    db = deps["db"]
    get_current_user = deps["get_current_user"]
    log_audit = deps["log_audit"]
    get_ist_now = deps["get_ist_now"]
    ADMIN_ROLES = deps["ADMIN_ROLES"]

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _clean(doc: dict) -> dict:
        doc = dict(doc)
        doc.pop("_id", None)
        return doc

    async def _require_admin(user: dict):
        if user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="IT Component Management is restricted to administrators.")

    async def _ensure_types():
        if await db.it_component_types.count_documents({}) == 0:
            for name, prefix, group, trackable in DEFAULT_TYPES:
                await db.it_component_types.insert_one({
                    "id": str(uuid.uuid4()), "name": name, "prefix": prefix,
                    "group": group, "trackable_default": trackable,
                    "is_active": True, "created_at": _now(),
                })

    async def _prefix_for_type(type_name: str) -> str:
        t = await db.it_component_types.find_one({"name": type_name})
        return (t or {}).get("prefix") or "CMP"

    async def _next_component_id(prefix: str) -> str:
        rx = {"$regex": f"^{prefix}-\\d+$"}
        top = await db.it_components.find_one({"component_id": rx}, sort=[("component_id", -1)],
                                              projection={"component_id": 1})
        n = 0
        if top:
            try:
                n = int(top["component_id"].split("-")[-1])
            except Exception:
                n = 0
        cnt = await db.it_components.count_documents({"component_id": rx})
        n = max(n, cnt)
        return f"{prefix}-{n + 1:04d}"

    async def _history(component_id: str, action: str, user: dict, note: str = "",
                       parent_asset_id: str = None, extra: dict = None):
        entry = {
            "id": str(uuid.uuid4()), "component_id": component_id, "action": action,
            "note": note, "parent_asset_id": parent_asset_id,
            "by_user_id": user.get("id"), "by_name": user.get("name") or user.get("username"),
            "at": _now(),
        }
        if extra:
            entry.update(extra)
        await db.it_component_history.insert_one(entry)

    async def _parent_asset(asset_id: str) -> Optional[dict]:
        return await db.it_assets.find_one({"asset_id": asset_id, "is_deleted": {"$ne": True}}, {"_id": 0})

    def _display(c: dict) -> str:
        parts = [c.get("capacity"), c.get("brand"), c.get("model")]
        s = " ".join([p for p in parts if p]).strip()
        return s or c.get("name") or c.get("type") or c.get("component_id")

    async def _holder_for(asset_id: str) -> Optional[dict]:
        """Employee currently holding the parent asset (inherited)."""
        if not asset_id:
            return None
        a = await _parent_asset(asset_id)
        if not a:
            return None
        return a.get("assigned_to")

    # ================= META / TYPES =================
    @api_router.get("/it/components/meta")
    async def comp_meta(current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        await _ensure_types()
        types = [_clean(t) async for t in db.it_component_types.find({"is_active": {"$ne": False}}).sort("name", 1)]
        return {"statuses": C_STATUSES, "conditions": C_CONDITIONS, "sources": C_SOURCES,
                "removal_reasons": REMOVAL_REASONS, "types": types,
                "import_columns": C_IMPORT_COLUMNS, "assembly_columns": ASSEMBLY_COLUMNS}

    @api_router.post("/it/component-types")
    async def comp_add_type(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        name = (payload.get("name") or "").strip()
        prefix = (payload.get("prefix") or "").strip().upper()
        if not name or not prefix:
            raise HTTPException(status_code=400, detail="Type name and prefix are required.")
        if await db.it_component_types.find_one({"name": name}):
            raise HTTPException(status_code=400, detail="Component type already exists.")
        doc = {"id": str(uuid.uuid4()), "name": name, "prefix": prefix,
               "group": payload.get("group") or "Other",
               "trackable_default": bool(payload.get("trackable_default", True)),
               "is_active": True, "created_at": _now()}
        await db.it_component_types.insert_one(doc)
        await log_audit(current_user["id"], "it_component_type_created", "it_component_type", doc["id"])
        return _clean(doc)

    # ================= COMPONENT LIST =================
    @api_router.get("/it/components")
    async def comp_list(
        search: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None,
        parent_asset_id: Optional[str] = None, location: Optional[str] = None,
        trackable: Optional[str] = None, installed: Optional[str] = None,
        page: int = 1, page_size: int = 25,
        current_user: dict = Depends(get_current_user),
    ):
        await _require_admin(current_user)
        q: dict = {"is_deleted": {"$ne": True}}
        if type and type != "All":
            q["type"] = type
        if status and status != "All":
            q["status"] = status
        if location and location != "All":
            q["location"] = location
        if parent_asset_id:
            q["parent_asset_id"] = parent_asset_id
        if trackable in ("true", "false"):
            q["trackable"] = (trackable == "true")
        if installed == "true":
            q["parent_asset_id"] = {"$ne": None}
        elif installed == "false":
            q["parent_asset_id"] = None
        if search:
            rx = {"$regex": re.escape(search.strip()), "$options": "i"}
            q["$or"] = [{"component_id": rx}, {"name": rx}, {"brand": rx}, {"model": rx},
                        {"serial_number": rx}, {"part_number": rx}, {"capacity": rx}]
        total = await db.it_components.count_documents(q)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        cur = db.it_components.find(q, {"_id": 0}).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
        items = [d async for d in cur]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ================= CREATE =================
    async def _build_component_doc(payload: dict, user: dict) -> dict:
        await _ensure_types()
        type_name = (payload.get("type") or "").strip()
        if not type_name:
            raise HTTPException(status_code=400, detail="Component Type is required.")
        tdef = await db.it_component_types.find_one({"name": type_name})
        if not tdef:
            raise HTTPException(status_code=400, detail=f"Invalid component type '{type_name}'.")
        status = (payload.get("status") or "").strip() or "Available"
        if status not in C_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'.")
        cid = (payload.get("component_id") or "").strip()
        if cid:
            if await db.it_components.find_one({"component_id": cid}):
                raise HTTPException(status_code=400, detail=f"Component ID {cid} already exists.")
        else:
            cid = await _next_component_id(tdef.get("prefix") or "CMP")
        serial = (payload.get("serial_number") or "").strip() or None
        if serial and await db.it_components.find_one({"serial_number": serial, "is_deleted": {"$ne": True}}):
            raise HTTPException(status_code=400, detail=f"Serial Number {serial} already exists on another component.")
        trackable = payload.get("trackable")
        if trackable is None:
            trackable = bool(tdef.get("trackable_default", True))
        return {
            "component_id": cid, "type": type_name, "name": payload.get("name") or None,
            "brand": payload.get("brand") or None, "model": payload.get("model") or None,
            "serial_number": serial, "part_number": payload.get("part_number") or None,
            "capacity": payload.get("capacity") or None, "status": status,
            "condition": payload.get("condition") or None, "source": payload.get("source") or None,
            "location": payload.get("location") or None, "remarks": payload.get("remarks") or None,
            "purchase": payload.get("purchase") or {}, "warranty": payload.get("warranty") or {},
            "specs": payload.get("specs") or {}, "trackable": bool(trackable),
            "parent_asset_id": None, "slot": None, "installed_date": None, "installed_by": None,
            "is_deleted": False, "created_at": _now(), "updated_at": _now(),
            "created_by": user.get("id"),
        }

    @api_router.post("/it/components")
    async def comp_create(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        doc = await _build_component_doc(payload, current_user)
        await db.it_components.insert_one(doc)
        await _history(doc["component_id"], "Created", current_user, f"Component created with status {doc['status']}")
        await log_audit(current_user["id"], "it_component_created", "it_component", doc["component_id"])
        return _clean(doc)

    # ================= DASHBOARD (literal route — declared before /{component_id}) =================
    @api_router.get("/it/components/dashboard")
    async def comp_dashboard(current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        base = {"is_deleted": {"$ne": True}}
        total = await db.it_components.count_documents(base)
        by_status = {}
        async for row in db.it_components.aggregate([{"$match": base}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            by_status[row["_id"] or "Unknown"] = row["n"]
        by_type = {}
        async for row in db.it_components.aggregate([{"$match": base}, {"$group": {"_id": "$type", "n": {"$sum": 1}}}]):
            by_type[row["_id"] or "Unknown"] = row["n"]
        installed = await db.it_components.count_documents({**base, "parent_asset_id": {"$ne": None}})
        replaced = await db.it_component_history.count_documents({"action": "Replaced"})
        today = get_ist_now().strftime("%Y-%m-%d")
        in30 = (get_ist_now() + timedelta(days=30)).strftime("%Y-%m-%d")
        warranty_expiring = await db.it_components.count_documents({**base, "warranty.warranty_end": {"$gte": today, "$lte": in30}})
        return {
            "total": total, "installed": installed,
            "summary": {
                "Available": by_status.get("Available", 0),
                "Installed": installed,
                "Under Repair": by_status.get("Under Repair", 0),
                "Damaged": by_status.get("Damaged", 0),
                "Disposed": by_status.get("Disposed", 0) + by_status.get("Scrapped", 0),
                "Replaced": replaced,
            },
            "by_type": by_type, "by_status": by_status,
            "alerts": {
                "under_repair": by_status.get("Under Repair", 0),
                "damaged": by_status.get("Damaged", 0),
                "available_in_store": by_status.get("Available", 0),
                "warranty_expiring": warranty_expiring,
            },
        }

    # ================= EXPORT / REPORTS (literal route — declared before /{component_id}) =================
    @api_router.get("/it/components/export")
    async def comp_export(
        report: Optional[str] = "inventory", search: Optional[str] = None, type: Optional[str] = None,
        status: Optional[str] = None, current_user: dict = Depends(get_current_user),
    ):
        await _require_admin(current_user)
        buf = io.StringIO()
        w = csv.writer(buf)

        if report == "replacement":
            w.writerow(["parent_asset_id", "old_component_id", "new_component_id", "date", "by"])
            async for h in db.it_component_history.find({"action": "Replaced", "replacement_component_id": {"$ne": None}}).sort("at", 1):
                w.writerow([h.get("parent_asset_id"), h.get("component_id"),
                            h.get("replacement_component_id"), h.get("at"), h.get("by_name")])
        elif report == "movement":
            w.writerow(["component_id", "action", "parent_asset_id", "at", "by", "note"])
            async for h in db.it_component_history.find({"action": {"$in": ["Installed", "Removed", "Replaced"]}}).sort([("component_id", 1), ("at", 1)]):
                w.writerow([h.get("component_id"), h.get("action"), h.get("parent_asset_id"),
                            h.get("at"), h.get("by_name"), h.get("note")])
        elif report == "maintenance":
            w.writerow(["component_id", "parent_asset_id", "issue", "action", "vendor", "cost", "status", "reported_date", "resolved_date"])
            async for m in db.it_component_maintenance.find({}).sort("created_at", -1):
                w.writerow([m.get("component_id"), m.get("parent_asset_id"), m.get("issue"), m.get("action"),
                            m.get("vendor"), m.get("cost"), m.get("status"), m.get("reported_date"), m.get("resolved_date")])
        else:
            q: dict = {"is_deleted": {"$ne": True}}
            if report == "installed":
                q["parent_asset_id"] = {"$ne": None}
            elif report == "available":
                q["parent_asset_id"] = None
                q["status"] = "Available"
            elif report == "removed":
                q["parent_asset_id"] = None
                q["status"] = {"$in": ["Damaged", "Under Repair", "Available", "Scrapped", "Disposed", "Lost"]}
            if type and type != "All":
                q["type"] = type
            if status and status != "All":
                q["status"] = status
            if search:
                rx = {"$regex": re.escape(search.strip()), "$options": "i"}
                q["$or"] = [{"component_id": rx}, {"brand": rx}, {"model": rx}, {"serial_number": rx}]
            w.writerow(["component_id", "type", "brand", "model", "serial_number", "capacity", "status",
                        "condition", "location", "parent_asset_id", "slot", "installed_date"])
            async for c in db.it_components.find(q, {"_id": 0}).sort("component_id", 1):
                w.writerow([c.get("component_id"), c.get("type"), c.get("brand"), c.get("model"),
                            c.get("serial_number"), c.get("capacity"), c.get("status"), c.get("condition"),
                            c.get("location"), c.get("parent_asset_id"), c.get("slot"), c.get("installed_date")])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=it_components_{report}.csv"})

    # ================= AVAILABILITY (literal route — declared before /{component_id}) =================
    async def _availability_counts(type_name: str = None) -> dict:
        base = {"is_deleted": {"$ne": True}}
        if type_name and type_name != "All":
            base["type"] = type_name
        total = await db.it_components.count_documents(base)
        used = await db.it_components.count_documents({**base, "parent_asset_id": {"$ne": None}})
        available = await db.it_components.count_documents({**base, "parent_asset_id": None, "status": "Available"})
        under_repair = await db.it_components.count_documents({**base, "status": "Under Repair"})
        damaged = await db.it_components.count_documents({**base, "status": "Damaged"})
        disposed = await db.it_components.count_documents({**base, "status": {"$in": ["Disposed", "Scrapped", "Lost"]}})
        return {"total": total, "used": used, "available": available,
                "under_repair": under_repair, "damaged": damaged, "disposed": disposed}

    @api_router.get("/it/components/availability")
    async def comp_availability(
        type: Optional[str] = None, search: Optional[str] = None,
        exclude: Optional[str] = None, current_user: dict = Depends(get_current_user),
    ):
        """Real-time availability. `exclude` is a comma-separated list of component_ids
        to hide (e.g. already picked in the current Create-Asset form)."""
        await _require_admin(current_user)
        await _ensure_types()
        counts = await _availability_counts(type)
        q = {"is_deleted": {"$ne": True}, "parent_asset_id": None, "status": "Available"}
        if type and type != "All":
            q["type"] = type
        if search:
            rx = {"$regex": re.escape(search.strip()), "$options": "i"}
            q["$or"] = [{"component_id": rx}, {"serial_number": rx}, {"brand": rx},
                        {"model": rx}, {"part_number": rx}, {"capacity": rx}]
        ex = set((exclude or "").split(",")) if exclude else set()
        items = []
        async for c in db.it_components.find(q, {"_id": 0}).sort("component_id", 1).limit(100):
            if c["component_id"] in ex:
                continue
            items.append(c)
        return {"type": type, "counts": counts, "available_items": items,
                "message": None if items else f"No {type or 'matching'} components are currently available."}

    # ================= DETAIL =================
    @api_router.get("/it/components/{component_id}")
    async def comp_detail(component_id: str, current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        doc = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Component not found.")
        history = [_clean(h) async for h in db.it_component_history.find({"component_id": component_id}).sort("at", 1)]
        maint = [_clean(m) async for m in db.it_component_maintenance.find({"component_id": component_id}).sort("created_at", -1)]
        holder = await _holder_for(doc.get("parent_asset_id"))
        assignments = await component_assignment_history(db, component_id)
        return {"component": doc, "history": history, "maintenance": maint,
                "current_holder": holder, "assignments": assignments}

    # ================= UPDATE =================
    @api_router.put("/it/components/{component_id}")
    async def comp_update(component_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        existing = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}})
        if not existing:
            raise HTTPException(status_code=404, detail="Component not found.")
        editable = ["type", "name", "brand", "model", "serial_number", "part_number", "capacity",
                    "condition", "source", "location", "remarks", "purchase", "warranty", "specs", "trackable"]
        updates = {}
        for k in editable:
            if k in payload:
                updates[k] = payload[k]
        if "status" in payload:
            # Only allow non-lifecycle status edits when NOT installed (installed status is derived)
            new_status = payload["status"]
            if new_status not in C_STATUSES:
                raise HTTPException(status_code=400, detail="Invalid status.")
            if existing.get("parent_asset_id") and new_status != "Installed":
                raise HTTPException(status_code=400, detail="Component is installed. Remove it before changing status.")
            updates["status"] = new_status
        new_serial = (updates.get("serial_number") or "").strip() if "serial_number" in updates else None
        if new_serial and new_serial != existing.get("serial_number"):
            if await db.it_components.find_one({"serial_number": new_serial, "is_deleted": {"$ne": True}, "component_id": {"$ne": component_id}}):
                raise HTTPException(status_code=400, detail=f"Serial Number {new_serial} already exists.")
        updates["updated_at"] = _now()
        await db.it_components.update_one({"component_id": component_id}, {"$set": updates})
        await _history(component_id, "Updated", current_user, "Component details updated",
                       parent_asset_id=existing.get("parent_asset_id"))
        await log_audit(current_user["id"], "it_component_updated", "it_component", component_id)
        return {"success": True}

    # ================= INSTALL =================
    async def _do_install(component: dict, asset_id: str, user: dict, payload: dict):
        cid = component["component_id"]
        if component.get("parent_asset_id"):
            raise HTTPException(status_code=400,
                                detail=f"{cid} is already installed in {component['parent_asset_id']}. Remove it first.")
        if component.get("status") in C_BLOCKED_INSTALL:
            raise HTTPException(status_code=400,
                                detail=f"Component status is '{component['status']}' and cannot be installed.")
        parent = await _parent_asset(asset_id)
        if not parent:
            raise HTTPException(status_code=404, detail=f"Parent asset {asset_id} not found.")
        slot = (payload.get("slot") or "").strip() or None
        inst_date = payload.get("installed_date") or get_ist_now().strftime("%d-%m-%Y")
        installed_by = payload.get("installed_by") or (user.get("name") or user.get("username"))
        updates = {"parent_asset_id": asset_id, "slot": slot, "installed_date": inst_date,
                   "installed_by": installed_by, "status": "Installed", "updated_at": _now()}
        if payload.get("condition"):
            updates["condition"] = payload["condition"]
        # Concurrency-safe: only install if STILL free (no parent, not blocked). Prevents
        # two saves grabbing the same physical component.
        res = await db.it_components.find_one_and_update(
            {"component_id": cid, "is_deleted": {"$ne": True},
             "parent_asset_id": None, "status": {"$nin": list(C_BLOCKED_INSTALL)}},
            {"$set": updates})
        if not res:
            raise HTTPException(status_code=409,
                                detail=f"{cid} is no longer available — it may have just been assigned to another asset.")
        holder = parent.get("assigned_to")
        note = f"Installed in {asset_id}" + (f" (slot {slot})" if slot else "")
        if holder:
            note += f" · holder {holder.get('employee_name')}"
        if payload.get("remarks"):
            note += f". {payload['remarks']}"
        await _history(cid, "Installed", user, note, parent_asset_id=asset_id, extra={"slot": slot})
        # Open a component-level employee assignment period if the asset is assigned
        if holder and holder.get("employee_id"):
            await open_component_assignment(db, cid, asset_id, holder,
                                            payload.get("assign_reason") or "Installed in assigned asset",
                                            user.get("name") or user.get("username"))
        await log_audit(user["id"], "it_component_installed", "it_component", cid)

    @api_router.post("/it/components/{component_id}/install")
    async def comp_install(component_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        component = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}})
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")
        asset_id = (payload.get("parent_asset_id") or "").strip()
        if not asset_id:
            raise HTTPException(status_code=400, detail="Parent asset is required.")
        await _do_install(component, asset_id, current_user, payload)
        return {"success": True}

    # ================= REMOVE =================
    async def _do_remove(component: dict, user: dict, payload: dict):
        asset_id = component.get("parent_asset_id")
        if not asset_id:
            raise HTTPException(status_code=400, detail="Component is not currently installed.")
        reason = payload.get("reason") or "Removed"
        rem_date = payload.get("removal_date") or get_ist_now().strftime("%d-%m-%Y")
        removed_by = payload.get("removed_by") or (user.get("name") or user.get("username"))
        new_status = payload.get("new_status") or "Available"
        if new_status not in C_STATUSES or new_status == "Installed":
            raise HTTPException(status_code=400, detail="Invalid post-removal status.")
        updates = {"parent_asset_id": None, "slot": None, "installed_date": None, "installed_by": None,
                   "status": new_status, "updated_at": _now(),
                   "location": payload.get("destination") or component.get("location")}
        if payload.get("condition"):
            updates["condition"] = payload["condition"]
        await db.it_components.update_one({"component_id": component["component_id"]}, {"$set": updates})
        # Close any open component-level employee assignment period
        await close_component_assignment(db, component["component_id"], reason,
                                         user.get("name") or user.get("username"))
        note = f"Removed from {asset_id} · reason {reason} → status {new_status}"
        if payload.get("remarks"):
            note += f". {payload['remarks']}"
        await _history(component["component_id"], "Removed", user, note, parent_asset_id=asset_id,
                       extra={"reason": reason, "removal_date": rem_date, "removed_by": removed_by})
        await log_audit(user["id"], "it_component_removed", "it_component", component["component_id"])
        return asset_id

    @api_router.post("/it/components/{component_id}/remove")
    async def comp_remove(component_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        component = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}})
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")
        await _do_remove(component, current_user, payload)
        return {"success": True}

    # ================= REPLACE (remove old + install new) =================
    @api_router.post("/it/components/replace")
    async def comp_replace(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        asset_id = (payload.get("parent_asset_id") or "").strip()
        old_id = (payload.get("old_component_id") or "").strip()
        new_id = (payload.get("new_component_id") or "").strip()
        if not (asset_id and old_id and new_id):
            raise HTTPException(status_code=400, detail="parent_asset_id, old_component_id and new_component_id are required.")
        if old_id == new_id:
            raise HTTPException(status_code=400, detail="Old and new components must differ.")
        old = await db.it_components.find_one({"component_id": old_id, "is_deleted": {"$ne": True}})
        new = await db.it_components.find_one({"component_id": new_id, "is_deleted": {"$ne": True}})
        if not old or not new:
            raise HTTPException(status_code=404, detail="Component(s) not found.")
        if old.get("parent_asset_id") != asset_id:
            raise HTTPException(status_code=400, detail=f"{old_id} is not installed in {asset_id}.")
        if new.get("parent_asset_id"):
            raise HTTPException(status_code=400, detail=f"{new_id} is already installed in {new['parent_asset_id']}.")
        if new.get("status") in C_BLOCKED_INSTALL:
            raise HTTPException(status_code=400, detail=f"{new_id} status '{new['status']}' cannot be installed.")
        parent = await _parent_asset(asset_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent asset not found.")
        reason = payload.get("reason") or "Replacement"
        rep_date = payload.get("replacement_date") or get_ist_now().strftime("%d-%m-%Y")
        slot = payload.get("slot") or old.get("slot")
        # Remove old
        await _do_remove(old, current_user, {
            "reason": reason, "removal_date": rep_date, "condition": payload.get("old_condition"),
            "new_status": payload.get("old_new_status") or "Damaged", "destination": payload.get("old_destination"),
            "remarks": f"Replaced by {new_id}",
        })
        # Install new
        await _do_install(new, asset_id, current_user, {
            "slot": slot, "installed_date": rep_date, "condition": payload.get("new_condition"),
            "remarks": f"Replacement for {old_id}. {payload.get('remarks') or ''}".strip(),
        })
        # Cross-link history notes
        await _history(old_id, "Replaced", current_user, f"Replaced by {new_id} in {asset_id} · {reason}",
                       parent_asset_id=asset_id, extra={"replacement_component_id": new_id})
        await _history(new_id, "Replaced", current_user, f"Replacement for {old_id} in {asset_id} · {reason}",
                       parent_asset_id=asset_id, extra={"replaced_component_id": old_id})
        await log_audit(current_user["id"], "it_component_replaced", "it_component", f"{old_id}->{new_id}")
        return {"success": True, "old_component_id": old_id, "new_component_id": new_id, "parent_asset_id": asset_id}

    # ================= MAINTENANCE =================
    @api_router.post("/it/components/{component_id}/maintenance")
    async def comp_maintenance(component_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        component = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}})
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")
        rec = {
            "id": str(uuid.uuid4()), "component_id": component_id,
            "parent_asset_id": component.get("parent_asset_id"),
            "issue": payload.get("issue") or None, "action": payload.get("action") or None,
            "vendor": payload.get("vendor") or None, "cost": payload.get("cost") or None,
            "reported_date": payload.get("reported_date") or get_ist_now().strftime("%d-%m-%Y"),
            "resolved_date": payload.get("resolved_date") or None,
            "status": payload.get("status") or "Open", "remarks": payload.get("remarks") or None,
            "by_user_id": current_user.get("id"), "by_name": current_user.get("name") or current_user.get("username"),
            "created_at": _now(),
        }
        await db.it_component_maintenance.insert_one(rec)
        # Optionally flip component status when sent for repair (only if not installed)
        set_status = payload.get("set_component_status")
        if set_status and set_status in C_STATUSES and not component.get("parent_asset_id"):
            await db.it_components.update_one({"component_id": component_id}, {"$set": {"status": set_status, "updated_at": _now()}})
        await _history(component_id, "Maintenance", current_user,
                       f"Maintenance: {rec['issue'] or ''} ({rec['status']})".strip(),
                       parent_asset_id=component.get("parent_asset_id"))
        await log_audit(current_user["id"], "it_component_maintenance", "it_component", component_id)
        return _clean(rec)

    # ================= DISPOSE =================
    @api_router.post("/it/components/{component_id}/dispose")
    async def comp_dispose(component_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        component = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}})
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")
        if component.get("parent_asset_id"):
            raise HTTPException(status_code=400, detail="Remove the component from its parent asset before disposal.")
        disposal = {
            "disposal_date": payload.get("disposal_date") or get_ist_now().strftime("%d-%m-%Y"),
            "reason": payload.get("reason") or None, "method": payload.get("method") or None,
            "approved_by": payload.get("approved_by") or None, "remarks": payload.get("remarks") or None,
        }
        await db.it_components.update_one({"component_id": component_id}, {"$set": {
            "status": "Disposed", "disposal": disposal, "parent_asset_id": None, "slot": None,
            "updated_at": _now(),
        }})
        await _history(component_id, "Disposed", current_user,
                       f"Disposed · {disposal['reason'] or ''} ({disposal['method'] or ''})".strip())
        await log_audit(current_user["id"], "it_component_disposed", "it_component", component_id)
        return {"success": True}

    # ================= SOFT DELETE / ARCHIVE =================
    @api_router.delete("/it/components/{component_id}")
    async def comp_delete(component_id: str, current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        component = await db.it_components.find_one({"component_id": component_id, "is_deleted": {"$ne": True}})
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")
        if component.get("parent_asset_id"):
            raise HTTPException(status_code=400, detail="Remove the component from its parent asset before archiving.")
        await db.it_components.update_one({"component_id": component_id}, {"$set": {
            "is_deleted": True, "archived": True, "updated_at": _now()}})
        await _history(component_id, "Archived", current_user, "Component archived (soft delete)")
        await log_audit(current_user["id"], "it_component_archived", "it_component", component_id)
        return {"success": True}

    # ================= PARENT ASSET: COMPONENTS + CURRENT CONFIG =================
    async def _installed_components(asset_id: str) -> List[dict]:
        return [d async for d in db.it_components.find(
            {"parent_asset_id": asset_id, "is_deleted": {"$ne": True}}, {"_id": 0}).sort("type", 1)]

    def _build_config(items: List[dict]) -> dict:
        by_type: dict = {}
        for c in items:
            by_type.setdefault(c["type"], []).append({
                "component_id": c["component_id"], "display": _display(c),
                "slot": c.get("slot"), "serial_number": c.get("serial_number"),
                "capacity": c.get("capacity"), "condition": c.get("condition"),
            })
        return {"by_type": by_type,
                "items": [{"type": c["type"], "component_id": c["component_id"], "slot": c.get("slot"),
                           "display": _display(c), "status": c.get("status")} for c in items]}

    @api_router.get("/it/assets/{asset_id}/components")
    async def asset_components(asset_id: str, current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        parent = await _parent_asset(asset_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Asset not found.")
        items = await _installed_components(asset_id)
        # Configuration history from install/remove events on this parent
        events = [_clean(h) async for h in db.it_component_history.find(
            {"parent_asset_id": asset_id, "action": {"$in": ["Installed", "Removed", "Replaced"]}}).sort("at", 1)]
        assignments = await asset_assignment_history(db, asset_id)
        return {"asset_id": asset_id, "assigned_to": parent.get("assigned_to"),
                "components": items, "current_configuration": _build_config(items),
                "config_history": events, "assignment_history": assignments}

    # ================= BULK INSTALL (used by Create/Edit-Asset component picker) =================
    @api_router.post("/it/assets/{asset_id}/install-components")
    async def asset_install_components(asset_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        """Install a batch of components into an asset with transaction-style safety:
        pre-validate all, install atomically one-by-one, and roll back everything
        already installed if any single install fails."""
        await _require_admin(current_user)
        parent = await _parent_asset(asset_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Asset not found.")
        items = payload.get("items") or payload.get("components") or []
        if not items:
            return {"installed": 0}
        # Pre-validate (fast fail) — no duplicates in request, all exist and free
        seen = set()
        for it in items:
            cid = (it.get("component_id") or "").strip()
            if not cid:
                raise HTTPException(status_code=400, detail="A component_id is missing.")
            if cid in seen:
                raise HTTPException(status_code=400, detail=f"{cid} listed more than once.")
            seen.add(cid)
            c = await db.it_components.find_one({"component_id": cid, "is_deleted": {"$ne": True}})
            if not c:
                raise HTTPException(status_code=400, detail=f"Component {cid} not found.")
            if c.get("parent_asset_id"):
                raise HTTPException(status_code=400, detail=f"{cid} is already installed in {c['parent_asset_id']}.")
            if c.get("status") in C_BLOCKED_INSTALL:
                raise HTTPException(status_code=400, detail=f"{cid} status '{c['status']}' cannot be installed.")
        installed = []
        try:
            for it in items:
                cid = it["component_id"].strip()
                comp = await db.it_components.find_one({"component_id": cid, "is_deleted": {"$ne": True}})
                await _do_install(comp, asset_id, current_user, {"slot": it.get("slot")})
                installed.append(cid)
        except HTTPException:
            # Roll back everything we installed in this batch
            for cid in installed:
                comp = await db.it_components.find_one({"component_id": cid, "is_deleted": {"$ne": True}})
                if comp and comp.get("parent_asset_id") == asset_id:
                    await _do_remove(comp, current_user, {"reason": "Rollback", "new_status": "Available", "remarks": "Batch install rolled back"})
            raise
        return {"installed": len(installed), "component_ids": installed}

    # ================= IMPORT =================
    @api_router.get("/it/components/import/template")
    async def comp_import_template(current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(C_IMPORT_COLUMNS)
        w.writerow(["", "RAM", "Kingston Fury 16GB", "Kingston", "Fury", "ABC123", "KF-16",
                    "16 GB", "Available", "Good", "Existing / Legacy Asset", "IT Store",
                    "", "", "", "", "", "", "Legacy component - purchase info unknown"])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=it_component_import_template.csv"})

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

    async def _validate_comp_rows(rows: List[dict]):
        types = {t["name"].lower(): t async for t in db.it_component_types.find({})}
        seen_ids, seen_serials = set(), set()
        existing_ids, existing_serials = set(), set()
        async for c in db.it_components.find({"is_deleted": {"$ne": True}}, {"_id": 0, "component_id": 1, "serial_number": 1}):
            existing_ids.add(c["component_id"])
            if c.get("serial_number"):
                existing_serials.add(c["serial_number"])
        out = []
        for idx, r in enumerate(rows, start=2):
            errors, warnings = [], []
            type_name = (r.get("type") or "").strip()
            status = (r.get("status") or "").strip() or "Available"
            cid = (r.get("component_id") or "").strip()
            serial = (r.get("serial_number") or "").strip()
            if not type_name:
                errors.append("Type is missing.")
            elif type_name.lower() not in types:
                errors.append(f"Invalid component type '{type_name}'.")
            if status not in C_STATUSES:
                errors.append(f"Invalid status '{status}'.")
            if cid:
                if cid in existing_ids:
                    errors.append(f"Component ID {cid} already exists.")
                if cid in seen_ids:
                    errors.append(f"Duplicate Component ID {cid} within file.")
                seen_ids.add(cid)
            if serial:
                if serial in existing_serials:
                    errors.append(f"Serial {serial} already exists.")
                if serial in seen_serials:
                    errors.append(f"Duplicate Serial {serial} within file.")
                seen_serials.add(serial)
            else:
                warnings.append("Serial number missing.")
            if not (r.get("purchase_date") or "").strip():
                warnings.append("Purchase date missing.")
            out.append({"row": idx, "data": r, "errors": errors, "warnings": warnings, "valid": len(errors) == 0})
        return out

    @api_router.post("/it/components/import/preview")
    async def comp_import_preview(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        await _ensure_types()
        content = await file.read()
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 8MB).")
        rows = _parse_upload(file.filename, content)
        if not rows:
            raise HTTPException(status_code=400, detail="No data rows found in file.")
        validated = await _validate_comp_rows(rows)
        return {"total": len(validated), "valid": sum(1 for v in validated if v["valid"]),
                "errors": sum(1 for v in validated if v["errors"]),
                "warnings": sum(1 for v in validated if v["warnings"]),
                "rows": validated[:1000]}

    @api_router.post("/it/components/import/confirm")
    async def comp_import_confirm(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        rows = payload.get("rows") or []
        validated = await _validate_comp_rows([r.get("data", r) for r in rows])
        created, skipped = 0, 0
        for v in validated:
            if not v["valid"]:
                skipped += 1
                continue
            r = v["data"]
            try:
                doc = await _build_component_doc({
                    "component_id": r.get("component_id"), "type": r.get("type"), "name": r.get("name"),
                    "brand": r.get("brand"), "model": r.get("model"), "serial_number": r.get("serial_number"),
                    "part_number": r.get("part_number"), "capacity": r.get("capacity"),
                    "status": (r.get("status") or "Available"), "condition": r.get("condition"),
                    "source": r.get("source") or "Existing / Legacy Asset", "location": r.get("location"),
                    "remarks": r.get("remarks"),
                    "purchase": {k: r.get(k) for k in ("purchase_date", "purchase_cost", "vendor", "invoice_number") if r.get(k)},
                    "warranty": {k: r.get(k) for k in ("warranty_start", "warranty_end") if r.get(k)},
                }, current_user)
                await db.it_components.insert_one(doc)
                await _history(doc["component_id"], "Created", current_user, "Imported from file")
                created += 1
            except Exception:
                skipped += 1
        await log_audit(current_user["id"], "it_component_bulk_import", "it_component", f"created={created}")
        return {"created": created, "skipped": skipped}

    # ================= BULK ASSEMBLY =================
    async def _validate_assembly(rows: List[dict]):
        out = []
        planned = {}  # component_id -> row (detect dup within file)
        for idx, r in enumerate(rows, start=2):
            errors, warnings = [], []
            aid = (r.get("parent_asset_id") or "").strip()
            cid = (r.get("component_id") or "").strip()
            slot = (r.get("slot") or "").strip()
            if not aid:
                errors.append("parent_asset_id missing.")
            if not cid:
                errors.append("component_id missing.")
            if aid and not await _parent_asset(aid):
                errors.append(f"Parent asset {aid} not found.")
            if cid:
                comp = await db.it_components.find_one({"component_id": cid, "is_deleted": {"$ne": True}})
                if not comp:
                    errors.append(f"Component {cid} not found.")
                else:
                    if comp.get("parent_asset_id"):
                        errors.append(f"{cid} already installed in {comp['parent_asset_id']}.")
                    if comp.get("status") in C_BLOCKED_INSTALL:
                        errors.append(f"{cid} status '{comp['status']}' cannot be installed.")
                if cid in planned:
                    errors.append(f"Component {cid} appears multiple times in file.")
                planned[cid] = idx
            out.append({"row": idx, "data": {"parent_asset_id": aid, "component_id": cid, "slot": slot},
                        "errors": errors, "warnings": warnings, "valid": len(errors) == 0})
        return out

    @api_router.post("/it/components/assembly/preview")
    async def comp_assembly_preview(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        content = await file.read()
        rows = _parse_upload(file.filename, content)
        if not rows:
            raise HTTPException(status_code=400, detail="No data rows found in file.")
        validated = await _validate_assembly(rows)
        return {"total": len(validated), "valid": sum(1 for v in validated if v["valid"]),
                "errors": sum(1 for v in validated if v["errors"]), "rows": validated[:1000]}

    @api_router.post("/it/components/assembly/confirm")
    async def comp_assembly_confirm(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        await _require_admin(current_user)
        rows = payload.get("rows") or []
        validated = await _validate_assembly([r.get("data", r) for r in rows])
        installed, skipped = 0, 0
        for v in validated:
            if not v["valid"]:
                skipped += 1
                continue
            r = v["data"]
            comp = await db.it_components.find_one({"component_id": r["component_id"], "is_deleted": {"$ne": True}})
            if not comp or comp.get("parent_asset_id"):
                skipped += 1
                continue
            try:
                await _do_install(comp, r["parent_asset_id"], current_user, {"slot": r.get("slot")})
                installed += 1
            except Exception:
                skipped += 1
        await log_audit(current_user["id"], "it_component_bulk_assembly", "it_component", f"installed={installed}")
        return {"installed": installed, "skipped": skipped}

    # ================= EMPLOYEE SELF-SERVICE (inherited via parent asset) =================
    @api_router.get("/employee/it-components")
    async def my_components(current_user: dict = Depends(get_current_user)):
        emp_id = current_user.get("employee_id")
        if not emp_id:
            return {"assets": []}
        assets = [a async for a in db.it_assets.find(
            {"assigned_to.employee_id": emp_id, "is_deleted": {"$ne": True}},
            {"_id": 0, "asset_id": 1, "category": 1})]
        out = []
        for a in assets:
            comps = await _installed_components(a["asset_id"])
            out.append({"asset_id": a["asset_id"], "category": a.get("category"),
                        "configuration": _build_config(comps)})
        return {"assets": out}

    return {"ok": True}
