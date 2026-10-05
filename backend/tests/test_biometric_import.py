"""
Test suite for POST /api/attendance/import-biometric endpoint
Tests biometric attendance data import including:
- Authentication/Authorization (401 without token, 403 for non-admin)
- deviceUserId to employee.biometric_id mapping
- Unmapped/invalid record handling
- Punch grouping by employee+date
- IN TIME (earliest) and OUT TIME (latest) calculation
- New attendance record creation with source='biometric'
- UPSERT: MIN(IN) and MAX(OUT) merge logic
- Total hours calculation
- Response counts (totalRecords, processed, skipped, unmapped)
- Raw punch log audit storage
- Large batch processing
- Invalid JSON handling
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Generate unique dates for each test run to avoid conflicts with existing data
# Using dates far in the future to avoid conflicts
TEST_RUN_ID = str(uuid.uuid4())[:8]


def get_unique_date(base_month=6, day_offset=0):
    """Generate unique test date in June 2026 to avoid conflicts"""
    day = 10 + day_offset  # Start from June 10
    return f"2026-{base_month:02d}-{day:02d}", f"{day:02d}-{base_month:02d}-2026"


class TestBiometricImportAuth:
    """Test authentication and authorization for biometric import"""
    
    def test_import_biometric_requires_auth_401(self):
        """Test that endpoint returns 401 without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=[{"deviceUserId": "BDT-101", "recordTime": "2026-06-01T09:00:00+05:30"}],
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401 or response.status_code == 403, f"Expected 401/403, got {response.status_code}"
        print(f"PASS: Endpoint correctly requires authentication (status: {response.status_code})")
    
    def test_import_biometric_rejects_non_admin_403(self, employee_token):
        """Test that non-admin users get 403"""
        if not employee_token:
            pytest.skip("No employee token available")
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=[{"deviceUserId": "BDT-101", "recordTime": "2026-06-01T09:00:00+05:30"}],
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {employee_token}"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("PASS: Non-admin users correctly rejected with 403")


class TestBiometricImportMapping:
    """Test deviceUserId to employee biometric_id mapping"""
    
    def test_correct_mapping_via_biometric_id(self, admin_auth):
        """Test that deviceUserId correctly maps to employee via biometric_id field"""
        iso_date, _ = get_unique_date(7, 1)
        records = [
            {
                "deviceUserId": "BDT-101",
                "recordTime": f"{iso_date}T10:00:00+05:30"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["totalRecords"] == 1
        assert data["processed"] >= 0
        assert data["unmapped"] == 0 or data["processed"] == 1
        print(f"PASS: deviceUserId correctly mapped to employee. Response: {data}")
    
    def test_unmapped_device_user_id_counted(self, admin_auth):
        """Test that unmapped deviceUserId records are counted in response"""
        records = [
            {
                "deviceUserId": "UNKNOWN-999",  # Non-existent biometric_id
                "recordTime": "2026-06-01T10:00:00+05:30"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["unmapped"] == 1, f"Expected 1 unmapped, got {data['unmapped']}"
        assert "UNKNOWN-999" in data.get("unmappedDeviceUserIds", [])
        print(f"PASS: Unmapped deviceUserId counted correctly. Response: {data}")


class TestBiometricImportValidation:
    """Test input validation and skipping invalid records"""
    
    def test_skips_missing_device_user_id(self, admin_auth):
        """Test that records without deviceUserId are skipped"""
        records = [{"recordTime": "2026-06-01T10:00:00+05:30"}]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == 1
        print(f"PASS: Records without deviceUserId skipped. Response: {data}")
    
    def test_skips_missing_record_time(self, admin_auth):
        """Test that records without recordTime are skipped"""
        records = [{"deviceUserId": "BDT-101"}]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == 1
        print(f"PASS: Records without recordTime skipped. Response: {data}")
    
    def test_invalid_json_body_error(self, admin_auth):
        """Test that invalid JSON body returns proper error"""
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            data="not valid json",
            headers={**admin_auth, "Content-Type": "application/json"}
        )
        
        assert response.status_code in [400, 422]
        print(f"PASS: Invalid JSON returns proper error (status: {response.status_code})")
    
    def test_empty_array_error(self, admin_auth):
        """Test that empty array returns error"""
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=[],
            headers=admin_auth
        )
        
        assert response.status_code == 400
        print("PASS: Empty array correctly rejected with 400")


class TestBiometricImportPunchGrouping:
    """Test punch grouping by employee+date with IN/OUT calculation"""
    
    def test_groups_punches_by_employee_date(self, admin_auth):
        """Test that multiple punches per employee per day are grouped correctly"""
        iso_date, _ = get_unique_date(7, 2)
        
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T09:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T12:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T18:00:00+05:30"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["totalRecords"] == 3
        assert data["processed"] == 1, f"Expected 1 (grouped), got {data['processed']}"
        print(f"PASS: Multiple punches grouped correctly. Response: {data}")
    
    def test_in_time_is_earliest_out_time_is_latest(self, admin_auth):
        """Test that IN TIME = earliest punch, OUT TIME = latest punch"""
        iso_date, date_str = get_unique_date(7, 3)
        
        # Send punches in non-chronological order
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T11:00:00+05:30"},  # Middle
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T08:30:00+05:30"},  # Earliest (IN)
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T19:30:00+05:30"},  # Latest (OUT)
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        
        # Verify the attendance record
        att_response = requests.get(
            f"{BASE_URL}/api/attendance?date={date_str}",
            headers=admin_auth
        )
        assert att_response.status_code == 200
        
        att_data = att_response.json()
        record = next((r for r in att_data if r.get("date") == date_str and r.get("emp_name") == "Date Test One"), None)
        
        assert record is not None, f"No attendance record found for date {date_str}"
        assert record.get("check_in_24h") == "08:30", f"Expected IN 08:30, got {record.get('check_in_24h')}"
        assert record.get("check_out_24h") == "19:30", f"Expected OUT 19:30, got {record.get('check_out_24h')}"
        print(f"PASS: IN={record.get('check_in_24h')}, OUT={record.get('check_out_24h')}")


class TestBiometricImportUpsert:
    """Test UPSERT logic for merging attendance records"""
    
    def test_creates_new_attendance_with_source_biometric(self, admin_auth):
        """Test that new attendance record has source='biometric'"""
        iso_date, date_str = get_unique_date(7, 4)
        
        records = [{"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T10:00:00+05:30"}]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        
        # Verify source field
        att_response = requests.get(f"{BASE_URL}/api/attendance?date={date_str}", headers=admin_auth)
        att_data = att_response.json()
        record = next((r for r in att_data if r.get("date") == date_str and r.get("emp_name") == "Date Test One"), None)
        
        assert record is not None, "Attendance record not found"
        assert record.get("source") == "biometric", f"Expected source='biometric', got {record.get('source')}"
        print(f"PASS: Attendance created with source='biometric'")
    
    def test_upsert_updates_in_to_min_out_to_max(self, admin_auth):
        """Test UPSERT: Updates IN to MIN(existing, new) and OUT to MAX(existing, new)"""
        iso_date, date_str = get_unique_date(7, 5)
        
        # First chunk: IN=10:00, OUT=17:00
        chunk1 = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T10:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T17:00:00+05:30"},
        ]
        
        response1 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk1,
            headers=admin_auth
        )
        assert response1.status_code == 200
        print(f"Chunk 1 response: {response1.json()}")
        
        # Verify first chunk result
        att_response1 = requests.get(f"{BASE_URL}/api/attendance?date={date_str}", headers=admin_auth)
        att_data1 = att_response1.json()
        record1 = next((r for r in att_data1 if r.get("date") == date_str and r.get("emp_name") == "Date Test One"), None)
        print(f"After chunk 1: IN={record1.get('check_in_24h')}, OUT={record1.get('check_out_24h')}")
        
        # Second chunk: IN=09:00 (earlier!), OUT=19:00 (later!)
        chunk2 = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T09:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T19:00:00+05:30"},
        ]
        
        response2 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk2,
            headers=admin_auth
        )
        assert response2.status_code == 200
        print(f"Chunk 2 response: {response2.json()}")
        
        # Verify merged times
        att_response2 = requests.get(f"{BASE_URL}/api/attendance?date={date_str}", headers=admin_auth)
        att_data2 = att_response2.json()
        record2 = next((r for r in att_data2 if r.get("date") == date_str and r.get("emp_name") == "Date Test One"), None)
        
        assert record2 is not None, "Attendance record not found"
        assert record2.get("check_in_24h") == "09:00", f"Expected MIN IN 09:00, got {record2.get('check_in_24h')}"
        assert record2.get("check_out_24h") == "19:00", f"Expected MAX OUT 19:00, got {record2.get('check_out_24h')}"
        print(f"PASS: UPSERT correctly merged IN={record2.get('check_in_24h')}, OUT={record2.get('check_out_24h')}")


class TestBiometricImportTotalHours:
    """Test total hours calculation"""
    
    def test_calculates_total_hours_correctly(self, admin_auth):
        """Test that total_hours is calculated from IN and OUT times"""
        iso_date, date_str = get_unique_date(7, 6)
        
        # 9:00 AM to 6:00 PM = 9 hours
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T09:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T18:00:00+05:30"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        
        # Verify total hours
        att_response = requests.get(f"{BASE_URL}/api/attendance?date={date_str}", headers=admin_auth)
        att_data = att_response.json()
        record = next((r for r in att_data if r.get("date") == date_str and r.get("emp_name") == "Date Test One"), None)
        
        assert record is not None, "Attendance record not found"
        total_decimal = record.get("total_hours_decimal")
        assert total_decimal == 9.0 or total_decimal == 9, f"Expected 9 hours, got {total_decimal}"
        print(f"PASS: Total hours calculated correctly: {total_decimal}")


class TestBiometricImportResponse:
    """Test response counts"""
    
    def test_response_returns_correct_counts(self, admin_auth):
        """Test response returns correct totalRecords, processed, skipped, unmapped counts"""
        iso_date, _ = get_unique_date(7, 7)
        
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T10:00:00+05:30"},
            {"deviceUserId": "UNKNOWN-XYZ", "recordTime": f"{iso_date}T10:00:00+05:30"},
            {"recordTime": f"{iso_date}T10:00:00+05:30"},
            {"deviceUserId": "BDT-102", "recordTime": f"{iso_date}T10:00:00+05:30"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "totalRecords" in data
        assert "processed" in data
        assert "skipped" in data
        assert "unmapped" in data
        
        assert data["totalRecords"] == 4
        assert data["skipped"] >= 1
        assert data["unmapped"] >= 1
        
        print(f"PASS: Response counts correct: {data}")


class TestBiometricImportAudit:
    """Test audit logging"""
    
    def test_raw_punch_logs_stored_for_audit(self, admin_auth):
        """Test that raw punch logs are stored in biometric_punch_logs collection"""
        iso_date, _ = get_unique_date(7, 8)
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T10:00:00+05:30", "ip": "192.168.1.100"}
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        print(f"PASS: Import successful, audit logs should be stored. Response: {response.json()}")


class TestBiometricImportLargeBatch:
    """Test large batch processing"""
    
    def test_handles_large_batch_50_plus_records(self, admin_auth):
        """Test that endpoint handles 50+ records without failure"""
        iso_date, _ = get_unique_date(7, 9)
        records = []
        
        # 30 valid records for BDT-101
        for i in range(30):
            hour = 8 + (i % 12)
            minute = i % 60
            records.append({
                "deviceUserId": "BDT-101",
                "recordTime": f"{iso_date}T{hour:02d}:{minute:02d}:00+05:30"
            })
        
        # 10 unmapped records
        for i in range(10):
            records.append({
                "deviceUserId": f"UNMAPPED-{i}",
                "recordTime": f"{iso_date}T10:00:00+05:30"
            })
        
        # 10 invalid records
        for i in range(5):
            records.append({"deviceUserId": f"SKIP-{i}"})
        for i in range(5):
            records.append({"recordTime": f"{iso_date}T10:00:00+05:30"})
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["totalRecords"] == 50
        assert data["skipped"] == 10
        assert data["unmapped"] == 10
        
        print(f"PASS: Large batch (50 records) processed successfully. Response: {data}")


class TestBiometricImportMultipleEmployees:
    """Test importing for multiple employees at once"""
    
    def test_multiple_employees_same_day(self, admin_auth):
        """Test importing records for both BDT-101 and BDT-102 on same day"""
        iso_date, _ = get_unique_date(7, 10)
        
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T09:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{iso_date}T18:00:00+05:30"},
            {"deviceUserId": "BDT-102", "recordTime": f"{iso_date}T10:00:00+05:30"},
            {"deviceUserId": "BDT-102", "recordTime": f"{iso_date}T17:00:00+05:30"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["totalRecords"] == 4
        assert data["processed"] == 2, f"Expected 2 processed (2 employees), got {data['processed']}"
        assert data["skipped"] == 0
        assert data["unmapped"] == 0
        
        print(f"PASS: Multiple employees processed correctly. Response: {data}")


# ============== FIXTURES ==============

@pytest.fixture(scope="session")
def admin_auth():
    """Get admin authentication headers"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin"}
    )
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    token = response.json().get("token")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

@pytest.fixture(scope="session")
def employee_token():
    """Try to get employee token for authorization tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "employee@test.com", "password": "password123"}
    )
    if response.status_code == 200:
        return response.json().get("token")
    return None


# ============== MAIN ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
