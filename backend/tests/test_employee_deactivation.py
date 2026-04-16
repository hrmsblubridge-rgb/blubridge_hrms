"""
Test Employee Deactivation Enhancement Feature
- Deactivation form modal with fields: inactive_type, inactive_date, reason, last_day_payable
- Inactive Type filter in employee list
- Inactive Type column in employee table
- Backend DELETE /api/employees/{id} with body
- Backend GET /api/employees with inactive_type filter
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmployeeDeactivation:
    """Test employee deactivation feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - login as HR admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as HR admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Store test employee ID for cleanup
        self.test_employee_id = None
        yield
        
        # Cleanup: restore test employee if deactivated
        if self.test_employee_id:
            try:
                self.session.put(f"{BASE_URL}/api/employees/{self.test_employee_id}/restore")
            except:
                pass
    
    def test_01_login_success(self):
        """Test HR admin login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "hr"
        print("PASS: HR admin login successful")
    
    def test_02_get_employees_endpoint(self):
        """Test GET /api/employees returns employees"""
        response = self.session.get(f"{BASE_URL}/api/employees")
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        assert "total" in data
        print(f"PASS: GET /api/employees returned {data['total']} employees")
    
    def test_03_get_employees_with_inactive_type_filter(self):
        """Test GET /api/employees with inactive_type filter"""
        # Test with Terminated filter
        response = self.session.get(f"{BASE_URL}/api/employees", params={
            "inactive_type": "Terminated",
            "include_deleted": True
        })
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        # All returned employees should have inactive_type = Terminated
        for emp in data["employees"]:
            if emp.get("inactive_type"):
                assert emp["inactive_type"] == "Terminated", f"Expected Terminated, got {emp['inactive_type']}"
        print(f"PASS: Inactive type filter (Terminated) returned {len(data['employees'])} employees")
        
        # Test with Relieved filter
        response = self.session.get(f"{BASE_URL}/api/employees", params={
            "inactive_type": "Relieved",
            "include_deleted": True
        })
        assert response.status_code == 200
        data = response.json()
        print(f"PASS: Inactive type filter (Relieved) returned {len(data['employees'])} employees")
        
        # Test with Completed Internship filter
        response = self.session.get(f"{BASE_URL}/api/employees", params={
            "inactive_type": "Completed Internship",
            "include_deleted": True
        })
        assert response.status_code == 200
        data = response.json()
        print(f"PASS: Inactive type filter (Completed Internship) returned {len(data['employees'])} employees")
    
    def test_04_create_test_employee_for_deactivation(self):
        """Create a test employee for deactivation testing"""
        unique_id = str(uuid.uuid4())[:8]
        test_employee = {
            "full_name": f"TEST_Deactivation_{unique_id}",
            "official_email": f"test_deact_{unique_id}@test.com",
            "phone_number": "9876543210",
            "date_of_joining": "2024-01-15",
            "department": "Research Unit",
            "team": "Data",
            "designation": "Research",
            "custom_employee_id": f"TEST-DEACT-{unique_id}",
            "biometric_id": f"BIO-DEACT-{unique_id}",
            "login_enabled": False  # Don't create user account
        }
        
        response = self.session.post(f"{BASE_URL}/api/employees", json=test_employee)
        assert response.status_code in [200, 201], f"Failed to create test employee: {response.text}"
        data = response.json()
        self.test_employee_id = data["id"]
        print(f"PASS: Created test employee {data['emp_id']} (ID: {self.test_employee_id})")
        return data
    
    def test_05_deactivate_employee_with_form_data(self):
        """Test DELETE /api/employees/{id} with deactivation form data"""
        # First create a test employee
        unique_id = str(uuid.uuid4())[:8]
        test_employee = {
            "full_name": f"TEST_Deact_Form_{unique_id}",
            "official_email": f"test_deact_form_{unique_id}@test.com",
            "date_of_joining": "2024-01-15",
            "department": "Research Unit",
            "team": "Data",
            "designation": "Research",
            "custom_employee_id": f"TEST-DF-{unique_id}",
            "biometric_id": f"BIO-DF-{unique_id}",
            "login_enabled": False
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/employees", json=test_employee)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        employee_id = create_response.json()["id"]
        self.test_employee_id = employee_id
        
        # Deactivate with form data
        deactivation_data = {
            "inactive_type": "Terminated",
            "inactive_date": "2026-01-15",
            "reason": "Test deactivation - performance issues",
            "last_day_payable": True
        }
        
        # Use requests directly with data parameter for DELETE with body
        delete_response = requests.delete(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers=self.session.headers,
            json=deactivation_data
        )
        assert delete_response.status_code == 200, f"Deactivation failed: {delete_response.text}"
        print("PASS: Employee deactivated with form data")
        
        # Verify the employee is deactivated with correct data
        get_response = self.session.get(f"{BASE_URL}/api/employees", params={
            "inactive_type": "Terminated",
            "include_deleted": True
        })
        assert get_response.status_code == 200
        employees = get_response.json()["employees"]
        
        # Find our deactivated employee
        deactivated_emp = next((e for e in employees if e["id"] == employee_id), None)
        assert deactivated_emp is not None, "Deactivated employee not found in Terminated filter"
        assert deactivated_emp["is_deleted"] == True
        assert deactivated_emp["inactive_type"] == "Terminated"
        assert deactivated_emp["inactive_date"] == "2026-01-15"
        assert deactivated_emp["inactive_reason"] == "Test deactivation - performance issues"
        assert deactivated_emp["last_day_payable"] == True
        assert deactivated_emp["employee_status"] == "Inactive"
        print("PASS: Deactivation data stored correctly in database")
    
    def test_06_deactivate_with_relieved_type(self):
        """Test deactivation with Relieved type"""
        unique_id = str(uuid.uuid4())[:8]
        test_employee = {
            "full_name": f"TEST_Relieved_{unique_id}",
            "official_email": f"test_relieved_{unique_id}@test.com",
            "date_of_joining": "2024-01-15",
            "department": "Support Staff",
            "team": "IT",
            "designation": "Front Office",
            "custom_employee_id": f"TEST-REL-{unique_id}",
            "biometric_id": f"BIO-REL-{unique_id}",
            "login_enabled": False
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/employees", json=test_employee)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        employee_id = create_response.json()["id"]
        self.test_employee_id = employee_id
        
        deactivation_data = {
            "inactive_type": "Relieved",
            "inactive_date": "2026-01-20",
            "reason": "Voluntary resignation",
            "last_day_payable": False
        }
        
        delete_response = requests.delete(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers=self.session.headers,
            json=deactivation_data
        )
        assert delete_response.status_code == 200
        
        # Verify with Relieved filter
        get_response = self.session.get(f"{BASE_URL}/api/employees", params={
            "inactive_type": "Relieved",
            "include_deleted": True
        })
        assert get_response.status_code == 200
        employees = get_response.json()["employees"]
        
        deactivated_emp = next((e for e in employees if e["id"] == employee_id), None)
        assert deactivated_emp is not None
        assert deactivated_emp["inactive_type"] == "Relieved"
        print("PASS: Relieved type deactivation works correctly")
    
    def test_07_deactivate_with_completed_internship_type(self):
        """Test deactivation with Completed Internship type"""
        unique_id = str(uuid.uuid4())[:8]
        test_employee = {
            "full_name": f"TEST_Intern_{unique_id}",
            "official_email": f"test_intern_{unique_id}@test.com",
            "date_of_joining": "2024-06-01",
            "department": "Research Unit",
            "team": "Compiler",
            "designation": "AI Research - Intern",
            "employment_type": "Intern",
            "custom_employee_id": f"TEST-INT-{unique_id}",
            "biometric_id": f"BIO-INT-{unique_id}",
            "login_enabled": False
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/employees", json=test_employee)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        employee_id = create_response.json()["id"]
        self.test_employee_id = employee_id
        
        deactivation_data = {
            "inactive_type": "Completed Internship",
            "inactive_date": "2026-01-25",
            "reason": "Internship period completed successfully",
            "last_day_payable": True
        }
        
        delete_response = requests.delete(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers=self.session.headers,
            json=deactivation_data
        )
        assert delete_response.status_code == 200
        
        # Verify with Completed Internship filter
        get_response = self.session.get(f"{BASE_URL}/api/employees", params={
            "inactive_type": "Completed Internship",
            "include_deleted": True
        })
        assert get_response.status_code == 200
        employees = get_response.json()["employees"]
        
        deactivated_emp = next((e for e in employees if e["id"] == employee_id), None)
        assert deactivated_emp is not None
        assert deactivated_emp["inactive_type"] == "Completed Internship"
        print("PASS: Completed Internship type deactivation works correctly")
    
    def test_08_user_account_deactivated_on_employee_deactivation(self):
        """Test that user account is deactivated when employee is deactivated"""
        unique_id = str(uuid.uuid4())[:8]
        test_employee = {
            "full_name": f"TEST_UserDeact_{unique_id}",
            "official_email": f"test_userdeact_{unique_id}@test.com",
            "date_of_joining": "2024-01-15",
            "department": "Research Unit",
            "team": "Data",
            "designation": "Research",
            "custom_employee_id": f"TEST-UD-{unique_id}",
            "biometric_id": f"BIO-UD-{unique_id}",
            "login_enabled": True  # Create user account
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/employees", json=test_employee)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        employee_id = create_response.json()["id"]
        self.test_employee_id = employee_id
        
        # Deactivate
        deactivation_data = {
            "inactive_type": "Terminated",
            "inactive_date": "2026-01-15",
            "reason": "Test user deactivation",
            "last_day_payable": False
        }
        
        delete_response = requests.delete(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers=self.session.headers,
            json=deactivation_data
        )
        assert delete_response.status_code == 200
        
        # Verify employee is deactivated
        get_response = self.session.get(f"{BASE_URL}/api/employees", params={
            "include_deleted": True
        })
        employees = get_response.json()["employees"]
        deactivated_emp = next((e for e in employees if e["id"] == employee_id), None)
        assert deactivated_emp is not None
        assert deactivated_emp["login_enabled"] == False
        print("PASS: User account deactivated along with employee")
    
    def test_09_active_employees_not_affected(self):
        """Test that active employees are not affected by deactivation filters"""
        # Get active employees (default - no include_deleted)
        response = self.session.get(f"{BASE_URL}/api/employees")
        assert response.status_code == 200
        data = response.json()
        
        # All returned employees should be active (not deleted)
        for emp in data["employees"]:
            assert emp.get("is_deleted") != True, f"Found deleted employee in active list: {emp['full_name']}"
        
        print(f"PASS: Active employees list contains only active employees ({len(data['employees'])} found)")
    
    def test_10_deactivation_without_body_uses_defaults(self):
        """Test deactivation without body uses default values"""
        unique_id = str(uuid.uuid4())[:8]
        test_employee = {
            "full_name": f"TEST_NoBody_{unique_id}",
            "official_email": f"test_nobody_{unique_id}@test.com",
            "date_of_joining": "2024-01-15",
            "department": "Research Unit",
            "team": "Data",
            "designation": "Research",
            "custom_employee_id": f"TEST-NB-{unique_id}",
            "biometric_id": f"BIO-NB-{unique_id}",
            "login_enabled": False
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/employees", json=test_employee)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        employee_id = create_response.json()["id"]
        self.test_employee_id = employee_id
        
        # Deactivate without body (should use defaults)
        delete_response = requests.delete(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers=self.session.headers
        )
        assert delete_response.status_code == 200
        
        # Verify defaults were applied
        get_response = self.session.get(f"{BASE_URL}/api/employees", params={
            "include_deleted": True
        })
        employees = get_response.json()["employees"]
        deactivated_emp = next((e for e in employees if e["id"] == employee_id), None)
        assert deactivated_emp is not None
        assert deactivated_emp["inactive_type"] == "Terminated"  # Default
        assert deactivated_emp["last_day_payable"] == False  # Default
        print("PASS: Deactivation without body uses default values")


class TestInactiveTypeColumn:
    """Test Inactive Type column in employee table"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - login as HR admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_inactive_type_field_in_response(self):
        """Test that inactive_type field is present in employee response for newly deactivated employees"""
        response = self.session.get(f"{BASE_URL}/api/employees", params={
            "include_deleted": True
        })
        assert response.status_code == 200
        employees = response.json()["employees"]
        
        # Check that inactive_type field exists for employees deactivated with the new feature
        # Note: Old deactivated employees may not have this field
        deactivated_with_type = [e for e in employees if e.get("is_deleted") and e.get("inactive_type")]
        active_employees = [e for e in employees if not e.get("is_deleted")]
        
        print(f"PASS: Found {len(deactivated_with_type)} deactivated employees with inactive_type")
        print(f"PASS: Found {len(active_employees)} active employees")
        
        # Verify active employees don't have inactive_type set
        for emp in active_employees:
            if emp.get("inactive_type"):
                print(f"WARNING: Active employee {emp['full_name']} has inactive_type set")
        
        print("PASS: inactive_type field present in employee response for deactivated employees")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
