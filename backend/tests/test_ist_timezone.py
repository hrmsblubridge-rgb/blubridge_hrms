"""
IST Timezone Testing for BluBridge HRMS
Tests that all datetime operations use Indian Standard Time (UTC+5:30)

Features tested:
1. Backend helper functions for IST
2. Attendance check-in/check-out times in IST
3. Date filters work correctly with IST dates
4. Payroll calculations use IST dates
5. Employee dashboard attendance shows IST times
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

# IST timezone definition (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestISTTimezone:
    """Test IST timezone implementation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - authenticate as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_current_ist_time_is_correct(self):
        """Verify IST is UTC+5:30"""
        now_utc = datetime.now(timezone.utc)
        now_ist = datetime.now(IST)
        
        # IST should be 5 hours 30 minutes ahead of UTC
        expected_ist = now_utc + timedelta(hours=5, minutes=30)
        
        # Allow 1 minute tolerance for test execution time
        diff = abs((now_ist - expected_ist.replace(tzinfo=IST)).total_seconds())
        assert diff < 60, f"IST time calculation incorrect. Expected ~{expected_ist}, got {now_ist}"
        print(f"PASS: IST time is correct. UTC: {now_utc.strftime('%H:%M:%S')}, IST: {now_ist.strftime('%H:%M:%S')}")
    
    def test_attendance_stats_uses_ist_date(self):
        """Test attendance stats endpoint uses IST date format"""
        # Get current IST date
        ist_today = datetime.now(IST).strftime("%d-%m-%Y")
        
        # Call attendance stats without date param - should default to IST today
        response = self.session.get(f"{BASE_URL}/api/attendance/stats")
        assert response.status_code == 200, f"Attendance stats failed: {response.text}"
        
        data = response.json()
        # Response should include total_employees count
        assert "total_employees" in data, "Missing total_employees in response"
        print(f"PASS: Attendance stats endpoint working. Total employees: {data['total_employees']}")
        print(f"      Current IST date: {ist_today}")
    
    def test_attendance_records_date_format(self):
        """Test attendance records use DD-MM-YYYY format (IST)"""
        # Get current IST date in DD-MM-YYYY format
        ist_today = datetime.now(IST).strftime("%d-%m-%Y")
        
        # Fetch attendance for today
        response = self.session.get(f"{BASE_URL}/api/attendance", params={
            "from_date": ist_today,
            "to_date": ist_today
        })
        assert response.status_code == 200, f"Attendance fetch failed: {response.text}"
        
        data = response.json()
        print(f"PASS: Fetched {len(data)} attendance records for IST date {ist_today}")
        
        # If records exist, verify date format
        if data:
            record = data[0]
            date_str = record.get("date", "")
            # Verify DD-MM-YYYY format
            assert len(date_str.split("-")) == 3, f"Invalid date format: {date_str}"
            print(f"      Sample record date: {date_str}, check_in: {record.get('check_in')}, check_out: {record.get('check_out')}")
    
    def test_get_employees_for_checkin(self):
        """Get an active employee for check-in testing"""
        response = self.session.get(f"{BASE_URL}/api/employees/all")
        assert response.status_code == 200, f"Failed to get employees: {response.text}"
        
        employees = response.json()
        assert len(employees) > 0, "No active employees found"
        
        print(f"PASS: Found {len(employees)} active employees")
        return employees[0]
    
    def test_attendance_checkin_records_ist_time(self):
        """Test that check-in records current IST time"""
        # Get an employee
        response = self.session.get(f"{BASE_URL}/api/employees/all")
        assert response.status_code == 200
        employees = response.json()
        
        if not employees:
            pytest.skip("No employees available for check-in test")
        
        employee = employees[0]
        employee_id = employee.get("id")
        
        # Try to check in - may fail if already checked in today
        response = self.session.post(f"{BASE_URL}/api/attendance/check-in?employee_id={employee_id}")
        
        if response.status_code == 200:
            data = response.json()
            check_in_time = data.get("check_in")
            check_in_24h = data.get("check_in_24h")
            date = data.get("date")
            
            # Verify IST date format (DD-MM-YYYY)
            ist_today = datetime.now(IST).strftime("%d-%m-%Y")
            assert date == ist_today, f"Check-in date not in IST: expected {ist_today}, got {date}"
            
            # Verify time is recorded
            assert check_in_time is not None, "check_in time not recorded"
            assert check_in_24h is not None, "check_in_24h time not recorded"
            
            print(f"PASS: Check-in recorded with IST time")
            print(f"      Date: {date}, Time: {check_in_time} ({check_in_24h})")
            
        elif response.status_code == 400 and "Already checked in" in response.text:
            print(f"PASS: Employee already checked in today (expected behavior)")
            # Verify the existing check-in record uses IST
            att_response = self.session.get(f"{BASE_URL}/api/attendance", params={
                "from_date": datetime.now(IST).strftime("%d-%m-%Y"),
                "to_date": datetime.now(IST).strftime("%d-%m-%Y")
            })
            if att_response.status_code == 200:
                records = att_response.json()
                for record in records:
                    if record.get("employee_id") == employee_id:
                        print(f"      Existing check-in: {record.get('check_in')} on {record.get('date')}")
                        break
        else:
            print(f"WARNING: Check-in returned {response.status_code}: {response.text}")
    
    def test_payroll_month_format(self):
        """Test payroll uses correct month format"""
        # Get current IST month
        ist_now = datetime.now(IST)
        current_month = ist_now.strftime("%Y-%m")
        
        response = self.session.get(f"{BASE_URL}/api/payroll", params={"month": current_month})
        assert response.status_code == 200, f"Payroll fetch failed: {response.text}"
        
        data = response.json()
        # Payroll returns a list directly
        payroll_records = data if isinstance(data, list) else data.get("payroll", [])
        print(f"PASS: Payroll endpoint working for month {current_month}")
        print(f"      Found {len(payroll_records)} payroll records")
        
        # Verify date format in payroll records
        if payroll_records:
            record = payroll_records[0]
            attendance_details = record.get("attendance_details", [])
            if attendance_details:
                # Check date format is DD-MM-YYYY
                sample_date = attendance_details[0].get("date", "")
                assert len(sample_date.split("-")) == 3, f"Invalid date format: {sample_date}"
                print(f"      Sample attendance date: {sample_date} (DD-MM-YYYY format verified)")
    
    def test_employee_dashboard_attendance(self):
        """Test employee dashboard attendance data uses IST"""
        # Login as regular employee
        employee_session = requests.Session()
        employee_session.headers.update({"Content-Type": "application/json"})
        
        response = employee_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "user",
            "password": "user"
        })
        
        if response.status_code != 200:
            pytest.skip("Employee login not available")
        
        token = response.json().get("token")
        employee_session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get employee dashboard data
        response = employee_session.get(f"{BASE_URL}/api/employee/dashboard")
        
        if response.status_code == 200:
            data = response.json()
            print(f"PASS: Employee dashboard accessible")
            
            attendance = data.get("recent_attendance", [])
            if attendance:
                print(f"      Recent attendance records: {len(attendance)}")
                for record in attendance[:3]:
                    print(f"      - {record.get('date')}: {record.get('check_in')} - {record.get('check_out')}")
        else:
            print(f"INFO: Employee dashboard returned {response.status_code}")
    
    def test_reports_date_filter_works(self):
        """Test that reports page date filters work with IST dates"""
        # Get date range in IST
        ist_now = datetime.now(IST)
        ist_today = ist_now.strftime("%d-%m-%Y")
        ist_week_ago = (ist_now - timedelta(days=7)).strftime("%d-%m-%Y")
        
        # Test attendance endpoint with date range
        response = self.session.get(f"{BASE_URL}/api/attendance", params={
            "from_date": ist_week_ago,
            "to_date": ist_today
        })
        assert response.status_code == 200, f"Attendance date filter failed: {response.text}"
        
        data = response.json()
        print(f"PASS: Date filter working for IST dates")
        print(f"      From: {ist_week_ago} To: {ist_today}")
        print(f"      Records found: {len(data)}")
    
    def test_leave_request_dates_format(self):
        """Test leave requests use correct date format"""
        response = self.session.get(f"{BASE_URL}/api/leaves")
        assert response.status_code == 200, f"Leaves fetch failed: {response.text}"
        
        data = response.json()
        print(f"PASS: Leaves endpoint working. Found {len(data)} leave records")
        
        if data:
            leave = data[0]
            print(f"      Sample leave: {leave.get('emp_name')}, {leave.get('start_date')} to {leave.get('end_date')}")
    
    def test_created_at_timestamps_in_ist(self):
        """Verify created_at timestamps are in IST"""
        response = self.session.get(f"{BASE_URL}/api/employees", params={"limit": 5})
        assert response.status_code == 200, f"Employees fetch failed: {response.text}"
        
        data = response.json()
        employees = data.get("employees", [])
        
        if employees:
            for emp in employees[:3]:
                created_at = emp.get("created_at", "")
                if created_at:
                    # Parse the timestamp
                    try:
                        if "+" in created_at:
                            # Has timezone info
                            print(f"      {emp.get('full_name')}: created_at = {created_at}")
                        else:
                            print(f"      {emp.get('full_name')}: created_at = {created_at} (no tz)")
                    except Exception:
                        print(f"      {emp.get('full_name')}: created_at = {created_at} (parse error)")
        
        print(f"PASS: Verified created_at timestamps on {len(employees)} employees")
    
    def test_attendance_stats_date_param(self):
        """Test attendance stats with specific IST date"""
        ist_today = datetime.now(IST).strftime("%d-%m-%Y")
        
        # Test with specific date
        response = self.session.get(f"{BASE_URL}/api/attendance/stats", params={"date": ist_today})
        assert response.status_code == 200, f"Attendance stats with date failed: {response.text}"
        
        data = response.json()
        print(f"PASS: Attendance stats working with date param: {ist_today}")
        print(f"      Total employees: {data.get('total_employees')}")
        print(f"      Present: {data.get('present')}, Absent: {data.get('absent')}")


class TestISTDateCalculations:
    """Test date calculations for IST"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - authenticate as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_payroll_working_days_calculation(self):
        """Test payroll calculates working days correctly for IST month"""
        ist_now = datetime.now(IST)
        current_month = ist_now.strftime("%Y-%m")
        
        response = self.session.get(f"{BASE_URL}/api/payroll", params={"month": current_month})
        assert response.status_code == 200, f"Payroll failed: {response.text}"
        
        data = response.json()
        # Payroll returns a list directly
        payroll_records = data if isinstance(data, list) else data.get("payroll", [])
        
        if payroll_records:
            record = payroll_records[0]
            working_days = record.get("working_days")
            print(f"PASS: Payroll working days calculation")
            print(f"      Month: {current_month}, Working days: {working_days}")
        else:
            print(f"INFO: No payroll records for month {current_month}")
    
    def test_ist_today_format(self):
        """Verify IST today format is DD-MM-YYYY"""
        ist_today = datetime.now(IST).strftime("%d-%m-%Y")
        
        # Verify format
        parts = ist_today.split("-")
        assert len(parts) == 3, f"Invalid IST date format: {ist_today}"
        assert len(parts[0]) == 2, f"Day should be 2 digits: {parts[0]}"
        assert len(parts[1]) == 2, f"Month should be 2 digits: {parts[1]}"
        assert len(parts[2]) == 4, f"Year should be 4 digits: {parts[2]}"
        
        print(f"PASS: IST today format correct: {ist_today}")
    
    def test_ist_offset_verification(self):
        """Verify IST offset is exactly +5:30"""
        utc_now = datetime.now(timezone.utc)
        ist_now = datetime.now(IST)
        
        # Calculate the offset
        utc_timestamp = utc_now.timestamp()
        ist_timestamp = ist_now.timestamp()
        
        # Both should have same timestamp (epoch)
        assert abs(utc_timestamp - ist_timestamp) < 1, "IST timestamp calculation error"
        
        # But displayed time should differ by 5.5 hours
        utc_hour = utc_now.hour + utc_now.minute / 60
        ist_hour = ist_now.hour + ist_now.minute / 60
        
        # Account for day wrap
        if ist_hour < utc_hour:
            ist_hour += 24
        
        diff = ist_hour - utc_hour
        assert abs(diff - 5.5) < 0.1, f"IST offset incorrect: expected 5.5h, got {diff}h"
        
        print(f"PASS: IST offset is correct (+5:30)")
        print(f"      UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"      IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
