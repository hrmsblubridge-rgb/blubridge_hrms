"""
Test Employee ID (custom_employee_id) and Biometric ID fields
Tests for the new employee fields and bulk import functionality
"""

import pytest
import requests
import os
import csv
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDENTIALS = {"username": "admin", "password": "admin"}

class TestEmployeeFieldsAPI:
    """Tests for Employee ID and Biometric ID fields in API"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDENTIALS)
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_01_login_success(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDENTIALS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print("✓ Admin login successful")
    
    def test_02_get_departments(self, auth_headers):
        """Get available departments for test data"""
        response = requests.get(f"{BASE_URL}/api/departments", headers=auth_headers)
        assert response.status_code == 200
        departments = response.json()
        assert len(departments) > 0, "No departments found"
        print(f"✓ Found {len(departments)} departments")
    
    def test_03_get_teams(self, auth_headers):
        """Get available teams for test data"""
        response = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        assert response.status_code == 200
        teams = response.json()
        assert len(teams) > 0, "No teams found"
        print(f"✓ Found {len(teams)} teams")
    
    def test_04_create_employee_with_new_fields(self, auth_headers):
        """Test creating employee with custom_employee_id and biometric_id"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        # Get department and team
        dept_res = requests.get(f"{BASE_URL}/api/departments", headers=auth_headers)
        departments = dept_res.json()
        team_res = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        teams = team_res.json()
        
        payload = {
            "full_name": f"Test Employee {unique_id}",
            "official_email": f"test_{unique_id}@company.com",
            "phone_number": "9876543210",
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Software Engineer",
            "employment_type": "Full-time",
            "tier_level": "Mid",
            "work_location": "Office",
            "shift_type": "General",
            "monthly_salary": 50000,
            "user_role": "employee",
            "login_enabled": True,
            "custom_employee_id": f"EID-TEST-{unique_id}",
            "biometric_id": f"BIO-TEST-{unique_id}"
        }
        
        response = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload)
        assert response.status_code in [200, 201], f"Failed to create employee: {response.text}"
        
        data = response.json()
        assert data.get("custom_employee_id") == payload["custom_employee_id"], "custom_employee_id not saved"
        assert data.get("biometric_id") == payload["biometric_id"], "biometric_id not saved"
        print(f"✓ Created employee with Employee ID: {data.get('custom_employee_id')}, Biometric ID: {data.get('biometric_id')}")
    
    def test_05_get_employee_verify_fields(self, auth_headers):
        """Test that created employee has the new fields"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        dept_res = requests.get(f"{BASE_URL}/api/departments", headers=auth_headers)
        departments = dept_res.json()
        team_res = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        teams = team_res.json()
        
        payload = {
            "full_name": f"Verify Fields {unique_id}",
            "official_email": f"verify_{unique_id}@company.com",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Tester",
            "custom_employee_id": f"VERIFY-{unique_id}",
            "biometric_id": f"BIOVER-{unique_id}"
        }
        
        create_res = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload)
        assert create_res.status_code in [200, 201], f"Failed: {create_res.text}"
        employee_id = create_res.json()["id"]
        
        # Now GET the employee
        response = requests.get(f"{BASE_URL}/api/employees/{employee_id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("custom_employee_id") == payload["custom_employee_id"], f"Expected {payload['custom_employee_id']}, got {data.get('custom_employee_id')}"
        assert data.get("biometric_id") == payload["biometric_id"], f"Expected {payload['biometric_id']}, got {data.get('biometric_id')}"
        print(f"✓ GET employee returns custom_employee_id and biometric_id correctly")
    
    def test_06_duplicate_employee_id_rejected(self, auth_headers):
        """Test that duplicate custom_employee_id is rejected"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        dept_res = requests.get(f"{BASE_URL}/api/departments", headers=auth_headers)
        departments = dept_res.json()
        team_res = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        teams = team_res.json()
        
        employee_id_val = f"DUP-EID-{unique_id}"
        
        # Create first employee
        payload1 = {
            "full_name": f"First Employee {unique_id}",
            "official_email": f"first_{unique_id}@company.com",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Developer",
            "custom_employee_id": employee_id_val,
            "biometric_id": f"BIO-FIRST-{unique_id}"
        }
        
        res1 = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload1)
        assert res1.status_code in [200, 201], f"First create failed: {res1.text}"
        
        # Try to create second with same custom_employee_id
        payload2 = {
            "full_name": f"Second Employee {unique_id}",
            "official_email": f"second_{unique_id}@company.com",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Developer",
            "custom_employee_id": employee_id_val,  # Duplicate!
            "biometric_id": f"BIO-SECOND-{unique_id}"
        }
        
        res2 = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload2)
        assert res2.status_code == 400, f"Expected 400 for duplicate Employee ID, got {res2.status_code}: {res2.text}"
        assert "Employee ID" in res2.text or "custom_employee_id" in res2.text.lower() or "already exists" in res2.text.lower()
        print(f"✓ Duplicate Employee ID correctly rejected with 400")
    
    def test_07_duplicate_biometric_id_rejected(self, auth_headers):
        """Test that duplicate biometric_id is rejected"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        dept_res = requests.get(f"{BASE_URL}/api/departments", headers=auth_headers)
        departments = dept_res.json()
        team_res = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        teams = team_res.json()
        
        biometric_id_val = f"DUP-BIO-{unique_id}"
        
        # Create first employee
        payload1 = {
            "full_name": f"Bio First {unique_id}",
            "official_email": f"biofirst_{unique_id}@company.com",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Developer",
            "custom_employee_id": f"EID-BIO1-{unique_id}",
            "biometric_id": biometric_id_val
        }
        
        res1 = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload1)
        assert res1.status_code in [200, 201], f"First create failed: {res1.text}"
        
        # Try to create second with same biometric_id
        payload2 = {
            "full_name": f"Bio Second {unique_id}",
            "official_email": f"biosecond_{unique_id}@company.com",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Developer",
            "custom_employee_id": f"EID-BIO2-{unique_id}",
            "biometric_id": biometric_id_val  # Duplicate!
        }
        
        res2 = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload2)
        assert res2.status_code == 400, f"Expected 400 for duplicate Biometric ID, got {res2.status_code}: {res2.text}"
        assert "Biometric ID" in res2.text or "biometric_id" in res2.text.lower() or "already exists" in res2.text.lower()
        print(f"✓ Duplicate Biometric ID correctly rejected with 400")
    
    def test_08_update_employee_with_new_fields(self, auth_headers):
        """Test updating employee custom_employee_id and biometric_id"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        dept_res = requests.get(f"{BASE_URL}/api/departments", headers=auth_headers)
        departments = dept_res.json()
        team_res = requests.get(f"{BASE_URL}/api/teams", headers=auth_headers)
        teams = team_res.json()
        
        # Create employee first
        payload = {
            "full_name": f"Update Test {unique_id}",
            "official_email": f"update_{unique_id}@company.com",
            "date_of_joining": "2026-01-01",
            "department": departments[0]["name"],
            "team": teams[0]["name"],
            "designation": "Developer",
            "custom_employee_id": f"UPD-ORIG-{unique_id}",
            "biometric_id": f"BIO-ORIG-{unique_id}"
        }
        
        create_res = requests.post(f"{BASE_URL}/api/employees", headers=auth_headers, json=payload)
        assert create_res.status_code in [200, 201], f"Create failed: {create_res.text}"
        employee_id = create_res.json()["id"]
        
        # Update the fields
        update_payload = {
            "custom_employee_id": f"UPD-NEW-{unique_id}",
            "biometric_id": f"BIO-NEW-{unique_id}"
        }
        
        update_res = requests.put(f"{BASE_URL}/api/employees/{employee_id}", headers=auth_headers, json=update_payload)
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        # Verify the update
        get_res = requests.get(f"{BASE_URL}/api/employees/{employee_id}", headers=auth_headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert data.get("custom_employee_id") == update_payload["custom_employee_id"]
        assert data.get("biometric_id") == update_payload["biometric_id"]
        print(f"✓ Employee update with new fields works correctly")
    
    def test_09_employees_list_includes_new_fields(self, auth_headers):
        """Test that employees list includes custom_employee_id and biometric_id"""
        response = requests.get(f"{BASE_URL}/api/employees", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        
        employees = data["employees"]
        if len(employees) > 0:
            emp = employees[0]
            print(f"✓ Employee list returns correctly. Sample employee has custom_employee_id: {emp.get('custom_employee_id')}, biometric_id: {emp.get('biometric_id')}")
    
    def test_10_import_template_download(self, auth_headers):
        """Test downloading the import template"""
        response = requests.get(f"{BASE_URL}/api/employees/import-template", headers=auth_headers)
        assert response.status_code == 200, f"Import template download failed: {response.status_code} - {response.text}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type or "excel" in content_type or "application/vnd" in content_type, f"Unexpected content type: {content_type}"
        
        # Check content disposition
        disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in disposition and "xlsx" in disposition, f"Unexpected disposition: {disposition}"
        
        print(f"✓ Import template downloads correctly as Excel file")
    
    def test_11_bulk_import_endpoint_exists(self, auth_headers):
        """Test that bulk import endpoint exists and accepts CSV"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        csv_content = f"""Employee Name,Employee ID,Biometric ID,Email,Phone,Gender,Date of Birth,Date of Joining,Department,Team,Designation,Employment Type,Tier Level,Work Location,Shift Type,Monthly Salary,User Role
Test Bulk {unique_id},BULK-{unique_id},BIOBULK-{unique_id},bulk{unique_id}@test.com,9876543210,Male,1990-01-01,2026-01-01,Research Unit,Data,Developer,Full-time,Mid,Office,General,50000,employee"""
        
        files = {"file": ("test.csv", csv_content, "text/csv")}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(f"{BASE_URL}/api/employees/bulk-import", headers=headers, files=files)
        
        if response.status_code == 404:
            pytest.fail("Bulk import endpoint /api/employees/bulk-import does not exist (404)")
        elif response.status_code == 405:
            pytest.fail("Bulk import endpoint exists but POST method not allowed (405)")
        
        assert response.status_code == 200, f"Bulk import failed: {response.text}"
        data = response.json()
        
        assert "total" in data, "Response missing 'total'"
        assert "success" in data, "Response missing 'success'"
        assert "failed" in data, "Response missing 'failed'"
        
        print(f"✓ Bulk import endpoint works. Total: {data.get('total')}, Success: {data.get('success')}, Failed: {data.get('failed')}")
    
    def test_12_bulk_import_validates_required_fields(self, auth_headers):
        """Test bulk import validates required fields"""
        # CSV with missing required fields
        csv_content = """Employee Name,Employee ID,Biometric ID,Email,Phone,Gender,Date of Birth,Date of Joining,Department,Team,Designation
,,,missing@test.com,,,,2026-01-01,Research Unit,Data,Developer"""
        
        files = {"file": ("test.csv", csv_content, "text/csv")}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(f"{BASE_URL}/api/employees/bulk-import", headers=headers, files=files)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("failed") >= 1, "Expected validation failure"
        assert len(data.get("errors", [])) >= 1, "Expected error details"
        
        errors_text = str(data.get("errors", []))
        assert "required" in errors_text.lower() or "Employee Name" in errors_text or "Employee ID" in errors_text
        print(f"✓ Bulk import validates required fields. Errors: {data.get('errors')}")
    
    def test_13_bulk_import_rejects_duplicates(self, auth_headers):
        """Test bulk import rejects duplicate Employee IDs and Biometric IDs within file"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        # CSV with duplicate Employee ID - using valid department and team from database
        csv_content = f"""Employee Name,Employee ID,Biometric ID,Email,Date of Joining,Department,Team,Designation
Dup Test 1,DUP-BULK-{unique_id},BIO-DUP1-{unique_id},dup1{unique_id}@test.com,2026-01-01,Research Unit,Data,Developer
Dup Test 2,DUP-BULK-{unique_id},BIO-DUP2-{unique_id},dup2{unique_id}@test.com,2026-01-01,Research Unit,Data,Developer"""
        
        files = {"file": ("test.csv", csv_content, "text/csv")}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(f"{BASE_URL}/api/employees/bulk-import", headers=headers, files=files)
        assert response.status_code == 200
        data = response.json()
        
        # At least one should fail due to duplicate
        assert data.get("success", 0) >= 1, "At least first record should succeed"
        assert data.get("failed", 0) >= 1, "Second record with duplicate ID should fail"
        
        errors_text = str(data.get("errors", []))
        assert "duplicate" in errors_text.lower() or "already exists" in errors_text.lower() or "Employee ID" in errors_text
        print(f"✓ Bulk import rejects duplicates. Success: {data.get('success')}, Failed: {data.get('failed')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
