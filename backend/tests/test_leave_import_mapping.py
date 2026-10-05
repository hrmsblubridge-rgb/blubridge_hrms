"""Regression tests for the Leave Import (new template) mapping + behaviour.

Covers the spec:
- Leave_Type mapping (Emergency/Sick/Preplanned/Optional Holiday)
- Action_Type -> is_lop (No_LOP/LOP/NULL)
- literal "NULL" cells treated as empty
- header underscores tolerant (Start_Date == Start Date)
- date + datetime parsing (D/M/YYYY, DD-MM-YYYY HH:MM)
- end-to-end import via API: single-day leaves, Applied_on -> created_at,
  remark -> lop_remark, idempotent re-import, Intern Paid-Leave block.
"""
import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

API = "http://localhost:8001/api"
T = 60.0


# ---------------- pure helper mappings ----------------

def test_leave_type_mapping():
    assert server._normalize_leave_type("Emergency") == "Emergency"
    assert server._normalize_leave_type("Sick") == "Sick"
    assert server._normalize_leave_type("Preplanned") == "Preplanned"
    assert server._normalize_leave_type("PrePlanned") == "Preplanned"
    assert server._normalize_leave_type("Optional Holiday") == "Optional"


def test_action_type_to_is_lop():
    assert server._normalize_action_type("No_LOP") is False
    assert server._normalize_action_type("NO_LOP") is False
    assert server._normalize_action_type("No LOP") is False
    assert server._normalize_action_type("LOP") is True
    assert server._normalize_action_type("NULL") is None
    assert server._normalize_action_type("") is None
    assert server._normalize_action_type("Half Day") is None  # stray value -> unset


def test_clean_null():
    for v in ("NULL", "null", "  ", "N/A", "-", None):
        assert server._clean_null(v) is None
    assert server._clean_null("Approved") == "Approved"


def test_header_underscore_tolerant():
    ai = server._build_alias_index()
    expect = {
        "Email": "email", "Leave_Type": "leave_type", "Status": "status",
        "Action_Type": "action_type", "Remark": "comments", "Applied_on": "applied_at",
        "Approved_by": "approved_by", "Start_Date": "start_date",
        "Leave_Split": "leave_split", "Reason": "reason",
    }
    for h, c in expect.items():
        assert ai.get(server._normalize_header(h)) == c, h


def test_date_parsing_day_first():
    assert server._parse_import_date("2/5/2026") == "2026-05-02"
    assert server._parse_import_date("30-04-2026") == "2026-04-30"
    assert server._parse_import_date("12/11/2025") == "2025-11-12"


def test_datetime_parsing_with_time():
    assert server._parse_import_datetime("30-04-2026 18:59") == ("2026-04-30", "18:59")
    assert server._parse_import_datetime("8/4/2026 9:28") == ("2026-04-08", "09:28")


# ---------------- end-to-end import via API ----------------

def _admin_token():
    r = httpx.post(f"{API}/auth/login", json={"username": "admin", "password": "HrAdmin786$"}, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def cleanup_leaves():
    created_marker = f"__pytest_import_{uuid.uuid4().hex[:8]}__"
    yield created_marker
    # Cleanup any leaves whose reason carries our unique marker.
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        server.db.leaves.delete_many({"reason": {"$regex": created_marker}})
    )


def test_end_to_end_import_single_day_and_idempotent(cleanup_leaves):
    marker = cleanup_leaves
    token = _admin_token()
    # aparna.a is a known employee in the dataset; use far-future dates to avoid
    # overlapping existing leaves.
    csv = (
        "Email,Leave_Type,Status,Action_Type,Remark,Applied_on,Approved_by,Start_Date,Leave_Split,Reason\n"
        f"aparna.a@blubridge.com,Sick,Approved,LOP,Approved by HR,30-11-2027 18:59,52,2/12/2027,Full Day,{marker} sick\n"
        f"aparna.a@blubridge.com,Emergency,Pending,NULL,NULL,01-12-2027 10:00,NULL,5/12/2027,Second Half,{marker} emg\n"
    )
    files = {"file": ("leaves.csv", csv, "text/csv")}
    r = httpx.post(f"{API}/leaves/bulk-import", headers={"Authorization": f"Bearer {token}"}, files=files, timeout=T)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] == 2, body
    assert body["failed"] == 0, body

    # Verify the records integrate: fetch via admin leaves API.
    lr = httpx.get(f"{API}/leaves?employee_name=Aparna", headers={"Authorization": f"Bearer {token}"}, timeout=T)
    rows = [x for x in lr.json() if marker in (x.get("reason") or "")]
    assert len(rows) == 2
    by_type = {x["leave_type"]: x for x in rows}
    sick = by_type["Sick"]
    assert sick["status"] == "approved"
    assert sick["is_lop"] is True
    assert sick["lop_remark"] == "Approved by HR"
    assert sick["start_date"] == "2027-12-02" and sick["end_date"] == "2027-12-02"  # single-day
    assert sick["created_at"].startswith("2027-11-30")  # Applied_on -> created_at
    assert sick.get("approved_by_name")  # resolved to importing admin
    emg = by_type["Emergency"]
    assert emg["status"] == "pending" and emg["is_lop"] is None
    assert emg["leave_split"] == "Second Half" and emg["duration"] == "0.5 day(s)"

    # Idempotent re-import → 0 new, 2 duplicates.
    r2 = httpx.post(f"{API}/leaves/bulk-import", headers={"Authorization": f"Bearer {token}"}, files={"file": ("leaves.csv", csv, "text/csv")}, timeout=T)
    b2 = r2.json()
    assert b2["success"] == 0 and b2["skipped_duplicates"] == 2, b2


def test_intern_paid_leave_blocked_on_import(cleanup_leaves):
    marker = cleanup_leaves
    token = _admin_token()
    import asyncio
    intern = asyncio.get_event_loop().run_until_complete(
        server.db.employees.find_one({"employment_type": "Intern", "is_deleted": {"$ne": True}}, {"_id": 0, "official_email": 1})
    )
    assert intern and intern.get("official_email"), "need an Intern employee for this test"
    csv = (
        "Email,Leave_Type,Status,Action_Type,Remark,Applied_on,Approved_by,Start_Date,Leave_Split,Reason\n"
        f"{intern['official_email']},Paid Leave,Approved,No_LOP,x,01-12-2027 10:00,52,9/12/2027,Full Day,{marker} paid\n"
    )
    r = httpx.post(f"{API}/leaves/bulk-import", headers={"Authorization": f"Bearer {token}"}, files={"file": ("l.csv", csv, "text/csv")}, timeout=T)
    body = r.json()
    assert body["success"] == 0, body
    assert body["failed"] == 1, body
    assert any("Intern" in e["reason"] for e in body["errors"]), body["errors"]
