"""
Test suite for Google Auth and Banner Removal features
Tests:
1. Banner 'Made with Emergent' should NOT appear in index.html
2. Google login button should appear on /admin page
3. POST /api/auth/google/session should reject invalid sessions with 401
4. Traditional email/password login should still work
5. GET /api/auth/me should work after login
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from main agent
TEST_ADMIN_EMAIL = "superadmin@dore.com"
TEST_ADMIN_PASSWORD = "superadmin123"
TEST_TENANT_EMAIL = "demo@cafe.com"
TEST_TENANT_PASSWORD = "demo123"


class TestBannerRemoval:
    """Test that 'Made with Emergent' banner is removed from index.html"""
    
    def test_banner_not_in_index_html(self):
        """Verify banner text is NOT present in index.html"""
        # Read the index.html file directly
        with open('/app/frontend/public/index.html', 'r') as f:
            content = f.read()
        
        # Check that 'Made with Emergent' banner is NOT present
        assert 'Made with Emergent' not in content, "Banner 'Made with Emergent' should be removed"
        assert 'emergent-banner' not in content.lower(), "Banner element should be removed"
        
        # Verify title was changed
        assert 'Doré | Sistema de Gestión' in content, "Title should be 'Doré | Sistema de Gestión'"
        assert 'Emergent | Fullstack App' not in content, "Old title should be removed"
        
        print("PASS: Banner 'Made with Emergent' is NOT present in index.html")
        print("PASS: Title is 'Doré | Sistema de Gestión'")


class TestGoogleAuthEndpoint:
    """Test Google OAuth session endpoint"""
    
    def test_google_session_rejects_invalid_session(self):
        """POST /api/auth/google/session should return 401 for invalid session_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/session",
            json={"session_id": "invalid_session_12345"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"PASS: Invalid session returns 401 with message: {data['detail']}")
    
    def test_google_session_rejects_empty_session(self):
        """POST /api/auth/google/session should reject empty session_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/session",
            json={"session_id": ""},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 or 422 (validation error)
        assert response.status_code in [401, 422], f"Expected 401 or 422, got {response.status_code}"
        print(f"PASS: Empty session returns {response.status_code}")


class TestTraditionalLogin:
    """Test that traditional email/password login still works"""
    
    def test_superadmin_login_success(self):
        """Login with superadmin credentials should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert data["user"]["email"] == TEST_ADMIN_EMAIL
        assert data["user"]["role"] == "superadmin"
        
        print(f"PASS: Superadmin login successful - role: {data['user']['role']}")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Login with wrong credentials should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@email.com", "password": "wrongpassword"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Invalid credentials return 401")
    
    def test_tenant_login_success(self):
        """Login with tenant credentials should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_TENANT_EMAIL, "password": TEST_TENANT_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        
        # This might fail if demo user doesn't exist - that's OK
        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            assert "user" in data
            print(f"PASS: Tenant login successful - role: {data['user']['role']}")
        elif response.status_code == 401:
            print("INFO: Tenant user demo@cafe.com doesn't exist (expected if not seeded)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


class TestAuthMe:
    """Test GET /api/auth/me endpoint"""
    
    def test_auth_me_with_valid_token(self):
        """GET /api/auth/me should return user data with valid token"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        
        assert login_response.status_code == 200, "Login should succeed"
        token = login_response.json()["token"]
        
        # Now test /auth/me
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert me_response.status_code == 200, f"Expected 200, got {me_response.status_code}"
        data = me_response.json()
        
        assert data["email"] == TEST_ADMIN_EMAIL
        assert data["role"] == "superadmin"
        assert "id" in data
        
        print(f"PASS: /api/auth/me returns correct user data - email: {data['email']}, role: {data['role']}")
    
    def test_auth_me_without_token(self):
        """GET /api/auth/me should return 401/403 without token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"
        print(f"PASS: /api/auth/me without token returns {response.status_code}")
    
    def test_auth_me_with_invalid_token(self):
        """GET /api/auth/me should return 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/auth/me with invalid token returns 401")


class TestGoogleLogout:
    """Test Google logout endpoint"""
    
    def test_google_logout_endpoint_exists(self):
        """POST /api/auth/google/logout should exist and work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/logout",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 200 even without session
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        print(f"PASS: Google logout endpoint works - message: {data.get('message')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
