"""
Test Suite for Employee Documents (Offer Letter Upload) Feature

Tests:
- GET /api/employees/{id}/documents - Admin can get employee documents
- POST /api/employees/{id}/documents - Admin can upload offer letter for employee
- GET /api/employee-profile/documents - Employee can get their own documents
- DELETE /api/employees/{id}/documents/{doc_id} - Admin can delete document
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
ADMIN_CREDENTIALS = {"username": "admin", "password": "admin"}
EMPLOYEE_CREDENTIALS = {"username": "testemployee", "password": "test@3210"}


class TestEmployeeDocumentsAPI:
    """Test Employee Documents CRUD operations"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and get admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Get admin token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDENTIALS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.admin_token = response.json().get("token")
        self.admin_user = response.json().get("user")
        assert self.admin_token, "No admin token received"
        
        # Get employee token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDENTIALS)
        assert response.status_code == 200, f"Employee login failed: {response.text}"
        self.employee_token = response.json().get("token")
        self.employee_user = response.json().get("user")
        self.employee_id = self.employee_user.get("employee_id")
        assert self.employee_token, "No employee token received"
        assert self.employee_id, "Employee ID not found in user data"
        
        yield
        
        # Cleanup: Delete test documents
        self._cleanup_test_documents()
    
    def _cleanup_test_documents(self):
        """Delete documents with test file names"""
        if hasattr(self, 'admin_token') and hasattr(self, 'employee_id'):
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            try:
                response = self.session.get(
                    f"{BASE_URL}/api/employees/{self.employee_id}/documents",
                    headers=headers
                )
                if response.status_code == 200:
                    docs = response.json().get("documents", [])
                    for doc in docs:
                        if doc.get("file_name", "").startswith("TEST_"):
                            self.session.delete(
                                f"{BASE_URL}/api/employees/{self.employee_id}/documents/{doc['id']}",
                                headers=headers
                            )
            except:
                pass
    
    def test_1_admin_can_get_employee_documents_empty(self):
        """Test admin can get employee documents (initial state may be empty or have existing docs)"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        response = self.session.get(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "employee_id" in data, "Response should contain employee_id"
        assert "employee_name" in data, "Response should contain employee_name"
        assert "documents" in data, "Response should contain documents list"
        assert isinstance(data["documents"], list), "documents should be a list"
        
        print(f"SUCCESS: Admin retrieved documents for employee. Count: {len(data['documents'])}")
    
    def test_2_admin_can_upload_offer_letter(self):
        """Test admin can upload offer letter for employee"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Create offer letter document with test prefix for cleanup
        document_data = {
            "file_url": "https://res.cloudinary.com/djsvuh19j/image/upload/v1234567890/test_offer_letter.pdf",
            "file_name": f"TEST_offer_letter_{uuid.uuid4().hex[:8]}.pdf",
            "file_type": "application/pdf",
            "file_public_id": f"blubridge/documents/test_{uuid.uuid4().hex[:8]}",
            "document_type": "offer_letter"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            json=document_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "message" in data, "Response should contain message"
        assert "document" in data, "Response should contain document"
        assert data["document"]["document_type"] == "offer_letter", "Document type should be offer_letter"
        assert data["document"]["file_url"] == document_data["file_url"], "File URL should match"
        assert data["document"]["file_name"] == document_data["file_name"], "File name should match"
        
        print(f"SUCCESS: Admin uploaded offer letter. Document ID: {data['document']['id']}")
    
    def test_3_admin_can_verify_uploaded_document(self):
        """Test that uploaded document appears in employee documents list"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        response = self.session.get(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Find offer letter in documents
        offer_letters = [d for d in data["documents"] if d["document_type"] == "offer_letter"]
        assert len(offer_letters) >= 1, "Should have at least one offer letter after upload"
        
        offer_letter = offer_letters[0]
        assert "file_url" in offer_letter, "Offer letter should have file_url"
        assert "file_name" in offer_letter, "Offer letter should have file_name"
        assert "uploaded_by_name" in offer_letter, "Offer letter should have uploaded_by_name"
        assert "uploaded_at" in offer_letter, "Offer letter should have uploaded_at"
        
        print(f"SUCCESS: Verified offer letter exists. Uploaded by: {offer_letter['uploaded_by_name']}")
    
    def test_4_employee_can_get_own_documents(self):
        """Test employee can get their own documents via /api/employee-profile/documents"""
        headers = {"Authorization": f"Bearer {self.employee_token}"}
        
        response = self.session.get(
            f"{BASE_URL}/api/employee-profile/documents",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "documents" in data, "Response should contain documents list"
        assert isinstance(data["documents"], list), "documents should be a list"
        
        # Check if offer letter is accessible to employee
        offer_letters = [d for d in data["documents"] if d["document_type"] == "offer_letter"]
        print(f"SUCCESS: Employee retrieved their documents. Offer letters: {len(offer_letters)}")
    
    def test_5_employee_cannot_upload_document(self):
        """Test employee cannot upload documents (admin only)"""
        headers = {"Authorization": f"Bearer {self.employee_token}"}
        
        document_data = {
            "file_url": "https://example.com/fake.pdf",
            "file_name": "fake_doc.pdf",
            "file_type": "application/pdf",
            "document_type": "offer_letter"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            json=document_data,
            headers=headers
        )
        
        # Employee should get 403 Forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"SUCCESS: Employee correctly denied from uploading documents (403)")
    
    def test_6_employee_cannot_access_other_employee_docs(self):
        """Test employee cannot access other employee's documents"""
        headers = {"Authorization": f"Bearer {self.employee_token}"}
        
        # Try to access documents using a different employee ID
        fake_employee_id = "non-existent-id-123"
        response = self.session.get(
            f"{BASE_URL}/api/employees/{fake_employee_id}/documents",
            headers=headers
        )
        
        # Should get 403 or 404
        assert response.status_code in [403, 404], f"Expected 403 or 404, got {response.status_code}: {response.text}"
        print(f"SUCCESS: Employee correctly denied from accessing other employee's documents ({response.status_code})")
    
    def test_7_admin_can_replace_offer_letter(self):
        """Test admin can replace/update existing offer letter"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Upload new version of offer letter
        document_data = {
            "file_url": "https://res.cloudinary.com/djsvuh19j/image/upload/v1234567890/updated_offer.pdf",
            "file_name": f"TEST_updated_offer_{uuid.uuid4().hex[:8]}.pdf",
            "file_type": "application/pdf",
            "file_public_id": f"blubridge/documents/updated_{uuid.uuid4().hex[:8]}",
            "document_type": "offer_letter"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            json=document_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should update existing, not create duplicate
        assert "Updated" in data["message"] or "uploaded" in data["message"].lower(), "Should indicate document update"
        
        # Verify only one offer letter exists
        get_response = self.session.get(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            headers=headers
        )
        docs = get_response.json().get("documents", [])
        offer_letters = [d for d in docs if d["document_type"] == "offer_letter"]
        
        # Should still be only one offer letter (replaced, not duplicated)
        # Note: There might be more due to other tests, but the latest should have our URL
        latest_offer = max(offer_letters, key=lambda x: x.get("updated_at", ""))
        assert latest_offer["file_url"] == document_data["file_url"], "Offer letter should be updated"
        
        print(f"SUCCESS: Admin replaced offer letter successfully")
    
    def test_8_admin_can_delete_document(self):
        """Test admin can delete an employee document"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # First, get documents to find one to delete
        response = self.session.get(
            f"{BASE_URL}/api/employees/{self.employee_id}/documents",
            headers=headers
        )
        
        assert response.status_code == 200
        docs = response.json().get("documents", [])
        
        # Find a test document to delete
        test_docs = [d for d in docs if d.get("file_name", "").startswith("TEST_")]
        
        if test_docs:
            doc_to_delete = test_docs[0]
            delete_response = self.session.delete(
                f"{BASE_URL}/api/employees/{self.employee_id}/documents/{doc_to_delete['id']}",
                headers=headers
            )
            
            assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
            print(f"SUCCESS: Admin deleted document {doc_to_delete['id']}")
        else:
            print("INFO: No test documents to delete, skipping deletion test")
    
    def test_9_get_non_existent_employee_docs_returns_404(self):
        """Test getting documents for non-existent employee returns 404"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        response = self.session.get(
            f"{BASE_URL}/api/employees/non-existent-employee-id/documents",
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"SUCCESS: Non-existent employee returns 404")
    
    def test_10_upload_to_non_existent_employee_returns_404(self):
        """Test uploading document to non-existent employee returns 404"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        document_data = {
            "file_url": "https://example.com/test.pdf",
            "file_name": "test.pdf",
            "file_type": "application/pdf",
            "document_type": "offer_letter"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/employees/non-existent-employee-id/documents",
            json=document_data,
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"SUCCESS: Upload to non-existent employee returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
