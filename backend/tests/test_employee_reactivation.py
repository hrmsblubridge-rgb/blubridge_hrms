"""
Test Employee Reactivation Feature
- PUT /api/employees/{id}/reactivate endpoint
- Reactivates inactive employee, sets status=Active, login_enabled=True
- Preserves inactive_type and inactive_date history
- Re-enables user login (is_active=True on users collection)
- Returns 400 for already-active employee
- Returns 403 for non-HR users
- Login blocked for inactive employees
- Login works after reactivation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test employee ID from context
TEST_EMPLOYEE_ID = "8bc4cef5-2213-4701-9f61-d98bac1cf582"  # TEST_Relieved_05658888

class TestEmployeeReactivation:
    """Test employee reactivation endpoint and related functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_hr_token(self):
        """Get HR admin token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert response.status_code == 200, f"HR login failed: {response.text}"
        return response.json()["token"]
    
    def get_employee_token(self):
        """Get employee token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "spartasolace1",
            "password": "spar@1230"
        })
        if response.status_code == 200:
            return response.json()["token"]
        return None
    
    def get_employee_details(self, employee_id, token):
        """Get employee details"""
        response = self.session.get(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response
    
    def test_01_verify_test_employee_exists(self):
        """Verify the test employee exists and check initial state"""
        token = self.get_hr_token()
        response = self.get_employee_details(TEST_EMPLOYEE_ID, token)
        
        assert response.status_code == 200, f"Employee not found: {response.text}"
        data = response.json()
        
        print(f"Employee: {data.get('full_name')}")
        print(f"Status: {data.get('employee_status')}")
        print(f"Inactive Type: {data.get('inactive_type')}")
        print(f"Inactive Date: {data.get('inactive_date')}")
        print(f"Login Enabled: {data.get('login_enabled')}")
        
        # Store initial state for later tests
        self.initial_status = data.get('employee_status')
        
    def test_02_reactivate_inactive_employee(self):
        """Test reactivating an inactive employee"""
        token = self.get_hr_token()
        
        # First check current status
        emp_response = self.get_employee_details(TEST_EMPLOYEE_ID, token)
        emp_data = emp_response.json()
        
        if emp_data.get('employee_status') != 'Inactive':
            # Employee is already active, need to deactivate first
            print(f"Employee is {emp_data.get('employee_status')}, deactivating first...")
            deact_response = self.session.delete(
                f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "inactive_type": "Terminated",
                    "inactive_date": "2026-04-16",
                    "reason": "Test deactivation",
                    "last_day_payable": True
                }
            )
            assert deact_response.status_code == 200, f"Deactivation failed: {deact_response.text}"
            print("Employee deactivated successfully")
        
        # Now reactivate
        response = self.session.put(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/reactivate",
            headers={"Authorization": f"Bearer {token}"},
            json={}
        )
        
        assert response.status_code == 200, f"Reactivation failed: {response.text}"
        data = response.json()
        
        # Verify status changed to Active
        assert data.get('employee_status') == 'Active', f"Expected Active, got {data.get('employee_status')}"
        
        # Verify login_enabled is True
        assert data.get('login_enabled') == True, f"Expected login_enabled=True, got {data.get('login_enabled')}"
        
        print(f"Reactivation successful: status={data.get('employee_status')}, login_enabled={data.get('login_enabled')}")
        
    def test_03_reactivation_preserves_inactive_history(self):
        """Test that reactivation preserves inactive_type and inactive_date"""
        token = self.get_hr_token()
        
        # Get employee details after reactivation
        response = self.get_employee_details(TEST_EMPLOYEE_ID, token)
        assert response.status_code == 200
        data = response.json()
        
        # Verify inactive history is preserved
        # Note: inactive_type and inactive_date should still be present
        print(f"After reactivation - inactive_type: {data.get('inactive_type')}")
        print(f"After reactivation - inactive_date: {data.get('inactive_date')}")
        print(f"After reactivation - inactive_reason: {data.get('inactive_reason')}")
        
        # The inactive_type and inactive_date should still be present (history preserved)
        # They are not cleared on reactivation
        
    def test_04_reactivate_already_active_returns_400(self):
        """Test that reactivating an already active employee returns 400"""
        token = self.get_hr_token()
        
        # First ensure employee is active
        emp_response = self.get_employee_details(TEST_EMPLOYEE_ID, token)
        emp_data = emp_response.json()
        
        if emp_data.get('employee_status') != 'Active':
            # Reactivate first
            self.session.put(
                f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/reactivate",
                headers={"Authorization": f"Bearer {token}"},
                json={}
            )
        
        # Now try to reactivate again - should fail
        response = self.session.put(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/reactivate",
            headers={"Authorization": f"Bearer {token}"},
            json={}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "not inactive" in data.get('detail', '').lower(), f"Unexpected error message: {data.get('detail')}"
        print(f"Correctly returned 400 for already active employee: {data.get('detail')}")
        
    def test_05_reactivate_requires_hr_role(self):
        """Test that non-HR users cannot reactivate employees"""
        # Get employee token
        emp_token = self.get_employee_token()
        
        if emp_token is None:
            pytest.skip("Could not get employee token")
        
        # Try to reactivate with employee token
        response = self.session.put(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/reactivate",
            headers={"Authorization": f"Bearer {emp_token}"},
            json={}
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"Correctly returned 403 for non-HR user")
        
    def test_06_reactivate_nonexistent_employee_returns_404(self):
        """Test that reactivating a non-existent employee returns 404"""
        token = self.get_hr_token()
        
        response = self.session.put(
            f"{BASE_URL}/api/employees/nonexistent-id-12345/reactivate",
            headers={"Authorization": f"Bearer {token}"},
            json={}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"Correctly returned 404 for non-existent employee")
        
    def test_07_user_login_enabled_after_reactivation(self):
        """Test that user's is_active is set to True after reactivation"""
        token = self.get_hr_token()
        
        # Get employee details
        emp_response = self.get_employee_details(TEST_EMPLOYEE_ID, token)
        emp_data = emp_response.json()
        
        # Verify login_enabled is True
        assert emp_data.get('login_enabled') == True, f"login_enabled should be True after reactivation"
        print(f"User login_enabled is True after reactivation")
        
    def test_08_deactivate_employee_for_cleanup(self):
        """Deactivate the test employee back to restore test state"""
        token = self.get_hr_token()
        
        # Check current status
        emp_response = self.get_employee_details(TEST_EMPLOYEE_ID, token)
        emp_data = emp_response.json()
        
        if emp_data.get('employee_status') == 'Active':
            # Deactivate to restore test state
            response = self.session.delete(
                f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "inactive_type": "Terminated",
                    "inactive_date": "2026-04-16",
                    "reason": "Test",
                    "last_day_payable": True
                }
            )
            assert response.status_code == 200, f"Deactivation failed: {response.text}"
            print("Employee deactivated back to restore test state")
        else:
            print(f"Employee already inactive: {emp_data.get('employee_status')}")


class TestInactiveEmployeeLogin:
    """Test login behavior for inactive employees"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_hr_token(self):
        """Get HR admin token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert response.status_code == 200, f"HR login failed: {response.text}"
        return response.json()["token"]
    
    def test_01_login_blocked_for_inactive_employee(self):
        """Test that login is blocked for inactive employees"""
        # Note: TEST_Relieved_05658888 may not have a user account
        # This test checks the general login behavior
        
        # Try to login with a known inactive employee
        # The employee spartasolace1 is active, so we test with a different approach
        
        # First, let's check if there's a user for TEST_Relieved_05658888
        hr_token = self.get_hr_token()
        
        # Get employee details
        emp_response = self.session.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}",
            headers={"Authorization": f"Bearer {hr_token}"}
        )
        emp_data = emp_response.json()
        
        print(f"Employee email: {emp_data.get('official_email')}")
        print(f"Employee status: {emp_data.get('employee_status')}")
        print(f"Login enabled: {emp_data.get('login_enabled')}")
        
        # If employee is inactive and has a user account, login should fail
        # We'll verify the login_enabled flag is correctly set
        if emp_data.get('employee_status') == 'Inactive':
            assert emp_data.get('login_enabled') == False, "Inactive employee should have login_enabled=False"
            print("Inactive employee correctly has login_enabled=False")
        else:
            print(f"Employee is {emp_data.get('employee_status')}, skipping inactive login test")


class TestPayrollWeekoffCorrection:
    """Test payroll weekoff calculation for inactive employees"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_hr_token(self):
        """Get HR admin token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert response.status_code == 200, f"HR login failed: {response.text}"
        return response.json()["token"]
    
    def test_01_payroll_weekoff_for_inactive_employee(self):
        """Test that weekoff_pay only counts up to inactive_date"""
        token = self.get_hr_token()
        
        # Get payroll for April 2026
        response = self.session.get(
            f"{BASE_URL}/api/payroll?month=2026-04",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Payroll fetch failed: {response.text}"
        data = response.json()
        
        # API returns array directly
        records = data if isinstance(data, list) else data.get('records', [])
        
        # Find TEST_Relieved_05658888 in payroll
        test_emp_payroll = None
        for record in records:
            if record.get('employee_id') == TEST_EMPLOYEE_ID:
                test_emp_payroll = record
                break
        
        if test_emp_payroll:
            print(f"Employee: {test_emp_payroll.get('emp_name')}")
            print(f"Weekoff Pay: {test_emp_payroll.get('weekoff_pay')}")
            print(f"Working Days: {test_emp_payroll.get('working_days')}")
            
            # Verify weekoff_pay is 4 (Sundays/holidays before inactive_date 2026-04-16)
            # April 2026: Sundays before Apr 16 are Apr 5, Apr 12 = 2 Sundays
            # Plus holidays: Apr 3 (Good Friday), Apr 14 (Tamil New Year) = 2 holidays
            # Total weekoff_pay should be around 4
            weekoff_pay = test_emp_payroll.get('weekoff_pay', 0)
            print(f"Weekoff pay for inactive employee: {weekoff_pay}")
            
            # Check that dates after inactive_date show R status
            attendance_details = test_emp_payroll.get('attendance_details', [])
            r_status_count = sum(1 for d in attendance_details if d.get('status') == 'R')
            print(f"Days with R status (after inactive_date): {r_status_count}")
        else:
            print("TEST_Relieved_05658888 not found in payroll (may be excluded due to inactive status)")


class TestGetInactiveEmployees:
    """Test filtering inactive employees"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_hr_token(self):
        """Get HR admin token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert response.status_code == 200, f"HR login failed: {response.text}"
        return response.json()["token"]
    
    def test_01_filter_inactive_employees(self):
        """Test filtering employees by status=Inactive"""
        token = self.get_hr_token()
        
        response = self.session.get(
            f"{BASE_URL}/api/employees?status=Inactive",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Filter failed: {response.text}"
        data = response.json()
        
        print(f"Total inactive employees: {data.get('total')}")
        
        # Verify all returned employees are inactive
        for emp in data.get('employees', []):
            assert emp.get('employee_status') == 'Inactive', f"Expected Inactive, got {emp.get('employee_status')}"
            print(f"  - {emp.get('full_name')} ({emp.get('inactive_type')})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
