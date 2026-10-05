"""
Star Rating Module Tests - Iteration 10
Tests for Star Reward functionality including:
- Get employees with stars
- Teams view
- Add stars (performance/learning/innovation/unsafe)
- Star history
- BluBridge theme verification for Reports
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthSetup:
    """Authentication setup"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with authentication token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestStarRewardsEmployeeList(TestAuthSetup):
    """Test Star Rewards - Employees tab functionality"""
    
    def test_get_star_rewards_employees(self, auth_headers):
        """GET /api/star-rewards - Returns list of employees with stars"""
        response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        assert response.status_code == 200, f"Failed to get star rewards: {response.text}"
        employees = response.json()
        assert isinstance(employees, list), "Response should be a list"
        print(f"Total employees in Research Unit: {len(employees)}")
        
        # Verify employee structure
        if len(employees) > 0:
            emp = employees[0]
            assert "id" in emp, "Employee should have id"
            # Verify either name or full_name exists
            assert "name" in emp or "full_name" in emp, "Employee should have name"
            print(f"First employee: {emp.get('name') or emp.get('full_name')}, Stars: {emp.get('stars', 0)}")
    
    def test_get_star_rewards_with_team_filter(self, auth_headers):
        """GET /api/star-rewards with team filter"""
        # First get teams to find a valid team name
        teams_response = requests.get(
            f"{BASE_URL}/api/teams",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        teams = teams_response.json()
        
        if len(teams) > 0:
            team_name = teams[0]["name"]
            response = requests.get(
                f"{BASE_URL}/api/star-rewards",
                headers=auth_headers,
                params={"team": team_name, "department": "Research Unit"}
            )
            assert response.status_code == 200
            employees = response.json()
            # All employees should be from the filtered team
            for emp in employees:
                assert emp.get("team") == team_name, f"Expected team {team_name}, got {emp.get('team')}"
            print(f"Employees in team {team_name}: {len(employees)}")
    
    def test_get_star_rewards_with_search(self, auth_headers):
        """GET /api/star-rewards with search filter"""
        response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"search": "Vijayan", "department": "Research Unit"}
        )
        assert response.status_code == 200
        employees = response.json()
        print(f"Employees matching 'Vijayan': {len(employees)}")
        
        for emp in employees:
            name = emp.get("name") or emp.get("full_name") or ""
            email = emp.get("email") or emp.get("official_email") or ""
            # Should match the search criteria
            assert "vijayan" in name.lower() or "vijayan" in email.lower(), f"Search result mismatch: {name}"
            print(f"Found: {name}, Stars: {emp.get('stars', 0)}")


class TestStarRewardsTeams(TestAuthSetup):
    """Test Star Rewards - Teams tab functionality"""
    
    def test_get_teams_for_research_unit(self, auth_headers):
        """GET /api/teams - Returns teams for Research Unit"""
        response = requests.get(
            f"{BASE_URL}/api/teams",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        assert response.status_code == 200, f"Failed to get teams: {response.text}"
        teams = response.json()
        
        # Filter for Research Unit teams
        research_teams = [t for t in teams if t.get("department") == "Research Unit"]
        print(f"Total Research Unit teams: {len(research_teams)}")
        
        for team in research_teams:
            assert "id" in team, "Team should have id"
            assert "name" in team, "Team should have name"
            print(f"Team: {team.get('name')}, Members: {team.get('member_count', 0)}")


class TestStarRewardsAdd(TestAuthSetup):
    """Test adding stars to employees"""
    
    def test_add_performance_stars(self, auth_headers):
        """POST /api/star-rewards - Add performance stars"""
        # First get a Research Unit employee
        emp_response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No Research Unit employees found")
        
        employee = employees[0]
        employee_id = employee["id"]
        employee_name = employee.get("name") or employee.get("full_name")
        initial_stars = employee.get("stars", 0)
        
        # Add performance stars
        response = requests.post(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            json={
                "employee_id": employee_id,
                "stars": 3,
                "reason": "Test performance stars - iteration 10",
                "type": "performance"
            }
        )
        assert response.status_code == 200, f"Failed to add stars: {response.text}"
        result = response.json()
        assert "new_total" in result, "Response should contain new_total"
        
        expected_total = initial_stars + 3
        assert result["new_total"] == expected_total, f"Expected {expected_total} stars, got {result['new_total']}"
        print(f"Added 3 performance stars to {employee_name}. New total: {result['new_total']}")
    
    def test_add_learning_stars(self, auth_headers):
        """POST /api/star-rewards - Add learning stars"""
        emp_response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        employees = emp_response.json()
        
        if len(employees) < 2:
            pytest.skip("Not enough Research Unit employees")
        
        employee = employees[1]  # Use second employee
        employee_id = employee["id"]
        initial_stars = employee.get("stars", 0)
        
        response = requests.post(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            json={
                "employee_id": employee_id,
                "stars": 2,
                "reason": "Test learning stars - iteration 10",
                "type": "learning"
            }
        )
        assert response.status_code == 200, f"Failed to add learning stars: {response.text}"
        result = response.json()
        assert result["new_total"] == initial_stars + 2
        print(f"Added 2 learning stars. New total: {result['new_total']}")
    
    def test_add_innovation_stars(self, auth_headers):
        """POST /api/star-rewards - Add innovation stars"""
        emp_response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No Research Unit employees found")
        
        employee = employees[0]
        employee_id = employee["id"]
        initial_stars = employee.get("stars", 0)
        
        response = requests.post(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            json={
                "employee_id": employee_id,
                "stars": 5,
                "reason": "Test innovation stars - excellent idea",
                "type": "innovation"
            }
        )
        assert response.status_code == 200
        result = response.json()
        print(f"Added 5 innovation stars. New total: {result['new_total']}")
    
    def test_add_unsafe_conduct_stars(self, auth_headers):
        """POST /api/star-rewards - Add unsafe conduct (negative) stars"""
        emp_response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No Research Unit employees found")
        
        employee = employees[0]
        employee_id = employee["id"]
        initial_stars = employee.get("stars", 0)
        initial_unsafe = employee.get("unsafe_count", 0)
        
        # Unsafe conduct deducts stars (negative value)
        response = requests.post(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            json={
                "employee_id": employee_id,
                "stars": -2,
                "reason": "Test unsafe conduct - safety violation",
                "type": "unsafe"
            }
        )
        assert response.status_code == 200
        result = response.json()
        assert result["new_total"] == initial_stars - 2, "Stars should be deducted for unsafe conduct"
        print(f"Deducted 2 stars for unsafe conduct. New total: {result['new_total']}")
        
        # Verify unsafe count incremented
        updated_emp = requests.get(
            f"{BASE_URL}/api/employees/{employee_id}",
            headers=auth_headers
        ).json()
        assert updated_emp.get("unsafe_count", 0) == initial_unsafe + 1, "Unsafe count should be incremented"
    
    def test_star_rewards_restricted_to_research_unit(self, auth_headers):
        """POST /api/star-rewards - Should fail for non-Research Unit employees"""
        # Get an employee NOT in Research Unit
        emp_response = requests.get(
            f"{BASE_URL}/api/employees",
            headers=auth_headers
        )
        all_employees = emp_response.json().get("employees", [])
        
        non_research_emp = None
        for emp in all_employees:
            if emp.get("department") != "Research Unit":
                non_research_emp = emp
                break
        
        if non_research_emp is None:
            pytest.skip("No non-Research Unit employees found")
        
        response = requests.post(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            json={
                "employee_id": non_research_emp["id"],
                "stars": 1,
                "reason": "Test - should fail",
                "type": "performance"
            }
        )
        assert response.status_code == 400, "Should reject non-Research Unit employees"
        assert "Research Unit" in response.json().get("detail", "")
        print(f"Correctly rejected star reward for non-Research Unit employee")


class TestStarRewardsHistory(TestAuthSetup):
    """Test Star Rewards history functionality"""
    
    def test_get_star_history(self, auth_headers):
        """GET /api/star-rewards/history/{employee_id}"""
        # Get a Research Unit employee
        emp_response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"department": "Research Unit"}
        )
        employees = emp_response.json()
        
        if len(employees) == 0:
            pytest.skip("No Research Unit employees found")
        
        employee = employees[0]
        employee_id = employee["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/star-rewards/history/{employee_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get history: {response.text}"
        history = response.json()
        assert isinstance(history, list), "History should be a list"
        
        print(f"Star history records for {employee.get('name') or employee.get('full_name')}: {len(history)}")
        
        # Verify history record structure
        for record in history[:3]:  # Check first 3 records
            assert "stars" in record, "Record should have stars"
            assert "reason" in record, "Record should have reason"
            assert "type" in record, "Record should have type"
            print(f"  - {record.get('type')}: {record.get('stars')} stars - {record.get('reason', '')[:50]}")


class TestVijayanStars(TestAuthSetup):
    """Test specific case: Vijayan K should have stars"""
    
    def test_vijayan_has_stars(self, auth_headers):
        """Verify Vijayan K has stars after admin award"""
        response = requests.get(
            f"{BASE_URL}/api/star-rewards",
            headers=auth_headers,
            params={"search": "Vijayan", "department": "Research Unit"}
        )
        assert response.status_code == 200
        employees = response.json()
        
        vijayan = None
        for emp in employees:
            name = emp.get("name") or emp.get("full_name") or ""
            if "vijayan" in name.lower():
                vijayan = emp
                break
        
        if vijayan is None:
            print("WARNING: Vijayan K not found in Research Unit employees")
            pytest.skip("Vijayan K not found")
        
        stars = vijayan.get("stars", 0)
        print(f"Vijayan K current stars: {stars}")
        
        # Vijayan should have at least some stars (5 were added per the test request)
        assert stars >= 5, f"Vijayan should have at least 5 stars, but has {stars}"


class TestReportsPage(TestAuthSetup):
    """Test Reports page API and theme colors"""
    
    def test_reports_leaves_endpoint(self, auth_headers):
        """GET /api/reports/leaves - Leave reports endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/reports/leaves",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get leave reports: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Leave report records: {len(data)}")
    
    def test_reports_attendance_endpoint(self, auth_headers):
        """GET /api/reports/attendance - Attendance reports endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/reports/attendance",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get attendance reports: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Attendance report records: {len(data)}")
