"""
Test suite for Coupon System and Fund Status endpoints
Tests: 
- GET /api/partners/fund-status - Fund status (5000 lots max, available, sold)
- POST /api/coupons - Create coupon (percent or fixed type)
- GET /api/coupons - List coupons for tenant
- POST /api/coupons/validate - Validate coupon and calculate discount
- GET /api/coupons/report - Usage report
- PUT /api/coupons/{id} - Update coupon (activate/deactivate)
- DELETE /api/coupons/{id} - Delete coupon
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "gustavo@lepaindore.com.mx"
ADMIN_PASSWORD = "demo123"
PARTNER_EMAIL = "test.socio@example.com"
PARTNER_PASSWORD = "test123"
TENANT_ID = "9fd4933a-45fa-480a-9dc3-dbd46551b859"


class TestFundStatus:
    """Test fund status endpoint - public endpoint"""
    
    def test_fund_status_returns_correct_structure(self):
        """GET /api/partners/fund-status returns fund info"""
        response = requests.get(f"{BASE_URL}/api/partners/fund-status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify all required fields
        assert "fund_total_value" in data, "Missing fund_total_value"
        assert "lot_price" in data, "Missing lot_price"
        assert "lot_percent" in data, "Missing lot_percent"
        assert "max_total_lots" in data, "Missing max_total_lots"
        assert "total_lots_sold" in data, "Missing total_lots_sold"
        assert "available_lots" in data, "Missing available_lots"
        assert "fund_percentage_sold" in data, "Missing fund_percentage_sold"
        assert "is_sold_out" in data, "Missing is_sold_out"
        
        print(f"Fund status: {data}")
    
    def test_fund_status_values_are_correct(self):
        """Verify fund values match expected configuration"""
        response = requests.get(f"{BASE_URL}/api/partners/fund-status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected values
        assert data["fund_total_value"] == 20000000, f"Expected 20M, got {data['fund_total_value']}"
        assert data["max_total_lots"] == 5000, f"Expected 5000 max lots, got {data['max_total_lots']}"
        assert data["lot_price"] == 4000, f"Expected $4000/lot, got {data['lot_price']}"
        assert data["lot_percent"] == 0.1, f"Expected 0.1% per lot, got {data['lot_percent']}"
        
        # Verify calculated values
        assert data["available_lots"] == data["max_total_lots"] - data["total_lots_sold"]
        assert data["is_sold_out"] == (data["available_lots"] <= 0)
        
        print(f"Fund: {data['total_lots_sold']} sold, {data['available_lots']} available")


class TestCouponsCRUD:
    """Test coupon CRUD operations - requires admin auth"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.text}")
        
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_create_percent_coupon(self, auth_headers):
        """POST /api/coupons creates percent discount coupon"""
        unique_code = f"TEST_PCT_{uuid.uuid4().hex[:6].upper()}"
        
        response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 15,
            "valid_for": "both",
            "max_uses": 10,
            "description": "Test percent coupon"
        }, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["code"] == unique_code
        assert data["discount_type"] == "percent"
        assert data["discount_value"] == 15
        assert data["valid_for"] == "both"
        assert data["is_active"] == True
        assert data["uses_count"] == 0
        
        print(f"Created percent coupon: {unique_code}")
        return data
    
    def test_create_fixed_coupon(self, auth_headers):
        """POST /api/coupons creates fixed amount coupon"""
        unique_code = f"TEST_FIX_{uuid.uuid4().hex[:6].upper()}"
        
        response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "fixed",
            "discount_value": 500,
            "valid_for": "investment",
            "description": "Test fixed coupon"
        }, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["code"] == unique_code
        assert data["discount_type"] == "fixed"
        assert data["discount_value"] == 500
        assert data["valid_for"] == "investment"
        
        print(f"Created fixed coupon: {unique_code}")
        return data
    
    def test_create_subscription_only_coupon(self, auth_headers):
        """POST /api/coupons creates subscription-only coupon"""
        unique_code = f"TEST_SUB_{uuid.uuid4().hex[:6].upper()}"
        
        response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 20,
            "valid_for": "subscription",
            "description": "Subscription only coupon"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid_for"] == "subscription"
        
        print(f"Created subscription coupon: {unique_code}")
    
    def test_create_duplicate_coupon_fails(self, auth_headers):
        """POST /api/coupons rejects duplicate code"""
        unique_code = f"TEST_DUP_{uuid.uuid4().hex[:6].upper()}"
        
        # Create first coupon
        response1 = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 10,
            "valid_for": "both"
        }, headers=auth_headers)
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 20,
            "valid_for": "both"
        }, headers=auth_headers)
        
        assert response2.status_code == 400, f"Expected 400 for duplicate, got {response2.status_code}"
        print("Duplicate coupon correctly rejected")
    
    def test_create_invalid_percent_fails(self, auth_headers):
        """POST /api/coupons rejects invalid percent value"""
        response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": f"TEST_INV_{uuid.uuid4().hex[:6].upper()}",
            "discount_type": "percent",
            "discount_value": 150,  # Invalid: > 100
            "valid_for": "both"
        }, headers=auth_headers)
        
        assert response.status_code == 400, f"Expected 400 for invalid percent, got {response.status_code}"
        print("Invalid percent correctly rejected")
    
    def test_list_coupons(self, auth_headers):
        """GET /api/coupons returns list of coupons"""
        response = requests.get(f"{BASE_URL}/api/coupons", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of coupons"
        
        print(f"Found {len(data)} coupons")
        
        # Verify structure of first coupon if exists
        if len(data) > 0:
            coupon = data[0]
            assert "id" in coupon
            assert "code" in coupon
            assert "discount_type" in coupon
            assert "discount_value" in coupon
            assert "is_active" in coupon
    
    def test_toggle_coupon_active_status(self, auth_headers):
        """PUT /api/coupons/{id} toggles active status"""
        # First create a coupon
        unique_code = f"TEST_TOG_{uuid.uuid4().hex[:6].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 10,
            "valid_for": "both"
        }, headers=auth_headers)
        
        assert create_response.status_code == 200
        coupon_id = create_response.json()["id"]
        
        # Deactivate coupon
        response = requests.put(
            f"{BASE_URL}/api/coupons/{coupon_id}?is_active=false",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify it's deactivated by listing
        list_response = requests.get(f"{BASE_URL}/api/coupons", headers=auth_headers)
        coupons = list_response.json()
        updated_coupon = next((c for c in coupons if c["id"] == coupon_id), None)
        
        assert updated_coupon is not None
        assert updated_coupon["is_active"] == False
        
        print(f"Coupon {unique_code} deactivated successfully")
    
    def test_delete_coupon(self, auth_headers):
        """DELETE /api/coupons/{id} removes coupon"""
        # First create a coupon
        unique_code = f"TEST_DEL_{uuid.uuid4().hex[:6].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 5,
            "valid_for": "both"
        }, headers=auth_headers)
        
        assert create_response.status_code == 200
        coupon_id = create_response.json()["id"]
        
        # Delete coupon
        response = requests.delete(
            f"{BASE_URL}/api/coupons/{coupon_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify it's deleted
        list_response = requests.get(f"{BASE_URL}/api/coupons", headers=auth_headers)
        coupons = list_response.json()
        deleted_coupon = next((c for c in coupons if c["id"] == coupon_id), None)
        
        assert deleted_coupon is None, "Coupon should be deleted"
        print(f"Coupon {unique_code} deleted successfully")


class TestCouponValidation:
    """Test coupon validation endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.text}")
        
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture(scope="class")
    def test_coupon(self, auth_headers):
        """Create a test coupon for validation tests"""
        unique_code = f"VALIDATE_{uuid.uuid4().hex[:6].upper()}"
        
        response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 25,
            "valid_for": "both",
            "max_uses": 100,
            "description": "Test validation coupon"
        }, headers=auth_headers)
        
        if response.status_code != 200:
            pytest.skip(f"Failed to create test coupon: {response.text}")
        
        return response.json()
    
    def test_validate_percent_coupon(self, test_coupon):
        """POST /api/coupons/validate calculates percent discount"""
        code = test_coupon["code"]
        amount = 4000  # 1 lot
        
        response = requests.post(
            f"{BASE_URL}/api/coupons/validate?code={code}&valid_for=investment&amount={amount}&tenant_id={TENANT_ID}"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["valid"] == True
        assert data["code"] == code
        assert data["discount_type"] == "percent"
        assert data["discount_value"] == 25
        assert data["original_amount"] == amount
        
        # 25% of 4000 = 1000
        expected_discount = amount * 0.25
        assert data["discount_amount"] == expected_discount, f"Expected {expected_discount}, got {data['discount_amount']}"
        assert data["final_amount"] == amount - expected_discount
        
        print(f"Validated coupon: {code}, discount: ${data['discount_amount']}")
    
    def test_validate_fixed_coupon(self, auth_headers):
        """POST /api/coupons/validate calculates fixed discount"""
        # Create fixed coupon
        unique_code = f"FIXED_{uuid.uuid4().hex[:6].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "fixed",
            "discount_value": 500,
            "valid_for": "investment"
        }, headers=auth_headers)
        
        assert create_response.status_code == 200
        
        amount = 4000
        response = requests.post(
            f"{BASE_URL}/api/coupons/validate?code={unique_code}&valid_for=investment&amount={amount}&tenant_id={TENANT_ID}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["discount_type"] == "fixed"
        assert data["discount_amount"] == 500
        assert data["final_amount"] == 3500
        
        print(f"Fixed coupon validated: ${data['discount_amount']} off")
    
    def test_validate_invalid_coupon_fails(self):
        """POST /api/coupons/validate rejects invalid code"""
        response = requests.post(
            f"{BASE_URL}/api/coupons/validate?code=INVALID_CODE_XYZ&valid_for=investment&amount=4000&tenant_id={TENANT_ID}"
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid coupon, got {response.status_code}"
        print("Invalid coupon correctly rejected")
    
    def test_validate_wrong_type_fails(self, auth_headers):
        """POST /api/coupons/validate rejects coupon for wrong type"""
        # Create investment-only coupon
        unique_code = f"INVONLY_{uuid.uuid4().hex[:6].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 10,
            "valid_for": "investment"  # Only for investment
        }, headers=auth_headers)
        
        assert create_response.status_code == 200
        
        # Try to use for subscription
        response = requests.post(
            f"{BASE_URL}/api/coupons/validate?code={unique_code}&valid_for=subscription&amount=399&tenant_id={TENANT_ID}"
        )
        
        assert response.status_code == 400, f"Expected 400 for wrong type, got {response.status_code}"
        print("Wrong type coupon correctly rejected")
    
    def test_validate_deactivated_coupon_fails(self, auth_headers):
        """POST /api/coupons/validate rejects deactivated coupon"""
        # Create and deactivate coupon
        unique_code = f"DEACT_{uuid.uuid4().hex[:6].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/coupons", json={
            "code": unique_code,
            "discount_type": "percent",
            "discount_value": 10,
            "valid_for": "both"
        }, headers=auth_headers)
        
        assert create_response.status_code == 200
        coupon_id = create_response.json()["id"]
        
        # Deactivate
        requests.put(
            f"{BASE_URL}/api/coupons/{coupon_id}?is_active=false",
            headers=auth_headers
        )
        
        # Try to validate
        response = requests.post(
            f"{BASE_URL}/api/coupons/validate?code={unique_code}&valid_for=investment&amount=4000&tenant_id={TENANT_ID}"
        )
        
        assert response.status_code == 404, f"Expected 404 for deactivated coupon, got {response.status_code}"
        print("Deactivated coupon correctly rejected")


class TestCouponReport:
    """Test coupon usage report endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.text}")
        
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_get_coupon_report(self, auth_headers):
        """GET /api/coupons/report returns usage report"""
        response = requests.get(f"{BASE_URL}/api/coupons/report", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "summary" in data, "Missing summary"
        assert "coupons" in data, "Missing coupons list"
        assert "recent_usages" in data, "Missing recent_usages"
        
        # Verify summary fields
        summary = data["summary"]
        assert "total_coupons" in summary
        assert "active_coupons" in summary
        assert "total_uses" in summary
        assert "total_discount_given" in summary
        
        print(f"Report: {summary['total_coupons']} coupons, {summary['total_uses']} uses, ${summary['total_discount_given']} discounted")


class TestPartnerCouponIntegration:
    """Test coupon integration with partner lot purchase"""
    
    @pytest.fixture(scope="class")
    def partner_token(self):
        """Get partner authentication token"""
        response = requests.post(f"{BASE_URL}/api/partners/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Partner login failed: {response.text}")
        
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.text}")
        
        return response.json()["token"]
    
    def test_partner_dashboard_shows_fund_status(self, partner_token):
        """Partner dashboard includes fund status"""
        response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers={"Authorization": f"Bearer {partner_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "partner" in data
        assert "current_lot_price" in data
        
        print(f"Partner dashboard loaded, lot price: ${data['current_lot_price']}")
    
    def test_fund_status_accessible_from_dashboard(self, partner_token):
        """Fund status endpoint accessible for partners"""
        # Fund status is public, no auth needed
        response = requests.get(f"{BASE_URL}/api/partners/fund-status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["max_total_lots"] == 5000
        assert "available_lots" in data
        assert "is_sold_out" in data
        
        print(f"Fund status: {data['available_lots']} lots available")


# Cleanup test coupons after all tests
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_coupons():
    """Cleanup test coupons after all tests"""
    yield
    
    # Login as admin
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if response.status_code != 200:
        return
    
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all coupons
    coupons_response = requests.get(f"{BASE_URL}/api/coupons", headers=headers)
    if coupons_response.status_code != 200:
        return
    
    coupons = coupons_response.json()
    
    # Delete test coupons (those starting with TEST_, VALIDATE_, FIXED_, etc.)
    test_prefixes = ["TEST_", "VALIDATE_", "FIXED_", "INVONLY_", "DEACT_"]
    for coupon in coupons:
        if any(coupon["code"].startswith(prefix) for prefix in test_prefixes):
            requests.delete(f"{BASE_URL}/api/coupons/{coupon['id']}", headers=headers)
            print(f"Cleaned up test coupon: {coupon['code']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
