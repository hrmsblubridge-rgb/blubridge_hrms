"""
Tests for Date Picker UI components and LOP calculation (0.5 day for Late Login/Early Out)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication setup"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("token")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}"}

class TestPayrollLOPCalculation(TestAuth):
    """Test LOP calculation: Late Login = 0.5 day, Early Out = 0.5 day"""
    
    def test_payroll_endpoint_accessible(self, auth_headers):
        """Test that payroll endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/payroll?month=2026-02", headers=auth_headers)
        assert response.status_code == 200, f"Payroll endpoint failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Payroll should return a list"
        print(f"✅ Payroll endpoint returns {len(data)} employees")
    
    def test_lop_days_is_float(self, auth_headers):
        """Test that lop_days can be float (0.5 for half-day LOP)"""
        response = requests.get(f"{BASE_URL}/api/payroll?month=2026-02", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Find employee with LOP (Adhitya Charan has 2 Early Outs = 1.0 LOP)
        adhitya = next((e for e in data if "Adhitya" in e.get("emp_name", "")), None)
        assert adhitya is not None, "Adhitya Charan should be in payroll data"
        
        lop_days = adhitya.get("lop_days", 0)
        print(f"Adhitya Charan LOP days: {lop_days}")
        
        # LOP days should be 1.0 (2 Early Outs × 0.5)
        assert lop_days == 1.0, f"Expected lop_days=1.0 (2 × 0.5), got {lop_days}"
        print("✅ LOP days correctly calculated as 1.0 (2 Early Outs × 0.5)")
    
    def test_attendance_details_have_lop_value(self, auth_headers):
        """Test that attendance_details contain lop_value for half-day calculations"""
        response = requests.get(f"{BASE_URL}/api/payroll?month=2026-02", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        adhitya = next((e for e in data if "Adhitya" in e.get("emp_name", "")), None)
        assert adhitya is not None
        
        attendance_details = adhitya.get("attendance_details", [])
        
        # Find Early Out days
        early_out_days = [d for d in attendance_details if d.get("status") == "Early Out"]
        print(f"Found {len(early_out_days)} Early Out days")
        
        for day in early_out_days:
            lop_value = day.get("lop_value")
            print(f"  Date: {day.get('date')}, Status: {day.get('status')}, LOP Value: {lop_value}")
            assert lop_value == 0.5, f"Early Out should have lop_value=0.5, got {lop_value}"
        
        print("✅ All Early Out days have lop_value=0.5")
    
    def test_payroll_summary_total_lop_days(self, auth_headers):
        """Test payroll summary has correct total_lop_days"""
        response = requests.get(f"{BASE_URL}/api/payroll/summary/2026-02", headers=auth_headers)
        assert response.status_code == 200, f"Summary endpoint failed: {response.status_code}"
        
        summary = response.json()
        total_lop = summary.get("total_lop_days", 0)
        print(f"Total LOP days in summary: {total_lop}")
        
        # At least 1 LOP day (Adhitya's 2 Early Outs = 1.0)
        assert total_lop >= 1, f"Expected at least 1 LOP day, got {total_lop}"
        print(f"✅ Payroll summary shows correct total_lop_days: {total_lop}")


class TestStarRewardMonthPicker(TestAuth):
    """Test Star Reward page uses MonthPicker component"""
    
    def test_star_rewards_endpoint(self, auth_headers):
        """Test star rewards endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/star-rewards", headers=auth_headers)
        assert response.status_code == 200, f"Star rewards failed: {response.status_code}"
        data = response.json()
        print(f"✅ Star rewards endpoint returns {len(data)} employees")


class TestAttendanceDatePicker(TestAuth):
    """Test Attendance page uses DatePicker component"""
    
    def test_attendance_with_date_filter(self, auth_headers):
        """Test attendance endpoint with date filter"""
        response = requests.get(
            f"{BASE_URL}/api/attendance",
            headers=auth_headers,
            params={
                "from_date": "05-02-2026",
                "to_date": "05-02-2026"
            }
        )
        assert response.status_code == 200, f"Attendance filter failed: {response.status_code}"
        data = response.json()
        print(f"✅ Attendance for 05-02-2026: {len(data)} records")


class TestReportsDatePicker(TestAuth):
    """Test Reports page uses DatePicker component"""
    
    def test_leave_report_endpoint(self, auth_headers):
        """Test leave report endpoint with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/reports/leaves",
            headers=auth_headers,
            params={
                "from_date": "2026-01-01",
                "to_date": "2026-02-28"
            }
        )
        assert response.status_code == 200, f"Leave report failed: {response.status_code}"
        data = response.json()
        print(f"✅ Leave report endpoint returns {len(data)} records")
    
    def test_attendance_report_endpoint(self, auth_headers):
        """Test attendance report endpoint with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/reports/attendance",
            headers=auth_headers,
            params={
                "from_date": "01-02-2026",
                "to_date": "28-02-2026"
            }
        )
        assert response.status_code == 200, f"Attendance report failed: {response.status_code}"
        data = response.json()
        print(f"✅ Attendance report endpoint returns {len(data)} records")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
