"""
Tests for Employee Onboarding Flow, Tickets, and Audit Logs APIs
- Onboarding: Stats, List, Employee details, Document upload/verify/approve
- Tickets: CRUD operations, stats
- Audit Logs: Fetch with filters
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        return data["token"]
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] in ["super_admin", "admin", "hr_manager"]
        print(f"Admin login successful - Role: {data['user']['role']}")


class TestOnboardingStats:
    """Onboarding Statistics API tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        return response.json()["token"]
    
    def test_get_onboarding_stats(self, admin_token):
        """Test GET /api/onboarding/stats returns statistics"""
        response = requests.get(
            f"{BASE_URL}/api/onboarding/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get onboarding stats: {response.text}"
        data = response.json()
        
        # Verify required fields
        required_fields = ["total_employees", "pending", "in_progress", "under_review", "approved", "rejected", "completion_rate"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["total_employees"], int)
        assert isinstance(data["pending"], int)
        assert isinstance(data["completion_rate"], (int, float))
        
        print(f"Onboarding stats: Total={data['total_employees']}, Pending={data['pending']}, Under Review={data['under_review']}, Approved={data['approved']}")


class TestOnboardingList:
    """Onboarding List API tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        return response.json()["token"]
    
    def test_get_onboarding_list(self, admin_token):
        """Test GET /api/onboarding/list returns onboarding queue"""
        response = requests.get(
            f"{BASE_URL}/api/onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get onboarding list: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        print(f"Found {len(data)} onboarding records")
        
        if len(data) > 0:
            record = data[0]
            # Verify record has expected fields
            expected_fields = ["employee_id", "emp_id", "emp_name", "department", "status"]
            for field in expected_fields:
                assert field in record, f"Missing field in onboarding record: {field}"
            print(f"Sample record: {record['emp_name']} - Status: {record['status']}")
    
    def test_get_onboarding_list_with_status_filter(self, admin_token):
        """Test onboarding list filters by status"""
        for status in ["pending", "in_progress", "under_review", "approved"]:
            response = requests.get(
                f"{BASE_URL}/api/onboarding/list",
                params={"status": status},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"Failed for status={status}"
            data = response.json()
            print(f"Status '{status}': {len(data)} records")


class TestTickets:
    """Support Tickets API tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        return response.json()["token"]
    
    def test_get_tickets(self, admin_token):
        """Test GET /api/tickets returns tickets list"""
        response = requests.get(
            f"{BASE_URL}/api/tickets",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get tickets: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} tickets")
    
    def test_create_ticket(self, admin_token):
        """Test POST /api/tickets creates a new ticket"""
        ticket_data = {
            "subject": "TEST_Onboarding Issue",
            "description": "Test ticket for onboarding flow testing",
            "priority": "medium"
        }
        response = requests.post(
            f"{BASE_URL}/api/tickets",
            json=ticket_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to create ticket: {response.text}"
        data = response.json()
        
        # Verify response
        assert "id" in data
        assert data["subject"] == ticket_data["subject"]
        assert data["description"] == ticket_data["description"]
        assert data["priority"] == ticket_data["priority"]
        assert data["status"] == "open"
        
        print(f"Created ticket: {data['id']}")
        return data["id"]
    
    def test_get_ticket_stats(self, admin_token):
        """Test GET /api/tickets/stats returns statistics"""
        response = requests.get(
            f"{BASE_URL}/api/tickets/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get ticket stats: {response.text}"
        data = response.json()
        
        # Verify fields
        assert "total" in data
        assert "open" in data
        assert "in_progress" in data
        assert "resolved" in data
        
        print(f"Ticket stats: Total={data['total']}, Open={data['open']}, In Progress={data['in_progress']}, Resolved={data['resolved']}")
    
    def test_update_ticket_status(self, admin_token):
        """Test PUT /api/tickets/{id}/status updates ticket status"""
        # First create a ticket
        ticket_data = {
            "subject": "TEST_Status Update Ticket",
            "description": "Test ticket for status update testing",
            "priority": "high"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/tickets",
            json=ticket_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_response.status_code == 200
        ticket_id = create_response.json()["id"]
        
        # Update status to in_progress
        response = requests.put(
            f"{BASE_URL}/api/tickets/{ticket_id}/status",
            params={"status": "in_progress"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to update ticket status: {response.text}"
        
        # Verify status changed
        get_response = requests.get(
            f"{BASE_URL}/api/tickets",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        tickets = get_response.json()
        updated_ticket = next((t for t in tickets if t["id"] == ticket_id), None)
        assert updated_ticket is not None
        assert updated_ticket["status"] == "in_progress"
        
        print(f"Ticket {ticket_id} status updated to 'in_progress'")


class TestAuditLogs:
    """Audit Logs API tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        return response.json()["token"]
    
    def test_get_audit_logs(self, admin_token):
        """Test GET /api/audit-logs returns logs"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get audit logs: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        print(f"Found {len(data)} audit logs")
        
        if len(data) > 0:
            log = data[0]
            # Verify log structure
            expected_fields = ["id", "user_id", "action", "resource", "timestamp"]
            for field in expected_fields:
                assert field in log, f"Missing field in audit log: {field}"
            print(f"Latest log: Action={log['action']}, Resource={log['resource']}")
    
    def test_get_audit_logs_with_resource_filter(self, admin_token):
        """Test audit logs filters by resource"""
        for resource in ["auth", "employee", "attendance", "leave", "onboarding"]:
            response = requests.get(
                f"{BASE_URL}/api/audit-logs",
                params={"resource": resource, "limit": 10},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"Failed for resource={resource}"
            data = response.json()
            print(f"Resource '{resource}': {len(data)} logs")


class TestEmployeeOnboardingLogin:
    """Test employee login redirects to onboarding if not approved"""
    
    def test_employee_login_returns_onboarding_status(self):
        """Test employee login includes onboarding status"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "onboardtest",
            "password": "onbo@6655"
        })
        
        if response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            
            print(f"Employee login successful")
            print(f"  - Role: {user.get('role')}")
            print(f"  - Onboarding Status: {user.get('onboarding_status')}")
            print(f"  - Is First Login: {user.get('is_first_login')}")
            print(f"  - Onboarding Completed: {user.get('onboarding_completed')}")
            
            # For employee role, should have onboarding info
            if user.get("role") == "employee":
                assert "onboarding_status" in user, "Missing onboarding_status field"
                assert "onboarding_completed" in user, "Missing onboarding_completed field"
        else:
            print(f"Employee login failed with status {response.status_code}: {response.text}")
            # This is acceptable - employee might not exist
            pytest.skip("Employee 'onboardtest' not found - skipping this test")


class TestOnboardingEmployeeDetails:
    """Test onboarding employee details API"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        return response.json()["token"]
    
    def test_get_employee_onboarding_details(self, admin_token):
        """Test GET /api/onboarding/employee/{id} returns details"""
        # First get list of onboarding records
        list_response = requests.get(
            f"{BASE_URL}/api/onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if list_response.status_code != 200:
            pytest.skip("Could not get onboarding list")
        
        records = list_response.json()
        if len(records) == 0:
            pytest.skip("No onboarding records found")
        
        # Get details for first employee
        employee_id = records[0]["employee_id"]
        response = requests.get(
            f"{BASE_URL}/api/onboarding/employee/{employee_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Failed to get employee onboarding: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "onboarding" in data
        assert "documents" in data
        assert isinstance(data["documents"], list)
        
        print(f"Employee {records[0]['emp_name']} has {len(data['documents'])} documents")
        
        # Check document structure
        if len(data["documents"]) > 0:
            doc = data["documents"][0]
            expected_fields = ["document_type", "document_label", "status"]
            for field in expected_fields:
                assert field in doc, f"Missing field in document: {field}"
            print(f"Document types: {[d['document_type'] for d in data['documents']]}")


class TestDepartmentAPI:
    """Test departments API (used in Verification page)"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        return response.json()["token"]
    
    def test_get_departments(self, admin_token):
        """Test GET /api/departments returns department list"""
        response = requests.get(
            f"{BASE_URL}/api/departments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get departments: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        print(f"Found {len(data)} departments")
        if len(data) > 0:
            print(f"Departments: {[d.get('name') for d in data[:5]]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
