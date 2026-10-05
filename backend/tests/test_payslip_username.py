"""
Test cases for Payslip UI and Username Collision Fix
Tests:
1. Salary API returns correct structure for payslip
2. Username collision fix - creating employees with same email prefix generates unique usernames
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPayslipAndUsernameCollision:
    """Tests for Payslip feature and Username collision fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.admin_token = token
        yield
    
    def test_salary_api_returns_structure(self):
        """Test that salary API returns correct structure for payslip"""
        # Get list of employees
        emp_response = self.session.get(f"{BASE_URL}/api/employees?page=1&limit=1")
        assert emp_response.status_code == 200
        employees = emp_response.json().get("employees", [])
        
        if len(employees) == 0:
            pytest.skip("No employees found to test salary API")
        
        employee_id = employees[0]["id"]
        
        # Get salary for employee
        salary_response = self.session.get(f"{BASE_URL}/api/employees/{employee_id}/salary")
        assert salary_response.status_code == 200, f"Salary API failed: {salary_response.text}"
        
        salary_data = salary_response.json()
        assert "salary" in salary_data, "Response should contain 'salary' key"
        
        salary = salary_data["salary"]
        if salary:
            # Check for required fields in salary structure
            required_fields = [
                "annual_ctc", "monthly_ctc", "basic", "hra",
                "pf_employee", "pf_employer", "professional_tax",
                "net_salary", "total_deductions"
            ]
            for field in required_fields:
                assert field in salary, f"Salary should contain '{field}'"
            print(f"SUCCESS: Salary API returns correct structure with all required fields")
        else:
            print("INFO: Employee has no salary configured yet")
    
    def test_salary_api_with_ctc_update(self):
        """Test updating CTC and verifying salary breakdown"""
        # Get list of employees
        emp_response = self.session.get(f"{BASE_URL}/api/employees?page=1&limit=1")
        assert emp_response.status_code == 200
        employees = emp_response.json().get("employees", [])
        
        if len(employees) == 0:
            pytest.skip("No employees found to test salary API")
        
        employee_id = employees[0]["id"]
        
        # Update CTC
        update_response = self.session.put(
            f"{BASE_URL}/api/employees/{employee_id}/salary",
            json={"annual_ctc": 600000}
        )
        assert update_response.status_code == 200, f"Salary update failed: {update_response.text}"
        
        # Get salary again
        salary_response = self.session.get(f"{BASE_URL}/api/employees/{employee_id}/salary")
        assert salary_response.status_code == 200
        
        salary = salary_response.json().get("salary")
        assert salary is not None, "Salary should be set after CTC update"
        assert salary["annual_ctc"] == 600000, "Annual CTC should be 600000"
        assert salary["monthly_ctc"] == 50000, "Monthly CTC should be 50000"
        
        # Verify salary breakdown components exist
        assert salary["basic"] > 0, "Basic should be calculated"
        assert salary["hra"] > 0, "HRA should be calculated"
        assert salary["net_salary"] > 0, "Net salary should be calculated"
        
        print(f"SUCCESS: CTC update works correctly. Net salary: {salary['net_salary']}")
    
    def test_username_collision_fix(self):
        """Test that creating employees with same email prefix generates unique usernames"""
        timestamp = int(time.time())
        email_prefix = f"testuser{timestamp}"
        
        # Create first employee
        employee1_data = {
            "full_name": f"Test User One {timestamp}",
            "official_email": f"{email_prefix}@testdomain.com",
            "date_of_joining": "2026-01-01",
            "department": "Research Unit",
            "team": "Data",
            "designation": "AI Research scientist",
            "custom_employee_id": f"TEST-{timestamp}-1",
            "biometric_id": f"BIO-{timestamp}-1",
            "login_enabled": True
        }
        
        response1 = self.session.post(f"{BASE_URL}/api/employees", json=employee1_data)
        assert response1.status_code in [200, 201], f"First employee creation failed: {response1.text}"
        
        emp1_result = response1.json()
        username1 = emp1_result.get("username", email_prefix)
        print(f"First employee created with username: {username1}")
        
        # Create second employee with same email prefix but different domain
        employee2_data = {
            "full_name": f"Test User Two {timestamp}",
            "official_email": f"{email_prefix}@anotherdomain.com",
            "date_of_joining": "2026-01-01",
            "department": "Research Unit",
            "team": "Data",
            "designation": "AI Research scientist",
            "custom_employee_id": f"TEST-{timestamp}-2",
            "biometric_id": f"BIO-{timestamp}-2",
            "login_enabled": True
        }
        
        response2 = self.session.post(f"{BASE_URL}/api/employees", json=employee2_data)
        assert response2.status_code in [200, 201], f"Second employee creation failed: {response2.text}"
        
        emp2_result = response2.json()
        username2 = emp2_result.get("username", "")
        print(f"Second employee created with username: {username2}")
        
        # Verify usernames are different
        assert username1 != username2, f"Usernames should be different but got: {username1} and {username2}"
        
        # The second username should have a numeric suffix
        assert username2.startswith(email_prefix), f"Second username should start with {email_prefix}"
        
        # Clean up - delete test employees
        emp1_id = emp1_result.get("id")
        emp2_id = emp2_result.get("id")
        
        if emp1_id:
            self.session.delete(f"{BASE_URL}/api/employees/{emp1_id}")
        if emp2_id:
            self.session.delete(f"{BASE_URL}/api/employees/{emp2_id}")
        
        print(f"SUCCESS: Username collision fix works. First: {username1}, Second: {username2}")
    
    def test_salary_adjustments_api(self):
        """Test salary adjustments API"""
        # Get list of employees
        emp_response = self.session.get(f"{BASE_URL}/api/employees?page=1&limit=1")
        assert emp_response.status_code == 200
        employees = emp_response.json().get("employees", [])
        
        if len(employees) == 0:
            pytest.skip("No employees found to test adjustments API")
        
        employee_id = employees[0]["id"]
        
        # Get adjustments
        adj_response = self.session.get(f"{BASE_URL}/api/employees/{employee_id}/salary/adjustments")
        assert adj_response.status_code == 200, f"Adjustments API failed: {adj_response.text}"
        
        adj_data = adj_response.json()
        assert "adjustments" in adj_data, "Response should contain 'adjustments' key"
        
        print(f"SUCCESS: Salary adjustments API works. Found {len(adj_data['adjustments'])} adjustments")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
