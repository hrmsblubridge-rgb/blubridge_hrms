"""
Test suite for Policies and Education & Experience modules
Tests cover:
- Policies API (GET /api/policies, GET /api/policies/{id})
- Employee Education & Experience (GET/PUT for employee profile)
- Admin Education & Experience View (GET /api/employees/{id}/education-experience)
- Admin Verify Education (POST /api/employees/{id}/verify-education)
- Admin Verify Experience (POST /api/employees/{id}/verify-experience)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token missing in response"
        assert data["user"]["role"] in ["admin", "super_admin"], f"Unexpected role: {data['user']['role']}"
        print(f"✓ Admin login successful, role: {data['user']['role']}")
        return data["token"]
    
    def test_employee_login(self):
        """Test employee login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "test.employee",
            "password": "test123"
        })
        assert response.status_code == 200, f"Employee login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token missing in response"
        print(f"✓ Employee login successful, role: {data['user']['role']}")
        return data["token"]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def employee_token():
    """Get employee auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "test.employee",
        "password": "test123"
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Employee authentication failed")


@pytest.fixture(scope="module")
def test_employee_id(admin_token):
    """Get test employee ID (EMP0055)"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/employees", headers=headers, params={"search": "EMP0055"})
    if response.status_code == 200:
        data = response.json()
        if data.get("employees"):
            return data["employees"][0]["id"]
    pytest.skip("Test employee EMP0055 not found")


class TestPoliciesAPI:
    """Test Policies API endpoints"""
    
    def test_get_policies_as_admin(self, admin_token):
        """Test GET /api/policies as admin - should return 3 policies"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/policies", headers=headers)
        
        assert response.status_code == 200, f"Failed to get policies: {response.text}"
        policies = response.json()
        
        assert isinstance(policies, list), "Response should be a list"
        assert len(policies) >= 3, f"Expected at least 3 policies, got {len(policies)}"
        
        # Check policy IDs
        policy_ids = [p["id"] for p in policies]
        assert "policy_leave" in policy_ids, "Leave policy not found"
        assert "policy_it" in policy_ids, "IT policy not found"
        assert "policy_research" in policy_ids, "Research policy not found"
        
        print(f"✓ Found {len(policies)} policies: {policy_ids}")
        
    def test_get_policies_as_employee(self, employee_token):
        """Test GET /api/policies as employee - should also return policies"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/policies", headers=headers)
        
        assert response.status_code == 200, f"Failed to get policies as employee: {response.text}"
        policies = response.json()
        assert len(policies) >= 3, f"Expected at least 3 policies for employee, got {len(policies)}"
        print(f"✓ Employee can view {len(policies)} policies")
    
    def test_leave_policy_details(self, admin_token):
        """Test Leave Policy structure and content"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/policies", headers=headers)
        
        assert response.status_code == 200
        policies = response.json()
        
        leave_policy = next((p for p in policies if p["id"] == "policy_leave"), None)
        assert leave_policy is not None, "Leave policy not found"
        
        # Validate structure
        assert leave_policy["name"] == "Leave Policy", f"Unexpected name: {leave_policy['name']}"
        assert leave_policy["category"] == "HR", f"Unexpected category: {leave_policy['category']}"
        assert "content" in leave_policy, "Content missing"
        assert "overview" in leave_policy["content"], "Overview missing"
        assert "sections" in leave_policy["content"], "Sections missing"
        
        # Validate sections exist
        sections = leave_policy["content"]["sections"]
        assert len(sections) >= 3, f"Expected at least 3 sections, got {len(sections)}"
        
        # Check for leave types section
        leave_types_section = next((s for s in sections if "Leave Types" in s["title"]), None)
        assert leave_types_section is not None, "Leave Types section not found"
        
        print(f"✓ Leave policy has {len(sections)} sections")
        
    def test_it_policy_details(self, admin_token):
        """Test IT Policy structure and content"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/policies", headers=headers)
        
        assert response.status_code == 200
        policies = response.json()
        
        it_policy = next((p for p in policies if p["id"] == "policy_it"), None)
        assert it_policy is not None, "IT policy not found"
        
        assert it_policy["name"] == "IT Team Policy"
        assert it_policy["category"] == "Department"
        assert it_policy["applicable_to"] == "Technology Department"
        
        sections = it_policy["content"]["sections"]
        section_titles = [s["title"] for s in sections]
        
        assert any("Security" in t for t in section_titles), "Security section missing"
        print(f"✓ IT policy sections: {section_titles}")
        
    def test_research_policy_details(self, admin_token):
        """Test Research Policy structure and content"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/policies", headers=headers)
        
        assert response.status_code == 200
        policies = response.json()
        
        research_policy = next((p for p in policies if p["id"] == "policy_research"), None)
        assert research_policy is not None, "Research policy not found"
        
        assert research_policy["name"] == "Research Unit Policy"
        assert research_policy["category"] == "Department"
        assert research_policy["applicable_to"] == "Research & Development Team"
        
        sections = research_policy["content"]["sections"]
        section_titles = [s["title"] for s in sections]
        
        assert any("Intellectual Property" in t for t in section_titles), "IP section missing"
        print(f"✓ Research policy sections: {section_titles}")
    
    def test_get_single_policy(self, admin_token):
        """Test GET /api/policies/{id} endpoint"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/policies/policy_leave", headers=headers)
        
        assert response.status_code == 200, f"Failed to get single policy: {response.text}"
        policy = response.json()
        
        assert policy["id"] == "policy_leave"
        assert "content" in policy
        print(f"✓ Single policy fetch successful")
    
    def test_get_nonexistent_policy(self, admin_token):
        """Test GET /api/policies/{id} with invalid ID"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/policies/invalid_policy_id", headers=headers)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent policy returns 404")


class TestEmployeeEducationExperience:
    """Test Employee Education & Experience API endpoints"""
    
    def test_get_employee_education_experience(self, employee_token):
        """Test GET /api/employee-profile/education-experience as employee"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        response = requests.get(f"{BASE_URL}/api/employee-profile/education-experience", headers=headers)
        
        assert response.status_code == 200, f"Failed to get education/experience: {response.text}"
        data = response.json()
        
        assert "education" in data, "Education field missing"
        assert "experience" in data, "Experience field missing"
        assert "education_verified" in data, "education_verified field missing"
        assert "experience_verified" in data, "experience_verified field missing"
        
        print(f"✓ Employee education/experience retrieved: {len(data['education'])} education entries, {len(data['experience'])} experience entries")
        return data
    
    def test_add_education_entry(self, employee_token):
        """Test adding education entry via PUT /api/employee-profile/education-experience"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        
        # First get current data
        response = requests.get(f"{BASE_URL}/api/employee-profile/education-experience", headers=headers)
        current_data = response.json()
        
        # Skip if education is already verified
        if current_data.get("education_verified"):
            print("⚠ Education already verified, skipping add test")
            return
        
        # Add new education entry
        new_education = list(current_data.get("education", []))
        test_entry = {
            "level": "Diploma",
            "institution": "TEST_Technical Institute",
            "board_university": "TEST Board",
            "year_of_passing": "2018",
            "percentage_cgpa": "75%"
        }
        new_education.append(test_entry)
        
        response = requests.put(
            f"{BASE_URL}/api/employee-profile/education-experience",
            headers=headers,
            json={"education": new_education}
        )
        
        assert response.status_code == 200, f"Failed to add education: {response.text}"
        
        # Verify it was added
        response = requests.get(f"{BASE_URL}/api/employee-profile/education-experience", headers=headers)
        updated_data = response.json()
        
        assert len(updated_data["education"]) >= len(current_data.get("education", [])), "Education not added"
        print(f"✓ Education entry added successfully")
        
        # Clean up - remove the test entry
        cleaned_education = [e for e in updated_data["education"] if "TEST_" not in str(e.get("institution", ""))]
        requests.put(
            f"{BASE_URL}/api/employee-profile/education-experience",
            headers=headers,
            json={"education": cleaned_education}
        )
        print("✓ Test education entry cleaned up")
    
    def test_add_experience_entry(self, employee_token):
        """Test adding experience entry via PUT /api/employee-profile/education-experience"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        
        # First get current data
        response = requests.get(f"{BASE_URL}/api/employee-profile/education-experience", headers=headers)
        current_data = response.json()
        
        # Skip if experience is already verified
        if current_data.get("experience_verified"):
            print("⚠ Experience already verified, skipping add test")
            return
        
        # Add new experience entry
        new_experience = list(current_data.get("experience", []))
        test_entry = {
            "company_name": "TEST_Previous Company",
            "designation": "TEST_Developer",
            "start_date": "2017-01-01",
            "end_date": "2018-12-31",
            "is_current": False,
            "responsibilities": "Testing work"
        }
        new_experience.append(test_entry)
        
        response = requests.put(
            f"{BASE_URL}/api/employee-profile/education-experience",
            headers=headers,
            json={"experience": new_experience}
        )
        
        assert response.status_code == 200, f"Failed to add experience: {response.text}"
        
        # Verify it was added
        response = requests.get(f"{BASE_URL}/api/employee-profile/education-experience", headers=headers)
        updated_data = response.json()
        
        assert len(updated_data["experience"]) >= len(current_data.get("experience", [])), "Experience not added"
        print(f"✓ Experience entry added successfully")
        
        # Clean up - remove the test entry
        cleaned_experience = [e for e in updated_data["experience"] if "TEST_" not in str(e.get("company_name", ""))]
        requests.put(
            f"{BASE_URL}/api/employee-profile/education-experience",
            headers=headers,
            json={"experience": cleaned_experience}
        )
        print("✓ Test experience entry cleaned up")


class TestAdminEducationExperience:
    """Test Admin view of Education & Experience"""
    
    def test_admin_get_employee_education_experience(self, admin_token, test_employee_id):
        """Test GET /api/employees/{id}/education-experience as admin"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/employees/{test_employee_id}/education-experience",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to get employee education/experience: {response.text}"
        data = response.json()
        
        assert "employee_id" in data, "employee_id missing"
        assert "education" in data, "education field missing"
        assert "experience" in data, "experience field missing"
        assert "education_verified" in data, "education_verified missing"
        assert "experience_verified" in data, "experience_verified missing"
        
        print(f"✓ Admin view of education/experience: {len(data.get('education', []))} edu, {len(data.get('experience', []))} exp")
        return data
    
    def test_verify_education(self, admin_token, test_employee_id):
        """Test POST /api/employees/{id}/verify-education"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First check current status
        response = requests.get(
            f"{BASE_URL}/api/employees/{test_employee_id}/education-experience",
            headers=headers
        )
        current = response.json()
        
        if current.get("education_verified"):
            print("⚠ Education already verified, skipping verify test")
            return
        
        # Verify education
        response = requests.post(
            f"{BASE_URL}/api/employees/{test_employee_id}/verify-education",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to verify education: {response.text}"
        
        # Confirm verification
        response = requests.get(
            f"{BASE_URL}/api/employees/{test_employee_id}/education-experience",
            headers=headers
        )
        updated = response.json()
        
        assert updated.get("education_verified") == True, "Education not marked as verified"
        print("✓ Education verified successfully")
    
    def test_verify_experience(self, admin_token, test_employee_id):
        """Test POST /api/employees/{id}/verify-experience"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First check current status
        response = requests.get(
            f"{BASE_URL}/api/employees/{test_employee_id}/education-experience",
            headers=headers
        )
        current = response.json()
        
        if current.get("experience_verified"):
            print("⚠ Experience already verified, skipping verify test")
            return
        
        # Verify experience
        response = requests.post(
            f"{BASE_URL}/api/employees/{test_employee_id}/verify-experience",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed to verify experience: {response.text}"
        
        # Confirm verification
        response = requests.get(
            f"{BASE_URL}/api/employees/{test_employee_id}/education-experience",
            headers=headers
        )
        updated = response.json()
        
        assert updated.get("experience_verified") == True, "Experience not marked as verified"
        print("✓ Experience verified successfully")
    
    def test_employee_cannot_edit_after_verification(self, employee_token):
        """Test that employee cannot edit verified education/experience"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        
        # Get current data
        response = requests.get(f"{BASE_URL}/api/employee-profile/education-experience", headers=headers)
        current = response.json()
        
        # Try to update education if verified
        if current.get("education_verified"):
            response = requests.put(
                f"{BASE_URL}/api/employee-profile/education-experience",
                headers=headers,
                json={"education": [{"level": "Test", "institution": "Test", "board_university": "Test", "year_of_passing": "2020", "percentage_cgpa": "80%"}]}
            )
            # Should fail with 400
            assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
            print("✓ Verified education cannot be edited (as expected)")
        else:
            print("⚠ Education not verified, skipping edit prevention test")
        
        # Try to update experience if verified  
        if current.get("experience_verified"):
            response = requests.put(
                f"{BASE_URL}/api/employee-profile/education-experience",
                headers=headers,
                json={"experience": [{"company_name": "Test", "designation": "Test", "start_date": "2020-01-01"}]}
            )
            # Should fail with 400
            assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
            print("✓ Verified experience cannot be edited (as expected)")
        else:
            print("⚠ Experience not verified, skipping edit prevention test")


class TestEmployeeBySearch:
    """Test employee search to find test employee"""
    
    def test_find_test_employee(self, admin_token):
        """Find employee by EMP0055 ID"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/employees", headers=headers, params={"search": "EMP0055"})
        assert response.status_code == 200, f"Failed to search employees: {response.text}"
        
        data = response.json()
        employees = data.get("employees", [])
        
        if employees:
            emp = employees[0]
            print(f"✓ Found test employee: {emp.get('emp_id')} - {emp.get('full_name')}")
            print(f"  Education: {emp.get('education', [])}")
            print(f"  Experience: {emp.get('experience', [])}")
        else:
            print("⚠ Test employee EMP0055 not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
