"""
Test Research Designation CTC-based Salary Calculation
Tests the new Research-specific salary formula vs default formula.

Key differences for Research employees:
- Variable = 20% CTC, Fixed = 80% CTC
- Basic = 30% CTC, HRA = 50% Basic
- PF fixed at 1800 (both employer and employee)
- NO Medical Allowance (0)
- NO Conveyance (0)
- B-percentage allocation: LTA=5.6%B, Bonus=9.9%B, Stay=30%B, Special=remainder
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test employee IDs from context
RESEARCH_EMPLOYEE_ID = "ffca7302-cd6a-48eb-b298-b9af257bb36d"  # Research designation
NON_RESEARCH_EMPLOYEE_ID = "caef948c-7db1-4914-8455-3cbfda2376fc"  # Front Office designation

TEST_CTC = 660000  # Annual CTC for testing


class TestResearchCTCCalculation:
    """Test Research designation CTC-based salary calculation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
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
        yield
    
    def test_research_employee_salary_calculation(self):
        """Test PUT /api/employees/{id}/salary with annual_ctc=660000 for Research designation"""
        # Update salary for Research employee
        response = self.session.put(
            f"{BASE_URL}/api/employees/{RESEARCH_EMPLOYEE_ID}/salary",
            json={"annual_ctc": TEST_CTC}
        )
        assert response.status_code == 200, f"Failed to update salary: {response.text}"
        
        salary = response.json().get("salary", {})
        
        # Verify CTC values
        assert salary.get("annual_ctc") == TEST_CTC, f"Annual CTC mismatch: {salary.get('annual_ctc')}"
        monthly_ctc = TEST_CTC / 12  # 55000
        assert salary.get("monthly_ctc") == monthly_ctc, f"Monthly CTC mismatch: {salary.get('monthly_ctc')}"
        
        # Verify Variable = 20% CTC
        expected_variable = round(monthly_ctc * 0.20, 2)  # 11000
        assert salary.get("variable_compensation") == expected_variable, \
            f"Variable mismatch: expected {expected_variable}, got {salary.get('variable_compensation')}"
        
        # Verify Fixed = 80% CTC
        expected_fixed = round(monthly_ctc * 0.80, 2)  # 44000
        assert salary.get("fixed_compensation") == expected_fixed, \
            f"Fixed mismatch: expected {expected_fixed}, got {salary.get('fixed_compensation')}"
        
        # Verify Basic = 30% CTC
        expected_basic = round(monthly_ctc * 0.30, 2)  # 16500
        assert salary.get("basic") == expected_basic, \
            f"Basic mismatch: expected {expected_basic}, got {salary.get('basic')}"
        
        # Verify HRA = 50% Basic
        expected_hra = round(expected_basic * 0.50, 2)  # 8250
        assert salary.get("hra") == expected_hra, \
            f"HRA mismatch: expected {expected_hra}, got {salary.get('hra')}"
        
        # Verify A (Base Components) = Basic + HRA
        expected_a = round(expected_basic + expected_hra, 2)  # 24750
        assert salary.get("base_components_total") == expected_a, \
            f"Base Components (A) mismatch: expected {expected_a}, got {salary.get('base_components_total')}"
        
        # Verify PF = 1800 (fixed for Research)
        assert salary.get("pf_employer") == 1800, f"PF Employer mismatch: {salary.get('pf_employer')}"
        assert salary.get("pf_employee") == 1800, f"PF Employee mismatch: {salary.get('pf_employee')}"
        
        # Verify NO Medical Allowance
        assert salary.get("medical_allowance") == 0, \
            f"Medical Allowance should be 0 for Research, got {salary.get('medical_allowance')}"
        
        # Verify NO Conveyance
        assert salary.get("conveyance") == 0, \
            f"Conveyance should be 0 for Research, got {salary.get('conveyance')}"
        
        print(f"✓ Research employee salary calculation verified:")
        print(f"  Basic: {salary.get('basic')}, HRA: {salary.get('hra')}, A: {salary.get('base_components_total')}")
        print(f"  Fixed: {salary.get('fixed_compensation')}, Variable: {salary.get('variable_compensation')}")
        print(f"  CTC: {salary.get('monthly_ctc')}, PF: {salary.get('pf_employer')}")
        print(f"  Medical: {salary.get('medical_allowance')}, Conveyance: {salary.get('conveyance')}")
    
    def test_research_salary_formula_integrity(self):
        """Test A+B+C = Fixed and Fixed+Variable = CTC for Research employees"""
        # Get salary for Research employee
        response = self.session.get(f"{BASE_URL}/api/employees/{RESEARCH_EMPLOYEE_ID}/salary")
        assert response.status_code == 200, f"Failed to get salary: {response.text}"
        
        salary = response.json().get("salary", {})
        
        # A + B + C = Fixed
        a = salary.get("base_components_total", 0)
        b = salary.get("basket_allowances_total", 0)
        c = salary.get("retirement_benefits_total", 0)
        fixed = salary.get("fixed_compensation", 0)
        
        calculated_fixed = round(a + b + c, 2)
        assert abs(calculated_fixed - fixed) < 1, \
            f"A+B+C ({calculated_fixed}) != Fixed ({fixed})"
        
        # Fixed + Variable = CTC
        variable = salary.get("variable_compensation", 0)
        monthly_ctc = salary.get("monthly_ctc", 0)
        
        calculated_ctc = round(fixed + variable, 2)
        assert abs(calculated_ctc - monthly_ctc) < 1, \
            f"Fixed+Variable ({calculated_ctc}) != CTC ({monthly_ctc})"
        
        print(f"✓ Research salary formula integrity verified:")
        print(f"  A={a} + B={b} + C={c} = {calculated_fixed} (Fixed={fixed})")
        print(f"  Fixed={fixed} + Variable={variable} = {calculated_ctc} (CTC={monthly_ctc})")
    
    def test_non_research_employee_salary_calculation(self):
        """Test non-Research employee (Front Office) with same CTC gets Medical=1250, Conveyance=1600"""
        # Update salary for non-Research employee
        response = self.session.put(
            f"{BASE_URL}/api/employees/{NON_RESEARCH_EMPLOYEE_ID}/salary",
            json={"annual_ctc": TEST_CTC}
        )
        assert response.status_code == 200, f"Failed to update salary: {response.text}"
        
        salary = response.json().get("salary", {})
        
        # Verify Medical Allowance = 1250 (default formula)
        assert salary.get("medical_allowance") == 1250, \
            f"Medical Allowance should be 1250 for non-Research, got {salary.get('medical_allowance')}"
        
        # Verify Conveyance = 1600 (default formula)
        assert salary.get("conveyance") == 1600, \
            f"Conveyance should be 1600 for non-Research, got {salary.get('conveyance')}"
        
        print(f"✓ Non-Research employee salary calculation verified:")
        print(f"  Medical: {salary.get('medical_allowance')}, Conveyance: {salary.get('conveyance')}")
    
    def test_designation_based_routing(self):
        """Test that designation-based routing works correctly"""
        # Get employee details to verify designations
        research_emp = self.session.get(f"{BASE_URL}/api/employees/{RESEARCH_EMPLOYEE_ID}")
        non_research_emp = self.session.get(f"{BASE_URL}/api/employees/{NON_RESEARCH_EMPLOYEE_ID}")
        
        assert research_emp.status_code == 200
        assert non_research_emp.status_code == 200
        
        research_designation = research_emp.json().get("designation", "")
        non_research_designation = non_research_emp.json().get("designation", "")
        
        print(f"Research employee designation: {research_designation}")
        print(f"Non-Research employee designation: {non_research_designation}")
        
        # Verify Research designation contains 'research' (case-insensitive)
        assert "research" in research_designation.lower(), \
            f"Research employee should have 'research' in designation, got: {research_designation}"
        
        # Verify non-Research designation does NOT contain 'research'
        assert "research" not in non_research_designation.lower(), \
            f"Non-Research employee should NOT have 'research' in designation, got: {non_research_designation}"
        
        print(f"✓ Designation-based routing verified")
    
    def test_research_b_percentage_allocation(self):
        """Test B-percentage allocation for Research: LTA=5.6%B, Bonus=9.9%B, Stay=30%B"""
        response = self.session.get(f"{BASE_URL}/api/employees/{RESEARCH_EMPLOYEE_ID}/salary")
        assert response.status_code == 200
        
        salary = response.json().get("salary", {})
        basket_total = salary.get("basket_allowances_total", 0)
        
        if basket_total > 0:
            # Verify LTA = 5.6% of B
            expected_lta = round(basket_total * 0.056, 2)
            actual_lta = salary.get("lta", 0)
            assert abs(actual_lta - expected_lta) < 1, \
                f"LTA mismatch: expected {expected_lta}, got {actual_lta}"
            
            # Verify Bonus = 9.9% of B
            expected_bonus = round(basket_total * 0.099, 2)
            actual_bonus = salary.get("bonus", 0)
            assert abs(actual_bonus - expected_bonus) < 1, \
                f"Bonus mismatch: expected {expected_bonus}, got {actual_bonus}"
            
            # Verify Stay = 30% of B
            expected_stay = round(basket_total * 0.30, 2)
            actual_stay = salary.get("stay_travel", 0)
            assert abs(actual_stay - expected_stay) < 1, \
                f"Stay Travel mismatch: expected {expected_stay}, got {actual_stay}"
            
            # Verify Phone = 1100 (fixed)
            assert salary.get("phone_internet") == 1100, \
                f"Phone mismatch: expected 1100, got {salary.get('phone_internet')}"
            
            # Verify Food = 1210 (fixed)
            assert salary.get("food_reimbursement") == 1210, \
                f"Food mismatch: expected 1210, got {salary.get('food_reimbursement')}"
            
            print(f"✓ B-percentage allocation verified:")
            print(f"  B Total: {basket_total}")
            print(f"  LTA (5.6%B): {actual_lta}, Bonus (9.9%B): {actual_bonus}, Stay (30%B): {actual_stay}")
            print(f"  Phone: {salary.get('phone_internet')}, Food: {salary.get('food_reimbursement')}")
            print(f"  Special Allowance (remainder): {salary.get('special_allowance')}")


class TestResearchDesignationVariants:
    """Test that various Research designation variants use Research formula"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as HR admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "pass123"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_get_salary_calculator_routing(self):
        """Verify designation routing logic by checking employee designations"""
        # Get all employees to check designations
        response = self.session.get(f"{BASE_URL}/api/employees")
        assert response.status_code == 200
        
        data = response.json()
        # Handle both list and dict response formats
        employees = data if isinstance(data, list) else data.get("employees", data.get("data", []))
        
        research_designations = []
        non_research_designations = []
        
        for emp in employees:
            if isinstance(emp, dict):
                designation = emp.get("designation", "")
                if "research" in designation.lower():
                    research_designations.append(designation)
                else:
                    non_research_designations.append(designation)
        
        print(f"Research designations found: {set(research_designations)}")
        print(f"Non-Research designations found: {set(non_research_designations)}")
        
        # Verify at least one Research employee exists
        assert len(research_designations) > 0, "No Research designation employees found"
        
        print(f"✓ Designation routing test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
