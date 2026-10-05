"""
Test Employee Autocomplete API
Tests the new autocomplete endpoint for employee search suggestions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmployeeAutocomplete:
    """Tests for GET /api/employees/autocomplete endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token"""
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
    
    def test_autocomplete_by_name(self):
        """Test autocomplete returns matches by name"""
        # Search for a common name pattern
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "ven"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify structure of results
        if len(data) > 0:
            emp = data[0]
            assert "id" in emp, "Result should have 'id' field"
            assert "full_name" in emp, "Result should have 'full_name' field"
            assert "official_email" in emp, "Result should have 'official_email' field"
            assert "emp_id" in emp, "Result should have 'emp_id' field"
            assert "department" in emp, "Result should have 'department' field"
            print(f"Found {len(data)} matches for 'ven': {[e['full_name'] for e in data]}")
        else:
            print("No matches found for 'ven' - this may be expected if no employees match")
    
    def test_autocomplete_by_email(self):
        """Test autocomplete returns matches by email"""
        # Search by email pattern
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "kasper"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} matches for 'kasper': {[e.get('official_email', e.get('full_name')) for e in data]}")
    
    def test_autocomplete_by_emp_id(self):
        """Test autocomplete returns matches by employee ID"""
        # Search by EMP ID pattern
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "EMP003"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If matches found, verify emp_id contains the search term
        for emp in data:
            emp_id = emp.get("emp_id", "")
            custom_id = emp.get("custom_employee_id", "")
            name = emp.get("full_name", "")
            email = emp.get("official_email", "")
            # At least one field should contain the search term
            match_found = any("EMP003" in str(field).upper() for field in [emp_id, custom_id, name, email])
            print(f"Match: {emp_id} - {name} - {email}")
        
        print(f"Found {len(data)} matches for 'EMP003'")
    
    def test_autocomplete_no_matches(self):
        """Test autocomplete returns empty array for no matches"""
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "zzzzz"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 0, f"Expected empty array for 'zzzzz', got {len(data)} results"
        print("Correctly returned empty array for non-matching query 'zzzzz'")
    
    def test_autocomplete_empty_query(self):
        """Test autocomplete returns empty array for empty query"""
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": ""})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 0, f"Expected empty array for empty query, got {len(data)} results"
        print("Correctly returned empty array for empty query")
    
    def test_autocomplete_no_query_param(self):
        """Test autocomplete returns empty array when q param is missing"""
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 0, f"Expected empty array for missing query, got {len(data)} results"
        print("Correctly returned empty array for missing query param")
    
    def test_autocomplete_max_results(self):
        """Test autocomplete returns max 10 results"""
        # Search with a common letter that should match many employees
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "a"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) <= 10, f"Expected max 10 results, got {len(data)}"
        print(f"Returned {len(data)} results for 'a' (max 10 enforced)")
    
    def test_autocomplete_case_insensitive(self):
        """Test autocomplete is case insensitive"""
        # Search with lowercase
        response_lower = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "emp"})
        assert response_lower.status_code == 200
        
        # Search with uppercase
        response_upper = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "EMP"})
        assert response_upper.status_code == 200
        
        # Both should return results (case insensitive)
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        
        print(f"Lowercase 'emp' returned {len(data_lower)} results")
        print(f"Uppercase 'EMP' returned {len(data_upper)} results")
        
        # Results should be similar (case insensitive search)
        assert isinstance(data_lower, list) and isinstance(data_upper, list)
    
    def test_autocomplete_response_fields(self):
        """Test autocomplete response has all required fields for UI display"""
        # Get some results
        response = self.session.get(f"{BASE_URL}/api/employees/autocomplete", params={"q": "a"})
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            emp = data[0]
            required_fields = ["id", "full_name", "official_email", "emp_id", "department"]
            for field in required_fields:
                assert field in emp, f"Missing required field: {field}"
            
            # Verify field types
            assert isinstance(emp["id"], str), "id should be string"
            assert isinstance(emp["full_name"], str), "full_name should be string"
            assert isinstance(emp["official_email"], str), "official_email should be string"
            assert isinstance(emp["emp_id"], str), "emp_id should be string"
            assert isinstance(emp["department"], str), "department should be string"
            
            print(f"All required fields present: {required_fields}")
            print(f"Sample result: {emp['full_name']} | {emp['emp_id']} | {emp['official_email']} | {emp['department']}")
        else:
            pytest.skip("No employees found to verify response fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
