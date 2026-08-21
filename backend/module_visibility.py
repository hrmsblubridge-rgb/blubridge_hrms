"""Module Visibility Control — Admin can toggle employee-facing HRMS modules
ON/OFF and restrict them to selected or excluded employees.

Backward-compat: any module without a settings record is treated as
`enabled=True, visibility_mode=ALL` (default open). Admin always bypasses
these checks.

Collections:
  - module_visibility_settings  (one doc per module_key)
  - module_visibility_selections (module_key + employee_id, one row each)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import HTTPException, Depends, Body
from pydantic import BaseModel, Field

from server import (
    api_router, db, get_current_user, UserRole,
    ALL_ADMIN_ROLES, log_audit,
)


# ---------------------------------------------------------------------------
# Module registry — the canonical list of employee-facing modules that can
# be controlled. `route` is the frontend path used by the sidebar filter.
# Dashboard and Profile are intentionally excluded (essential system pages).
# ---------------------------------------------------------------------------
EMPLOYEE_MODULES = [
    {"key": "attendance",           "name": "My Attendance",         "route": "/employee/attendance"},
    {"key": "leave",                "name": "Leave",                 "route": "/employee/leave"},
    {"key": "late_request",         "name": "Late Request",          "route": "/employee/late-request"},
    {"key": "early_out",            "name": "Early Out",             "route": "/employee/early-out"},
    {"key": "missed_punch",         "name": "Missed Punch",          "route": "/employee/missed-punch"},
    {"key": "holidays",             "name": "Holidays",              "route": "/employee/holidays"},
    {"key": "payslips",             "name": "My Payslips",           "route": "/employee/payslips"},
    {"key": "policies",             "name": "Policies",              "route": "/employee/policies"},
    {"key": "education_experience", "name": "Education & Experience","route": "/employee/education-experience"},
    {"key": "documents",            "name": "My Documents",          "route": "/employee/documents"},
    {"key": "tickets",              "name": "Support Tickets",       "route": "/employee/tickets"},
    {"key": "warnings",             "name": "My Warnings",           "route": "/employee/warnings"},
    {"key": "vigilance",            "name": "Vigilance Report",      "route": "/employee/vigilance"},
]
_VALID_KEYS = {m["key"] for m in EMPLOYEE_MODULES}

VISIBILITY_ALL = "ALL"
VISIBILITY_SELECTED_ONLY = "SELECTED_ONLY"
VISIBILITY_ALL_EXCEPT_SELECTED = "ALL_EXCEPT_SELECTED"
_VALID_MODES = {VISIBILITY_ALL, VISIBILITY_SELECTED_ONLY, VISIBILITY_ALL_EXCEPT_SELECTED}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _require_admin(user):
    if user.get("role") not in ALL_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")


def _is_admin(user) -> bool:
    return user.get("role") in ALL_ADMIN_ROLES


# ---------------------------------------------------------------------------
# Public helper used by other backend routes to enforce access.
# ---------------------------------------------------------------------------
async def check_module_access(user: dict, module_key: str) -> bool:
    """Return True if the user is allowed to access `module_key`.

    Admin roles bypass unconditionally. Employees are checked against the
    stored settings — missing records default to ALLOW (backward-compat).
    """
    if _is_admin(user):
        return True
    if module_key not in _VALID_KEYS:
        # Unknown module → no restriction (defensive default)
        return True

    setting = await db.module_visibility_settings.find_one(
        {"module_key": module_key}, {"_id": 0}
    )
    if not setting:
        return True  # unmigrated → default open
    if not setting.get("enabled", True):
        return False
    mode = setting.get("visibility_mode", VISIBILITY_ALL)
    if mode == VISIBILITY_ALL:
        return True

    emp_id = user.get("employee_id") or user.get("id")
    sel = await db.module_visibility_selections.find_one(
        {"module_key": module_key, "employee_id": emp_id}, {"_id": 0, "employee_id": 1}
    )
    in_list = sel is not None
    if mode == VISIBILITY_SELECTED_ONLY:
        return in_list
    if mode == VISIBILITY_ALL_EXCEPT_SELECTED:
        return not in_list
    return True


# ---------------------------------------------------------------------------
# Startup seed — ensure every module has a default settings record.
# ---------------------------------------------------------------------------
async def ensure_module_visibility_seed():
    try:
        await db.module_visibility_settings.create_index(
            [("module_key", 1)], unique=True, name="unique_module_key"
        )
        await db.module_visibility_selections.create_index(
            [("module_key", 1), ("employee_id", 1)],
            unique=True,
            name="unique_module_employee",
        )
        await db.module_visibility_selections.create_index(
            [("module_key", 1)], name="mv_selections_by_module"
        )
    except Exception:
        pass

    now = _now()
    for m in EMPLOYEE_MODULES:
        existing = await db.module_visibility_settings.find_one(
            {"module_key": m["key"]}, {"_id": 0, "module_key": 1}
        )
        if not existing:
            await db.module_visibility_settings.insert_one({
                "id": str(uuid.uuid4()),
                "module_key": m["key"],
                "module_name": m["name"],
                "enabled": True,
                "visibility_mode": VISIBILITY_ALL,
                "updated_by": "system",
                "updated_by_id": None,
                "updated_at": now,
                "created_at": now,
            })


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ModuleSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    visibility_mode: Optional[str] = None


class ModuleEmployeeSelection(BaseModel):
    employee_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
@api_router.get("/settings/module-visibility")
async def list_module_visibility(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    settings_by_key = {}
    async for s in db.module_visibility_settings.find({}, {"_id": 0}):
        settings_by_key[s["module_key"]] = s

    # Fetch selection counts per module in one aggregation
    counts_by_key = {}
    pipeline = [{"$group": {"_id": "$module_key", "count": {"$sum": 1}}}]
    async for row in db.module_visibility_selections.aggregate(pipeline):
        counts_by_key[row["_id"]] = row["count"]

    result = []
    for m in EMPLOYEE_MODULES:
        s = settings_by_key.get(m["key"], {})
        result.append({
            "module_key": m["key"],
            "module_name": m["name"],
            "route": m["route"],
            "enabled": s.get("enabled", True),
            "visibility_mode": s.get("visibility_mode", VISIBILITY_ALL),
            "selection_count": counts_by_key.get(m["key"], 0),
            "updated_at": s.get("updated_at"),
            "updated_by": s.get("updated_by"),
        })
    return result


@api_router.put("/settings/module-visibility/{module_key}")
async def update_module_visibility(
    module_key: str,
    body: ModuleSettingUpdate,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    if module_key not in _VALID_KEYS:
        raise HTTPException(status_code=404, detail="Unknown module")

    update = {}
    if body.enabled is not None:
        update["enabled"] = bool(body.enabled)
    if body.visibility_mode is not None:
        if body.visibility_mode not in _VALID_MODES:
            raise HTTPException(status_code=400, detail="Invalid visibility_mode")
        update["visibility_mode"] = body.visibility_mode

    if not update:
        raise HTTPException(status_code=400, detail="No changes provided")

    update["updated_at"] = _now()
    update["updated_by"] = current_user.get("username") or current_user.get("name")
    update["updated_by_id"] = current_user.get("id")

    # Validation: SELECTED_ONLY requires at least one selection when enabling
    if update.get("visibility_mode") == VISIBILITY_SELECTED_ONLY:
        count = await db.module_visibility_selections.count_documents(
            {"module_key": module_key}
        )
        if count == 0 and (update.get("enabled", True) is not False):
            raise HTTPException(
                status_code=400,
                detail="Select at least one employee before enabling 'Selected Only' mode.",
            )

    await db.module_visibility_settings.update_one(
        {"module_key": module_key},
        {"$set": update},
        upsert=True,
    )
    await log_audit(
        current_user["id"],
        "module_visibility_update",
        "module_visibility",
        module_key,
        f"Module {module_key} updated: {update}",
    )
    updated = await db.module_visibility_settings.find_one(
        {"module_key": module_key}, {"_id": 0}
    )
    return updated


@api_router.get("/settings/module-visibility/{module_key}/employees")
async def get_module_selected_employees(
    module_key: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    if module_key not in _VALID_KEYS:
        raise HTTPException(status_code=404, detail="Unknown module")
    rows = await db.module_visibility_selections.find(
        {"module_key": module_key}, {"_id": 0, "employee_id": 1}
    ).to_list(10000)
    return {"module_key": module_key, "employee_ids": [r["employee_id"] for r in rows]}


@api_router.put("/settings/module-visibility/{module_key}/employees")
async def set_module_selected_employees(
    module_key: str,
    body: ModuleEmployeeSelection,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    if module_key not in _VALID_KEYS:
        raise HTTPException(status_code=404, detail="Unknown module")

    # Deduplicate & drop empties
    new_ids = sorted({eid.strip() for eid in (body.employee_ids or []) if eid and eid.strip()})

    # Replace-set: delete old and insert new (simple + correct at expected scale)
    await db.module_visibility_selections.delete_many({"module_key": module_key})
    if new_ids:
        docs = [{"module_key": module_key, "employee_id": eid} for eid in new_ids]
        try:
            await db.module_visibility_selections.insert_many(docs, ordered=False)
        except Exception:
            pass

    # Touch updated_at on the parent setting
    await db.module_visibility_settings.update_one(
        {"module_key": module_key},
        {
            "$set": {
                "updated_at": _now(),
                "updated_by": current_user.get("username") or current_user.get("name"),
                "updated_by_id": current_user.get("id"),
            }
        },
        upsert=True,
    )

    await log_audit(
        current_user["id"],
        "module_visibility_selection_update",
        "module_visibility",
        module_key,
        f"Module {module_key} selection set to {len(new_ids)} employees",
    )
    return {"module_key": module_key, "employee_ids": new_ids, "count": len(new_ids)}


# ---------------------------------------------------------------------------
# Employee endpoint — returns list of visible module keys for the sidebar.
# ---------------------------------------------------------------------------
@api_router.get("/employee/module-visibility")
async def get_visible_modules_for_me(current_user: dict = Depends(get_current_user)):
    # Admins get everything (sidebar/settings guard uses this too if needed)
    if _is_admin(current_user):
        return {"visible_modules": [m["key"] for m in EMPLOYEE_MODULES]}

    visible = []
    for m in EMPLOYEE_MODULES:
        if await check_module_access(current_user, m["key"]):
            visible.append(m["key"])
    return {"visible_modules": visible}
