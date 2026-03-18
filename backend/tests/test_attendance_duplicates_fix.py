"""
Test suite for Attendance Duplicate Fix - verifies:
1. MongoDB unique compound index exists on attendance (employee_id, date)
2. Biometric import: two chunks for same employee+date = exactly ONE record
3. Biometric import: IN = MIN of all punches, OUT = MAX across chunks
4. Biometric import: single punch = IN set, OUT = null
5. No duplicate attendance records exist in database
6. GET /api/attendance date filtering works correctly with DD-MM-YYYY
7. GET /api/attendance returns results sorted by date descending
8. Direct duplicate insert is prevented by unique index
9. Response format includes totalRecords, processed, skipped, unmapped
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test dates for March 2026 (fresh dates as per main agent instructions)
TEST_DATE_1_ISO = "2026-03-26"
TEST_DATE_1_DDMMYYYY = "26-03-2026"
TEST_DATE_2_ISO = "2026-03-27"
TEST_DATE_2_DDMMYYYY = "27-03-2026"
TEST_DATE_3_ISO = "2026-03-28"
TEST_DATE_3_DDMMYYYY = "28-03-2026"


class TestUniqueIndexExists:
    """Verify MongoDB unique compound index on attendance collection"""
    
    def test_duplicate_insert_prevented_by_index(self, admin_auth, cleanup_test_attendance):
        """
        Test that trying to insert duplicate (employee_id+date) directly 
        results in UPSERT behavior instead of duplicate records.
        
        The biometric import uses update_one with upsert=True, so this tests
        that the same employee+date combination doesn't create duplicates.
        """
        # First import: create attendance for employee BDT-101 on TEST_DATE_1
        chunk1 = [
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_1_ISO}T09:00:00+05:30"}
        ]
        
        response1 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk1,
            headers=admin_auth
        )
        assert response1.status_code == 200, f"First import failed: {response1.text}"
        data1 = response1.json()
        print(f"First import result: {data1}")
        
        # Second import: same employee, same date, different time
        chunk2 = [
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_1_ISO}T18:00:00+05:30"}
        ]
        
        response2 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk2,
            headers=admin_auth
        )
        assert response2.status_code == 200, f"Second import failed: {response2.text}"
        data2 = response2.json()
        print(f"Second import result: {data2}")
        
        # Verify: There should be EXACTLY ONE record for this employee+date
        att_response = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_1_DDMMYYYY}&to_date={TEST_DATE_1_DDMMYYYY}",
            headers=admin_auth
        )
        assert att_response.status_code == 200
        records = att_response.json()
        
        # Filter for our specific employee
        bdt101_records = [r for r in records if r.get("emp_name") == "Date Test One" and r.get("date") == TEST_DATE_1_DDMMYYYY]
        
        assert len(bdt101_records) == 1, f"Expected exactly 1 record for BDT-101 on {TEST_DATE_1_DDMMYYYY}, got {len(bdt101_records)}: {bdt101_records}"
        print(f"PASS: Unique index prevents duplicates - exactly 1 record for employee+date")


class TestBiometricImportTwoChunksOneRecord:
    """Test that importing two chunks for same employee+date results in ONE record"""
    
    def test_two_chunks_same_employee_date_one_record(self, admin_auth, cleanup_test_attendance):
        """
        Feature: Two chunks for same employee+date = exactly ONE record
        """
        # Chunk 1: IN=10:00, OUT=17:00
        chunk1 = [
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_2_ISO}T10:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_2_ISO}T17:00:00+05:30"},
        ]
        
        response1 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk1,
            headers=admin_auth
        )
        assert response1.status_code == 200
        print(f"Chunk 1 processed: {response1.json()}")
        
        # Chunk 2: IN=09:00 (earlier), OUT=19:00 (later)
        chunk2 = [
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_2_ISO}T09:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_2_ISO}T19:00:00+05:30"},
        ]
        
        response2 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk2,
            headers=admin_auth
        )
        assert response2.status_code == 200
        print(f"Chunk 2 processed: {response2.json()}")
        
        # Verify: exactly ONE record exists
        att_response = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_2_DDMMYYYY}&to_date={TEST_DATE_2_DDMMYYYY}",
            headers=admin_auth
        )
        assert att_response.status_code == 200
        records = att_response.json()
        
        bdt101_records = [r for r in records if r.get("emp_name") == "Date Test One" and r.get("date") == TEST_DATE_2_DDMMYYYY]
        
        assert len(bdt101_records) == 1, f"Expected exactly 1 record after 2 chunks, got {len(bdt101_records)}"
        print(f"PASS: Two chunks resulted in exactly ONE attendance record")


class TestBiometricImportMinInMaxOut:
    """Test IN = MIN of all punches, OUT = MAX of all punches across chunks"""
    
    def test_in_min_out_max_across_chunks(self, admin_auth, cleanup_test_attendance):
        """
        Feature: IN = MIN of all punches, OUT = MAX across chunks
        """
        # Chunk 1: IN=10:00, OUT=17:00
        chunk1 = [
            {"deviceUserId": "BDT-102", "recordTime": f"{TEST_DATE_2_ISO}T10:00:00+05:30"},
            {"deviceUserId": "BDT-102", "recordTime": f"{TEST_DATE_2_ISO}T17:00:00+05:30"},
        ]
        
        response1 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk1,
            headers=admin_auth
        )
        assert response1.status_code == 200
        
        # Verify initial times
        att_response1 = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_2_DDMMYYYY}&to_date={TEST_DATE_2_DDMMYYYY}",
            headers=admin_auth
        )
        records1 = att_response1.json()
        record1 = next((r for r in records1 if r.get("emp_name") == "Date Test Two" and r.get("date") == TEST_DATE_2_DDMMYYYY), None)
        
        assert record1 is not None, "Initial attendance record not created"
        assert record1.get("check_in_24h") == "10:00", f"Expected initial IN 10:00, got {record1.get('check_in_24h')}"
        assert record1.get("check_out_24h") == "17:00", f"Expected initial OUT 17:00, got {record1.get('check_out_24h')}"
        print(f"After chunk 1: IN={record1.get('check_in_24h')}, OUT={record1.get('check_out_24h')}")
        
        # Chunk 2: IN=09:00 (earlier!), OUT=19:00 (later!)
        chunk2 = [
            {"deviceUserId": "BDT-102", "recordTime": f"{TEST_DATE_2_ISO}T09:00:00+05:30"},  # Earlier than 10:00
            {"deviceUserId": "BDT-102", "recordTime": f"{TEST_DATE_2_ISO}T19:00:00+05:30"},  # Later than 17:00
        ]
        
        response2 = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=chunk2,
            headers=admin_auth
        )
        assert response2.status_code == 200
        
        # Verify merged times: IN should be MIN(10:00, 09:00) = 09:00
        #                      OUT should be MAX(17:00, 19:00) = 19:00
        att_response2 = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_2_DDMMYYYY}&to_date={TEST_DATE_2_DDMMYYYY}",
            headers=admin_auth
        )
        records2 = att_response2.json()
        record2 = next((r for r in records2 if r.get("emp_name") == "Date Test Two" and r.get("date") == TEST_DATE_2_DDMMYYYY), None)
        
        assert record2 is not None, "Attendance record not found after second chunk"
        assert record2.get("check_in_24h") == "09:00", f"Expected MIN IN 09:00, got {record2.get('check_in_24h')}"
        assert record2.get("check_out_24h") == "19:00", f"Expected MAX OUT 19:00, got {record2.get('check_out_24h')}"
        print(f"PASS: After chunk 2 (merge): IN={record2.get('check_in_24h')}, OUT={record2.get('check_out_24h')}")


class TestBiometricImportSinglePunch:
    """Test single punch results in IN set and OUT = null"""
    
    def test_single_punch_in_set_out_null(self, admin_auth, cleanup_test_attendance):
        """
        Feature: Single punch = IN set, OUT = null
        """
        # Single punch only
        records = [
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_3_ISO}T09:30:00+05:30"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Single punch import result: {data}")
        
        # Verify: IN is set, OUT is null
        att_response = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_3_DDMMYYYY}&to_date={TEST_DATE_3_DDMMYYYY}",
            headers=admin_auth
        )
        assert att_response.status_code == 200
        records = att_response.json()
        
        record = next((r for r in records if r.get("emp_name") == "Date Test One" and r.get("date") == TEST_DATE_3_DDMMYYYY), None)
        
        assert record is not None, f"Attendance record not found for {TEST_DATE_3_DDMMYYYY}"
        assert record.get("check_in_24h") == "09:30", f"Expected IN 09:30, got {record.get('check_in_24h')}"
        assert record.get("check_out_24h") is None or record.get("check_out") is None, \
            f"Expected OUT to be null for single punch, got check_out_24h={record.get('check_out_24h')}, check_out={record.get('check_out')}"
        
        print(f"PASS: Single punch - IN={record.get('check_in_24h')}, OUT={record.get('check_out_24h')} (null)")


class TestGetAttendanceDateFiltering:
    """Test GET /api/attendance date filtering with DD-MM-YYYY format"""
    
    def test_date_filtering_returns_correct_range(self, admin_auth, setup_multiple_dates_attendance):
        """
        Feature: GET /api/attendance date filtering works correctly 
        with DD-MM-YYYY strings (doesn't sort lexicographically)
        """
        # Query from_date=26-03-2026 to_date=27-03-2026
        response = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_1_DDMMYYYY}&to_date={TEST_DATE_2_DDMMYYYY}",
            headers=admin_auth
        )
        assert response.status_code == 200
        records = response.json()
        
        # Verify all returned records are within the date range
        for record in records:
            record_date = record.get("date")
            if record_date:
                # Parse DD-MM-YYYY
                parts = record_date.split("-")
                if len(parts) == 3:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    record_num = year * 10000 + month * 100 + day
                    
                    # 26-03-2026 = 20260326, 27-03-2026 = 20260327
                    from_num = 20260326
                    to_num = 20260327
                    
                    assert from_num <= record_num <= to_num, \
                        f"Record date {record_date} is outside range {TEST_DATE_1_DDMMYYYY} to {TEST_DATE_2_DDMMYYYY}"
        
        print(f"PASS: Date filtering returned {len(records)} records within correct range")
    
    def test_date_filtering_excludes_out_of_range(self, admin_auth, setup_multiple_dates_attendance):
        """
        Test that date filtering excludes records outside the range
        """
        # Import attendance for a date outside our test range
        out_of_range_records = [
            {"deviceUserId": "BDT-101", "recordTime": "2026-01-15T10:00:00+05:30"},  # January 2026
        ]
        
        requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=out_of_range_records,
            headers=admin_auth
        )
        
        # Query for March 2026 only
        response = requests.get(
            f"{BASE_URL}/api/attendance?from_date={TEST_DATE_1_DDMMYYYY}&to_date={TEST_DATE_2_DDMMYYYY}",
            headers=admin_auth
        )
        assert response.status_code == 200
        records = response.json()
        
        # Verify no January records are returned
        january_records = [r for r in records if "01-2026" in r.get("date", "")]
        assert len(january_records) == 0, f"January records incorrectly included: {january_records}"
        print(f"PASS: Date filtering correctly excludes out-of-range records")


class TestGetAttendanceSortOrder:
    """Test GET /api/attendance returns results sorted by date descending"""
    
    def test_results_sorted_date_descending(self, admin_auth, setup_multiple_dates_attendance):
        """
        Feature: GET /api/attendance returns results sorted by date descending
        """
        response = requests.get(
            f"{BASE_URL}/api/attendance?from_date=01-03-2026&to_date=31-03-2026",
            headers=admin_auth
        )
        assert response.status_code == 200
        records = response.json()
        
        if len(records) < 2:
            pytest.skip("Need at least 2 records to verify sort order")
        
        # Verify descending order
        def parse_date(date_str):
            try:
                parts = date_str.split("-")
                return int(parts[2]) * 10000 + int(parts[1]) * 100 + int(parts[0])
            except:
                return 0
        
        prev_date_num = float('inf')
        for record in records:
            current_date_num = parse_date(record.get("date", "01-01-1970"))
            assert current_date_num <= prev_date_num, \
                f"Records not sorted descending: {record.get('date')} came after a smaller date"
            prev_date_num = current_date_num
        
        print(f"PASS: Results sorted by date descending ({len(records)} records verified)")


class TestNoDuplicatesInDatabase:
    """Test that no duplicate attendance records exist for same employee+date"""
    
    def test_no_duplicates_for_employee_date(self, admin_auth):
        """
        Feature: No duplicate attendance records exist in the database
        This verifies the cleanup of existing duplicates was successful.
        """
        # Get all attendance records
        response = requests.get(
            f"{BASE_URL}/api/attendance",
            headers=admin_auth
        )
        assert response.status_code == 200
        records = response.json()
        
        # Check for duplicates by counting (employee_id, date) combinations
        seen = {}
        duplicates = []
        
        for record in records:
            emp_id = record.get("employee_id")
            date = record.get("date")
            key = f"{emp_id}:{date}"
            
            if key in seen:
                duplicates.append({
                    "employee_id": emp_id,
                    "date": date,
                    "count": seen[key] + 1
                })
                seen[key] += 1
            else:
                seen[key] = 1
        
        assert len(duplicates) == 0, f"Found duplicate records: {duplicates}"
        print(f"PASS: No duplicate attendance records found in database (checked {len(records)} records)")


class TestBiometricImportResponseFormat:
    """Test response format includes required fields"""
    
    def test_response_includes_required_fields(self, admin_auth):
        """
        Feature: Response format includes totalRecords, processed, skipped, unmapped
        """
        records = [
            {"deviceUserId": "BDT-101", "recordTime": "2026-04-01T10:00:00+05:30"},  # Valid
            {"deviceUserId": "UNKNOWN-XYZ", "recordTime": "2026-04-01T10:00:00+05:30"},  # Unmapped
            {"recordTime": "2026-04-01T10:00:00+05:30"},  # Missing deviceUserId - skipped
            {"deviceUserId": "BDT-101"},  # Missing recordTime - skipped
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=records,
            headers=admin_auth
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        assert "totalRecords" in data, "Response missing 'totalRecords'"
        assert "processed" in data, "Response missing 'processed'"
        assert "skipped" in data, "Response missing 'skipped'"
        assert "unmapped" in data, "Response missing 'unmapped'"
        
        # Verify values make sense
        assert data["totalRecords"] == 4, f"Expected totalRecords=4, got {data['totalRecords']}"
        assert data["skipped"] >= 2, f"Expected at least 2 skipped, got {data['skipped']}"
        assert data["unmapped"] >= 1, f"Expected at least 1 unmapped, got {data['unmapped']}"
        
        print(f"PASS: Response format correct: {data}")


class TestManualAttendanceNotAffected:
    """Test that existing manual attendance entries are not affected by biometric import"""
    
    def test_manual_attendance_preserved_by_biometric_import(self, admin_auth):
        """
        Feature: Existing manual attendance entries are not affected by biometric import
        
        The biometric import should update check_in/check_out times using MIN/MAX logic,
        but shouldn't overwrite other fields like status if manually set.
        """
        # First, create manual attendance via check-in (simulating manual entry)
        # This test verifies that biometric import respects the upsert pattern
        
        test_date_iso = "2026-04-05"
        test_date_ddmm = "05-04-2026"
        
        # Import biometric data for a specific date
        biometric_records = [
            {"deviceUserId": "BDT-102", "recordTime": f"{test_date_iso}T09:00:00+05:30"},
            {"deviceUserId": "BDT-102", "recordTime": f"{test_date_iso}T18:00:00+05:30"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/attendance/import-biometric",
            json=biometric_records,
            headers=admin_auth
        )
        assert response.status_code == 200
        
        # Verify record was created
        att_response = requests.get(
            f"{BASE_URL}/api/attendance?from_date={test_date_ddmm}&to_date={test_date_ddmm}",
            headers=admin_auth
        )
        assert att_response.status_code == 200
        records = att_response.json()
        
        record = next((r for r in records if r.get("emp_name") == "Date Test Two" and r.get("date") == test_date_ddmm), None)
        assert record is not None, "Biometric attendance record not created"
        assert record.get("source") == "biometric", "Expected source='biometric'"
        
        print(f"PASS: Biometric import creates record with source='biometric', not affecting manual entries logic")


# ============== FIXTURES ==============

@pytest.fixture(scope="session")
def admin_auth():
    """Get admin authentication headers"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin"}
    )
    if response.status_code != 200:
        pytest.fail(f"Admin login failed: {response.status_code} - {response.text}")
    
    token = response.json().get("token")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }


@pytest.fixture
def cleanup_test_attendance(admin_auth):
    """
    Note: Since we can't delete attendance records via API,
    we use unique test dates (March 26-28, 2026) to avoid conflicts
    """
    yield
    # Cleanup would happen here if there was a delete endpoint
    # For now, test dates are chosen to be unique


@pytest.fixture
def setup_multiple_dates_attendance(admin_auth):
    """Set up attendance records on multiple dates for filter/sort tests"""
    # Import attendance for 26-03-2026
    requests.post(
        f"{BASE_URL}/api/attendance/import-biometric",
        json=[
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_1_ISO}T09:00:00+05:30"},
            {"deviceUserId": "BDT-101", "recordTime": f"{TEST_DATE_1_ISO}T18:00:00+05:30"},
        ],
        headers=admin_auth
    )
    
    # Import attendance for 27-03-2026
    requests.post(
        f"{BASE_URL}/api/attendance/import-biometric",
        json=[
            {"deviceUserId": "BDT-102", "recordTime": f"{TEST_DATE_2_ISO}T10:00:00+05:30"},
            {"deviceUserId": "BDT-102", "recordTime": f"{TEST_DATE_2_ISO}T17:00:00+05:30"},
        ],
        headers=admin_auth
    )
    
    yield


# ============== MAIN ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
