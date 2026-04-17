"""
Test suite for Payroll Weekoff Fix - April 2026
Tests that:
1. Active employees count ALL Sundays/holidays in the month (including future) for weekoff_pay
2. Inactive employees stop counting weekoff at inactive_date (R status after that)
3. Future working days are counted in working_days for active employees
4. No regression for past months

April 2026 Calendar:
- Sundays: 5, 12, 19, 26 (4 Sundays)
- Holidays: Apr 3 (Good Friday), Apr 14 (Tamil New Year) (2 holidays)
- Total weekoff for full month: 6 (4 Sundays + 2 holidays)
- Working days: 24 (30 - 4 Sundays - 2 holidays)
- Today: April 17, 2026 IST
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


class TestActiveEmployeeApril2026:
    """Tests for active employee payroll in April 2026"""
    
    # Active employee: TEST_NoBody_25a93648
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_active_employee_weekoff_pay_equals_6(self, auth_headers):
        """Active employee April 2026: weekoff_pay=6 (4 Sundays + 2 holidays for full month)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # Active employee should have weekoff_pay = 6 (4 Sundays + 2 holidays)
        assert data.get("weekoff_pay") == 6.0, f"Expected weekoff_pay=6, got {data.get('weekoff_pay')}"
    
    def test_active_employee_working_days_equals_24(self, auth_headers):
        """Active employee April 2026: working_days=24 (30 days - 4 Sundays - 2 holidays)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Active employee should have working_days = 24
        assert data.get("working_days") == 24, f"Expected working_days=24, got {data.get('working_days')}"
    
    def test_active_employee_future_sundays_show_su_with_weekoff_value_1(self, auth_headers):
        """Active employee: future Sundays show Su with weekoff_value=1"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        # Future Sundays: Apr 19, Apr 26
        future_sundays = [d for d in details if d.get("is_sunday") and int(d["date"].split("-")[0]) > 17]
        
        assert len(future_sundays) == 2, f"Expected 2 future Sundays, got {len(future_sundays)}"
        for sunday in future_sundays:
            assert sunday.get("status") == "Su", f"Expected status=Su for {sunday['date']}, got {sunday.get('status')}"
            assert sunday.get("weekoff_value") == 1, f"Expected weekoff_value=1 for {sunday['date']}, got {sunday.get('weekoff_value')}"
    
    def test_active_employee_future_working_days_show_na_and_count(self, auth_headers):
        """Active employee: future working days show NA and count in working_days"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        # Future working days (not Sunday, not holiday, after Apr 17)
        future_working = [d for d in details 
                         if not d.get("is_sunday") 
                         and not d.get("is_holiday") 
                         and int(d["date"].split("-")[0]) > 17]
        
        # All future working days should have status=NA
        for day in future_working:
            assert day.get("status") == "NA", f"Expected status=NA for {day['date']}, got {day.get('status')}"


class TestInactiveEmployeeApril14:
    """Tests for inactive employee with inactive_date=2026-04-14"""
    
    # Inactive employee: TEST_Deactivation_f98a8836 (inactive_date=2026-04-14)
    INACTIVE_EMPLOYEE_ID = "e93ef490-5c06-4c2c-8290-00537df17516"
    
    def test_inactive_employee_weekoff_pay_equals_4(self, auth_headers):
        """Inactive employee (inactive_date=2026-04-14): weekoff_pay=4 (only before/on Apr 14)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # Inactive employee should have weekoff_pay = 4
        # Apr 3 (Good Friday), Apr 5 (Sun), Apr 12 (Sun), Apr 14 (Tamil New Year)
        assert data.get("weekoff_pay") == 4.0, f"Expected weekoff_pay=4, got {data.get('weekoff_pay')}"
    
    def test_inactive_employee_working_days_equals_10(self, auth_headers):
        """Inactive employee (inactive_date=2026-04-14): working_days=10 (only non-Sun non-Holiday days up to Apr 14)"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Working days up to Apr 14 (excluding Sundays and holidays)
        # Apr 1-14 = 14 days, minus Apr 3 (holiday), Apr 5 (Sun), Apr 12 (Sun), Apr 14 (holiday) = 10
        assert data.get("working_days") == 10, f"Expected working_days=10, got {data.get('working_days')}"
    
    def test_inactive_employee_dates_after_inactive_show_r_status(self, auth_headers):
        """Inactive employee: dates after inactive_date show R status with zero weekoff_value"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        details = data.get("attendance_details", [])
        # Dates after Apr 14 should have status=R
        after_inactive = [d for d in details if int(d["date"].split("-")[0]) > 14]
        
        assert len(after_inactive) == 16, f"Expected 16 days after Apr 14, got {len(after_inactive)}"
        for day in after_inactive:
            assert day.get("status") == "R", f"Expected status=R for {day['date']}, got {day.get('status')}"
            assert day.get("weekoff_value") == 0, f"Expected weekoff_value=0 for {day['date']}, got {day.get('weekoff_value')}"
    
    def test_inactive_employee_final_payable_days_formula(self, auth_headers):
        """Inactive employee: final_payable_days = (working_days - lop) + weekoff_pay + extra_pay - last_day_adjustment"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        working_days = data.get("working_days", 0)
        lop = data.get("lop", 0)
        weekoff_pay = data.get("weekoff_pay", 0)
        extra_pay = data.get("extra_pay", 0)
        final_payable_days = data.get("final_payable_days", 0)
        
        # Base formula: (working_days - lop) + weekoff_pay + extra_pay
        base_expected = (working_days - lop) + weekoff_pay + extra_pay
        
        # This employee has last_day_payable=False, so 1 day is subtracted
        # Expected: (10 - 10) + 4 + 0 - 1 = 3
        expected_with_adjustment = max(0, base_expected - 1)  # -1 for last_day_payable=False
        assert final_payable_days == expected_with_adjustment, f"Expected final_payable_days={expected_with_adjustment}, got {final_payable_days}"


class TestInactiveEmployeeApril16:
    """Tests for inactive employee with inactive_date=2026-04-16"""
    
    # Inactive employee: TEST_Relieved_05658888 (inactive_date=2026-04-16)
    INACTIVE_EMPLOYEE_ID = "8bc4cef5-2213-4701-9f61-d98bac1cf582"
    
    def test_inactive_employee_apr16_weekoff_pay_equals_4(self, auth_headers):
        """Inactive employee (inactive_date=2026-04-16): weekoff_pay=4"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # Inactive employee should have weekoff_pay = 4
        # Apr 3 (Good Friday), Apr 5 (Sun), Apr 12 (Sun), Apr 14 (Tamil New Year)
        # Apr 16 is Thursday, so no additional weekoff
        assert data.get("weekoff_pay") == 4.0, f"Expected weekoff_pay=4, got {data.get('weekoff_pay')}"
    
    def test_inactive_employee_apr16_working_days_equals_12(self, auth_headers):
        """Inactive employee (inactive_date=2026-04-16): working_days=12"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Working days up to Apr 16 (excluding Sundays and holidays)
        # Apr 1-16 = 16 days, minus Apr 3 (holiday), Apr 5 (Sun), Apr 12 (Sun), Apr 14 (holiday) = 12
        assert data.get("working_days") == 12, f"Expected working_days=12, got {data.get('working_days')}"


class TestNoRegressionPastMonth:
    """Tests for no regression in past months"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    
    def test_active_employee_january_2026_unchanged(self, auth_headers):
        """Edge case: active employee payroll for January (past full month) unchanged"""
        response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-01",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payroll API failed: {response.text}"
        data = response.json()
        
        # January 2026 has 31 days
        # Sundays: 4, 11, 18, 25 (4 Sundays)
        # Holidays: Jan 1 (New Year), Jan 15 (Pongal), Jan 16 (Thiruvalluvar), Jan 26 (Republic Day) (4 holidays)
        # Total weekoff: 8 (4 Sundays + 4 holidays)
        # Working days: 31 - 8 = 23
        
        assert data.get("total_days") == 31, f"Expected total_days=31, got {data.get('total_days')}"
        assert data.get("weekoff_pay") == 8.0, f"Expected weekoff_pay=8, got {data.get('weekoff_pay')}"
        assert data.get("working_days") == 23, f"Expected working_days=23, got {data.get('working_days')}"


class TestPayrollSummary:
    """Tests for payroll summary endpoint"""
    
    def test_payroll_summary_includes_updated_totals(self, auth_headers):
        """Payroll summary endpoint includes updated totals"""
        # Note: endpoint is /api/payroll/summary/{month} not /api/payroll/summary?month=
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


class TestActiveVsInactiveComparison:
    """Tests comparing active vs inactive employee payroll"""
    
    ACTIVE_EMPLOYEE_ID = "4666841e-2f7b-4659-9158-2b3e1bf7a357"
    INACTIVE_EMPLOYEE_ID = "e93ef490-5c06-4c2c-8290-00537df17516"  # inactive_date=2026-04-14
    
    def test_active_has_more_weekoff_than_inactive(self, auth_headers):
        """Active employee has more weekoff_pay than inactive employee"""
        # Get active employee payroll
        active_response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert active_response.status_code == 200
        active_data = active_response.json()
        
        # Get inactive employee payroll
        inactive_response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert inactive_response.status_code == 200
        inactive_data = inactive_response.json()
        
        # Active should have more weekoff (6 vs 4)
        assert active_data.get("weekoff_pay") > inactive_data.get("weekoff_pay"), \
            f"Active weekoff ({active_data.get('weekoff_pay')}) should be > inactive weekoff ({inactive_data.get('weekoff_pay')})"
        
        # Specifically: active=6, inactive=4
        assert active_data.get("weekoff_pay") == 6.0, f"Active weekoff should be 6, got {active_data.get('weekoff_pay')}"
        assert inactive_data.get("weekoff_pay") == 4.0, f"Inactive weekoff should be 4, got {inactive_data.get('weekoff_pay')}"
    
    def test_active_has_more_working_days_than_inactive(self, auth_headers):
        """Active employee has more working_days than inactive employee"""
        # Get active employee payroll
        active_response = requests.get(
            f"{BASE_URL}/api/payroll/{self.ACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert active_response.status_code == 200
        active_data = active_response.json()
        
        # Get inactive employee payroll
        inactive_response = requests.get(
            f"{BASE_URL}/api/payroll/{self.INACTIVE_EMPLOYEE_ID}?month=2026-04",
            headers=auth_headers
        )
        assert inactive_response.status_code == 200
        inactive_data = inactive_response.json()
        
        # Active should have more working days (24 vs 10)
        assert active_data.get("working_days") > inactive_data.get("working_days"), \
            f"Active working_days ({active_data.get('working_days')}) should be > inactive working_days ({inactive_data.get('working_days')})"
        
        # Specifically: active=24, inactive=10
        assert active_data.get("working_days") == 24, f"Active working_days should be 24, got {active_data.get('working_days')}"
        assert inactive_data.get("working_days") == 10, f"Inactive working_days should be 10, got {inactive_data.get('working_days')}"
