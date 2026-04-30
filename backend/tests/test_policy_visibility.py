"""Tests for department-based policy visibility (Research Unit Policy restriction)."""
import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import server  # noqa: E402


@pytest.mark.asyncio
async def test_admin_sees_research_policy():
    user = {"id": "test-admin", "role": "hr"}
    assert await server._is_policy_visible_to_user("policy_research", user) is True


@pytest.mark.asyncio
async def test_system_admin_sees_research_policy():
    user = {"id": "test-sysadmin", "role": "system_admin"}
    assert await server._is_policy_visible_to_user("policy_research", user) is True


@pytest.mark.asyncio
async def test_office_admin_sees_research_policy():
    user = {"id": "test-offadmin", "role": "office_admin"}
    assert await server._is_policy_visible_to_user("policy_research", user) is True


@pytest.mark.asyncio
async def test_research_unit_employee_sees_research_policy():
    emp_id = f"test-emp-{uuid.uuid4()}"
    await server.db.employees.insert_one({
        "id": emp_id,
        "full_name": "Test Research Emp",
        "department": "Research Unit",
        "employee_status": "Active",
        "is_deleted": False,
    })
    try:
        user = {"id": "u1", "role": "employee", "employee_id": emp_id}
        assert await server._is_policy_visible_to_user("policy_research", user) is True
    finally:
        await server.db.employees.delete_one({"id": emp_id})


@pytest.mark.asyncio
async def test_non_research_employee_does_not_see_research_policy():
    emp_id = f"test-emp-{uuid.uuid4()}"
    await server.db.employees.insert_one({
        "id": emp_id,
        "full_name": "Test Support Emp",
        "department": "Support Staff",
        "employee_status": "Active",
        "is_deleted": False,
    })
    try:
        user = {"id": "u2", "role": "employee", "employee_id": emp_id}
        assert await server._is_policy_visible_to_user("policy_research", user) is False
    finally:
        await server.db.employees.delete_one({"id": emp_id})


@pytest.mark.asyncio
async def test_leave_policy_visible_to_everyone():
    """Non-restricted policies must be visible to all users."""
    emp_id = f"test-emp-{uuid.uuid4()}"
    await server.db.employees.insert_one({
        "id": emp_id,
        "full_name": "Anyone",
        "department": "Business & Product",
        "employee_status": "Active",
        "is_deleted": False,
    })
    try:
        user = {"id": "u3", "role": "employee", "employee_id": emp_id}
        assert await server._is_policy_visible_to_user("policy_leave", user) is True
        assert await server._is_policy_visible_to_user("policy_it", user) is True
    finally:
        await server.db.employees.delete_one({"id": emp_id})


@pytest.mark.asyncio
async def test_employee_without_employee_id_blocked():
    user = {"id": "ghost", "role": "employee"}
    assert await server._is_policy_visible_to_user("policy_research", user) is False
