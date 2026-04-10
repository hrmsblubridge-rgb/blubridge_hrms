"""
Test CTC Salary Calculation - Iteration 33
Tests that Special Allowance is the balancing figure and Fixed + Variable = Monthly CTC exactly
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCTCCalculation:
    """Test CTC salary calculation with Special Allowance as balancing figure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test with authentication"""
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
        
        # Use existing employee ID from context
        self.employee_id = "19eb4448-ff09-426f-95b7-211c6dab8b95"
    
    def test_ctc_660000_calculation(self):
        """Test CTC calculation for 6,60,000 annual CTC
        Expected: Fixed Comp (44000) + Variable (11000) = Monthly CTC (55000)
        """
        # Update salary with annual CTC of 660000
        response = self.session.put(
            f"{BASE_URL}/api/employees/{self.employee_id}/salary",
            json={"annual_ctc": 660000}
        )
        
        assert response.status_code == 200, f"Salary update failed: {response.text}"
        data = response.json()
        salary = data.get("salary", {})
        
        # Verify monthly CTC
        monthly_ctc = salary.get("monthly_ctc")
        assert monthly_ctc == 55000, f"Expected monthly_ctc=55000, got {monthly_ctc}"
        
        # Verify variable compensation (20% of CTC)
        variable_compensation = salary.get("variable_compensation")
        expected_variable = 55000 * 0.20  # 11000
        assert variable_compensation == expected_variable, f"Expected variable_compensation={expected_variable}, got {variable_compensation}"
        
        # Verify fixed compensation
        fixed_compensation = salary.get("fixed_compensation")
        expected_fixed = 55000 - 11000  # 44000
        assert fixed_compensation == expected_fixed, f"Expected fixed_compensation={expected_fixed}, got {fixed_compensation}"
        
        # CRITICAL: Verify Fixed + Variable = Monthly CTC exactly
        total = fixed_compensation + variable_compensation
        assert total == monthly_ctc, f"Fixed ({fixed_compensation}) + Variable ({variable_compensation}) = {total}, expected {monthly_ctc}"
        
        print(f"✓ CTC 660000: Fixed={fixed_compensation}, Variable={variable_compensation}, Total={total}, Monthly CTC={monthly_ctc}")
    
    def test_ctc_7920000_calculation(self):
        """Test CTC calculation for 79,20,000 annual CTC
        Expected: Fixed Comp (528000) + Variable (132000) = Monthly CTC (660000)
        """
        # Update salary with annual CTC of 7920000
        response = self.session.put(
            f"{BASE_URL}/api/employees/{self.employee_id}/salary",
            json={"annual_ctc": 7920000}
        )
        
        assert response.status_code == 200, f"Salary update failed: {response.text}"
        data = response.json()
        salary = data.get("salary", {})
        
        # Verify monthly CTC
        monthly_ctc = salary.get("monthly_ctc")
        assert monthly_ctc == 660000, f"Expected monthly_ctc=660000, got {monthly_ctc}"
        
        # Verify variable compensation (20% of CTC)
        variable_compensation = salary.get("variable_compensation")
        expected_variable = 660000 * 0.20  # 132000
        assert variable_compensation == expected_variable, f"Expected variable_compensation={expected_variable}, got {variable_compensation}"
        
        # Verify fixed compensation
        fixed_compensation = salary.get("fixed_compensation")
        expected_fixed = 660000 - 132000  # 528000
        assert fixed_compensation == expected_fixed, f"Expected fixed_compensation={expected_fixed}, got {fixed_compensation}"
        
        # CRITICAL: Verify Fixed + Variable = Monthly CTC exactly
        total = fixed_compensation + variable_compensation
        assert total == monthly_ctc, f"Fixed ({fixed_compensation}) + Variable ({variable_compensation}) = {total}, expected {monthly_ctc}"
        
        print(f"✓ CTC 7920000: Fixed={fixed_compensation}, Variable={variable_compensation}, Total={total}, Monthly CTC={monthly_ctc}")
    
    def test_salary_component_percentages(self):
        """Test that salary components follow the correct percentages:
        - Basic = 30% of CTC
        - HRA = 50% of Basic
        - Variable = 20% of CTC
        - PF = 12% of min(Basic, 15000)
        """
        # Use 660000 CTC for testing
        response = self.session.put(
            f"{BASE_URL}/api/employees/{self.employee_id}/salary",
            json={"annual_ctc": 660000}
        )
        
        assert response.status_code == 200, f"Salary update failed: {response.text}"
        data = response.json()
        salary = data.get("salary", {})
        
        monthly_ctc = salary.get("monthly_ctc")  # 55000
        
        # Basic = 30% of Monthly CTC
        basic = salary.get("basic")
        expected_basic = round(monthly_ctc * 0.30, 2)  # 16500
        assert basic == expected_basic, f"Expected basic={expected_basic}, got {basic}"
        
        # HRA = 50% of Basic
        hra = salary.get("hra")
        expected_hra = round(basic * 0.50, 2)  # 8250
        assert hra == expected_hra, f"Expected hra={expected_hra}, got {hra}"
        
        # Variable = 20% of Monthly CTC
        variable = salary.get("variable_compensation")
        expected_variable = round(monthly_ctc * 0.20, 2)  # 11000
        assert variable == expected_variable, f"Expected variable={expected_variable}, got {variable}"
        
        # PF = 12% of min(Basic, 15000)
        pf_basic = min(basic, 15000)
        pf_employee = salary.get("pf_employee")
        expected_pf = round(pf_basic * 0.12, 2)  # 1800 (12% of 15000)
        assert pf_employee == expected_pf, f"Expected pf_employee={expected_pf}, got {pf_employee}"
        
        print(f"✓ Component percentages verified: Basic={basic}, HRA={hra}, Variable={variable}, PF={pf_employee}")
    
    def test_special_allowance_is_balancing_figure(self):
        """Test that Special Allowance is calculated as the balancing figure
        Special Allowance = Fixed Target - Base Components - Known Allowances - Retirement Benefits
        """
        response = self.session.put(
            f"{BASE_URL}/api/employees/{self.employee_id}/salary",
            json={"annual_ctc": 660000}
        )
        
        assert response.status_code == 200, f"Salary update failed: {response.text}"
        data = response.json()
        salary = data.get("salary", {})
        
        monthly_ctc = salary.get("monthly_ctc")
        variable = salary.get("variable_compensation")
        fixed_target = monthly_ctc - variable
        
        # Get all components
        base_components = salary.get("base_components_total")
        basket_allowances = salary.get("basket_allowances_total")
        retirement_benefits = salary.get("retirement_benefits_total")
        special_allowance = salary.get("special_allowance")
        
        # Verify special allowance is not a fixed percentage (not 12% of CTC)
        # It should be the balancing figure
        fixed_12_percent = round(monthly_ctc * 0.12, 2)
        
        # Calculate what special allowance should be
        # Known allowances (without special allowance)
        basic = salary.get("basic")
        lta = salary.get("lta")
        phone_internet = salary.get("phone_internet")
        bonus = salary.get("bonus")
        stay_travel = salary.get("stay_travel")
        food_reimbursement = salary.get("food_reimbursement")
        medical_allowance = salary.get("medical_allowance", 0)
        conveyance = salary.get("conveyance", 0)
        
        known_allowances = lta + phone_internet + bonus + stay_travel + food_reimbursement + medical_allowance + conveyance
        
        expected_special = round(fixed_target - base_components - known_allowances - retirement_benefits, 2)
        
        # Special allowance should match the calculated balancing figure
        assert abs(special_allowance - expected_special) < 1, f"Special allowance mismatch: got {special_allowance}, expected {expected_special}"
        
        # Verify fixed compensation equals fixed target
        fixed_compensation = salary.get("fixed_compensation")
        assert abs(fixed_compensation - fixed_target) < 1, f"Fixed compensation ({fixed_compensation}) should equal fixed target ({fixed_target})"
        
        print(f"✓ Special Allowance is balancing figure: {special_allowance} (not fixed 12%: {fixed_12_percent})")
    
    def test_get_salary_after_update(self):
        """Test that GET salary returns the updated values"""
        # First update
        self.session.put(
            f"{BASE_URL}/api/employees/{self.employee_id}/salary",
            json={"annual_ctc": 660000}
        )
        
        # Then GET
        response = self.session.get(f"{BASE_URL}/api/employees/{self.employee_id}/salary")
        assert response.status_code == 200, f"GET salary failed: {response.text}"
        
        data = response.json()
        salary = data.get("salary", {})
        
        assert salary.get("annual_ctc") == 660000, f"Annual CTC mismatch"
        assert salary.get("monthly_ctc") == 55000, f"Monthly CTC mismatch"
        
        # Verify Fixed + Variable = Monthly CTC
        fixed = salary.get("fixed_compensation")
        variable = salary.get("variable_compensation")
        monthly = salary.get("monthly_ctc")
        
        assert fixed + variable == monthly, f"Fixed ({fixed}) + Variable ({variable}) != Monthly CTC ({monthly})"
        
        print(f"✓ GET salary returns correct values: Fixed={fixed}, Variable={variable}, Monthly CTC={monthly}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
