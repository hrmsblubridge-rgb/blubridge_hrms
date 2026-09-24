"""Shared assignment-history helpers for IT Assets & Components (additive).

Maintains structured employee assignment PERIODS at two levels:
  it_asset_assignments      — which employee held a parent asset, from → to
  it_component_assignments  — which employee held a component (via its parent), from → to

Rule: reassigning a parent asset updates each installed component's employee
history WITHOUT any physical remove/install event. Physically moving a
component between assets is handled by the component install/remove flow.
Nothing here is ever hard-deleted, so history is permanent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emp_fields(emp: dict) -> dict:
    emp = emp or {}
    return {
        "employee_id": emp.get("employee_id"),
        "employee_name": emp.get("employee_name"),
        "emp_code": emp.get("emp_code"),
        "department": emp.get("department"),
        "designation": emp.get("designation"),
    }


async def open_asset_assignment(db, asset_id, emp, reason, by_name, at=None):
    at = at or _iso()
    await db.it_asset_assignments.update_many(
        {"asset_id": asset_id, "to": None}, {"$set": {"to": at, "close_reason": reason, "closed_by": by_name}})
    doc = {"id": str(uuid.uuid4()), "asset_id": asset_id, **_emp_fields(emp),
           "from": at, "to": None, "reason": reason, "by_name": by_name, "created_at": at}
    await db.it_asset_assignments.insert_one(doc)


async def close_asset_assignment(db, asset_id, reason, by_name, at=None):
    at = at or _iso()
    await db.it_asset_assignments.update_many(
        {"asset_id": asset_id, "to": None}, {"$set": {"to": at, "close_reason": reason, "closed_by": by_name}})


async def open_component_assignment(db, component_id, asset_id, emp, reason, by_name, at=None):
    at = at or _iso()
    await db.it_component_assignments.update_many(
        {"component_id": component_id, "to": None}, {"$set": {"to": at, "close_reason": reason, "closed_by": by_name}})
    doc = {"id": str(uuid.uuid4()), "component_id": component_id, "asset_id": asset_id, **_emp_fields(emp),
           "from": at, "to": None, "reason": reason, "by_name": by_name, "created_at": at}
    await db.it_component_assignments.insert_one(doc)


async def close_component_assignment(db, component_id, reason, by_name, at=None):
    at = at or _iso()
    await db.it_component_assignments.update_many(
        {"component_id": component_id, "to": None}, {"$set": {"to": at, "close_reason": reason, "closed_by": by_name}})


async def sync_components_on_asset_reassign(db, asset_id, emp_or_none, reason, by_name, at=None):
    """When a parent asset's employee changes, mirror it onto every installed
    component's assignment history — WITHOUT creating physical move events."""
    at = at or _iso()
    async for c in db.it_components.find(
        {"parent_asset_id": asset_id, "is_deleted": {"$ne": True}}, {"_id": 0, "component_id": 1}):
        cid = c["component_id"]
        await close_component_assignment(db, cid, reason, by_name, at)
        if emp_or_none and emp_or_none.get("employee_id"):
            await open_component_assignment(db, cid, asset_id, emp_or_none, reason, by_name, at)


async def asset_assignment_history(db, asset_id):
    return [{k: v for k, v in d.items() if k != "_id"}
            async for d in db.it_asset_assignments.find({"asset_id": asset_id}).sort("from", 1)]


async def component_assignment_history(db, component_id):
    return [{k: v for k, v in d.items() if k != "_id"}
            async for d in db.it_component_assignments.find({"component_id": component_id}).sort("from", 1)]
