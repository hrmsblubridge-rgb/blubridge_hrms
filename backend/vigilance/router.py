"""Vigilance router factory — mounted by server.py without import cycles."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import service as svc

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ADMIN_ROLES = ("hr", "system_admin", "office_admin")


class BreakItem(BaseModel):
    label: str
    from_: Optional[str] = Field("", alias="from")
    to: Optional[str] = ""
    total: Optional[str] = ""

    class Config:
        populate_by_name = True


class EntryBody(BaseModel):
    target_employee_id: str
    date: str                       # ISO or DD-MMM-YYYY
    system_login: Optional[str] = ""
    system_logout: Optional[str] = ""
    total_research_hours: Optional[str] = ""
    total_break_hours: Optional[str] = ""
    breaks: List[dict] = []


class UpdateBody(BaseModel):
    system_login: Optional[str] = None
    system_logout: Optional[str] = None
    total_research_hours: Optional[str] = None
    total_break_hours: Optional[str] = None
    breaks: Optional[List[dict]] = None


async def ensure_vigilance_indexes(db):
    await db.vigilance_entries.create_index(
        [("target_employee_id", 1), ("date", 1), ("uploaded_by_employee_id", 1)],
        unique=True, name="uniq_emp_date_uploader",
    )
    await db.vigilance_entries.create_index([("id", 1)], unique=True, name="uniq_id")


def get_vigilance_router(db, get_current_user):
    router = APIRouter(prefix="/api/vigilance", tags=["vigilance"])

    async def context(current_user):
        """Resolve access. Returns ctx dict or raises 403."""
        role = current_user.get("role")
        if role in ADMIN_ROLES:
            return {"is_admin": True, "is_vigilance": False,
                    "employee_id": current_user.get("id"), "name": "Admin"}
        if role == "employee" and current_user.get("employee_id"):
            emp = await db.employees.find_one(
                {"id": current_user["employee_id"]},
                {"_id": 0, "id": 1, "full_name": 1, "designation": 1},
            )
            if emp and (emp.get("designation") or "").strip().lower() == svc.VIGILANCE_DESIGNATION:
                return {"is_admin": False, "is_vigilance": True,
                        "employee_id": emp["id"], "name": emp.get("full_name")}
        raise HTTPException(status_code=403, detail="Access restricted to Admins and Vigilance-designation employees.")

    # ---------------------------------------------------------------- access
    @router.get("/access")
    async def access(current_user: dict = Depends(get_current_user)):
        try:
            ctx = await context(current_user)
        except HTTPException:
            return {"has_access": False, "is_admin": False, "is_vigilance": False}
        return {"has_access": True, **ctx}

    # ----------------------------------------------------------- filter meta
    @router.get("/filters-meta")
    async def filters_meta(current_user: dict = Depends(get_current_user)):
        await context(current_user)
        emps = await db.employees.find(
            {}, {"_id": 0, "id": 1, "full_name": 1, "department": 1, "team": 1, "designation": 1}
        ).to_list(100000)
        departments = sorted({e.get("department") for e in emps if e.get("department")})
        teams = sorted({e.get("team") for e in emps if e.get("team")})
        designations = sorted({e.get("designation") for e in emps if e.get("designation")})
        employees = sorted(
            [{"id": e["id"], "name": e.get("full_name")} for e in emps if e.get("full_name")],
            key=lambda x: (x["name"] or "").lower(),
        )
        return {"departments": departments, "teams": teams,
                "designations": designations, "employees": employees}

    # ------------------------------------------------------------- template
    @router.get("/template")
    async def template(from_date: str = Query(...), to_date: str = Query(...),
                       current_user: dict = Depends(get_current_user)):
        await context(current_user)
        iso_from = svc.to_iso(from_date)
        iso_to = svc.to_iso(to_date)
        if not iso_from or not iso_to:
            raise HTTPException(status_code=400, detail="From Date and To Date are required (DD-MMM-YYYY).")
        if iso_to < iso_from:
            raise HTTPException(status_code=400, detail="To Date must be the same as or after From Date.")

        emps = await svc.get_active_employees(db, iso_from, iso_to)
        emp_ids = [e["id"] for e in emps]
        att = await svc.get_attendance_map(db, emp_ids, iso_from, iso_to)
        days = svc.daterange_iso(iso_from, iso_to)

        prefill = []
        for day in days:
            day_display = svc.iso_to_display(day)
            for e in emps:
                if not svc.is_active_on(e, day):
                    continue
                a = att.get((e["id"], day), {})
                prefill.append({
                    "name": e.get("full_name", ""),
                    "email": e.get("official_email", ""),
                    "team": e.get("team", ""),
                    "date_display": day_display,
                    "punch_in": a.get("punch_in", ""),
                    "punch_out": a.get("punch_out", ""),
                    "total_hours": a.get("total_hours", ""),
                })

        buf = await run_in_threadpool(svc.build_template_workbook, prefill)
        fname = f"Vigilance-Template_{svc.iso_to_display(iso_from)}_to_{svc.iso_to_display(iso_to)}.xlsx"
        return StreamingResponse(
            buf, media_type=XLSX_MIME,
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    # --------------------------------------------------------------- upload
    @router.post("/upload")
    async def upload(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
        ctx = await context(current_user)
        if not (file.filename or "").lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Only .xlsx files are accepted.")
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        emps = await db.employees.find(
            {}, {"_id": 0, "id": 1, "full_name": 1, "official_email": 1, "team": 1,
                 "department": 1, "designation": 1}
        ).to_list(100000)
        by_email = {(e.get("official_email") or "").strip().lower(): e for e in emps if e.get("official_email")}

        uploaded_by = {"employee_id": ctx["employee_id"], "name": ctx["name"]}
        entries, errors = await run_in_threadpool(svc.parse_upload, data, by_email, uploaded_by)
        if errors:
            raise HTTPException(status_code=422, detail={"message": "Upload rejected — fix the rows below.", "errors": errors[:200]})
        if not entries:
            raise HTTPException(status_code=400, detail="No vigilance data found to save. Fill at least one row.")

        created = updated = 0
        for entry in entries:
            res = await svc.upsert_entry(db, entry, uploaded_by)
            if res.upserted_id is not None:
                created += 1
            elif res.modified_count:
                updated += 1
            else:
                updated += 1
        return {"created": created, "updated": updated, "total": len(entries)}

    # --------------------------------------------------------------- entries
    def _filters(from_date, to_date, employee_name, department, designation, team):
        return {
            "from_iso": svc.to_iso(from_date) if from_date else None,
            "to_iso": svc.to_iso(to_date) if to_date else None,
            "employee_name": employee_name,
            "department": department,
            "designation": designation,
            "team": team,
        }

    @router.get("/entries")
    async def entries(
        from_date: Optional[str] = None, to_date: Optional[str] = None,
        employee_name: Optional[str] = None, department: Optional[str] = None,
        designation: Optional[str] = None, team: Optional[str] = None,
        current_user: dict = Depends(get_current_user),
    ):
        ctx = await context(current_user)
        f = _filters(from_date, to_date, employee_name, department, designation, team)
        if ctx["is_admin"]:
            data = await svc.list_admin_merged(db, f)
            return {"mode": "admin", **data}
        data = await svc.list_own_rows(db, ctx["employee_id"], f)
        return {"mode": "vigilance", **data}

    @router.post("/entries")
    async def create_entry(body: EntryBody, current_user: dict = Depends(get_current_user)):
        ctx = await context(current_user)
        iso = svc.parse_display_date_strict(body.date) or svc.to_iso(body.date)
        if not iso:
            raise HTTPException(status_code=400, detail="Invalid date. Use DD-MMM-YYYY.")
        emp = await db.employees.find_one({"id": body.target_employee_id}, {"_id": 0})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found.")
        entry, err = _validate_editable(body, emp, iso)
        if err:
            raise HTTPException(status_code=422, detail=err)
        uploaded_by = {"employee_id": ctx["employee_id"], "name": ctx["name"]}
        await svc.upsert_entry(db, entry, uploaded_by)
        return {"ok": True}

    @router.put("/entries/{entry_id}")
    async def update_entry(entry_id: str, body: UpdateBody, current_user: dict = Depends(get_current_user)):
        ctx = await context(current_user)
        doc = await db.vigilance_entries.find_one({"id": entry_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Vigilance entry not found.")
        if not ctx["is_admin"] and doc["uploaded_by_employee_id"] != ctx["employee_id"]:
            raise HTTPException(status_code=403, detail="You can only edit your own vigilance entries.")

        update = {}
        if body.system_login is not None:
            ok, v = svc.norm_clock(body.system_login)
            if not ok:
                raise HTTPException(status_code=422, detail="System Login must be HH:MM AM/PM.")
            update["system_login"] = v
        if body.system_logout is not None:
            ok, v = svc.norm_clock(body.system_logout)
            if not ok:
                raise HTTPException(status_code=422, detail="System Logout must be HH:MM AM/PM.")
            update["system_logout"] = v
        if body.total_research_hours is not None:
            ok, v = svc.norm_duration(body.total_research_hours)
            if not ok:
                raise HTTPException(status_code=422, detail="Total Research Hours — invalid duration format. Accepted: HH:MM or HH:MM:SS.")
            update["total_research_hours"] = v
        if body.total_break_hours is not None:
            ok, v = svc.norm_duration(body.total_break_hours)
            if not ok:
                raise HTTPException(status_code=422, detail="Total Break Hours — invalid duration format. Accepted: HH:MM or HH:MM:SS.")
            update["total_break_hours"] = v
        if body.breaks is not None:
            breaks, err = _validate_breaks(body.breaks)
            if err:
                raise HTTPException(status_code=422, detail=err)
            update["breaks"] = breaks

        if update:
            update["updated_at"] = svc.now_iso()
            await db.vigilance_entries.update_one({"id": entry_id}, {"$set": update})
        return {"ok": True}

    @router.delete("/entries/{entry_id}")
    async def delete_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
        ctx = await context(current_user)
        doc = await db.vigilance_entries.find_one({"id": entry_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Vigilance entry not found.")
        if not ctx["is_admin"] and doc["uploaded_by_employee_id"] != ctx["employee_id"]:
            raise HTTPException(status_code=403, detail="You can only delete your own vigilance entries.")
        await db.vigilance_entries.delete_one({"id": entry_id})
        return {"ok": True}

    # ---------------------------------------------------------------- export
    @router.get("/export")
    async def export(
        from_date: Optional[str] = None, to_date: Optional[str] = None,
        employee_name: Optional[str] = None, department: Optional[str] = None,
        designation: Optional[str] = None, team: Optional[str] = None,
        current_user: dict = Depends(get_current_user),
    ):
        ctx = await context(current_user)
        f = _filters(from_date, to_date, employee_name, department, designation, team)
        if ctx["is_admin"]:
            data = await svc.list_admin_merged(db, f)
            buf = await run_in_threadpool(svc.build_export_workbook, data["rows"], data["break_labels"], admin_mode=True)
        else:
            data = await svc.list_own_rows(db, ctx["employee_id"], f)
            buf = await run_in_threadpool(svc.build_export_workbook, data["rows"], data["break_labels"], admin_mode=False, clock_24h=True)
        return StreamingResponse(
            buf, media_type=XLSX_MIME,
            headers={"Content-Disposition": 'attachment; filename="Vigilance-Report.xlsx"'},
        )

    # ----------------------------------------- attendance module integration
    @router.get("/attendance-integration")
    async def attendance_integration(
        from_date: str = Query(...), to_date: str = Query(...),
        current_user: dict = Depends(get_current_user),
    ):
        ctx = await context(current_user)
        if not ctx["is_admin"]:
            raise HTTPException(status_code=403, detail="Admin only.")
        iso_from, iso_to = svc.to_iso(from_date), svc.to_iso(to_date)
        if not iso_from or not iso_to:
            raise HTTPException(status_code=400, detail="from_date and to_date required.")
        data = await svc.attendance_integration_map(db, [], iso_from, iso_to)
        members = await svc.list_vigilance_members(db)
        return {"map": data, "vigilance_members": members}

    return router


# -------------------------- shared validation helpers --------------------------
def _validate_breaks(raw_breaks):
    breaks = []
    for b in raw_breaks or []:
        label = (b.get("label") or "").strip()
        if not label:
            continue
        fr = b.get("from", b.get("from_", ""))
        okf, nf = svc.norm_clock(fr)
        okt, nt = svc.norm_clock(b.get("to", ""))
        okv, nv = svc.norm_duration(b.get("total", ""))
        if not okf:
            return None, f"'{label} From' must be HH:MM AM/PM."
        if not okt:
            return None, f"'{label} To' must be HH:MM AM/PM."
        if not okv:
            return None, f"'{label} Total' — invalid duration format. Accepted: HH:MM or HH:MM:SS."
        if nf or nt or nv:
            breaks.append({"label": label, "from": nf, "to": nt, "total": nv})
    return breaks, None


def _validate_editable(body, emp, iso):
    ok1, sl = svc.norm_clock(body.system_login)
    ok2, slo = svc.norm_clock(body.system_logout)
    ok3, rh = svc.norm_duration(body.total_research_hours)
    ok4, bh = svc.norm_duration(body.total_break_hours)
    if not ok1:
        return None, "System Login must be HH:MM AM/PM."
    if not ok2:
        return None, "System Logout must be HH:MM AM/PM."
    if not ok3:
        return None, "Total Research Hours — invalid duration format. Accepted: HH:MM or HH:MM:SS."
    if not ok4:
        return None, "Total Break Hours — invalid duration format. Accepted: HH:MM or HH:MM:SS."
    breaks, err = _validate_breaks(body.breaks)
    if err:
        return None, err
    return {
        "target_employee_id": emp["id"],
        "target_employee_name": emp.get("full_name"),
        "target_email": emp.get("official_email"),
        "target_team": emp.get("team"),
        "target_department": emp.get("department"),
        "target_designation": emp.get("designation"),
        "date": iso,
        "system_login": sl, "system_logout": slo,
        "total_research_hours": rh, "total_break_hours": bh,
        "breaks": breaks,
    }, None
