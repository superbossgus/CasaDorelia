"""
Test Partners Module - New Features (PayPal, SPEI, Receipt Upload)
Tests for iteration 5 - new payment methods and receipt upload
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TENANT_ID = "9fd4933a-45fa-480a-9dc3-dbd46551b859"

class TestPartnerRegistrationPaymentMethods:
    """Test partner registration with different payment methods"""
    
    def test_register_partner_with_bank_account(self):
        """Test registration with bank account (CLABE)"""
        unique_email = f"test.bank.{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test Bank Partner",
                "email": unique_email,
                "phone": "+52 55 1234 5678",
                "payment_method": "bank",
                "bank_name": "BBVA",
                "clabe": "012180001064835429",
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        print(f"Bank registration status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert "partner_id" in data
        assert "partner_code" in data
        print(f"✓ Partner registered with bank account: {data['partner_code']}")
        
        return data["token"]
    
    def test_register_partner_with_paypal(self):
        """Test registration with PayPal email"""
        unique_email = f"test.paypal.{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test PayPal Partner",
                "email": unique_email,
                "phone": "+52 55 9876 5432",
                "payment_method": "paypal",
                "paypal_email": "paypal.test@example.com",
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        print(f"PayPal registration status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert "partner_id" in data
        print(f"✓ Partner registered with PayPal: {data['partner_code']}")
        
        return data["token"]
    
    def test_register_partner_invalid_paypal_email(self):
        """Test registration with invalid PayPal email"""
        unique_email = f"test.invalid.{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test Invalid PayPal",
                "email": unique_email,
                "phone": "+52 55 1111 2222",
                "payment_method": "paypal",
                "paypal_email": "invalid-email",  # No @ symbol
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        print(f"Invalid PayPal registration status: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid PayPal email correctly rejected")
    
    def test_register_partner_missing_bank_info(self):
        """Test registration with bank method but missing CLABE"""
        unique_email = f"test.nobank.{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test No Bank Info",
                "email": unique_email,
                "phone": "+52 55 3333 4444",
                "payment_method": "bank",
                "bank_name": "BBVA",
                # Missing CLABE
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        print(f"Missing CLABE registration status: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Missing CLABE correctly rejected")


class TestBuyLotsPaymentMethods:
    """Test buying lots with different payment methods"""
    
    @pytest.fixture
    def partner_token(self):
        """Create a test partner and return token"""
        unique_email = f"test.buyer.{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test Buyer Partner",
                "email": unique_email,
                "phone": "+52 55 5555 6666",
                "payment_method": "bank",
                "bank_name": "BBVA",
                "clabe": "012180001064835429",
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Could not create test partner")
    
    def test_buy_lots_stripe(self, partner_token):
        """Test buying lots with Stripe"""
        response = requests.post(
            f"{BASE_URL}/api/partners/buy-lots?lots=1&method=stripe",
            headers={"Authorization": f"Bearer {partner_token}"}
        )
        
        print(f"Stripe buy lots status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "checkout_url" in data
        assert "purchase_id" in data
        assert data["lots"] == 1
        assert data["total_amount"] == 4000  # $4,000 per lot
        print(f"✓ Stripe checkout URL generated: {data['checkout_url'][:50]}...")
    
    def test_buy_lots_spei(self, partner_token):
        """Test buying lots with SPEI"""
        response = requests.post(
            f"{BASE_URL}/api/partners/buy-lots?lots=2&method=spei",
            headers={"Authorization": f"Bearer {partner_token}"}
        )
        
        print(f"SPEI buy lots status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "purchase_id" in data
        assert data["lots"] == 2
        assert data["total_amount"] == 8000  # 2 lots * $4,000
        assert data["payment_method"] == "spei"
        assert "message" in data
        print(f"✓ SPEI purchase created: {data['purchase_id']}")
    
    def test_buy_lots_paypal(self, partner_token):
        """Test buying lots with PayPal"""
        response = requests.post(
            f"{BASE_URL}/api/partners/buy-lots?lots=3&method=paypal",
            headers={"Authorization": f"Bearer {partner_token}"}
        )
        
        print(f"PayPal buy lots status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "purchase_id" in data
        assert data["lots"] == 3
        assert data["total_amount"] == 12000  # 3 lots * $4,000
        assert data["payment_method"] == "paypal"
        print(f"✓ PayPal purchase created: {data['purchase_id']}")


class TestReceiptUpload:
    """Test receipt upload endpoint"""
    
    @pytest.fixture
    def partner_token(self):
        """Create a test partner and return token"""
        unique_email = f"test.receipt.{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test Receipt Partner",
                "email": unique_email,
                "phone": "+52 55 7777 8888",
                "payment_method": "bank",
                "bank_name": "BBVA",
                "clabe": "012180001064835429",
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Could not create test partner")
    
    def test_upload_receipt_image(self, partner_token):
        """Test uploading receipt image"""
        # Create a simple test image (1x1 pixel PNG)
        import base64
        # Minimal valid PNG
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        files = {
            "file": ("receipt.png", png_data, "image/png")
        }
        data = {
            "lots": "1",
            "payment_method": "spei"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/partners/upload-receipt",
            headers={"Authorization": f"Bearer {partner_token}"},
            files=files,
            data=data
        )
        
        print(f"Upload receipt status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "purchase_id" in result
        assert result["status"] == "pending_verification"
        print(f"✓ Receipt uploaded successfully: {result['purchase_id']}")
    
    def test_upload_receipt_pdf(self, partner_token):
        """Test uploading receipt PDF"""
        # Minimal valid PDF
        pdf_data = b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
        
        files = {
            "file": ("receipt.pdf", pdf_data, "application/pdf")
        }
        data = {
            "lots": "2",
            "payment_method": "paypal"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/partners/upload-receipt",
            headers={"Authorization": f"Bearer {partner_token}"},
            files=files,
            data=data
        )
        
        print(f"Upload PDF receipt status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "purchase_id" in result
        print(f"✓ PDF receipt uploaded successfully: {result['purchase_id']}")
    
    def test_upload_receipt_invalid_type(self, partner_token):
        """Test uploading invalid file type"""
        files = {
            "file": ("receipt.exe", b"invalid content", "application/octet-stream")
        }
        data = {
            "lots": "1",
            "payment_method": "spei"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/partners/upload-receipt",
            headers={"Authorization": f"Bearer {partner_token}"},
            files=files,
            data=data
        )
        
        print(f"Invalid file type status: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid file type correctly rejected")


class TestDashboardPaymentInfo:
    """Test dashboard shows correct payment info"""
    
    def test_dashboard_shows_bank_info(self):
        """Test dashboard shows bank info for bank payment method"""
        unique_email = f"test.dash.bank.{uuid.uuid4().hex[:8]}@example.com"
        
        # Register with bank
        reg_response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test Dashboard Bank",
                "email": unique_email,
                "phone": "+52 55 1111 1111",
                "payment_method": "bank",
                "bank_name": "BBVA",
                "clabe": "012180001064835429",
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        assert reg_response.status_code == 200
        token = reg_response.json()["token"]
        
        # Get dashboard
        dash_response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert dash_response.status_code == 200
        data = dash_response.json()
        
        # Check payment info
        partner = data["partner"]
        assert partner.get("clabe") is None, "Full CLABE should not be exposed"
        assert "clabe_last4" in partner
        assert partner["clabe_last4"] == "5429"  # Last 4 of 012180001064835429
        print(f"✓ Dashboard shows masked CLABE: ****{partner['clabe_last4']}")
    
    def test_dashboard_shows_paypal_info(self):
        """Test dashboard shows PayPal info for PayPal payment method"""
        unique_email = f"test.dash.paypal.{uuid.uuid4().hex[:8]}@example.com"
        
        # Register with PayPal
        reg_response = requests.post(
            f"{BASE_URL}/api/partners/register?tenant_id={TENANT_ID}",
            json={
                "name": "Test Dashboard PayPal",
                "email": unique_email,
                "phone": "+52 55 2222 2222",
                "payment_method": "paypal",
                "paypal_email": "mytest@paypal.com",
                "password": "test123",
                "lots_to_buy": 1
            }
        )
        
        assert reg_response.status_code == 200
        token = reg_response.json()["token"]
        
        # Get dashboard
        dash_response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert dash_response.status_code == 200
        data = dash_response.json()
        
        # Check payment info
        partner = data["partner"]
        payment_info = partner.get("payment_info", {})
        assert payment_info.get("method") == "paypal"
        assert partner.get("paypal_email") is None, "Full PayPal email should not be exposed"
        print(f"✓ Dashboard shows PayPal payment method with masked email")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
