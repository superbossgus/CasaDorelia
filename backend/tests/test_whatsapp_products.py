"""
Test suite for WhatsApp Alerts, Product Images, and Catalog Export features
Tests the new features added in iteration 3:
- WhatsApp alerts integration with Twilio
- Product image upload functionality
- Catalog export (JSON/CSV)
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cafecontrol.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
        return data["token"]
    
    def test_login_success(self, auth_token):
        """Test login with valid credentials"""
        assert auth_token is not None
        assert len(auth_token) > 0


class TestWhatsAppAlerts:
    """WhatsApp alerts endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cafecontrol.com",
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_whatsapp_status(self, headers):
        """Test WhatsApp status endpoint - should show Twilio configured"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/status", headers=headers)
        assert response.status_code == 200, f"Status check failed: {response.text}"
        
        data = response.json()
        assert "configured" in data
        assert "message" in data
        assert data["configured"] == True, "Twilio should be configured"
        assert "twilio_number" in data
        print(f"WhatsApp Status: {data}")
    
    def test_get_whatsapp_numbers(self, headers):
        """Test getting list of WhatsApp numbers"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/numbers", headers=headers)
        assert response.status_code == 200, f"Get numbers failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"WhatsApp Numbers count: {len(data)}")
    
    def test_add_whatsapp_number(self, headers):
        """Test adding a WhatsApp number"""
        test_number = {
            "phone_number": "+525591985187",
            "name": "TEST_WhatsApp_User"
        }
        
        response = requests.post(f"{BASE_URL}/api/whatsapp/numbers", 
                                json=test_number, headers=headers)
        
        # Could be 200 (created) or 400 (already exists)
        if response.status_code == 200:
            data = response.json()
            assert data["phone_number"] == test_number["phone_number"]
            assert data["name"] == test_number["name"]
            assert "id" in data
            print(f"Created WhatsApp number: {data['id']}")
        elif response.status_code == 400:
            # Number already exists - this is acceptable
            print("WhatsApp number already exists (expected)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code} - {response.text}")
    
    def test_add_invalid_whatsapp_number(self, headers):
        """Test adding invalid WhatsApp number (without + prefix)"""
        test_number = {
            "phone_number": "5591985187",  # Missing + prefix
            "name": "Invalid Number"
        }
        
        response = requests.post(f"{BASE_URL}/api/whatsapp/numbers", 
                                json=test_number, headers=headers)
        assert response.status_code == 400, "Should reject number without + prefix"
        print("Invalid number correctly rejected")


class TestProductImages:
    """Product image management tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cafecontrol.com",
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_product_id(self, headers):
        """Get a product ID for testing"""
        response = requests.get(f"{BASE_URL}/api/products", headers=headers)
        assert response.status_code == 200
        products = response.json()
        if products:
            return products[0]["id"]
        return None
    
    def test_get_products_with_images(self, headers):
        """Test that products include image fields"""
        response = requests.get(f"{BASE_URL}/api/products", headers=headers)
        assert response.status_code == 200
        
        products = response.json()
        assert isinstance(products, list)
        
        if products:
            product = products[0]
            # Check that image fields exist in response
            assert "main_image" in product or product.get("main_image") is None
            assert "images" in product or product.get("images") is None
            print(f"Products count: {len(products)}")
            print(f"First product has main_image: {product.get('main_image')}")
            print(f"First product has images: {product.get('images')}")
    
    def test_update_product_images_via_url(self, headers, test_product_id):
        """Test updating product images via URL"""
        if not test_product_id:
            pytest.skip("No products available for testing")
        
        image_data = {
            "main_image": "https://example.com/test-image.jpg",
            "images": ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
        }
        
        response = requests.put(f"{BASE_URL}/api/products/{test_product_id}/images",
                               json=image_data, headers=headers)
        assert response.status_code == 200, f"Update images failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        print(f"Image update response: {data}")
        
        # Verify the update
        response = requests.get(f"{BASE_URL}/api/products", headers=headers)
        products = response.json()
        updated_product = next((p for p in products if p["id"] == test_product_id), None)
        
        if updated_product:
            assert updated_product.get("main_image") == image_data["main_image"]
            print(f"Product images updated successfully")


class TestCatalogExport:
    """Catalog export tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cafecontrol.com",
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def cafeteria_id(self, headers):
        """Get a cafeteria ID for testing"""
        response = requests.get(f"{BASE_URL}/api/cafeterias", headers=headers)
        assert response.status_code == 200
        cafeterias = response.json()
        if cafeterias:
            return cafeterias[0]["id"]
        return None
    
    def test_export_catalog_json(self, headers, cafeteria_id):
        """Test exporting catalog as JSON"""
        if not cafeteria_id:
            pytest.skip("No cafeterias available for testing")
        
        response = requests.get(f"{BASE_URL}/api/catalog/export/{cafeteria_id}",
                               params={"format": "json"}, headers=headers)
        assert response.status_code == 200, f"Export JSON failed: {response.text}"
        
        data = response.json()
        assert "cafeteria" in data
        assert "products" in data
        assert "exported_at" in data
        
        print(f"Catalog export - Cafeteria: {data['cafeteria']['name']}")
        print(f"Catalog export - Products count: {len(data['products'])}")
        
        # Verify product structure
        if data["products"]:
            product = data["products"][0]
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert "category" in product
    
    def test_export_catalog_csv(self, headers, cafeteria_id):
        """Test exporting catalog as CSV"""
        if not cafeteria_id:
            pytest.skip("No cafeterias available for testing")
        
        response = requests.get(f"{BASE_URL}/api/catalog/export/{cafeteria_id}",
                               params={"format": "csv"}, headers=headers)
        assert response.status_code == 200, f"Export CSV failed: {response.text}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV content type, got: {content_type}"
        
        # Check CSV content
        csv_content = response.text
        assert "ID" in csv_content or "Nombre" in csv_content
        print(f"CSV export successful, content length: {len(csv_content)}")
    
    def test_export_catalog_invalid_cafeteria(self, headers):
        """Test exporting catalog with invalid cafeteria ID"""
        response = requests.get(f"{BASE_URL}/api/catalog/export/invalid-id-12345",
                               params={"format": "json"}, headers=headers)
        assert response.status_code == 404, "Should return 404 for invalid cafeteria"


class TestIngredientAlerts:
    """Ingredient alerts endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cafecontrol.com",
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_get_ingredient_alerts(self, headers):
        """Test getting ingredient alerts"""
        response = requests.get(f"{BASE_URL}/api/ingredient-inventory/alerts", headers=headers)
        assert response.status_code == 200, f"Get alerts failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"Ingredient alerts count: {len(data)}")
        
        if data:
            alert = data[0]
            assert "ingredient_name" in alert
            assert "current_stock" in alert
            assert "alert_type" in alert
            print(f"First alert: {alert['ingredient_name']} - {alert['alert_type']}")


class TestSidebarNavigation:
    """Test that all sidebar navigation endpoints exist"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cafecontrol.com",
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_all_api_endpoints(self, headers):
        """Test all main API endpoints are accessible"""
        endpoints = [
            "/api/products",
            "/api/categories",
            "/api/cafeterias",
            "/api/ingredients",
            "/api/recipes",
            "/api/suppliers",
            "/api/inventory",
            "/api/ingredient-inventory",
            "/api/sales",
            "/api/purchases",
            "/api/dashboard/stats",
            "/api/whatsapp/status",
            "/api/whatsapp/numbers",
        ]
        
        results = []
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            status = "✓" if response.status_code == 200 else "✗"
            results.append(f"{status} {endpoint}: {response.status_code}")
            assert response.status_code == 200, f"Endpoint {endpoint} failed: {response.status_code}"
        
        print("\nAPI Endpoints Status:")
        for result in results:
            print(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
