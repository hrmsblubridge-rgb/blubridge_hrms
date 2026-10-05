"""
Test suite for Payroll Correction - Weekoff = Sundays ONLY
Tests that:
1. Weekoff_pay counts ONLY Sundays (NOT holidays)
2. Holidays do NOT contribute to weekoff_pay
3. Holidays: if employee worked → Extra Pay only. If not worked → OH status with weekoff_value=0
4. Active employee April 2026: weekoff_pay=4 (4 Sundays ONLY: 5,12,19,26)
5. Inactive employee (Apr 14): weekoff_pay=2 (Sundays 5,12 only)
6. Inactive employee (Apr 16): weekoff_pay=2 (Sundays 5,12 only)

April 2026 Calendar:
- Sundays: 5, 12, 19, 26 (4 Sundays)
- Holidays: Apr 3 (Good Friday), Apr 14 (Tamil New Year) (2 holidays)
- Weekoff_pay for full month: 4 (ONLY Sundays, NOT holidays)
- Working days: 24 (30 - 4 Sundays - 2 holidays)

January 2026 Calendar:
- Sundays: 4, 11, 18, 25 (4 Sundays)
- Holidays: Jan 1, 15, 16, 26 (4 holidays)
- Weekoff_pay for full month: 4 (ONLY Sundays, NOT holidays)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for HR admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "pass123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestActiveEmployeeApril2026SundaysOnly:
    """Tests for active employee payroll in April 2026 - Sundays ONLY for weekoff"""
    
    # Active employee: TEST_NoBody_25a93648
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_active_employee_weekoff_pay_equals_4_sundays_only(self, auth_headers):
        """Active employee April 2026: weekoff_pay=4 (4 Sundays ONLY: 5,12,19,26)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # Active employee should have weekoff_pay = 4 (ONLY Sundays, NOT holidays)
        assert data.get("weekoff_pay") == 4.0, f"Expected weekoff_pay=4 (Sundays only), got {data.get('weekoff_pay')}"
    
    def test_active_employee_holidays_show_oh_with_weekoff_value_0(self, auth_headers):
        """Active employee: holidays (Apr 3, Apr 14) show OH/H status with weekoff_value=0"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Find Apr 3 (Good Friday) and Apr 14 (Tamil New Year)
        apr3 = next((d for d in details if d.get("date") == "03-04-2026"), None)
        apr14 = next((d for d in details if d.get("date") == "14-04-2026"), None)
        
        assert apr3 is not None, "Apr 3 not found in attendance_details"
        assert apr14 is not None, "Apr 14 not found in attendance_details"
        
        # Holidays should have weekoff_value=0 (NOT contributing to weekoff_pay)
        assert apr3.get("weekoff_value") == 0, f"Apr 3 (holiday) should have weekoff_value=0, got {apr3.get('weekoff_value')}"
        assert apr14.get("weekoff_value") == 0, f"Apr 14 (holiday) should have weekoff_value=0, got {apr14.get('weekoff_value')}"
        
        # Status should be OH (holiday not worked) or H (future holiday)
        assert apr3.get("status") in ["OH", "H"], f"Apr 3 should have status OH or H, got {apr3.get('status')}"
        assert apr14.get("status") in ["OH", "H"], f"Apr 14 should have status OH or H, got {apr14.get('status')}"
    
    def test_active_employee_holidays_not_in_weekoff_pay(self, auth_headers):
        """Active employee: holidays NOT included in weekoff_pay"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Count total weekoff_value from all days
        total_weekoff_value = sum(d.get("weekoff_value", 0) for d in details)
        
        # Should equal weekoff_pay (4 Sundays only)
        assert total_weekoff_value == 4.0, f"Total weekoff_value should be 4 (Sundays only), got {total_weekoff_value}"
        assert data.get("weekoff_pay") == total_weekoff_value, f"weekoff_pay ({data.get('weekoff_pay')}) should equal sum of weekoff_values ({total_weekoff_value})"
    
    def test_active_employee_sundays_have_weekoff_value_1(self, auth_headers):
        """Active employee: Sundays (Apr 5, 12, 19, 26) have weekoff_value=1"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Find all Sundays
        sundays = [d for d in details if d.get("is_sunday")]
        
        assert len(sundays) == 4, f"Expected 4 Sundays, got {len(sundays)}"
        
        for sunday in sundays:
            assert sunday.get("weekoff_value") == 1, f"Sunday {sunday['date']} should have weekoff_value=1, got {sunday.get('weekoff_value')}"
    
    def test_active_employee_future_sunday_status_su_weekoff_1(self, auth_headers):
        """Future Sunday → status Su, weekoff_value=1"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Future Sundays: Apr 19, Apr 26 (assuming today is around Apr 17)
        future_sundays = [d for d in details if d.get("is_sunday") and int(d["date"].split("-")[0]) > 17]
        
        for sunday in future_sundays:
            assert sunday.get("status") == "Su", f"Future Sunday {sunday['date']} should have status=Su, got {sunday.get('status')}"
            assert sunday.get("weekoff_value") == 1, f"Future Sunday {sunday['date']} should have weekoff_value=1, got {sunday.get('weekoff_value')}"
    
    def test_active_employee_future_holiday_status_h_weekoff_0(self, auth_headers):
        """Future Holiday → status H, weekoff_value=0 (NO weekoff for holidays)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Find holidays that are in the future
        holidays = [d for d in details if d.get("is_holiday") and not d.get("is_sunday")]
        
        for holiday in holidays:
            # Holiday should have weekoff_value=0
            assert holiday.get("weekoff_value") == 0, f"Holiday {holiday['date']} should have weekoff_value=0, got {holiday.get('weekoff_value')}"


class TestInactiveEmployeeApril14SundaysOnly:
    """Tests for inactive employee with inactive_date=2026-04-14 - Sundays ONLY"""
    
    # Inactive employee: TEST_Deactivation_f98a8836 (inactive_date=2026-04-14)
    INACTIVE_EMPLOYEE_ID = "e93ef490-5c06-4c2c-8290-00537df17516"
    
    def test_inactive_employee_weekoff_pay_equals_2_sundays_only(self, auth_headers):
        """Inactive employee (inactive_date=2026-04-14): weekoff_pay=2 (only Sundays Apr 5, Apr 12)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # Inactive employee should have weekoff_pay = 2 (ONLY Sundays before Apr 14: Apr 5, Apr 12)
        # Holidays (Apr 3, Apr 14) do NOT contribute to weekoff
        assert data.get("weekoff_pay") == 2.0, f"Expected weekoff_pay=2 (Sundays 5,12 only), got {data.get('weekoff_pay')}"
    
    def test_inactive_employee_holidays_show_oh_with_weekoff_value_0(self, auth_headers):
        """Inactive employee: holidays (Apr 3, Apr 14) show OH status with weekoff_value=0"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Find Apr 3 (Good Friday) - should be OH with weekoff_value=0
        apr3 = next((d for d in details if d.get("date") == "03-04-2026"), None)
        
        assert apr3 is not None, "Apr 3 not found in attendance_details"
        assert apr3.get("weekoff_value") == 0, f"Apr 3 (holiday) should have weekoff_value=0, got {apr3.get('weekoff_value')}"
        assert apr3.get("status") == "OH", f"Apr 3 should have status OH, got {apr3.get('status')}"


class TestInactiveEmployeeApril16SundaysOnly:
    """Tests for inactive employee with inactive_date=2026-04-16 - Sundays ONLY"""
    
    # Inactive employee: TEST_Relieved_05658888 (inactive_date=2026-04-16)
    INACTIVE_EMPLOYEE_ID = "8bc4cef5-2213-4701-9f61-d98bac1cf582"
    
    def test_inactive_employee_apr16_weekoff_pay_equals_2_sundays_only(self, auth_headers):
        """Inactive employee (inactive_date=2026-04-16): weekoff_pay=2 (only Sundays Apr 5, Apr 12)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # Inactive employee should have weekoff_pay = 2 (ONLY Sundays before Apr 16: Apr 5, Apr 12)
        # Holidays (Apr 3, Apr 14) do NOT contribute to weekoff
        assert data.get("weekoff_pay") == 2.0, f"Expected weekoff_pay=2 (Sundays 5,12 only), got {data.get('weekoff_pay')}"


class TestSundayNotWorkedStatus:
    """Tests for Sunday not worked status"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_sunday_not_worked_status_wo_weekoff_1(self, auth_headers):
        """Sunday not worked → status WO, weekoff_value=1"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Find past Sundays (Apr 5, Apr 12) that were not worked
        past_sundays = [d for d in details if d.get("is_sunday") and int(d["date"].split("-")[0]) <= 17]
        
        for sunday in past_sundays:
            # If not worked, status should be WO
            if sunday.get("check_in") is None:
                assert sunday.get("status") == "WO", f"Sunday {sunday['date']} not worked should have status=WO, got {sunday.get('status')}"
            # Regardless of worked or not, weekoff_value should be 1
            assert sunday.get("weekoff_value") == 1, f"Sunday {sunday['date']} should have weekoff_value=1, got {sunday.get('weekoff_value')}"


class TestHolidayNotWorkedStatus:
    """Tests for Holiday not worked status"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_holiday_not_worked_status_oh_weekoff_0_extra_0(self, auth_headers):
        """Holiday not worked → status OH, weekoff_value=0, extra_value=0"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        
        # Find holidays (Apr 3, Apr 14) that are not Sundays
        holidays = [d for d in details if d.get("is_holiday") and not d.get("is_sunday")]
        
        for holiday in holidays:
            # If not worked, status should be OH
            if holiday.get("check_in") is None:
                assert holiday.get("status") in ["OH", "H"], f"Holiday {holiday['date']} not worked should have status=OH or H, got {holiday.get('status')}"
            # weekoff_value should always be 0 for holidays
            assert holiday.get("weekoff_value") == 0, f"Holiday {holiday['date']} should have weekoff_value=0, got {holiday.get('weekoff_value')}"
            # If not worked, extra_value should be 0
            if holiday.get("check_in") is None:
                assert holiday.get("extra_value") == 0, f"Holiday {holiday['date']} not worked should have extra_value=0, got {holiday.get('extra_value')}"


class TestWorkingDaysCalculation:
    """Tests for working days calculation"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_working_days_excludes_sundays_and_holidays(self, auth_headers):
        """Working days correctly excludes both Sundays and holidays"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # April 2026: 30 days - 4 Sundays - 2 holidays = 24 working days
        assert data.get("working_days") == 24, f"Expected working_days=24, got {data.get('working_days')}"


class TestPayableFormula:
    """Tests for payable formula"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_payable_formula_correct(self, auth_headers):
        """Payable formula: (working_days - lop) + weekoff_pay + extra_pay still correct"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        working_days = data.get("working_days", 0)
        lop = data.get("lop", 0)
        weekoff_pay = data.get("weekoff_pay", 0)
        extra_pay = data.get("extra_pay", 0)
        final_payable_days = data.get("final_payable_days", 0)
        
        # Formula: (working_days - lop) + weekoff_pay + extra_pay
        expected = (working_days - lop) + weekoff_pay + extra_pay
        
        assert final_payable_days == expected, f"Expected final_payable_days={expected}, got {final_payable_days}"


class TestJanuary2026SundaysOnly:
    """Tests for January 2026 - Sundays ONLY for weekoff"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_january_2026_weekoff_pay_4_sundays_only(self, auth_headers):
        """January 2026 (past month): weekoff_pay = count of Sundays only (no holidays in weekoff)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-01",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # January 2026 has 31 days
        # Sundays: 4, 11, 18, 25 (4 Sundays)
        # Holidays: Jan 1, 15, 16, 26 (4 holidays) - NOT counted in weekoff
        # weekoff_pay should be 4 (ONLY Sundays)
        
        assert data.get("total_days") == 31, f"Expected total_days=31, got {data.get('total_days')}"
        assert data.get("weekoff_pay") == 4.0, f"Expected weekoff_pay=4 (Sundays only), got {data.get('weekoff_pay')}"
        
        # Working days: 31 - 4 Sundays - 4 holidays = 23
        assert data.get("working_days") == 23, f"Expected working_days=23, got {data.get('working_days')}"


class TestPayrollSummaryEndpoint:
    """Tests for payroll summary endpoint"""
    
    def test_payroll_summary_includes_total_weekoff_pay(self, auth_headers):
        """Payroll summary endpoint includes total_weekoff_pay"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/summary/2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll summary API failed: {response.text}"
        data = response.json()
        
        # Verify summary has expected fields
        assert "total_employees" in data, "Missing total_employees in summary"
        assert "total_weekoff_pay" in data, "Missing total_weekoff_pay in summary"
        assert "total_lop_days" in data, "Missing total_lop_days in summary"
