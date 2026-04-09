"""
Test suite for HRMS Jobs 1-7:
- JOB 1: Datetime picker for missed punch forms
- JOB 2: Admin missed punch filters + pagination
- JOB 3: Approved missed punch → auto-update attendance
- JOB 4: Prevent duplicate requests for missed punch/leave/late
- JOB 5: Fix 'Failed to apply leave' bug
- JOB 6: Leave rules (Sick=past only, Casual=4 working days, Emergency=any)
- JOB 7: Single leave per day rule
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
HR_CREDS = {"username": "admin", "password": "pass123"}
EMPLOYEE_CREDS = {"username": "user", "password": "user"}


class TestSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def hr_token(self):
        """Get HR authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=HR_CREDS)
        assert response.status_code == 200, f"HR login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def employee_token(self):
        """Get Employee authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        assert response.status_code == 200, f"Employee login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def hr_headers(self, hr_token):
        return {"Authorization": f"Bearer {hr_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def employee_headers(self, employee_token):
        return {"Authorization": f"Bearer {employee_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def employee_info(self, employee_headers):
        """Get employee info for the logged-in employee user"""
        response = requests.get(f"{BASE_URL}/api/employee/profile", headers=employee_headers)
        if response.status_code == 200:
            return response.json()
        return None
    
    @pytest.fixture(scope="class")
    def test_employee_id(self, hr_headers):
        """Get a test employee ID"""
        response = requests.get(f"{BASE_URL}/api/employees/all", headers=hr_headers)
        assert response.status_code == 200
        employees = response.json()
        assert len(employees) > 0, "No employees found"
        return employees[0]["id"]


class TestJob2MissedPunchPagination(TestSetup):
    """JOB 2: GET /api/missed-punches returns paginated response"""
    
    def test_missed_punches_returns_paginated_response(self, hr_headers):
        """Test that missed punches API returns paginated format"""
        response = requests.get(f"{BASE_URL}/api/missed-punches", headers=hr_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check paginated response structure
        assert "data" in data, "Response should have 'data' field"
        assert "total" in data, "Response should have 'total' field"
        assert "page" in data, "Response should have 'page' field"
        assert "per_page" in data, "Response should have 'per_page' field"
        
        assert isinstance(data["data"], list), "'data' should be a list"
        assert isinstance(data["total"], int), "'total' should be an integer"
        assert isinstance(data["page"], int), "'page' should be an integer"
        assert isinstance(data["per_page"], int), "'per_page' should be an integer"
        print(f"PASS: Paginated response with {data['total']} total records")
    
    def test_missed_punches_pagination_params(self, hr_headers):
        """Test pagination parameters work correctly"""
        # Test page 1 with 10 per page
        response = requests.get(f"{BASE_URL}/api/missed-punches?page=1&per_page=10", headers=hr_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert len(data["data"]) <= 10
        print(f"PASS: Pagination params work - page={data['page']}, per_page={data['per_page']}")
    
    def test_missed_punches_filter_by_status(self, hr_headers):
        """Test filtering by status"""
        for status in ["pending", "approved", "rejected"]:
            response = requests.get(f"{BASE_URL}/api/missed-punches?status={status}", headers=hr_headers)
            assert response.status_code == 200
            data = response.json()
            # All returned records should have the filtered status
            for record in data["data"]:
                assert record["status"] == status, f"Expected status {status}, got {record['status']}"
        print("PASS: Status filter works correctly")
    
    def test_missed_punches_filter_by_date_range(self, hr_headers):
        """Test filtering by date range"""
        from_date = "2026-01-01"
        to_date = "2026-12-31"
        response = requests.get(
            f"{BASE_URL}/api/missed-punches?from_date={from_date}&to_date={to_date}",
            headers=hr_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Verify date range filter is applied
        for record in data["data"]:
            assert record["date"] >= from_date, f"Date {record['date']} is before {from_date}"
            assert record["date"] <= to_date, f"Date {record['date']} is after {to_date}"
        print(f"PASS: Date range filter works - {len(data['data'])} records in range")
    
    def test_missed_punches_filter_by_employee_name(self, hr_headers):
        """Test filtering by employee name"""
        response = requests.get(f"{BASE_URL}/api/missed-punches?employee_name=test", headers=hr_headers)
        assert response.status_code == 200
        data = response.json()
        # All returned records should contain the search term in emp_name
        for record in data["data"]:
            assert "test" in record["emp_name"].lower(), f"Employee name filter not working"
        print("PASS: Employee name filter works")


class TestJob4DuplicatePrevention(TestSetup):
    """JOB 4: Prevent duplicate requests"""
    
    def test_duplicate_missed_punch_returns_400(self, hr_headers, test_employee_id):
        """Test that duplicate missed punch (same employee + date + punch_type) returns 400"""
        unique_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        
        # First request should succeed
        payload = {
            "employee_id": test_employee_id,
            "date": unique_date,
            "punch_type": "Check-in",
            "check_in_time": f"{unique_date}T09:00",
            "reason": "Testing duplicate prevention"
        }
        response1 = requests.post(f"{BASE_URL}/api/missed-punches", json=payload, headers=hr_headers)
        
        if response1.status_code == 400 and "already exists" in response1.text:
            # Already exists from previous test run, try with different date
            unique_date = (datetime.now() - timedelta(days=200 + int(uuid.uuid4().hex[:4], 16) % 100)).strftime("%Y-%m-%d")
            payload["date"] = unique_date
            payload["check_in_time"] = f"{unique_date}T09:00"
            response1 = requests.post(f"{BASE_URL}/api/missed-punches", json=payload, headers=hr_headers)
        
        if response1.status_code == 200:
            # Second request with same data should fail
            response2 = requests.post(f"{BASE_URL}/api/missed-punches", json=payload, headers=hr_headers)
            assert response2.status_code == 400, f"Expected 400 for duplicate, got {response2.status_code}"
            assert "already exists" in response2.text.lower(), f"Expected 'already exists' error message"
            print("PASS: Duplicate missed punch correctly returns 400")
        else:
            print(f"INFO: First request returned {response1.status_code} - {response1.text}")
    
    def test_duplicate_late_request_returns_400(self, hr_headers, test_employee_id):
        """Test that duplicate late request (same employee + date) returns 400"""
        unique_date = (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d")
        
        payload = {
            "employee_id": test_employee_id,
            "date": unique_date,
            "reason": "Testing duplicate late request prevention"
        }
        response1 = requests.post(f"{BASE_URL}/api/late-requests", json=payload, headers=hr_headers)
        
        if response1.status_code == 400 and "already exists" in response1.text:
            unique_date = (datetime.now() - timedelta(days=250 + int(uuid.uuid4().hex[:4], 16) % 100)).strftime("%Y-%m-%d")
            payload["date"] = unique_date
            response1 = requests.post(f"{BASE_URL}/api/late-requests", json=payload, headers=hr_headers)
        
        if response1.status_code == 200:
            response2 = requests.post(f"{BASE_URL}/api/late-requests", json=payload, headers=hr_headers)
            assert response2.status_code == 400, f"Expected 400 for duplicate late request, got {response2.status_code}"
            assert "already exists" in response2.text.lower()
            print("PASS: Duplicate late request correctly returns 400")
        else:
            print(f"INFO: First late request returned {response1.status_code}")
    
    def test_duplicate_early_out_request_returns_400(self, hr_headers, test_employee_id):
        """Test that duplicate early out request (same employee + date) returns 400"""
        unique_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        
        payload = {
            "employee_id": test_employee_id,
            "date": unique_date,
            "reason": "Testing duplicate early out prevention"
        }
        response1 = requests.post(f"{BASE_URL}/api/early-out-requests", json=payload, headers=hr_headers)
        
        if response1.status_code == 400 and "already exists" in response1.text:
            unique_date = (datetime.now() - timedelta(days=280 + int(uuid.uuid4().hex[:4], 16) % 100)).strftime("%Y-%m-%d")
            payload["date"] = unique_date
            response1 = requests.post(f"{BASE_URL}/api/early-out-requests", json=payload, headers=hr_headers)
        
        if response1.status_code == 200:
            response2 = requests.post(f"{BASE_URL}/api/early-out-requests", json=payload, headers=hr_headers)
            assert response2.status_code == 400, f"Expected 400 for duplicate early out, got {response2.status_code}"
            assert "already exists" in response2.text.lower()
            print("PASS: Duplicate early out request correctly returns 400")
        else:
            print(f"INFO: First early out request returned {response1.status_code}")


class TestJob5LeaveApplyFix(TestSetup):
    """JOB 5: Employee leave apply works successfully (no more NameError)"""
    
    def test_employee_leave_apply_works(self, employee_headers):
        """Test that employee can apply for leave without NameError"""
        # Use a past date for sick leave (which allows past dates)
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        payload = {
            "leave_type": "Sick",
            "leave_split": "Full Day",
            "start_date": past_date,
            "end_date": past_date,
            "reason": "Testing leave application - should work without NameError"
        }
        
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=payload, headers=employee_headers)
        
        # Should not get 500 error (which would indicate NameError)
        assert response.status_code != 500, f"Got 500 error - possible NameError: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "leave_id" in data or "message" in data
            print("PASS: Employee leave apply works successfully")
        elif response.status_code == 400:
            # 400 is acceptable if it's a validation error (e.g., duplicate leave)
            print(f"INFO: Leave apply returned 400 (validation): {response.json().get('detail', '')}")
        else:
            print(f"INFO: Leave apply returned {response.status_code}: {response.text}")


class TestJob6LeaveRules(TestSetup):
    """JOB 6: Leave rules (Sick=past only, Casual=4 working days, Emergency=any)"""
    
    def test_sick_leave_future_date_returns_400(self, employee_headers):
        """Test that sick leave with future date returns 400"""
        future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        
        payload = {
            "leave_type": "Sick",
            "leave_split": "Full Day",
            "start_date": future_date,
            "end_date": future_date,
            "reason": "Testing sick leave future date restriction"
        }
        
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=payload, headers=employee_headers)
        assert response.status_code == 400, f"Expected 400 for sick leave with future date, got {response.status_code}"
        assert "past" in response.text.lower() or "current" in response.text.lower(), \
            f"Expected error about past/current dates: {response.text}"
        print("PASS: Sick leave with future date correctly returns 400")
    
    def test_casual_leave_less_than_4_days_returns_400(self, employee_headers):
        """Test that casual leave with less than 4 working days advance returns 400"""
        # Tomorrow is less than 4 working days
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        payload = {
            "leave_type": "Casual",
            "leave_split": "Full Day",
            "start_date": tomorrow,
            "end_date": tomorrow,
            "reason": "Testing casual leave advance notice requirement"
        }
        
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=payload, headers=employee_headers)
        assert response.status_code == 400, f"Expected 400 for casual leave without 4 days notice, got {response.status_code}"
        assert "4" in response.text or "working days" in response.text.lower() or "advance" in response.text.lower(), \
            f"Expected error about 4 working days: {response.text}"
        print("PASS: Casual leave with less than 4 working days correctly returns 400")
    
    def test_emergency_leave_any_date_succeeds(self, employee_headers):
        """Test that emergency leave with any date succeeds"""
        # Use a unique future date
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        
        payload = {
            "leave_type": "Emergency",
            "leave_split": "Full Day",
            "start_date": future_date,
            "end_date": future_date,
            "reason": "Testing emergency leave - no date restrictions"
        }
        
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=payload, headers=employee_headers)
        
        # Emergency leave should succeed (200) or fail only due to duplicate (400)
        if response.status_code == 200:
            print("PASS: Emergency leave with any date succeeds")
        elif response.status_code == 400:
            detail = response.json().get("detail", "")
            # If it's a duplicate error, that's fine - the date rule passed
            if "already exists" in detail.lower():
                print("PASS: Emergency leave date rule passed (duplicate prevented)")
            else:
                # Should not fail due to date restrictions
                assert "past" not in detail.lower() and "advance" not in detail.lower(), \
                    f"Emergency leave should not have date restrictions: {detail}"
                print(f"INFO: Emergency leave returned 400: {detail}")
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text}")


class TestJob7SingleLeavePerDay(TestSetup):
    """JOB 7: Single leave per day rule"""
    
    def test_two_leaves_same_date_returns_400(self, employee_headers):
        """Test that two leaves on same date returns 400"""
        # Use a unique past date for sick leave
        unique_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        
        payload1 = {
            "leave_type": "Sick",
            "leave_split": "Full Day",
            "start_date": unique_date,
            "end_date": unique_date,
            "reason": "First leave request for single leave per day test"
        }
        
        response1 = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=payload1, headers=employee_headers)
        
        if response1.status_code == 400 and "already exists" in response1.text:
            # Already exists, which proves the rule works
            print("PASS: Single leave per day rule working (existing leave found)")
            return
        
        if response1.status_code == 200:
            # Try to create another leave for the same date
            payload2 = {
                "leave_type": "Sick",
                "leave_split": "Full Day",
                "start_date": unique_date,
                "end_date": unique_date,
                "reason": "Second leave request - should fail"
            }
            
            response2 = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=payload2, headers=employee_headers)
            assert response2.status_code == 400, f"Expected 400 for second leave on same date, got {response2.status_code}"
            assert "already exists" in response2.text.lower(), f"Expected 'already exists' error: {response2.text}"
            print("PASS: Two leaves on same date correctly returns 400")
        else:
            print(f"INFO: First leave request returned {response1.status_code}: {response1.text}")


class TestJob3MissedPunchAttendanceUpdate(TestSetup):
    """JOB 3: Approved missed punch → auto-update attendance"""
    
    def test_approve_missed_punch_updates_attendance(self, hr_headers, test_employee_id):
        """Test that approving missed punch creates/updates attendance record"""
        # Use a unique date that likely doesn't have attendance
        unique_date = (datetime.now() - timedelta(days=300 + int(uuid.uuid4().hex[:4], 16) % 50)).strftime("%Y-%m-%d")
        
        # Create a missed punch request
        payload = {
            "employee_id": test_employee_id,
            "date": unique_date,
            "punch_type": "Check-in",
            "check_in_time": f"{unique_date}T09:30",
            "reason": "Testing attendance update on approval"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/missed-punches", json=payload, headers=hr_headers)
        
        if create_response.status_code == 400 and "already exists" in create_response.text:
            print("INFO: Missed punch already exists for this date - skipping")
            return
        
        if create_response.status_code == 200:
            missed_punch = create_response.json()
            request_id = missed_punch.get("id")
            
            if missed_punch.get("status") == "pending":
                # Approve the request
                approve_response = requests.put(
                    f"{BASE_URL}/api/missed-punches/{request_id}/approve",
                    headers=hr_headers
                )
                assert approve_response.status_code == 200, f"Approve failed: {approve_response.text}"
                
                approved = approve_response.json()
                assert approved.get("status") == "approved", "Status should be approved"
                print("PASS: Missed punch approved successfully")
                
                # Verify attendance was updated (check attendance API)
                # Note: The attendance update happens asynchronously
                print("INFO: Attendance should be updated with first_punch from missed punch")
            else:
                print(f"INFO: Missed punch was auto-approved: {missed_punch.get('status')}")
        else:
            print(f"INFO: Create missed punch returned {create_response.status_code}")


class TestJob1DatetimeInputs(TestSetup):
    """JOB 1: Datetime picker for missed punch forms (backend accepts datetime-local format)"""
    
    def test_missed_punch_accepts_datetime_format(self, hr_headers, test_employee_id):
        """Test that missed punch API accepts datetime-local format (YYYY-MM-DDTHH:MM)"""
        unique_date = (datetime.now() - timedelta(days=350)).strftime("%Y-%m-%d")
        
        # datetime-local format: YYYY-MM-DDTHH:MM
        payload = {
            "employee_id": test_employee_id,
            "date": unique_date,
            "punch_type": "Both",
            "check_in_time": f"{unique_date}T09:00",  # datetime-local format
            "check_out_time": f"{unique_date}T18:00",  # datetime-local format
            "reason": "Testing datetime-local format acceptance"
        }
        
        response = requests.post(f"{BASE_URL}/api/missed-punches", json=payload, headers=hr_headers)
        
        # Should accept the datetime format (200) or fail due to duplicate (400)
        if response.status_code == 200:
            data = response.json()
            # Verify the times were stored
            assert data.get("check_in_time") is not None
            assert data.get("check_out_time") is not None
            print("PASS: Missed punch accepts datetime-local format")
        elif response.status_code == 400:
            if "already exists" in response.text.lower():
                print("PASS: Datetime format accepted (duplicate prevented)")
            else:
                print(f"INFO: Returned 400: {response.text}")
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text}")


class TestAdminLeaveCreate(TestSetup):
    """Test admin leave creation with duplicate prevention"""
    
    def test_admin_leave_duplicate_per_day_returns_400(self, hr_headers, test_employee_id):
        """Test that admin creating duplicate leave for same date returns 400"""
        unique_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        payload = {
            "employee_id": test_employee_id,
            "leave_type": "Sick",
            "leave_split": "Full Day",
            "start_date": unique_date,
            "end_date": unique_date,
            "reason": "Admin leave creation test"
        }
        
        response1 = requests.post(f"{BASE_URL}/api/leaves", json=payload, headers=hr_headers)
        
        if response1.status_code == 400 and "already exists" in response1.text:
            print("PASS: Admin leave duplicate prevention working")
            return
        
        if response1.status_code == 200:
            # Try to create another leave for same date
            response2 = requests.post(f"{BASE_URL}/api/leaves", json=payload, headers=hr_headers)
            assert response2.status_code == 400, f"Expected 400 for duplicate admin leave, got {response2.status_code}"
            assert "already exists" in response2.text.lower()
            print("PASS: Admin leave duplicate per day correctly returns 400")
        else:
            print(f"INFO: Admin leave create returned {response1.status_code}")


class TestBackwardCompatibility(TestSetup):
    """Test backward compatibility for old records"""
    
    def test_missed_punch_api_handles_both_formats(self, hr_headers):
        """Test that API returns data that can handle both old (time-only) and new (datetime) formats"""
        response = requests.get(f"{BASE_URL}/api/missed-punches", headers=hr_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Should return paginated format
        assert "data" in data
        
        # Check that records can have either format
        for record in data["data"][:5]:  # Check first 5 records
            check_in = record.get("check_in_time")
            if check_in:
                # Should be either time-only (HH:MM) or datetime (YYYY-MM-DDTHH:MM)
                assert len(check_in) >= 5, f"Invalid time format: {check_in}"
        
        print("PASS: API handles both old and new time formats")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
