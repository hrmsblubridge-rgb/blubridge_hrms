import requests
import sys
from datetime import datetime, timedelta
import json

class BluBridgeHRMSTester:
    def __init__(self, base_url="https://employee-portal-202.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.user_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json() if response.text else {}
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_seed_database(self):
        """Seed the database with test data"""
        print("\n🌱 Seeding database...")
        success, response = self.run_test(
            "Seed Database",
            "POST",
            "seed",
            200
        )
        return success

    def test_login(self):
        """Test login with admin credentials"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": "admin", "password": "admin"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response.get('user', {}).get('id')
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_get_me(self):
        """Test get current user info"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        if success:
            required_fields = ['total_research_unit', 'total_support_staff', 'pending_approvals', 'upcoming_leaves', 'attendance']
            for field in required_fields:
                if field not in response:
                    print(f"   ⚠️  Missing field: {field}")
        return success

    def test_dashboard_leave_list(self):
        """Test dashboard leave list"""
        success, response = self.run_test(
            "Dashboard Leave List",
            "GET",
            "dashboard/leave-list",
            200
        )
        return success

    def test_employees_crud(self):
        """Test employee CRUD operations"""
        # Get employee stats
        success0, stats = self.run_test(
            "Get Employee Stats",
            "GET",
            "employees/stats",
            200
        )
        if success0:
            required_fields = ['total', 'active', 'inactive', 'resigned']
            for field in required_fields:
                if field not in stats:
                    print(f"   ⚠️  Missing stats field: {field}")
        
        # Get employees
        success1, employees_response = self.run_test(
            "Get Employees",
            "GET",
            "employees",
            200
        )
        
        employees = employees_response.get('employees', []) if success1 else []
        
        # Get all employees (for dropdowns)
        success1a, all_employees = self.run_test(
            "Get All Employees",
            "GET",
            "employees/all",
            200
        )
        
        # Get specific employee if any exist
        success2 = True
        if success1 and employees:
            emp_id = employees[0]['id']
            success2, _ = self.run_test(
                "Get Single Employee",
                "GET",
                f"employees/{emp_id}",
                200
            )
        
        # Test employee creation
        success3, new_emp = self.run_test(
            "Create Employee",
            "POST",
            "employees",
            200,
            data={
                "full_name": "Test Employee",
                "official_email": "test@blubridge.com",
                "department": "Research Unit",
                "team": "Data",
                "designation": "Software Engineer",
                "date_of_joining": "2024-01-01",
                "employment_type": "Full-time",
                "tier_level": "Mid",
                "work_location": "Office"
            }
        )
        
        # Test employee update if creation succeeded
        success4 = True
        if success3 and new_emp:
            emp_id = new_emp['id']
            success4, _ = self.run_test(
                "Update Employee",
                "PUT",
                f"employees/{emp_id}",
                200,
                data={"full_name": "Updated Test Employee"}
            )
            
            # Test employee deactivation (soft delete)
            success5, _ = self.run_test(
                "Deactivate Employee",
                "DELETE",
                f"employees/{emp_id}",
                200
            )
        else:
            success5 = True
        
        return success0 and success1 and success1a and success2 and success3 and success4 and success5

    def test_attendance_operations(self):
        """Test attendance operations"""
        # Get attendance records
        success1, attendance = self.run_test(
            "Get Attendance",
            "GET",
            "attendance",
            200
        )
        
        # Get attendance stats
        success2, stats = self.run_test(
            "Get Attendance Stats",
            "GET",
            "attendance/stats",
            200
        )
        
        # Test attendance with filters
        today = datetime.now().strftime("%d-%m-%Y")
        success3, filtered = self.run_test(
            "Get Filtered Attendance",
            "GET",
            f"attendance?from_date={today}&to_date={today}",
            200
        )
        
        return success1 and success2 and success3

    def test_leave_operations(self):
        """Test leave management operations"""
        # Get leaves
        success1, leaves = self.run_test(
            "Get Leaves",
            "GET",
            "leaves",
            200
        )
        
        # Test leave creation (need employee ID)
        success2 = True
        employees_success, employees = self.run_test(
            "Get Employees for Leave",
            "GET",
            "employees",
            200
        )
        
        if employees_success and employees.get('employees'):
            emp_id = employees['employees'][0]['id']
            success2, new_leave = self.run_test(
                "Create Leave Request",
                "POST",
                "leaves",
                200,
                data={
                    "employee_id": emp_id,
                    "leave_type": "Casual",
                    "start_date": "2024-12-25",
                    "end_date": "2024-12-26",
                    "reason": "Test leave request"
                }
            )
            
            # Test leave approval if creation succeeded
            if success2 and new_leave:
                leave_id = new_leave['id']
                success3, _ = self.run_test(
                    "Approve Leave",
                    "PUT",
                    f"leaves/{leave_id}/approve",
                    200
                )
                return success1 and success2 and success3
        
        return success1 and success2

    def test_star_rewards(self):
        """Test star rewards operations"""
        # Get star rewards (employees)
        success1, employees = self.run_test(
            "Get Star Rewards",
            "GET",
            "star-rewards",
            200
        )
        
        # Test adding star reward
        success2 = True
        if success1 and employees:
            emp_id = employees[0]['id']
            success2, _ = self.run_test(
                "Add Star Reward",
                "POST",
                "star-rewards",
                200,
                data={
                    "employee_id": emp_id,
                    "stars": 5,
                    "reason": "Test star award"
                }
            )
            
            # Get star history
            success3, _ = self.run_test(
                "Get Star History",
                "GET",
                f"star-rewards/history/{emp_id}",
                200
            )
            return success1 and success2 and success3
        
        return success1 and success2

    def test_teams_and_departments(self):
        """Test teams and departments"""
        # Get teams
        success1, teams = self.run_test(
            "Get Teams",
            "GET",
            "teams",
            200
        )
        
        # Get departments
        success2, departments = self.run_test(
            "Get Departments",
            "GET",
            "departments",
            200
        )
        
        # Get specific team details
        success3 = True
        if success1 and teams:
            team_id = teams[0]['id']
            success3, _ = self.run_test(
                "Get Team Details",
                "GET",
                f"teams/{team_id}",
                200
            )
        
        return success1 and success2 and success3

    def test_reports(self):
        """Test report generation"""
        from_date = "01-12-2024"
        to_date = "31-12-2024"
        
        # Test attendance report
        success1, _ = self.run_test(
            "Generate Attendance Report",
            "GET",
            f"reports/attendance?from_date={from_date}&to_date={to_date}",
            200
        )
        
        # Test leave report
        success2, _ = self.run_test(
            "Generate Leave Report",
            "GET",
            f"reports/leaves?from_date={from_date}&to_date={to_date}",
            200
        )
        
        return success1 and success2

    def test_config_endpoints(self):
        """Test configuration endpoints"""
        config_endpoints = [
            "config/employment-types",
            "config/employee-statuses", 
            "config/tier-levels",
            "config/work-locations",
            "config/user-roles"
        ]
        
        all_success = True
        for endpoint in config_endpoints:
            success, _ = self.run_test(
                f"Get {endpoint.split('/')[-1].title()}",
                "GET",
                endpoint,
                200
            )
            all_success = all_success and success
        
        return all_success
        
    def test_audit_logs(self):
        """Test audit logs (admin only)"""
        success, _ = self.run_test(
            "Get Audit Logs",
            "GET",
            "audit-logs",
            200
        )
        return success

def main():
    print("🚀 Starting BluBridge HRMS Backend Testing")
    print("=" * 50)
    
    tester = BluBridgeHRMSTester()
    
    # Test sequence
    tests = [
        ("Seed Database", tester.test_seed_database),
        ("Authentication", tester.test_login),
        ("User Info", tester.test_get_me),
        ("Config Endpoints", tester.test_config_endpoints),
        ("Dashboard Stats", tester.test_dashboard_stats),
        ("Dashboard Leave List", tester.test_dashboard_leave_list),
        ("Employee Operations", tester.test_employees_crud),
        ("Attendance Operations", tester.test_attendance_operations),
        ("Leave Operations", tester.test_leave_operations),
        ("Star Rewards", tester.test_star_rewards),
        ("Teams & Departments", tester.test_teams_and_departments),
        ("Reports", tester.test_reports),
        ("Audit Logs", tester.test_audit_logs)
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} Tests...")
        try:
            if not test_func():
                failed_tests.append(test_name)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            failed_tests.append(test_name)
    
    # Print final results
    print("\n" + "=" * 50)
    print("📊 FINAL TEST RESULTS")
    print("=" * 50)
    print(f"Total Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    if failed_tests:
        print(f"\n❌ Failed Test Categories: {', '.join(failed_tests)}")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())