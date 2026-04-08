"""
Comprehensive Backend API Tests for BluBridge HRMS
Tests both Admin and Employee modules based on requirements document
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://hrms-module-enhance.preview.emergentagent.com').rstrip('/')

class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
        
    def test_employee_login_success(self):
        """Test employee login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "user",
            "password": "user"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "employee"
        
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "invalid",
            "password": "invalid"
        })
        assert response.status_code == 401


@pytest.fixture
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def employee_token():
    """Get employee authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "user",
        "password": "user"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Employee authentication failed")


@pytest.fixture
def admin_headers(admin_token):
    """Get headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def employee_headers(employee_token):
    """Get headers with employee auth token"""
    return {
        "Authorization": f"Bearer {employee_token}",
        "Content-Type": "application/json"
    }


class TestAdminDashboard:
    """Admin Dashboard API tests"""
    
    def test_dashboard_stats(self, admin_headers):
        """Test dashboard statistics endpoint"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify required fields
        assert "total_research_unit" in data
        assert "total_support_staff" in data
        assert "pending_approvals" in data
        assert "upcoming_leaves" in data
        assert "attendance" in data
        
    def test_dashboard_leave_list(self, admin_headers):
        """Test dashboard leave list endpoint"""
        response = requests.get(f"{BASE_URL}/api/dashboard/leave-list", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_attendance_stats(self, admin_headers):
        """Test attendance statistics endpoint"""
        response = requests.get(f"{BASE_URL}/api/attendance/stats", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_employees" in data
        assert "logged_in" in data
        assert "not_logged" in data
        assert "early_out" in data
        assert "late_login" in data
        assert "logout" in data


class TestEmployeeManagement:
    """Employee Management API tests"""
    
    def test_get_employees_list(self, admin_headers):
        """Test getting employee list with pagination"""
        response = requests.get(f"{BASE_URL}/api/employees", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "pages" in data
        
    def test_get_employees_with_filters(self, admin_headers):
        """Test employee list with filters"""
        response = requests.get(f"{BASE_URL}/api/employees", headers=admin_headers, params={
            "department": "Research Unit",
            "status": "Active"
        })
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        
    def test_get_employees_with_search(self, admin_headers):
        """Test employee search functionality"""
        response = requests.get(f"{BASE_URL}/api/employees", headers=admin_headers, params={
            "search": "Adhitya"
        })
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        
    def test_get_all_employees_dropdown(self, admin_headers):
        """Test getting all employees for dropdown"""
        response = requests.get(f"{BASE_URL}/api/employees/all", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_employee_stats(self, admin_headers):
        """Test employee statistics"""
        response = requests.get(f"{BASE_URL}/api/employees/stats", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "active" in data
        assert "inactive" in data
        assert "resigned" in data
        
    def test_get_single_employee(self, admin_headers):
        """Test getting single employee details"""
        # First get list to get an employee ID
        list_response = requests.get(f"{BASE_URL}/api/employees", headers=admin_headers)
        employees = list_response.json().get("employees", [])
        if employees:
            emp_id = employees[0]["id"]
            response = requests.get(f"{BASE_URL}/api/employees/{emp_id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert "full_name" in data
            assert "official_email" in data
            assert "department" in data
            
    def test_create_employee(self, admin_headers):
        """Test creating new employee"""
        test_email = f"test_emp_{datetime.now().strftime('%Y%m%d%H%M%S')}@test.com"
        response = requests.post(f"{BASE_URL}/api/employees", headers=admin_headers, json={
            "full_name": "TEST Employee Create",
            "official_email": test_email,
            "phone_number": "1234567890",
            "gender": "Male",
            "date_of_joining": "2024-01-15",
            "employment_type": "Full-time",
            "designation": "Test Engineer",
            "tier_level": "Junior",
            "department": "Research Unit",
            "team": "AI Team",
            "work_location": "Office",
            "user_role": "employee",
            "login_enabled": False
        })
        assert response.status_code == 200
        data = response.json()
        assert "emp_id" in data
        assert data["full_name"] == "TEST Employee Create"
        # Store for cleanup
        return data.get("id")
        
    def test_update_employee(self, admin_headers):
        """Test updating employee"""
        # First get an employee
        list_response = requests.get(f"{BASE_URL}/api/employees", headers=admin_headers, params={"search": "TEST"})
        employees = list_response.json().get("employees", [])
        if employees:
            emp_id = employees[0]["id"]
            response = requests.put(f"{BASE_URL}/api/employees/{emp_id}", headers=admin_headers, json={
                "designation": "Updated Test Engineer"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["designation"] == "Updated Test Engineer"


class TestAttendanceManagement:
    """Attendance Management API tests"""
    
    def test_get_attendance_records(self, admin_headers):
        """Test getting attendance records"""
        response = requests.get(f"{BASE_URL}/api/attendance", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_attendance_with_date_filter(self, admin_headers):
        """Test attendance with date range filter - REPORTED BUG"""
        today = datetime.now().strftime("%d-%m-%Y")
        response = requests.get(f"{BASE_URL}/api/attendance", headers=admin_headers, params={
            "from_date": today,
            "to_date": today
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_attendance_with_status_filter(self, admin_headers):
        """Test attendance with status filter"""
        response = requests.get(f"{BASE_URL}/api/attendance", headers=admin_headers, params={
            "status": "Login"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_attendance_with_team_filter(self, admin_headers):
        """Test attendance with team filter"""
        response = requests.get(f"{BASE_URL}/api/attendance", headers=admin_headers, params={
            "team": "AI Team"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestLeaveManagement:
    """Leave Management API tests"""
    
    def test_get_leaves(self, admin_headers):
        """Test getting leave requests"""
        response = requests.get(f"{BASE_URL}/api/leaves", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_leaves_with_status_filter(self, admin_headers):
        """Test leaves with status filter"""
        response = requests.get(f"{BASE_URL}/api/leaves", headers=admin_headers, params={
            "status": "pending"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_leaves_with_type_filter(self, admin_headers):
        """Test leaves with type filter"""
        response = requests.get(f"{BASE_URL}/api/leaves", headers=admin_headers, params={
            "leave_type": "Sick"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_create_leave_request(self, admin_headers):
        """Test creating leave request"""
        # Get an employee ID first
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=admin_headers)
        employees = emp_response.json()
        if employees:
            emp_id = employees[0]["id"]
            future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            response = requests.post(f"{BASE_URL}/api/leaves", headers=admin_headers, json={
                "employee_id": emp_id,
                "leave_type": "Sick",
                "start_date": future_date,
                "end_date": future_date,
                "reason": "Test leave request"
            })
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["status"] == "pending"
            return data.get("id")


class TestStarReward:
    """Star Reward API tests"""
    
    def test_get_star_rewards(self, admin_headers):
        """Test getting star rewards (employees with stars)"""
        response = requests.get(f"{BASE_URL}/api/star-rewards", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_star_rewards_with_team_filter(self, admin_headers):
        """Test star rewards with team filter"""
        response = requests.get(f"{BASE_URL}/api/star-rewards", headers=admin_headers, params={
            "team": "AI Team"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_star_rewards_with_search(self, admin_headers):
        """Test star rewards with search"""
        response = requests.get(f"{BASE_URL}/api/star-rewards", headers=admin_headers, params={
            "search": "Adhitya"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_add_star_reward(self, admin_headers):
        """Test adding star reward"""
        # Get an employee ID first
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=admin_headers)
        employees = emp_response.json()
        if employees:
            emp_id = employees[0]["id"]
            response = requests.post(f"{BASE_URL}/api/star-rewards", headers=admin_headers, json={
                "employee_id": emp_id,
                "stars": 1,
                "reason": "Test star reward"
            })
            assert response.status_code == 200
            data = response.json()
            assert "new_total" in data
            
    def test_get_star_history(self, admin_headers):
        """Test getting star history for employee"""
        emp_response = requests.get(f"{BASE_URL}/api/employees/all", headers=admin_headers)
        employees = emp_response.json()
        if employees:
            emp_id = employees[0]["id"]
            response = requests.get(f"{BASE_URL}/api/star-rewards/history/{emp_id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestTeamManagement:
    """Team Management API tests"""
    
    def test_get_teams(self, admin_headers):
        """Test getting teams list"""
        response = requests.get(f"{BASE_URL}/api/teams", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "name" in data[0]
            assert "department" in data[0]
            assert "member_count" in data[0]
            
    def test_get_teams_by_department(self, admin_headers):
        """Test getting teams filtered by department"""
        response = requests.get(f"{BASE_URL}/api/teams", headers=admin_headers, params={
            "department": "Research Unit"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_get_team_details(self, admin_headers):
        """Test getting single team with members"""
        teams_response = requests.get(f"{BASE_URL}/api/teams", headers=admin_headers)
        teams = teams_response.json()
        if teams:
            team_id = teams[0]["id"]
            response = requests.get(f"{BASE_URL}/api/teams/{team_id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert "team" in data
            assert "members" in data
            
    def test_get_departments(self, admin_headers):
        """Test getting departments list"""
        response = requests.get(f"{BASE_URL}/api/departments", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "name" in data[0]


class TestReports:
    """Reports API tests"""
    
    def test_attendance_report(self, admin_headers):
        """Test attendance report generation"""
        today = datetime.now().strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        response = requests.get(f"{BASE_URL}/api/reports/attendance", headers=admin_headers, params={
            "from_date": month_ago,
            "to_date": today
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_leave_report(self, admin_headers):
        """Test leave report generation"""
        today = datetime.now().strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        response = requests.get(f"{BASE_URL}/api/reports/leaves", headers=admin_headers, params={
            "from_date": month_ago,
            "to_date": today
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_employee_report(self, admin_headers):
        """Test employee report generation"""
        response = requests.get(f"{BASE_URL}/api/reports/employees", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestEmployeePortal:
    """Employee Portal API tests"""
    
    def test_employee_dashboard(self, employee_headers):
        """Test employee dashboard endpoint"""
        response = requests.get(f"{BASE_URL}/api/employee/dashboard", headers=employee_headers)
        assert response.status_code == 200
        data = response.json()
        assert "employee_name" in data
        assert "summary" in data
        assert "today" in data
        assert "active_days" in data["summary"]
        assert "inactive_days" in data["summary"]
        assert "late_arrivals" in data["summary"]
        assert "early_outs" in data["summary"]
        
    def test_employee_profile(self, employee_headers):
        """Test employee profile endpoint"""
        response = requests.get(f"{BASE_URL}/api/employee/profile", headers=employee_headers)
        assert response.status_code == 200
        data = response.json()
        assert "full_name" in data
        assert "official_email" in data
        assert "department" in data
        assert "team" in data
        
    def test_employee_attendance(self, employee_headers):
        """Test employee attendance endpoint"""
        response = requests.get(f"{BASE_URL}/api/employee/attendance", headers=employee_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_employee_attendance_with_duration_filter(self, employee_headers):
        """Test employee attendance with duration filter"""
        response = requests.get(f"{BASE_URL}/api/employee/attendance", headers=employee_headers, params={
            "duration": "this_week"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_employee_leaves(self, employee_headers):
        """Test employee leaves endpoint"""
        response = requests.get(f"{BASE_URL}/api/employee/leaves", headers=employee_headers)
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "history" in data
        
    def test_employee_apply_leave(self, employee_headers):
        """Test employee apply leave endpoint"""
        future_date = (datetime.now() + timedelta(days=14)).strftime("%d-%m-%Y")
        response = requests.post(f"{BASE_URL}/api/employee/leaves/apply", headers=employee_headers, json={
            "leave_type": "Sick",
            "leave_date": future_date,
            "duration": "Full Day",
            "reason": "Test leave application from automated test"
        })
        assert response.status_code == 200
        data = response.json()
        assert "leave_id" in data or "id" in data
        assert "message" in data


class TestConfigEndpoints:
    """Configuration endpoints tests"""
    
    def test_employment_types(self):
        """Test employment types config"""
        response = requests.get(f"{BASE_URL}/api/config/employment-types")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "Full-time" in data
        
    def test_employee_statuses(self):
        """Test employee statuses config"""
        response = requests.get(f"{BASE_URL}/api/config/employee-statuses")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "Active" in data
        
    def test_tier_levels(self):
        """Test tier levels config"""
        response = requests.get(f"{BASE_URL}/api/config/tier-levels")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_work_locations(self):
        """Test work locations config"""
        response = requests.get(f"{BASE_URL}/api/config/work-locations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_user_roles(self):
        """Test user roles config"""
        response = requests.get(f"{BASE_URL}/api/config/user-roles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
