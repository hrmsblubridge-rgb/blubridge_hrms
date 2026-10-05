"""
Employee Portal API Tests
Tests for the new Employee Module endpoints:
- /api/employee/dashboard
- /api/employee/profile
- /api/employee/attendance
- /api/employee/leaves
- /api/employee/clock-in
- /api/employee/clock-out
- /api/employee/leaves/apply
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
EMPLOYEE_CREDS = {"username": "user", "password": "user"}
ADMIN_CREDS = {"username": "admin", "password": "admin"}


class TestAuthentication:
    """Authentication and role-based routing tests"""
    
    def test_employee_login_success(self):
        """Test employee login returns correct role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "employee"
        assert data["user"]["employee_id"] is not None
        print(f"✓ Employee login successful, role: {data['user']['role']}")
    
    def test_admin_login_success(self):
        """Test admin login returns correct role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful, role: {data['user']['role']}")
    
    def test_invalid_credentials(self):
        """Test invalid credentials return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "invalid", "password": "invalid"})
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")


class TestEmployeeDashboard:
    """Employee Dashboard API tests"""
    
    @pytest.fixture
    def employee_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        return response.json()["token"]
    
    def test_dashboard_returns_employee_data(self, employee_token):
        """Test dashboard returns employee name and summary"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "employee_name" in data
        assert "employee_id" in data
        assert "department" in data
        assert "team" in data
        assert "summary" in data
        assert "today" in data
        assert "current_month" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "active_days" in summary
        assert "inactive_days" in summary
        assert "late_arrivals" in summary
        assert "early_outs" in summary
        
        # Verify today structure
        today = data["today"]
        assert "date" in today
        assert "login_time" in today
        assert "logout_time" in today
        assert "is_logged_in" in today
        assert "is_logged_out" in today
        
        print(f"✓ Dashboard data returned for: {data['employee_name']}")
    
    def test_dashboard_requires_auth(self):
        """Test dashboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/employee/dashboard")
        assert response.status_code in [401, 403]
        print("✓ Dashboard correctly requires authentication")


class TestEmployeeProfile:
    """Employee Profile API tests"""
    
    @pytest.fixture
    def employee_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        return response.json()["token"]
    
    def test_profile_returns_employee_info(self, employee_token):
        """Test profile returns complete employee information"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify personal info
        assert "full_name" in data
        assert "official_email" in data
        assert "gender" in data
        
        # Verify employment info
        assert "emp_id" in data
        assert "designation" in data
        assert "employment_type" in data
        assert "employee_status" in data
        assert "date_of_joining" in data
        assert "tier_level" in data
        
        # Verify organization info
        assert "department" in data
        assert "team" in data
        assert "work_location" in data
        
        # Verify HR config
        assert "leave_policy" in data
        assert "shift_type" in data
        assert "attendance_tracking_enabled" in data
        
        print(f"✓ Profile returned for: {data['full_name']} ({data['emp_id']})")
    
    def test_profile_requires_auth(self):
        """Test profile requires authentication"""
        response = requests.get(f"{BASE_URL}/api/employee/profile")
        assert response.status_code in [401, 403]
        print("✓ Profile correctly requires authentication")


class TestEmployeeAttendance:
    """Employee Attendance API tests"""
    
    @pytest.fixture
    def employee_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        return response.json()["token"]
    
    def test_attendance_this_week(self, employee_token):
        """Test attendance returns records for this week"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/attendance?duration=this_week", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 7  # 7 days in a week
        
        # Verify record structure
        for record in data:
            assert "date" in record
            assert "day" in record
            assert "login" in record
            assert "logout" in record
            assert "total_hours" in record
            assert "status" in record
        
        print(f"✓ Attendance returned {len(data)} records for this week")
    
    def test_attendance_this_month(self, employee_token):
        """Test attendance returns records for this month"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/attendance?duration=this_month", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 28  # At least 28 days in a month
        
        print(f"✓ Attendance returned {len(data)} records for this month")
    
    def test_attendance_status_filter(self, employee_token):
        """Test attendance status filter works"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/attendance?duration=this_month&status_filter=Present", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # All records should have Present status
        for record in data:
            assert record["status"] == "Present"
        
        print(f"✓ Status filter returned {len(data)} Present records")
    
    def test_attendance_requires_auth(self):
        """Test attendance requires authentication"""
        response = requests.get(f"{BASE_URL}/api/employee/attendance")
        assert response.status_code in [401, 403]
        print("✓ Attendance correctly requires authentication")


class TestEmployeeLeaves:
    """Employee Leave API tests"""
    
    @pytest.fixture
    def employee_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        return response.json()["token"]
    
    def test_leaves_returns_requests_and_history(self, employee_token):
        """Test leaves returns both requests and history"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/leaves", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "requests" in data
        assert "history" in data
        assert "requests_count" in data
        assert "history_count" in data
        
        assert isinstance(data["requests"], list)
        assert isinstance(data["history"], list)
        
        print(f"✓ Leaves returned {data['requests_count']} requests, {data['history_count']} history")
    
    def test_apply_leave_success(self, employee_token):
        """Test applying for leave"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        leave_data = {
            "leave_type": "Preplanned",
            "leave_date": "20-02-2026",
            "duration": "Full Day",
            "reason": "Personal work - need to attend a family function"
        }
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=leave_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "leave_id" in data
        assert data["message"] == "Leave request submitted successfully"
        
        print(f"✓ Leave applied successfully, ID: {data['leave_id']}")
    
    def test_apply_leave_past_date_validation(self, employee_token):
        """Test leave validation - past date should be rejected"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        leave_data = {
            "leave_type": "Sick",
            "leave_date": "01-01-2020",  # Past date
            "duration": "First Half",
            "reason": "Testing past date validation"
        }
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", json=leave_data, headers=headers)
        assert response.status_code == 400
        assert "past dates" in response.json().get("detail", "").lower()
        print("✓ Leave validation correctly rejects past dates")
    
    def test_leaves_requires_auth(self):
        """Test leaves requires authentication"""
        response = requests.get(f"{BASE_URL}/api/employee/leaves")
        assert response.status_code in [401, 403]
        print("✓ Leaves correctly requires authentication")


class TestEmployeeClockInOut:
    """Employee Clock In/Out API tests"""
    
    @pytest.fixture
    def employee_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        return response.json()["token"]
    
    def test_clock_in_already_clocked(self, employee_token):
        """Test clock-in when already clocked in"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.post(f"{BASE_URL}/api/employee/clock-in", headers=headers)
        # Should return 400 if already clocked in
        if response.status_code == 400:
            assert "Already clocked in" in response.json().get("detail", "")
            print("✓ Clock-in correctly rejects duplicate clock-in")
        else:
            assert response.status_code == 200
            print("✓ Clock-in successful")
    
    def test_clock_out_already_clocked(self, employee_token):
        """Test clock-out when already clocked out"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.post(f"{BASE_URL}/api/employee/clock-out", headers=headers)
        # Should return 400 if already clocked out
        if response.status_code == 400:
            assert "Already clocked out" in response.json().get("detail", "")
            print("✓ Clock-out correctly rejects duplicate clock-out")
        else:
            assert response.status_code == 200
            data = response.json()
            assert "time" in data
            assert "total_hours" in data
            print(f"✓ Clock-out successful, total hours: {data.get('total_hours')}")
    
    def test_clock_requires_auth(self):
        """Test clock-in/out requires authentication"""
        response = requests.post(f"{BASE_URL}/api/employee/clock-in")
        assert response.status_code in [401, 403]
        response = requests.post(f"{BASE_URL}/api/employee/clock-out")
        assert response.status_code in [401, 403]
        print("✓ Clock-in/out correctly requires authentication")


class TestAdminCannotAccessEmployeePortal:
    """Test that admin user without employee_id cannot access employee portal"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        return response.json()["token"]
    
    def test_admin_cannot_access_employee_dashboard(self, admin_token):
        """Admin without employee_id should get 404 on employee dashboard"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/dashboard", headers=headers)
        assert response.status_code == 404
        assert "No employee profile linked" in response.json().get("detail", "")
        print("✓ Admin correctly blocked from employee dashboard")
    
    def test_admin_cannot_access_employee_profile(self, admin_token):
        """Admin without employee_id should get 404 on employee profile"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/employee/profile", headers=headers)
        assert response.status_code == 404
        print("✓ Admin correctly blocked from employee profile")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
