"""
Test suite for HRMS new modules: Late Requests, Early Out, Missed Punch
Also tests Leave enhancements (leave_split, doc upload, LOP approval)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_admin_login(self, admin_token):
        """Test admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"✓ Admin login successful, token length: {len(admin_token)}")


class TestLateRequests:
    """Late Request module tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_late_requests(self, auth_headers):
        """Test GET /api/late-requests returns list"""
        response = requests.get(f"{BASE_URL}/api/late-requests", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/late-requests returned {len(data)} records")
    
    def test_create_late_request_requires_employee(self, auth_headers):
        """Test POST /api/late-requests - admin needs employee_id"""
        # First get an employee
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=auth_headers)
        assert emp_response.status_code == 200
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No employees to test with")
        
        employee = employees[0]
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/late-requests", headers=auth_headers, json={
            "employee_id": employee["id"],
            "date": today,
            "expected_time": "10:00",
            "actual_time": "10:30",
            "reason": "Traffic delay - testing late request creation"
        })
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert "id" in data, "Response should have id"
        print(f"✓ POST /api/late-requests created request for {employee['full_name']}")
        return data["id"]


class TestEarlyOutRequests:
    """Early Out Request module tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_early_out_requests(self, auth_headers):
        """Test GET /api/early-out-requests returns list"""
        response = requests.get(f"{BASE_URL}/api/early-out-requests", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/early-out-requests returned {len(data)} records")
    
    def test_create_early_out_request(self, auth_headers):
        """Test POST /api/early-out-requests"""
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=auth_headers)
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No employees to test with")
        
        employee = employees[0]
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/early-out-requests", headers=auth_headers, json={
            "employee_id": employee["id"],
            "date": today,
            "expected_time": "21:00",
            "actual_time": "18:00",
            "reason": "Personal emergency - testing early out request"
        })
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        print(f"✓ POST /api/early-out-requests created request for {employee['full_name']}")


class TestMissedPunch:
    """Missed Punch module tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_missed_punches(self, auth_headers):
        """Test GET /api/missed-punches returns list"""
        response = requests.get(f"{BASE_URL}/api/missed-punches", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/missed-punches returned {len(data)} records")
    
    def test_create_missed_punch_checkin(self, auth_headers):
        """Test POST /api/missed-punches with Check-in type"""
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=auth_headers)
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No employees to test with")
        
        employee = employees[0]
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/missed-punches", headers=auth_headers, json={
            "employee_id": employee["id"],
            "date": today,
            "punch_type": "Check-in",
            "check_in_time": "10:00",
            "reason": "Biometric not working - testing missed punch"
        })
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("punch_type") == "Check-in"
        print(f"✓ POST /api/missed-punches (Check-in) created for {employee['full_name']}")
    
    def test_create_missed_punch_both(self, auth_headers):
        """Test POST /api/missed-punches with Both type"""
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=auth_headers)
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No employees to test with")
        
        employee = employees[1] if len(employees) > 1 else employees[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/missed-punches", headers=auth_headers, json={
            "employee_id": employee["id"],
            "date": yesterday,
            "punch_type": "Both",
            "check_in_time": "10:00",
            "check_out_time": "19:00",
            "reason": "System was down - testing missed punch both"
        })
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert data.get("punch_type") == "Both"
        print(f"✓ POST /api/missed-punches (Both) created for {employee['full_name']}")


class TestAttendanceStats:
    """Attendance stats endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_attendance_stats(self, auth_headers):
        """Test GET /api/attendance/stats returns valid data"""
        response = requests.get(f"{BASE_URL}/api/attendance/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Check expected fields
        expected_fields = ["total_employees", "present_today", "absent_today", "on_leave"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        print(f"✓ GET /api/attendance/stats: {data}")


class TestLeaveEnhancements:
    """Leave module enhancement tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_leaves(self, auth_headers):
        """Test GET /api/leaves returns list"""
        response = requests.get(f"{BASE_URL}/api/leaves", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/leaves returned {len(data)} records")
    
    def test_create_leave_with_split(self, auth_headers):
        """Test POST /api/leaves with leave_split field"""
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=auth_headers)
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No employees to test with")
        
        employee = employees[0]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/leaves", headers=auth_headers, json={
            "employee_id": employee["id"],
            "leave_type": "Sick",
            "leave_split": "First Half",
            "start_date": tomorrow,
            "end_date": tomorrow,
            "reason": "Medical appointment - testing leave split feature"
        })
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("leave_split") == "First Half"
        print(f"✓ POST /api/leaves with leave_split='First Half' created")
    
    def test_approve_leave_with_lop(self, auth_headers):
        """Test PUT /api/leaves/{id}/approve with LOP option"""
        # First create a leave request
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=auth_headers)
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No employees to test with")
        
        employee = employees[0]
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        # Create leave
        create_response = requests.post(f"{BASE_URL}/api/leaves", headers=auth_headers, json={
            "employee_id": employee["id"],
            "leave_type": "Casual",
            "leave_split": "Full Day",
            "start_date": day_after,
            "end_date": day_after,
            "reason": "Personal work - testing LOP approval feature"
        })
        assert create_response.status_code in [200, 201]
        leave_id = create_response.json()["id"]
        
        # Approve with LOP
        approve_response = requests.put(f"{BASE_URL}/api/leaves/{leave_id}/approve", headers=auth_headers, json={
            "is_lop": True,
            "lop_remark": "Exceeded leave quota"
        })
        assert approve_response.status_code == 200, f"Failed: {approve_response.text}"
        data = approve_response.json()
        assert data.get("is_lop") == True
        print(f"✓ PUT /api/leaves/{leave_id}/approve with LOP=True successful")


class TestDashboardStats:
    """Dashboard stats tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_dashboard_stats(self, auth_headers):
        """Test GET /api/dashboard/stats"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"✓ GET /api/dashboard/stats: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
