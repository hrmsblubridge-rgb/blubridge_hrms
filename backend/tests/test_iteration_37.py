"""
Test Suite for Iteration 37 - Three-part fix:
1. Global Autocomplete - EmployeeAutocomplete component in all modules
2. Payroll sticky header - attendance view table header fixed during scroll
3. Inactive employee payroll fix - exclude inactive employees without inactive_date
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://employee-onboard-7.preview.emergentagent.com')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for HR admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "pass123"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping tests")

@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAutocompleteAPI:
    """Test the employee autocomplete API endpoint"""
    
    def test_autocomplete_by_name(self, auth_headers):
        """Test autocomplete search by employee name"""
        response = requests.get(
            f"{BASE_URL}/api/employees/autocomplete",
            headers=auth_headers,
            params={"q": "kath"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify response structure
        for emp in data:
            assert "id" in emp
            assert "full_name" in emp
            assert "official_email" in emp
            assert "emp_id" in emp
            assert "department" in emp
        # Verify search matches
        assert any("kath" in emp["full_name"].lower() for emp in data)
    
    def test_autocomplete_by_email(self, auth_headers):
        """Test autocomplete search by email"""
        response = requests.get(
            f"{BASE_URL}/api/employees/autocomplete",
            headers=auth_headers,
            params={"q": "blubridge"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should find employees with blubridge.com email
        if len(data) > 0:
            assert any("blubridge" in emp.get("official_email", "").lower() for emp in data)
    
    def test_autocomplete_by_emp_id(self, auth_headers):
        """Test autocomplete search by employee ID"""
        response = requests.get(
            f"{BASE_URL}/api/employees/autocomplete",
            headers=auth_headers,
            params={"q": "EMP00"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should find employees with EMP00 in their ID
        if len(data) > 0:
            assert any("EMP00" in emp.get("emp_id", "") for emp in data)
    
    def test_autocomplete_no_matches(self, auth_headers):
        """Test autocomplete with no matching results"""
        response = requests.get(
            f"{BASE_URL}/api/employees/autocomplete",
            headers=auth_headers,
            params={"q": "zzzznonexistent"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_autocomplete_empty_query(self, auth_headers):
        """Test autocomplete with empty query"""
        response = requests.get(
            f"{BASE_URL}/api/employees/autocomplete",
            headers=auth_headers,
            params={"q": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_autocomplete_max_results(self, auth_headers):
        """Test autocomplete returns max 10 results"""
        response = requests.get(
            f"{BASE_URL}/api/employees/autocomplete",
            headers=auth_headers,
            params={"q": "a"}  # Common letter, should match many
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10


class TestInactiveEmployeePayroll:
    """Test inactive employee handling in payroll"""
    
    def test_inactive_without_date_excluded(self, auth_headers):
        """Inactive employees WITHOUT inactive_date should be excluded from payroll"""
        # Get payroll for April 2026
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Get list of emp_ids in payroll
        payroll_emp_ids = [emp["emp_id"] for emp in data]
        
        # These employees are Inactive without inactive_date - should NOT be in payroll
        # EMP0043 - Test User One 1775805855
        # EMP0044 - Test User Two 1775805855
        # EMP0045 - Test User One 1775805876
        # EMP0046 - Test User Two 1775805876
        excluded_emp_ids = ["EMP0043", "EMP0044", "EMP0045", "EMP0046"]
        
        for emp_id in excluded_emp_ids:
            assert emp_id not in payroll_emp_ids, f"{emp_id} should be excluded from payroll (inactive without date)"
    
    def test_inactive_with_date_included(self, auth_headers):
        """Inactive employees WITH inactive_date should be included in payroll"""
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find TEST_Relieved_05658888 (EMP0056) - has inactive_date=2026-04-16
        test_emp = next((emp for emp in data if emp["emp_id"] == "EMP0056"), None)
        assert test_emp is not None, "TEST_Relieved_05658888 should be in payroll"
        assert test_emp["emp_name"] == "TEST_Relieved_05658888"
    
    def test_relieved_status_after_inactive_date(self, auth_headers):
        """Days after inactive_date should show R (Relieved) status"""
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find TEST_Relieved_05658888 (inactive_date=2026-04-16)
        test_emp = next((emp for emp in data if emp["emp_id"] == "EMP0056"), None)
        assert test_emp is not None
        
        attendance_details = test_emp.get("attendance_details", [])
        
        # Check days after Apr 16 have R status
        for detail in attendance_details:
            date_str = detail.get("date", "")
            # Parse day from date (format: DD-MM-YYYY)
            if date_str:
                day = int(date_str.split("-")[0])
                if day > 16:  # After Apr 16
                    assert detail.get("status") == "R", f"Day {day} should have R status, got {detail.get('status')}"
    
    def test_working_days_count_up_to_inactive_date(self, auth_headers):
        """Working days should only count up to inactive_date"""
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find TEST_Relieved_05658888 (inactive_date=2026-04-16)
        test_emp = next((emp for emp in data if emp["emp_id"] == "EMP0056"), None)
        assert test_emp is not None
        
        # Working days should be <= 16 (days 1-16 of April)
        # Excluding Sundays (5, 12) and holidays (3, 14)
        # Expected working days: 16 - 2 Sundays - 2 holidays = 12
        working_days = test_emp.get("working_days", 0)
        assert working_days <= 16, f"Working days should be <= 16, got {working_days}"
        assert working_days == 12, f"Expected 12 working days, got {working_days}"
    
    def test_weekoff_pay_up_to_inactive_date(self, auth_headers):
        """Weekoff pay should only count Sundays/holidays up to inactive_date"""
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find TEST_Relieved_05658888 (inactive_date=2026-04-16)
        test_emp = next((emp for emp in data if emp["emp_id"] == "EMP0056"), None)
        assert test_emp is not None
        
        # Weekoff pay should count Sundays (5, 12) and holidays (3, 14) up to Apr 16
        # Expected: 2 Sundays + 2 holidays = 4
        weekoff_pay = test_emp.get("weekoff_pay", 0)
        assert weekoff_pay == 4, f"Expected 4 weekoff pay, got {weekoff_pay}"


class TestActiveEmployeePayroll:
    """Test that active employees payroll is unchanged (no regression)"""
    
    def test_active_employee_in_payroll(self, auth_headers):
        """Active employees should appear in payroll"""
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have employees in payroll
        assert len(data) > 0
        
        # Find an active employee (e.g., Kathirvel S - EMP0002)
        kathirvel = next((emp for emp in data if emp["emp_id"] == "EMP0002"), None)
        assert kathirvel is not None, "Active employee Kathirvel S should be in payroll"
    
    def test_active_employee_full_month(self, auth_headers):
        """Active employees should have full month attendance details"""
        response = requests.get(
            f"{BASE_URL}/api/payroll",
            headers=auth_headers,
            params={"month": "2026-04"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find an active employee
        active_emp = next((emp for emp in data if emp["emp_id"] == "EMP0002"), None)
        assert active_emp is not None
        
        # Should have 30 days of attendance details (April has 30 days)
        attendance_details = active_emp.get("attendance_details", [])
        assert len(attendance_details) == 30, f"Expected 30 days, got {len(attendance_details)}"


class TestPayrollSummary:
    """Test payroll summary endpoint"""
    
    def test_payroll_summary(self, auth_headers):
        """Test payroll summary returns correct data"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/summary/2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify summary fields
        assert "total_employees" in data
        assert "total_salary" in data
        assert "total_deductions" in data
        assert "total_net_salary" in data
        assert "total_lop_days" in data
        
        # Values should be reasonable
        assert data["total_employees"] > 0
        assert data["total_salary"] >= 0
        assert data["total_net_salary"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
