import requests
import sys
import json
from datetime import datetime

class CafeControlAPITester:
    def __init__(self, base_url="https://cafe-dashboard-28.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_credentials = {"email": "admin@cafecontrol.com", "password": "admin123"}
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

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
            details = f"Status: {response.status_code}"
            
            if not success:
                details += f" (Expected: {expected_status})"
                if response.text:
                    try:
                        error_data = response.json()
                        details += f" - {error_data.get('detail', response.text[:100])}"
                    except:
                        details += f" - {response.text[:100]}"
            
            self.log_test(name, success, details)
            return success, response.json() if success and response.text else {}

        except Exception as e:
            self.log_test(name, False, f"Error: {str(e)}")
            return False, {}

    def test_seed_data(self):
        """Test seed data creation"""
        print("\n🌱 Testing Seed Data Creation...")
        success, response = self.run_test(
            "Seed Data Creation",
            "POST",
            "seed",
            200
        )
        return success

    def test_login(self):
        """Test login with admin credentials"""
        print("\n🔐 Testing Authentication...")
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data=self.admin_credentials
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.log_test("Token Extraction", True, "JWT token obtained")
            return True
        else:
            self.log_test("Token Extraction", False, "No token in response")
            return False

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n👤 Testing Auth Endpoints...")
        
        # Test /auth/me
        self.run_test("Get Current User", "GET", "auth/me", 200)

    def test_cafeterias(self):
        """Test cafeteria endpoints"""
        print("\n☕ Testing Cafeteria Endpoints...")
        
        # Get cafeterias
        success, cafeterias = self.run_test("Get Cafeterias", "GET", "cafeterias", 200)
        
        if success and cafeterias:
            self.cafeterias = cafeterias
            self.log_test("Cafeterias Data", len(cafeterias) >= 3, f"Found {len(cafeterias)} cafeterias")
            return True
        return False

    def test_categories_and_products(self):
        """Test categories and products"""
        print("\n📦 Testing Categories & Products...")
        
        # Get categories
        success, categories = self.run_test("Get Categories", "GET", "categories", 200)
        if success:
            self.categories = categories
            self.log_test("Categories Data", len(categories) >= 4, f"Found {len(categories)} categories")
        
        # Get products
        success, products = self.run_test("Get Products", "GET", "products", 200)
        if success:
            self.products = products
            self.log_test("Products Data", len(products) >= 10, f"Found {len(products)} products")
            return True
        return False

    def test_inventory(self):
        """Test inventory endpoints"""
        print("\n📋 Testing Inventory...")
        
        # Get inventory
        success, inventory = self.run_test("Get Inventory", "GET", "inventory", 200)
        if success:
            self.log_test("Inventory Data", len(inventory) > 0, f"Found {len(inventory)} inventory items")
            
            # Test inventory movements
            self.run_test("Get Inventory Movements", "GET", "inventory/movements", 200)
            return True
        return False

    def test_suppliers(self):
        """Test supplier endpoints"""
        print("\n🏪 Testing Suppliers...")
        
        # Get suppliers
        success, suppliers = self.run_test("Get Suppliers", "GET", "suppliers", 200)
        if success:
            self.suppliers = suppliers
            self.log_test("Suppliers Data", len(suppliers) >= 3, f"Found {len(suppliers)} suppliers")
            return True
        return False

    def test_sales(self):
        """Test sales endpoints"""
        print("\n💰 Testing Sales...")
        
        # Get sales
        success, sales = self.run_test("Get Sales", "GET", "sales", 200)
        if success:
            self.sales = sales
            self.log_test("Sales Data", len(sales) > 0, f"Found {len(sales)} sales")
            return True
        return False

    def test_purchases(self):
        """Test purchase endpoints"""
        print("\n🛒 Testing Purchases...")
        
        # Get purchases
        success, purchases = self.run_test("Get Purchases", "GET", "purchases", 200)
        if success:
            self.log_test("Purchases Data", True, f"Found {len(purchases)} purchases")
            return True
        return False

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        print("\n📊 Testing Dashboard Stats...")
        
        success, stats = self.run_test("Dashboard Stats", "GET", "dashboard/stats", 200)
        if success:
            required_fields = ['total_sales_today', 'total_sales_month', 'total_profit_today', 
                             'total_profit_month', 'sales_count_today', 'low_stock_alerts', 
                             'top_products', 'sales_by_cafeteria', 'sales_trend']
            
            missing_fields = [field for field in required_fields if field not in stats]
            
            if not missing_fields:
                self.log_test("Dashboard Stats Structure", True, "All required fields present")
                return True
            else:
                self.log_test("Dashboard Stats Structure", False, f"Missing fields: {missing_fields}")
        return False

    def test_reports(self):
        """Test report endpoints"""
        print("\n📈 Testing Reports...")
        
        # Sales comparison
        self.run_test("Sales Comparison Report", "GET", "reports/sales-comparison", 200)
        
        # Profit analysis
        self.run_test("Profit Analysis Report", "GET", "reports/profit-analysis", 200)

    def test_clip_integration(self):
        """Test Clip POS integration (mock)"""
        print("\n📱 Testing Clip Integration (Mock)...")
        
        # Clip status
        self.run_test("Clip Status", "GET", "clip/status", 200)
        
        # Clip sync
        self.run_test("Clip Sync", "POST", "clip/sync", 200)

    def test_users_management(self):
        """Test user management (admin only)"""
        print("\n👥 Testing User Management...")
        
        # Get users
        self.run_test("Get Users", "GET", "users", 200)

    def test_create_sale(self):
        """Test creating a new sale"""
        print("\n🛍️ Testing Sale Creation...")
        
        if not hasattr(self, 'cafeterias') or not hasattr(self, 'products'):
            self.log_test("Sale Creation", False, "Missing cafeterias or products data")
            return False
        
        if not self.cafeterias or not self.products:
            self.log_test("Sale Creation", False, "No cafeterias or products available")
            return False
        
        # Create a test sale
        sale_data = {
            "cafeteria_id": self.cafeterias[0]["id"],
            "items": [
                {
                    "product_id": self.products[0]["id"],
                    "product_name": self.products[0]["name"],
                    "quantity": 2,
                    "unit_price": self.products[0]["price"],
                    "subtotal": self.products[0]["price"] * 2
                }
            ],
            "payment_method": "efectivo"
        }
        
        success, response = self.run_test("Create Sale", "POST", "sales", 200, data=sale_data)
        return success

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting CaféControl API Tests...")
        print(f"🎯 Target URL: {self.base_url}")
        
        # Test sequence
        tests = [
            self.test_seed_data,
            self.test_login,
            self.test_auth_endpoints,
            self.test_cafeterias,
            self.test_categories_and_products,
            self.test_inventory,
            self.test_suppliers,
            self.test_sales,
            self.test_purchases,
            self.test_dashboard_stats,
            self.test_reports,
            self.test_clip_integration,
            self.test_users_management,
            self.test_create_sale
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(f"Test {test.__name__}", False, f"Exception: {str(e)}")
        
        # Print summary
        print(f"\n📊 Test Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = CafeControlAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/test_reports/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'tests_run': tester.tests_run,
                'tests_passed': tester.tests_passed,
                'success_rate': (tester.tests_passed/tester.tests_run*100) if tester.tests_run > 0 else 0,
                'timestamp': datetime.now().isoformat()
            },
            'results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())