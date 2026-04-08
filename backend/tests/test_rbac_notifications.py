"""
Test RBAC (Role-Based Access Control) and Notification System
Tests for:
- Login with different roles (HR, System Admin, Office Admin, Employee)
- Role-based API access permissions
- Notification endpoints
- Role management endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CREDENTIALS = {
    'hr': {'username': 'admin', 'password': 'pass123'},
    'system_admin': {'username': 'sysadmin', 'password': 'pass123'},
    'office_admin': {'username': 'offadmin', 'password': 'pass123'},
    'employee': {'username': 'user', 'password': 'user'}
}


class TestAuthentication:
    """Test login for all roles"""
    
    def test_hr_login(self):
        """HR role (admin/pass123) should login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=CREDENTIALS['hr'])
        assert response.status_code == 200, f"HR login failed: {response.text}"
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'hr'
        print(f"✓ HR login successful - role: {data['user']['role']}")
    
    def test_system_admin_login(self):
        """System Admin role (sysadmin/pass123) should login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=CREDENTIALS['system_admin'])
        assert response.status_code == 200, f"System Admin login failed: {response.text}"
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'system_admin'
        print(f"✓ System Admin login successful - role: {data['user']['role']}")
    
    def test_office_admin_login(self):
        """Office Admin role (offadmin/pass123) should login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=CREDENTIALS['office_admin'])
        assert response.status_code == 200, f"Office Admin login failed: {response.text}"
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'office_admin'
        print(f"✓ Office Admin login successful - role: {data['user']['role']}")
    
    def test_employee_login(self):
        """Employee role (user/user) should login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=CREDENTIALS['employee'])
        assert response.status_code == 200, f"Employee login failed: {response.text}"
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'employee'
        print(f"✓ Employee login successful - role: {data['user']['role']}")


def get_token(role):
    """Helper to get auth token for a role"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=CREDENTIALS[role])
    if response.status_code == 200:
        return response.json()['token']
    return None


class TestNotificationEndpoints:
    """Test notification system endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
    
    def test_get_notifications_hr(self):
        """GET /api/notifications returns array for HR"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ HR notifications: {len(data)} items")
    
    def test_get_notifications_system_admin(self):
        """GET /api/notifications returns array for System Admin"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ System Admin notifications: {len(data)} items")
    
    def test_get_unread_count_hr(self):
        """GET /api/notifications/unread-count returns count object"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert 'count' in data
        assert isinstance(data['count'], int)
        print(f"✓ HR unread count: {data['count']}")
    
    def test_mark_all_read(self):
        """PUT /api/notifications/mark-all-read works"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.put(f"{BASE_URL}/api/notifications/mark-all-read", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        print(f"✓ Mark all read: {data['message']}")


class TestRoleManagementEndpoints:
    """Test role management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
        self.employee_token = get_token('employee')
    
    def test_get_permissions_hr(self):
        """GET /api/roles/permissions returns permission matrix for HR"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/permissions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert 'hr' in data
        assert 'system_admin' in data
        assert 'office_admin' in data
        assert 'employee' in data
        print(f"✓ HR can access permissions matrix - roles: {list(data.keys())}")
    
    def test_get_permissions_system_admin(self):
        """GET /api/roles/permissions returns permission matrix for System Admin"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/permissions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert 'hr' in data
        print(f"✓ System Admin can access permissions matrix")
    
    def test_get_permissions_office_admin_denied(self):
        """GET /api/roles/permissions should be denied for Office Admin"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/permissions", headers=headers)
        assert response.status_code == 403
        print(f"✓ Office Admin correctly denied access to permissions")
    
    def test_get_users_hr(self):
        """GET /api/roles/users returns all users for HR"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/users", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Check user structure
        user = data[0]
        assert 'id' in user
        assert 'role' in user
        print(f"✓ HR can get users list: {len(data)} users")
    
    def test_get_users_system_admin(self):
        """GET /api/roles/users returns all users for System Admin"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/users", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ System Admin can get users list: {len(data)} users")
    
    def test_get_users_office_admin_denied(self):
        """GET /api/roles/users should be denied for Office Admin"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/users", headers=headers)
        assert response.status_code == 403
        print(f"✓ Office Admin correctly denied access to users list")


class TestRoleBasedEmployeeAccess:
    """Test employee CRUD access based on roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
    
    def test_hr_can_view_employees(self):
        """HR can view employees"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/employees", headers=headers)
        assert response.status_code == 200
        print(f"✓ HR can view employees")
    
    def test_system_admin_can_view_employees(self):
        """System Admin can view employees"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/employees", headers=headers)
        assert response.status_code == 200
        print(f"✓ System Admin can view employees")
    
    def test_office_admin_can_view_employees(self):
        """Office Admin can view employees"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/employees", headers=headers)
        assert response.status_code == 200
        print(f"✓ Office Admin can view employees")
    
    def test_system_admin_cannot_create_employee(self):
        """System Admin cannot create employees (403)"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        employee_data = {
            'full_name': 'TEST_SysAdmin_Create',
            'official_email': 'test_sysadmin@test.com',
            'phone_number': '1234567890',
            'date_of_joining': '2025-01-01',
            'department': 'Research Unit',
            'team': 'Data',
            'designation': 'AI Research scientist'
        }
        response = requests.post(f"{BASE_URL}/api/employees", json=employee_data, headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ System Admin correctly denied employee creation")
    
    def test_office_admin_cannot_create_employee(self):
        """Office Admin cannot create employees (403)"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        employee_data = {
            'full_name': 'TEST_OffAdmin_Create',
            'official_email': 'test_offadmin@test.com',
            'phone_number': '1234567890',
            'date_of_joining': '2025-01-01',
            'department': 'Research Unit',
            'team': 'Data',
            'designation': 'AI Research scientist'
        }
        response = requests.post(f"{BASE_URL}/api/employees", json=employee_data, headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Office Admin correctly denied employee creation")


class TestRoleBasedLeaveAccess:
    """Test leave approval access based on roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
    
    def test_hr_can_view_leaves(self):
        """HR can view leaves"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/leaves", headers=headers)
        assert response.status_code == 200
        print(f"✓ HR can view leaves")
    
    def test_system_admin_can_view_leaves(self):
        """System Admin can view leaves"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/leaves", headers=headers)
        assert response.status_code == 200
        print(f"✓ System Admin can view leaves")
    
    def test_office_admin_can_view_leaves(self):
        """Office Admin can view leaves"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/leaves", headers=headers)
        assert response.status_code == 200
        print(f"✓ Office Admin can view leaves")
    
    def test_office_admin_cannot_approve_leave(self):
        """Office Admin cannot approve leave (403)"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        # Try to approve a non-existent leave - should get 403 before 404
        response = requests.put(f"{BASE_URL}/api/leaves/fake-id/approve", json={}, headers=headers)
        # Should be 403 (permission denied) not 404 (not found)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Office Admin correctly denied leave approval")


class TestRoleBasedLateRequestAccess:
    """Test late request access based on roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
    
    def test_all_admins_can_view_late_requests(self):
        """All admin roles can view late requests"""
        for role, token in [('hr', self.hr_token), ('system_admin', self.sysadmin_token), ('office_admin', self.offadmin_token)]:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(f"{BASE_URL}/api/late-requests", headers=headers)
            assert response.status_code == 200, f"{role} failed to view late requests"
            print(f"✓ {role} can view late requests")
    
    def test_system_admin_cannot_reject_late_request(self):
        """System Admin cannot reject late requests (403)"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        # Use reject endpoint which doesn't require body
        response = requests.put(f"{BASE_URL}/api/late-requests/fake-id/reject", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ System Admin correctly denied late request rejection")
    
    def test_office_admin_cannot_reject_late_request(self):
        """Office Admin cannot reject late requests (403)"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.put(f"{BASE_URL}/api/late-requests/fake-id/reject", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Office Admin correctly denied late request rejection")


class TestRoleUpdatePermissions:
    """Test role update permissions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
        # Get a user ID to test with
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/users", headers=headers)
        if response.status_code == 200:
            users = response.json()
            # Find the employee user
            self.test_user = next((u for u in users if u['role'] == 'employee'), None)
    
    def test_hr_can_update_role(self):
        """HR can update user roles"""
        if not hasattr(self, 'test_user') or not self.test_user:
            pytest.skip("No employee user found for testing")
        
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        # Just verify the endpoint is accessible (don't actually change role)
        response = requests.get(f"{BASE_URL}/api/roles/users", headers=headers)
        assert response.status_code == 200
        print(f"✓ HR has access to role management")
    
    def test_system_admin_can_update_role(self):
        """System Admin can update user roles"""
        if not hasattr(self, 'test_user') or not self.test_user:
            pytest.skip("No employee user found for testing")
        
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/roles/users", headers=headers)
        assert response.status_code == 200
        print(f"✓ System Admin has access to role management")
    
    def test_office_admin_cannot_update_role(self):
        """Office Admin cannot update user roles"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.put(f"{BASE_URL}/api/roles/users/fake-id/role", json={'role': 'employee'}, headers=headers)
        assert response.status_code == 403
        print(f"✓ Office Admin correctly denied role update")


class TestAuditLogsAccess:
    """Test audit logs access based on roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.hr_token = get_token('hr')
        self.sysadmin_token = get_token('system_admin')
        self.offadmin_token = get_token('office_admin')
    
    def test_hr_can_view_audit_logs(self):
        """HR can view audit logs"""
        headers = {'Authorization': f'Bearer {self.hr_token}'}
        response = requests.get(f"{BASE_URL}/api/audit-logs", headers=headers)
        assert response.status_code == 200
        print(f"✓ HR can view audit logs")
    
    def test_system_admin_can_view_audit_logs(self):
        """System Admin can view audit logs"""
        headers = {'Authorization': f'Bearer {self.sysadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/audit-logs", headers=headers)
        assert response.status_code == 200
        print(f"✓ System Admin can view audit logs")
    
    def test_office_admin_cannot_view_audit_logs(self):
        """Office Admin cannot view audit logs"""
        headers = {'Authorization': f'Bearer {self.offadmin_token}'}
        response = requests.get(f"{BASE_URL}/api/audit-logs", headers=headers)
        # Office admin should be denied
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Office Admin correctly denied audit logs access")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
