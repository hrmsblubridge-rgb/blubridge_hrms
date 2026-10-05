"""
Test Salary Breakup Feature
Tests salary structure CRUD, adjustments, and payslip generation
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known employee ID for testemployee
TEST_EMPLOYEE_ID = "6ae79e19-2a3f-41ff-a72d-d00e0256ca93"

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]

@pytest.fixture(scope="module")
def employee_token():
    """Get employee auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "testemployee",
        "password": "test@3210"
    })
    assert response.status_code == 200, f"Employee login failed: {response.text}"
    return response.json()["token"]

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Admin auth headers"""
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture(scope="module")
def employee_headers(employee_token):
    """Employee auth headers"""
    return {"Authorization": f"Bearer {employee_token}"}


class TestSalaryStructure:
    """Tests for GET/PUT /api/employees/{id}/salary"""
    
    def test_get_employee_salary_admin(self, admin_headers):
        """Admin can get employee salary structure"""
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "employee_id" in data
        assert "salary" in data
        
        # If salary exists, verify components
        if data["salary"]:
            salary = data["salary"]
            assert "annual_ctc" in salary
            assert "monthly_ctc" in salary
            assert "basic" in salary
            assert "hra" in salary
            assert "da" in salary
            assert "conveyance" in salary
            assert "medical_allowance" in salary
            assert "special_allowance" in salary
            assert "gross_salary" in salary
            assert "pf_employee" in salary
            assert "professional_tax" in salary
            assert "net_salary" in salary
            print(f"Salary structure found: CTC={salary['annual_ctc']}, Net={salary['net_salary']}")
    
    def test_update_employee_salary_ctc(self, admin_headers):
        """Admin can update CTC and auto-calculate breakup"""
        new_ctc = 700000
        response = requests.put(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary",
            headers=admin_headers,
            json={"annual_ctc": new_ctc}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "message" in data
        assert data["message"] == "Salary structure updated"
        assert "salary" in data
        
        salary = data["salary"]
        assert salary["annual_ctc"] == new_ctc
        assert salary["monthly_ctc"] == round(new_ctc / 12, 2)
        
        # Verify Indian payroll standard breakdown
        # Basic should be 40% of CTC
        expected_basic = round(new_ctc * 0.4 / 12, 2)
        assert salary["basic"] == expected_basic, f"Basic mismatch: expected {expected_basic}, got {salary['basic']}"
        
        # HRA should be 50% of Basic
        expected_hra = round(expected_basic * 0.5, 2)
        assert salary["hra"] == expected_hra, f"HRA mismatch: expected {expected_hra}, got {salary['hra']}"
        
        print(f"CTC updated to {new_ctc}. Basic={salary['basic']}, HRA={salary['hra']}, Net={salary['net_salary']}")
    
    def test_update_salary_ctc_back_to_original(self, admin_headers):
        """Reset salary back to 600000"""
        original_ctc = 600000
        response = requests.put(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary",
            headers=admin_headers,
            json={"annual_ctc": original_ctc}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["salary"]["annual_ctc"] == original_ctc
        print(f"CTC reset to {original_ctc}")
    
    def test_get_salary_unauthorized(self):
        """Unauthenticated requests should fail"""
        response = requests.get(f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary")
        assert response.status_code in [401, 403]


class TestSalaryAdjustments:
    """Tests for salary adjustments CRUD"""
    
    created_adjustment_id = None
    
    def test_list_adjustments(self, admin_headers):
        """List adjustments for employee"""
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "employee_id" in data
        assert "adjustments" in data
        assert isinstance(data["adjustments"], list)
        print(f"Found {len(data['adjustments'])} existing adjustments")
    
    def test_create_bonus_adjustment_one_time(self, admin_headers):
        """Create one-time bonus adjustment"""
        current_month = datetime.now().strftime("%Y-%m")
        response = requests.post(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=admin_headers,
            json={
                "adjustment_type": "bonus",
                "description": "TEST_Performance Bonus Q4",
                "amount": 15000,
                "frequency": "one_time",
                "applicable_month": current_month
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert data["message"] == "Adjustment created"
        assert "adjustment" in data
        
        adj = data["adjustment"]
        assert adj["adjustment_type"] == "bonus"
        assert adj["description"] == "TEST_Performance Bonus Q4"
        assert adj["amount"] == 15000
        assert adj["frequency"] == "one_time"
        assert adj["category"] == "earning"
        
        TestSalaryAdjustments.created_adjustment_id = adj["id"]
        print(f"Created bonus adjustment ID: {adj['id']}")
    
    def test_create_deduction_adjustment(self, admin_headers):
        """Create deduction adjustment"""
        current_month = datetime.now().strftime("%Y-%m")
        response = requests.post(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=admin_headers,
            json={
                "adjustment_type": "advance_recovery",
                "description": "TEST_Salary Advance Recovery",
                "amount": 5000,
                "frequency": "one_time",
                "applicable_month": current_month
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        adj = data["adjustment"]
        assert adj["category"] == "deduction"
        print(f"Created deduction adjustment ID: {adj['id']}")
        
        # Delete this adjustment
        del_response = requests.delete(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments/{adj['id']}",
            headers=admin_headers
        )
        assert del_response.status_code == 200
    
    def test_create_recurring_adjustment(self, admin_headers):
        """Create recurring reimbursement"""
        current_month = datetime.now().strftime("%Y-%m")
        response = requests.post(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=admin_headers,
            json={
                "adjustment_type": "reimbursement",
                "description": "TEST_Monthly Fuel Reimbursement",
                "amount": 3000,
                "frequency": "recurring",
                "start_month": current_month,
                "end_month": None
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        adj = data["adjustment"]
        assert adj["frequency"] == "recurring"
        assert adj["is_active"] == True
        print(f"Created recurring adjustment ID: {adj['id']}")
        
        # Cleanup
        del_response = requests.delete(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments/{adj['id']}",
            headers=admin_headers
        )
        assert del_response.status_code == 200
    
    def test_delete_adjustment(self, admin_headers):
        """Delete adjustment"""
        if not TestSalaryAdjustments.created_adjustment_id:
            pytest.skip("No adjustment to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments/{TestSalaryAdjustments.created_adjustment_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["message"] == "Adjustment deleted"
        print(f"Deleted adjustment {TestSalaryAdjustments.created_adjustment_id}")
    
    def test_delete_nonexistent_adjustment(self, admin_headers):
        """Deleting non-existent adjustment returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments/nonexistent-id-123",
            headers=admin_headers
        )
        assert response.status_code == 404


class TestPayslip:
    """Tests for payslip generation"""
    
    def test_get_payslip_current_month(self, admin_headers):
        """Get payslip for current month"""
        current_month = datetime.now().strftime("%Y-%m")
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/payslip/{current_month}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify payslip structure
        assert "month" in data
        assert "employee_name" in data
        assert "emp_id" in data
        assert "department" in data
        assert "designation" in data
        assert "company_name" in data
        
        # Earnings components
        assert "basic" in data
        assert "hra" in data
        assert "da" in data
        assert "conveyance" in data
        assert "medical_allowance" in data
        assert "special_allowance" in data
        assert "gross_earnings" in data
        
        # Deductions components
        assert "pf_employee" in data
        assert "professional_tax" in data
        assert "total_deductions" in data
        
        # Net pay
        assert "net_pay" in data
        
        print(f"Payslip for {current_month}: Gross={data['gross_earnings']}, Deductions={data['total_deductions']}, Net={data['net_pay']}")
    
    def test_payslip_with_adjustments(self, admin_headers):
        """Payslip reflects adjustments"""
        current_month = datetime.now().strftime("%Y-%m")
        
        # Create a bonus adjustment
        adj_response = requests.post(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=admin_headers,
            json={
                "adjustment_type": "bonus",
                "description": "TEST_Payslip Test Bonus",
                "amount": 10000,
                "frequency": "one_time",
                "applicable_month": current_month
            }
        )
        assert adj_response.status_code == 200
        adj_id = adj_response.json()["adjustment"]["id"]
        
        # Get payslip
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/payslip/{current_month}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify adjustment is included
        assert "earnings_adjustments" in data
        assert len(data["earnings_adjustments"]) > 0
        assert data["total_earnings_adjustment"] >= 10000
        
        print(f"Payslip includes {len(data['earnings_adjustments'])} earnings adjustments, total: {data['total_earnings_adjustment']}")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments/{adj_id}",
            headers=admin_headers
        )
    
    def test_payslip_invalid_month_format(self, admin_headers):
        """Invalid month format returns error"""
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/payslip/invalid-month",
            headers=admin_headers
        )
        assert response.status_code == 400
    
    def test_payslip_nonexistent_employee(self, admin_headers):
        """Payslip for non-existent employee returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/employees/nonexistent-emp-id/payslip/2026-01",
            headers=admin_headers
        )
        assert response.status_code == 404


class TestEmployeeSalaryView:
    """Tests for employee viewing their own salary"""
    
    def test_employee_get_own_salary(self, employee_headers):
        """Employee can get their own salary"""
        response = requests.get(
            f"{BASE_URL}/api/employee-profile/salary",
            headers=employee_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "salary" in data
        assert "adjustments" in data
        
        if data["salary"]:
            salary = data["salary"]
            assert "annual_ctc" in salary
            assert "net_salary" in salary
            print(f"Employee salary: CTC={salary['annual_ctc']}, Net={salary['net_salary']}")
        else:
            print("Employee has no salary configured")
    
    def test_employee_cannot_update_salary(self, employee_headers):
        """Employee cannot update their own salary"""
        response = requests.put(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary",
            headers=employee_headers,
            json={"annual_ctc": 1000000}
        )
        # Should be 403 forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_employee_cannot_create_adjustment(self, employee_headers):
        """Employee cannot create salary adjustment"""
        response = requests.post(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=employee_headers,
            json={
                "adjustment_type": "bonus",
                "description": "Self-assigned bonus",
                "amount": 100000,
                "frequency": "one_time",
                "applicable_month": "2026-01"
            }
        )
        # Should be 403 forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"


class TestSalaryCalculations:
    """Tests for salary calculation logic"""
    
    def test_salary_components_add_up(self, admin_headers):
        """Verify earnings and deductions add up correctly"""
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("salary"):
            pytest.skip("No salary configured")
        
        salary = data["salary"]
        
        # Calculate expected gross
        earnings = (
            salary["basic"] +
            salary["hra"] +
            salary["da"] +
            salary["conveyance"] +
            salary["medical_allowance"] +
            salary["special_allowance"] +
            salary.get("other_allowances", 0)
        )
        
        # Verify gross matches
        assert abs(salary["gross_salary"] - earnings) < 1, f"Gross mismatch: {salary['gross_salary']} vs calculated {earnings}"
        
        # Calculate expected deductions
        deductions = (
            salary["pf_employee"] +
            salary.get("esi_employee", 0) +
            salary["professional_tax"] +
            salary.get("tds", 0) +
            salary.get("other_deductions", 0)
        )
        
        # Verify total deductions
        assert abs(salary["total_deductions"] - deductions) < 1, f"Deductions mismatch: {salary['total_deductions']} vs calculated {deductions}"
        
        # Verify net = gross - deductions
        expected_net = salary["gross_salary"] - salary["total_deductions"]
        assert abs(salary["net_salary"] - expected_net) < 1, f"Net mismatch: {salary['net_salary']} vs calculated {expected_net}"
        
        print(f"Salary math verified: Gross={earnings}, Deductions={deductions}, Net={expected_net}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_adjustments(self, admin_headers):
        """Remove any TEST_ prefixed adjustments"""
        response = requests.get(
            f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments",
            headers=admin_headers
        )
        if response.status_code != 200:
            return
        
        adjustments = response.json().get("adjustments", [])
        deleted = 0
        for adj in adjustments:
            if adj.get("description", "").startswith("TEST_"):
                del_response = requests.delete(
                    f"{BASE_URL}/api/employees/{TEST_EMPLOYEE_ID}/salary/adjustments/{adj['id']}",
                    headers=admin_headers
                )
                if del_response.status_code == 200:
                    deleted += 1
        
        print(f"Cleaned up {deleted} test adjustments")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
