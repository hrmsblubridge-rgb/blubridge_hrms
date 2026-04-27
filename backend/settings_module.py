"""
Centralized HRMS Settings Module.

Provides CRUD endpoints and service layer for:
  - Departments
  - Teams
  - Designations
  - Holidays (extends existing /holidays)
  - Shifts (new config, coexists with legacy SHIFT_DEFINITIONS)
  - Employee Shift Assignments (history with effective_from / effective_to)

Also exposes:
  - ShiftService.resolve_shift_for_employee(employee_id, date)
  - AttendanceRuleEngine.recompute_attendance(...)

Backward compatibility:
  - Existing 'departments', 'teams', 'holidays' collections are preserved.
  - Existing 'employees.shift_type / custom_*' fields remain the source of
    truth for realtime attendance. When a shift is assigned via Settings the
    corresponding employee doc is SYNCED so the legacy attendance engine
    keeps working unchanged for employees who have not yet been migrated.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, UploadFile, File as FastAPIFile
from pydantic import BaseModel, Field


# ============================================================
#  Pydantic models
# ============================================================

class DepartmentIn(BaseModel):
    name: str
    description: Optional[str] = ""
    head_id: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    head_id: Optional[str] = None


class TeamIn(BaseModel):
    name: str
    department: Optional[str] = None           # department NAME (legacy FK)
    department_id: Optional[str] = None        # department id (new FK)
    description: Optional[str] = ""


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[str] = None
    description: Optional[str] = None


class DesignationIn(BaseModel):
    name: str
    description: Optional[str] = ""


class DesignationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class HolidayIn(BaseModel):
    name: str
    holiday_date: str            # YYYY-MM-DD
    is_paid: bool = True
    day: Optional[str] = None    # optional (kept for legacy UI)
    type: Optional[str] = "company"
    note: Optional[str] = None


class HolidayUpdateIn(BaseModel):
    name: Optional[str] = None
    holiday_date: Optional[str] = None
    is_paid: Optional[bool] = None
    day: Optional[str] = None
    type: Optional[str] = None
    note: Optional[str] = None


class ShiftIn(BaseModel):
    name: str
    start_time: str                            # "HH:MM" 24h
    total_hours: float = Field(..., gt=0)
    late_grace_minutes: int = 0
    early_out_grace_minutes: int = 0
    status: str = "active"                     # active | inactive
    description: Optional[str] = ""


class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    total_hours: Optional[float] = None
    late_grace_minutes: Optional[int] = None
    early_out_grace_minutes: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None


class AssignShiftIn(BaseModel):
    employee_ids: List[str] = Field(default_factory=list)
    shift_id: str
    effective_from: str                        # YYYY-MM-DD
    effective_to: Optional[str] = None         # YYYY-MM-DD, nullable


class BulkAssignByFilterIn(BaseModel):
    shift_id: str
    effective_from: str
    effective_to: Optional[str] = None
    departments: Optional[List[str]] = None    # names
    teams: Optional[List[str]] = None
    designations: Optional[List[str]] = None


class RecalcIn(BaseModel):
    employee_ids: Optional[List[str]] = None
    from_date: Optional[str] = None            # DD-MM-YYYY
    to_date: Optional[str] = None              # DD-MM-YYYY


# ============================================================
#  Module registration
# ============================================================

def register(api_router, deps):
    """Attach Settings routes to the provided APIRouter.

    deps must contain: db, get_current_user, log_audit, get_ist_now,
    serialize_doc, parse_time_24h_to_minutes, UserRole, ADMIN_ROLES,
    SYSTEM_ROLES, EmployeeStatus.
    """
    db = deps["db"]
    get_current_user = deps["get_current_user"]
    log_audit = deps["log_audit"]
    get_ist_now = deps["get_ist_now"]
    serialize_doc = deps["serialize_doc"]
    parse_time_24h_to_minutes = deps["parse_time_24h_to_minutes"]
    SYSTEM_ROLES = deps["SYSTEM_ROLES"]
    EmployeeStatus = deps["EmployeeStatus"]

    def _now_iso():
        return get_ist_now().isoformat()

    def _require_settings_write(user: dict):
        if user["role"] not in SYSTEM_ROLES:
            raise HTTPException(status_code=403, detail="Permission denied")

    # --------------------------------------------------------
    #  Service layer
    # --------------------------------------------------------

    async def resolve_shift_for_employee(employee_id: str, date_yyyy_mm_dd: str) -> Optional[dict]:
        """Return the active shift config (with grace) for a given date.

        SELECT shift WHERE employee_id = X AND effective_from <= date
            AND (effective_to IS NULL OR effective_to >= date)
            ORDER BY effective_from DESC LIMIT 1
        """
        assignment = await db.employee_shifts.find_one(
            {
                "employee_id": employee_id,
                "is_deleted": {"$ne": True},
                "effective_from": {"$lte": date_yyyy_mm_dd},
                "$or": [
                    {"effective_to": None},
                    {"effective_to": {"$gte": date_yyyy_mm_dd}},
                ],
            },
            {"_id": 0},
            sort=[("effective_from", -1)],
        )
        if not assignment:
            return None
        shift = await db.shifts.find_one({"id": assignment["shift_id"], "is_deleted": {"$ne": True}}, {"_id": 0})
        if not shift:
            return None
        return {
            "shift_id": shift["id"],
            "name": shift["name"],
            "start_time": shift["start_time"],
            "total_hours": float(shift["total_hours"]),
            "late_grace_minutes": int(shift.get("late_grace_minutes", 0) or 0),
            "early_out_grace_minutes": int(shift.get("early_out_grace_minutes", 0) or 0),
        }

    async def _sync_shift_to_employee(employee_id: str, shift: dict):
        """Mirror the shift config onto the legacy employee.shift_* fields so the
        existing attendance engine continues to work unchanged."""
        login = shift["start_time"]
        total = float(shift["total_hours"])
        total_mins = int(round(total * 60))
        login_mins = parse_time_24h_to_minutes(login) or 0
        logout_mins = (login_mins + total_mins) % (24 * 60)
        logout = f"{logout_mins // 60:02d}:{logout_mins % 60:02d}"
        # Accept both db-shift docs (key 'id') and resolver dicts (key 'shift_id')
        sid = shift.get("id") or shift.get("shift_id")
        sname = shift.get("name") or shift.get("shift_name")
        await db.employees.update_one(
            {"id": employee_id},
            {"$set": {
                "shift_type": "Custom",
                "custom_login_time": login,
                "custom_logout_time": logout,
                "custom_total_hours": total,
                "late_grace_minutes": int(shift.get("late_grace_minutes", 0) or 0),
                "early_out_grace_minutes": int(shift.get("early_out_grace_minutes", 0) or 0),
                "active_shift_id": sid,
                "active_shift_name": sname,
                "updated_at": _now_iso(),
            }},
        )

    async def _apply_active_shifts_now():
        """Re-sync each employee with the currently-active shift (effective today)."""
        today = get_ist_now().strftime("%Y-%m-%d")
        employees = await db.employees.find({"is_deleted": {"$ne": True}}, {"_id": 0, "id": 1}).to_list(2000)
        for e in employees:
            shift = await resolve_shift_for_employee(e["id"], today)
            if shift:
                await _sync_shift_to_employee(e["id"], shift)

    # --------------------------------------------------------
    #  Departments
    # --------------------------------------------------------

    @api_router.get("/settings/departments")
    async def settings_list_departments(include_deleted: bool = False,
                                        current_user: dict = Depends(get_current_user)):
        q = {} if include_deleted else {"is_deleted": {"$ne": True}}
        depts = await db.departments.find(q, {"_id": 0}).to_list(500)
        for d in depts:
            d["employee_count"] = await db.employees.count_documents({
                "department": d["name"],
                "is_deleted": {"$ne": True},
                "employee_status": EmployeeStatus.ACTIVE,
            })
            d["team_count"] = await db.teams.count_documents({
                "department": d["name"], "is_deleted": {"$ne": True},
            })
        return [serialize_doc(d) for d in depts]

    @api_router.post("/settings/departments")
    async def settings_create_department(data: DepartmentIn, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        existing = await db.departments.find_one({"name": name, "is_deleted": {"$ne": True}})
        if existing:
            raise HTTPException(status_code=409, detail="Department with this name already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": data.description or "",
            "head_id": data.head_id,
            "is_deleted": False,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.departments.insert_one(doc.copy())
        await log_audit(current_user["id"], "create_department", "department", doc["id"], name)
        return serialize_doc(doc)

    @api_router.put("/settings/departments/{dept_id}")
    async def settings_update_department(dept_id: str, data: DepartmentUpdate,
                                         current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.departments.find_one({"id": dept_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Department not found")
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if "name" in updates and updates["name"] != existing["name"]:
            clash = await db.departments.find_one({"name": updates["name"], "is_deleted": {"$ne": True}})
            if clash:
                raise HTTPException(status_code=409, detail="Department with this name already exists")
        if not updates:
            return serialize_doc(existing)
        updates["updated_at"] = _now_iso()
        await db.departments.update_one({"id": dept_id}, {"$set": updates})
        # Propagate name change to teams + employees (maintain FK by-name)
        if "name" in updates and updates["name"] != existing["name"]:
            await db.teams.update_many({"department": existing["name"]}, {"$set": {"department": updates["name"]}})
            await db.employees.update_many({"department": existing["name"]}, {"$set": {"department": updates["name"]}})
        await log_audit(current_user["id"], "update_department", "department", dept_id)
        updated = await db.departments.find_one({"id": dept_id}, {"_id": 0})
        return serialize_doc(updated)

    @api_router.delete("/settings/departments/{dept_id}")
    async def settings_delete_department(dept_id: str, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.departments.find_one({"id": dept_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Department not found")
        emp_count = await db.employees.count_documents({
            "department": existing["name"], "is_deleted": {"$ne": True},
        })
        if emp_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete: {emp_count} employees are assigned to this department",
            )
        await db.departments.update_one(
            {"id": dept_id},
            {"$set": {"is_deleted": True, "deleted_at": _now_iso()}},
        )
        await log_audit(current_user["id"], "delete_department", "department", dept_id)
        return {"message": "Department deleted"}

    # --------------------------------------------------------
    #  Teams
    # --------------------------------------------------------

    @api_router.get("/settings/teams")
    async def settings_list_teams(department: Optional[str] = None,
                                  include_deleted: bool = False,
                                  current_user: dict = Depends(get_current_user)):
        q = {} if include_deleted else {"is_deleted": {"$ne": True}}
        if department and department != "All":
            q["department"] = department
        teams = await db.teams.find(q, {"_id": 0}).to_list(500)
        for t in teams:
            t["member_count"] = await db.employees.count_documents({
                "team": t["name"],
                "is_deleted": {"$ne": True},
                "employee_status": EmployeeStatus.ACTIVE,
            })
        return [serialize_doc(t) for t in teams]

    async def _resolve_department_name(department: Optional[str], department_id: Optional[str]) -> str:
        if department:
            dep = await db.departments.find_one({"name": department, "is_deleted": {"$ne": True}}, {"_id": 0})
            if not dep:
                raise HTTPException(status_code=400, detail=f"Department '{department}' not found")
            return dep["name"]
        if department_id:
            dep = await db.departments.find_one({"id": department_id, "is_deleted": {"$ne": True}}, {"_id": 0})
            if not dep:
                raise HTTPException(status_code=400, detail="Department id not found")
            return dep["name"]
        raise HTTPException(status_code=400, detail="department or department_id is required")

    @api_router.post("/settings/teams")
    async def settings_create_team(data: TeamIn, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        dept_name = await _resolve_department_name(data.department, data.department_id)
        existing = await db.teams.find_one({"name": name, "is_deleted": {"$ne": True}})
        if existing:
            raise HTTPException(status_code=409, detail="Team with this name already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "name": name,
            "department": dept_name,
            "description": data.description or "",
            "is_deleted": False,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.teams.insert_one(doc.copy())
        await log_audit(current_user["id"], "create_team", "team", doc["id"], name)
        return serialize_doc(doc)

    @api_router.put("/settings/teams/{team_id}")
    async def settings_update_team(team_id: str, data: TeamUpdate,
                                   current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Team not found")
        updates = {}
        if data.name is not None and data.name != existing["name"]:
            clash = await db.teams.find_one({"name": data.name, "is_deleted": {"$ne": True}})
            if clash:
                raise HTTPException(status_code=409, detail="Team with this name already exists")
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.department is not None or data.department_id is not None:
            updates["department"] = await _resolve_department_name(data.department, data.department_id)
        if not updates:
            return serialize_doc(existing)
        updates["updated_at"] = _now_iso()
        await db.teams.update_one({"id": team_id}, {"$set": updates})
        if "name" in updates and updates["name"] != existing["name"]:
            await db.employees.update_many({"team": existing["name"]}, {"$set": {"team": updates["name"]}})
        await log_audit(current_user["id"], "update_team", "team", team_id)
        updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
        return serialize_doc(updated)

    @api_router.delete("/settings/teams/{team_id}")
    async def settings_delete_team(team_id: str, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Team not found")
        emp_count = await db.employees.count_documents({
            "team": existing["name"], "is_deleted": {"$ne": True},
        })
        if emp_count > 0:
            raise HTTPException(status_code=400, detail=f"Cannot delete: {emp_count} employees are on this team")
        await db.teams.update_one(
            {"id": team_id},
            {"$set": {"is_deleted": True, "deleted_at": _now_iso()}},
        )
        await log_audit(current_user["id"], "delete_team", "team", team_id)
        return {"message": "Team deleted"}

    # --------------------------------------------------------
    #  Designations
    # --------------------------------------------------------

    async def _seed_designations_from_employees():
        existing = await db.designations.count_documents({})
        if existing > 0:
            return
        seen = set()
        cursor = db.employees.find({"is_deleted": {"$ne": True}}, {"_id": 0, "designation": 1})
        async for e in cursor:
            d = (e.get("designation") or "").strip()
            if d and d.lower() not in seen:
                seen.add(d.lower())
                await db.designations.insert_one({
                    "id": str(uuid.uuid4()),
                    "name": d,
                    "description": "",
                    "is_deleted": False,
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                })

    @api_router.get("/settings/designations")
    async def settings_list_designations(include_deleted: bool = False,
                                         current_user: dict = Depends(get_current_user)):
        await _seed_designations_from_employees()
        q = {} if include_deleted else {"is_deleted": {"$ne": True}}
        desigs = await db.designations.find(q, {"_id": 0}).sort("name", 1).to_list(500)
        for d in desigs:
            d["employee_count"] = await db.employees.count_documents({
                "designation": d["name"],
                "is_deleted": {"$ne": True},
                "employee_status": EmployeeStatus.ACTIVE,
            })
        return [serialize_doc(d) for d in desigs]

    @api_router.post("/settings/designations")
    async def settings_create_designation(data: DesignationIn, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        clash = await db.designations.find_one({"name": name, "is_deleted": {"$ne": True}})
        if clash:
            raise HTTPException(status_code=409, detail="Designation with this name already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": data.description or "",
            "is_deleted": False,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.designations.insert_one(doc.copy())
        await log_audit(current_user["id"], "create_designation", "designation", doc["id"], name)
        return serialize_doc(doc)

    @api_router.put("/settings/designations/{desig_id}")
    async def settings_update_designation(desig_id: str, data: DesignationUpdate,
                                          current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.designations.find_one({"id": desig_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Designation not found")
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if "name" in updates and updates["name"] != existing["name"]:
            clash = await db.designations.find_one({"name": updates["name"], "is_deleted": {"$ne": True}})
            if clash:
                raise HTTPException(status_code=409, detail="Designation already exists")
        if not updates:
            return serialize_doc(existing)
        updates["updated_at"] = _now_iso()
        await db.designations.update_one({"id": desig_id}, {"$set": updates})
        if "name" in updates and updates["name"] != existing["name"]:
            await db.employees.update_many(
                {"designation": existing["name"]},
                {"$set": {"designation": updates["name"]}},
            )
        await log_audit(current_user["id"], "update_designation", "designation", desig_id)
        updated = await db.designations.find_one({"id": desig_id}, {"_id": 0})
        return serialize_doc(updated)

    @api_router.delete("/settings/designations/{desig_id}")
    async def settings_delete_designation(desig_id: str, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.designations.find_one({"id": desig_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Designation not found")
        emp_count = await db.employees.count_documents({
            "designation": existing["name"], "is_deleted": {"$ne": True},
        })
        if emp_count > 0:
            raise HTTPException(status_code=400, detail=f"Cannot delete: {emp_count} employees have this designation")
        await db.designations.update_one(
            {"id": desig_id},
            {"$set": {"is_deleted": True, "deleted_at": _now_iso()}},
        )
        await log_audit(current_user["id"], "delete_designation", "designation", desig_id)
        return {"message": "Designation deleted"}

    # --------------------------------------------------------
    #  Holidays (thin wrapper enforcing unique date + is_paid)
    # --------------------------------------------------------

    @api_router.get("/settings/holidays")
    async def settings_list_holidays(year: Optional[int] = None,
                                     current_user: dict = Depends(get_current_user)):
        q = {}
        if year:
            q["year"] = year
        holidays = await db.holidays.find(q, {"_id": 0}).sort("date", 1).to_list(500)
        return [serialize_doc(h) for h in holidays]

    @api_router.post("/settings/holidays")
    async def settings_create_holiday(data: HolidayIn, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        try:
            y, m, d = data.holiday_date.split("-")
            dt = datetime(int(y), int(m), int(d))
        except Exception:
            raise HTTPException(status_code=400, detail="holiday_date must be YYYY-MM-DD")
        clash = await db.holidays.find_one({"date": data.holiday_date})
        if clash:
            raise HTTPException(status_code=409, detail="A holiday already exists on this date")
        doc = {
            "id": str(uuid.uuid4()),
            "name": data.name,
            "date": data.holiday_date,
            "day": data.day or dt.strftime("%A"),
            "type": data.type or "company",
            "note": data.note,
            "is_paid": bool(data.is_paid),
            "year": int(y),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.holidays.insert_one(doc.copy())
        await log_audit(current_user["id"], "create_holiday", "holiday", doc["id"], data.name)
        return serialize_doc(doc)

    @api_router.put("/settings/holidays/{holiday_id}")
    async def settings_update_holiday(holiday_id: str, data: HolidayUpdateIn,
                                      current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.holidays.find_one({"id": holiday_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Holiday not found")
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.holiday_date is not None:
            try:
                y, m, d = data.holiday_date.split("-")
                dt = datetime(int(y), int(m), int(d))
            except Exception:
                raise HTTPException(status_code=400, detail="holiday_date must be YYYY-MM-DD")
            clash = await db.holidays.find_one({"date": data.holiday_date, "id": {"$ne": holiday_id}})
            if clash:
                raise HTTPException(status_code=409, detail="Another holiday already exists on this date")
            updates["date"] = data.holiday_date
            updates["year"] = int(y)
            updates["day"] = data.day or dt.strftime("%A")
        elif data.day is not None:
            updates["day"] = data.day
        if data.is_paid is not None:
            updates["is_paid"] = bool(data.is_paid)
        if data.type is not None:
            updates["type"] = data.type
        if data.note is not None:
            updates["note"] = data.note
        if not updates:
            return serialize_doc(existing)
        updates["updated_at"] = _now_iso()
        await db.holidays.update_one({"id": holiday_id}, {"$set": updates})
        await log_audit(current_user["id"], "update_holiday", "holiday", holiday_id)
        updated = await db.holidays.find_one({"id": holiday_id}, {"_id": 0})
        return serialize_doc(updated)

    @api_router.delete("/settings/holidays/{holiday_id}")
    async def settings_delete_holiday(holiday_id: str, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        res = await db.holidays.delete_one({"id": holiday_id})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Holiday not found")
        await log_audit(current_user["id"], "delete_holiday", "holiday", holiday_id)
        return {"message": "Holiday deleted"}

    # --------------------------------------------------------
    #  Shifts
    # --------------------------------------------------------

    @api_router.get("/settings/shifts")
    async def settings_list_shifts(include_deleted: bool = False,
                                   current_user: dict = Depends(get_current_user)):
        q = {} if include_deleted else {"is_deleted": {"$ne": True}}
        shifts = await db.shifts.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        for s in shifts:
            s["assigned_count"] = await db.employees.count_documents({
                "active_shift_id": s["id"],
                "is_deleted": {"$ne": True},
                "employee_status": EmployeeStatus.ACTIVE,
            })
        return [serialize_doc(s) for s in shifts]

    def _validate_time(value: str):
        mins = parse_time_24h_to_minutes(value)
        if mins is None or mins < 0 or mins >= 24 * 60:
            raise HTTPException(status_code=400, detail=f"Invalid time: {value}")

    @api_router.post("/settings/shifts")
    async def settings_create_shift(data: ShiftIn, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        _validate_time(data.start_time)
        if data.total_hours <= 0 or data.total_hours > 24:
            raise HTTPException(status_code=400, detail="total_hours must be between 0 and 24")
        clash = await db.shifts.find_one({"name": data.name, "is_deleted": {"$ne": True}})
        if clash:
            raise HTTPException(status_code=409, detail="Shift with this name already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "name": data.name,
            "start_time": data.start_time,
            "total_hours": float(data.total_hours),
            "late_grace_minutes": int(data.late_grace_minutes or 0),
            "early_out_grace_minutes": int(data.early_out_grace_minutes or 0),
            "status": data.status or "active",
            "description": data.description or "",
            "is_deleted": False,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.shifts.insert_one(doc.copy())
        await log_audit(current_user["id"], "create_shift", "shift", doc["id"], data.name)
        return serialize_doc(doc)

    @api_router.put("/settings/shifts/{shift_id}")
    async def settings_update_shift(shift_id: str, data: ShiftUpdate,
                                    current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Shift not found")
        updates = {}
        if data.name is not None and data.name != existing["name"]:
            clash = await db.shifts.find_one({"name": data.name, "is_deleted": {"$ne": True}})
            if clash:
                raise HTTPException(status_code=409, detail="Shift name already exists")
            updates["name"] = data.name
        if data.start_time is not None:
            _validate_time(data.start_time)
            updates["start_time"] = data.start_time
        if data.total_hours is not None:
            if data.total_hours <= 0 or data.total_hours > 24:
                raise HTTPException(status_code=400, detail="total_hours must be between 0 and 24")
            updates["total_hours"] = float(data.total_hours)
        if data.late_grace_minutes is not None:
            updates["late_grace_minutes"] = int(data.late_grace_minutes)
        if data.early_out_grace_minutes is not None:
            updates["early_out_grace_minutes"] = int(data.early_out_grace_minutes)
        if data.status is not None:
            updates["status"] = data.status
        if data.description is not None:
            updates["description"] = data.description
        if not updates:
            return serialize_doc(existing)
        updates["updated_at"] = _now_iso()
        await db.shifts.update_one({"id": shift_id}, {"$set": updates})
        # Re-sync all employees currently on this shift (today's effective assignment)
        merged = {**existing, **updates}
        emps = await db.employees.find({"active_shift_id": shift_id}, {"_id": 0, "id": 1}).to_list(2000)
        for e in emps:
            await _sync_shift_to_employee(e["id"], merged)
        await log_audit(current_user["id"], "update_shift", "shift", shift_id)
        updated = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
        return serialize_doc(updated)

    @api_router.delete("/settings/shifts/{shift_id}")
    async def settings_delete_shift(shift_id: str, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Shift not found")
        active = await db.employees.count_documents({"active_shift_id": shift_id, "is_deleted": {"$ne": True}})
        if active > 0:
            raise HTTPException(status_code=400, detail=f"Cannot delete: {active} employees still on this shift")
        await db.shifts.update_one(
            {"id": shift_id},
            {"$set": {"is_deleted": True, "deleted_at": _now_iso()}},
        )
        await log_audit(current_user["id"], "delete_shift", "shift", shift_id)
        return {"message": "Shift deleted"}

    # --------------------------------------------------------
    #  Shift Assignment
    # --------------------------------------------------------

    def _validate_date(value: str, field: str = "date"):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except Exception:
            raise HTTPException(status_code=400, detail=f"{field} must be YYYY-MM-DD")

    async def _assign_shift_to_employees(employee_ids: List[str], shift_id: str,
                                         effective_from: str, effective_to: Optional[str],
                                         assigned_by: str) -> dict:
        shift = await db.shifts.find_one({"id": shift_id, "is_deleted": {"$ne": True}}, {"_id": 0})
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")
        if effective_to and effective_to < effective_from:
            raise HTTPException(status_code=400, detail="effective_to must be >= effective_from")
        created = 0
        updated = 0
        today = get_ist_now().strftime("%Y-%m-%d")
        for eid in employee_ids:
            emp = await db.employees.find_one({"id": eid, "is_deleted": {"$ne": True}}, {"_id": 0, "id": 1})
            if not emp:
                continue
            # Close any open-ended overlapping assignment: set effective_to = effective_from - 1 day
            overlap_query = {
                "employee_id": eid,
                "is_deleted": {"$ne": True},
                "effective_from": {"$lte": effective_from},
                "$or": [{"effective_to": None}, {"effective_to": {"$gte": effective_from}}],
            }
            overlapping = await db.employee_shifts.find(overlap_query, {"_id": 0}).to_list(100)
            for ov in overlapping:
                if ov["shift_id"] == shift_id and (ov.get("effective_to") or None) == (effective_to or None):
                    continue
                # Update: end the old one the day before the new starts
                prev_end = (datetime.strptime(effective_from, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
                await db.employee_shifts.update_one(
                    {"id": ov["id"]},
                    {"$set": {"effective_to": prev_end, "updated_at": _now_iso()}},
                )
                updated += 1
            # Idempotent insert: if an identical assignment already exists, skip
            identical = await db.employee_shifts.find_one({
                "employee_id": eid,
                "shift_id": shift_id,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "is_deleted": {"$ne": True},
            })
            if not identical:
                await db.employee_shifts.insert_one({
                    "id": str(uuid.uuid4()),
                    "employee_id": eid,
                    "shift_id": shift_id,
                    "effective_from": effective_from,
                    "effective_to": effective_to,
                    "assigned_by": assigned_by,
                    "is_deleted": False,
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                })
                created += 1
            # If the assignment is active today, mirror to employee doc
            if effective_from <= today and (effective_to is None or effective_to >= today):
                await _sync_shift_to_employee(eid, shift)
        return {"created": created, "updated": updated, "shift_id": shift_id}

    @api_router.post("/settings/shifts/assign")
    async def settings_assign_shift(data: AssignShiftIn, current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        if not data.employee_ids:
            raise HTTPException(status_code=400, detail="employee_ids is required")
        _validate_date(data.effective_from, "effective_from")
        if data.effective_to:
            _validate_date(data.effective_to, "effective_to")
        result = await _assign_shift_to_employees(
            data.employee_ids, data.shift_id, data.effective_from, data.effective_to,
            current_user["id"],
        )
        await log_audit(current_user["id"], "assign_shift", "shift", data.shift_id,
                        f"Assigned to {len(data.employee_ids)} employees")
        return {"message": "Shift assigned", **result}

    @api_router.post("/settings/shifts/bulk-assign")
    async def settings_bulk_assign_by_filter(data: BulkAssignByFilterIn,
                                             current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        _validate_date(data.effective_from, "effective_from")
        if data.effective_to:
            _validate_date(data.effective_to, "effective_to")
        q = {"is_deleted": {"$ne": True}, "employee_status": EmployeeStatus.ACTIVE}
        if data.departments:
            q["department"] = {"$in": data.departments}
        if data.teams:
            q["team"] = {"$in": data.teams}
        if data.designations:
            q["designation"] = {"$in": data.designations}
        employees = await db.employees.find(q, {"_id": 0, "id": 1}).to_list(5000)
        if not employees:
            return {"message": "No matching employees", "created": 0, "updated": 0, "matched": 0}
        emp_ids = [e["id"] for e in employees]
        result = await _assign_shift_to_employees(
            emp_ids, data.shift_id, data.effective_from, data.effective_to, current_user["id"],
        )
        await log_audit(current_user["id"], "bulk_assign_shift", "shift", data.shift_id,
                        f"Bulk assigned to {len(emp_ids)} employees")
        return {"message": "Shift assigned", "matched": len(emp_ids), **result}

    @api_router.get("/settings/shifts/assignments")
    async def settings_list_assignments(employee_id: Optional[str] = None,
                                        shift_id: Optional[str] = None,
                                        active_only: bool = False,
                                        current_user: dict = Depends(get_current_user)):
        q = {"is_deleted": {"$ne": True}}
        if employee_id:
            q["employee_id"] = employee_id
        if shift_id:
            q["shift_id"] = shift_id
        if active_only:
            today = get_ist_now().strftime("%Y-%m-%d")
            q["effective_from"] = {"$lte": today}
            q["$or"] = [{"effective_to": None}, {"effective_to": {"$gte": today}}]
        assignments = await db.employee_shifts.find(q, {"_id": 0}).sort("effective_from", -1).to_list(2000)
        # Enrich with names
        shift_ids = {a["shift_id"] for a in assignments}
        emp_ids = {a["employee_id"] for a in assignments}
        shifts = {s["id"]: s async for s in db.shifts.find({"id": {"$in": list(shift_ids)}}, {"_id": 0})}
        emps = {e["id"]: e async for e in db.employees.find({"id": {"$in": list(emp_ids)}},
                                                            {"_id": 0, "id": 1, "full_name": 1, "emp_id": 1,
                                                             "department": 1, "team": 1})}
        out = []
        for a in assignments:
            s = shifts.get(a["shift_id"], {})
            e = emps.get(a["employee_id"], {})
            out.append({
                **a,
                "shift_name": s.get("name"),
                "shift_start_time": s.get("start_time"),
                "shift_total_hours": s.get("total_hours"),
                "employee_name": e.get("full_name"),
                "emp_id": e.get("emp_id"),
                "department": e.get("department"),
                "team": e.get("team"),
            })
        return [serialize_doc(a) for a in out]

    @api_router.delete("/settings/shifts/assignments/{assignment_id}")
    async def settings_delete_assignment(assignment_id: str,
                                         current_user: dict = Depends(get_current_user)):
        _require_settings_write(current_user)
        existing = await db.employee_shifts.find_one({"id": assignment_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Assignment not found")
        await db.employee_shifts.update_one(
            {"id": assignment_id},
            {"$set": {"is_deleted": True, "deleted_at": _now_iso()}},
        )
        # If employee's active shift points to this, clear the sync so legacy path recomputes
        today = get_ist_now().strftime("%Y-%m-%d")
        fallback = await resolve_shift_for_employee(existing["employee_id"], today)
        if fallback:
            await _sync_shift_to_employee(existing["employee_id"], fallback)
        else:
            await db.employees.update_one(
                {"id": existing["employee_id"]},
                {"$unset": {"active_shift_id": "", "active_shift_name": ""}},
            )
        await log_audit(current_user["id"], "delete_assignment", "employee_shift", assignment_id)
        return {"message": "Assignment removed"}

    @api_router.get("/settings/shifts/resolve")
    async def settings_resolve_shift(employee_id: str, date: str,
                                     current_user: dict = Depends(get_current_user)):
        """Resolve the active shift for a given employee on a given date."""
        _validate_date(date)
        shift = await resolve_shift_for_employee(employee_id, date)
        if not shift:
            return {"resolved": False, "message": "NO SHIFT ASSIGNED"}
        return {"resolved": True, "shift": shift}

    # --------------------------------------------------------
    #  Attendance Rule Engine / Recompute
    # --------------------------------------------------------

    @api_router.post("/settings/attendance/recompute")
    async def settings_recompute_attendance(data: RecalcIn,
                                            current_user: dict = Depends(get_current_user)):
        """Recompute attendance flags (late, early out, worked hours, holiday)
        for the requested employees / date range using the LATEST shift rules.

        Locked fields:
          - attendance records with is_manual_override or is_approved_correction=True
            are SKIPPED to preserve the admin-approved value.
        """
        _require_settings_write(current_user)

        # First ensure latest shift is synced to employees so the legacy engine picks it up
        await _apply_active_shifts_now()

        calculate_attendance_status = deps.get("calculate_attendance_status")
        get_shift_timings = deps.get("get_shift_timings")
        if not calculate_attendance_status or not get_shift_timings:
            raise HTTPException(status_code=500, detail="Attendance engine not wired")

        q = {}
        if data.employee_ids:
            q["employee_id"] = {"$in": data.employee_ids}
        # MongoDB date strings use DD-MM-YYYY in this codebase; we do a string filter when possible
        if data.from_date and data.to_date:
            q["date"] = {"$gte": data.from_date, "$lte": data.to_date}

        records = await db.attendance.find(q, {"_id": 0}).to_list(10000)

        # Pre-load holidays
        holidays = await db.holidays.find({}, {"_id": 0}).to_list(500)
        holiday_dates_ymd = {h["date"] for h in holidays}

        updated = 0
        skipped_locked = 0
        holiday_flagged = 0
        for rec in records:
            if rec.get("is_manual_override") or rec.get("is_approved_correction"):
                skipped_locked += 1
                continue
            employee = await db.employees.find_one({"id": rec["employee_id"]}, {"_id": 0})
            if not employee:
                continue
            shift_timings = get_shift_timings(employee)
            if not shift_timings:
                continue
            status_result = calculate_attendance_status(
                rec.get("check_in_24h") or "",
                rec.get("check_out_24h") or "",
                shift_timings,
            )
            set_doc = {
                "status": status_result["status"],
                "is_lop": status_result["is_lop"],
                "lop_reason": status_result.get("lop_reason"),
                "total_hours_decimal": status_result.get("total_hours_decimal", 0),
                "updated_at": _now_iso(),
            }
            # Holiday flag: attendance date is stored as DD-MM-YYYY; holidays as YYYY-MM-DD
            try:
                dd, mm, yy = rec["date"].split("-")
                date_ymd = f"{yy}-{mm}-{dd}"
            except Exception:
                date_ymd = None
            if date_ymd and date_ymd in holiday_dates_ymd:
                set_doc["is_holiday"] = True
                # Worked on a holiday → flag for extra pay
                has_work = bool(rec.get("check_in_24h") or rec.get("check_out_24h"))
                set_doc["extra_pay_flag"] = has_work
                holiday_flagged += 1
            else:
                set_doc["is_holiday"] = False
                set_doc["extra_pay_flag"] = False
            await db.attendance.update_one({"id": rec["id"]}, {"$set": set_doc})
            updated += 1
        await log_audit(current_user["id"], "recompute_attendance", "attendance", None,
                        f"Updated {updated}, skipped {skipped_locked}, holiday flagged {holiday_flagged}")
        return {
            "message": "Attendance recomputed",
            "updated": updated,
            "skipped_locked": skipped_locked,
            "holiday_flagged": holiday_flagged,
            "total_records": len(records),
        }

    # Expose service for external use
    return {
        "resolve_shift_for_employee": resolve_shift_for_employee,
        "sync_shift_to_employee": _sync_shift_to_employee,
        "apply_active_shifts_now": _apply_active_shifts_now,
    }
