"""
Test Partners Dashboard Features - Iteration 6
Tests for:
- Dashboard with 3 tabs (Resumen Ejecutivo, Proyección de Inversión, Historial y Pagos)
- KPIs (inversión, participación, dividendos, valor)
- 48-month projection endpoint
- Reinvestment settings endpoint
- Purchase history and returns
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_PARTNER_EMAIL = "test.socio@example.com"
TEST_PARTNER_PASSWORD = "test123"

class TestPartnersDashboard:
    """Test partner dashboard endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get partner token for authenticated requests"""
        response = requests.post(
            f"{BASE_URL}/api/partners/login",
            json={"email": TEST_PARTNER_EMAIL, "password": TEST_PARTNER_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data["token"]
        self.partner = data["partner"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_partner_login_success(self):
        """Test partner login returns token and partner data"""
        response = requests.post(
            f"{BASE_URL}/api/partners/login",
            json={"email": TEST_PARTNER_EMAIL, "password": TEST_PARTNER_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify token exists
        assert "token" in data
        assert len(data["token"]) > 0
        
        # Verify partner data
        assert "partner" in data
        assert data["partner"]["email"] == TEST_PARTNER_EMAIL
        assert data["partner"]["total_lots"] == 10
        assert data["partner"]["total_investment"] == 40000
    
    def test_dashboard_returns_kpis(self):
        """Test dashboard endpoint returns correct KPIs"""
        response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify partner KPIs
        partner = data["partner"]
        assert partner["total_lots"] == 10
        assert partner["total_investment"] == 40000
        assert partner["participation_percent"] == 1.0  # 10 lots * 0.1%
        
        # Verify monthly return per lot
        assert data["monthly_return_per_lot"] == 100
        
        # Verify current lot price
        assert data["current_lot_price"] == 4000
        
        # Verify current value is calculated
        assert "current_value" in partner
        assert partner["current_value"] == 40000  # 10 lots * $4000
    
    def test_dashboard_returns_purchases_history(self):
        """Test dashboard returns purchase history"""
        response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify purchases array exists
        assert "purchases" in data
        assert isinstance(data["purchases"], list)
    
    def test_dashboard_returns_returns_history(self):
        """Test dashboard returns monthly returns history"""
        response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify recent_returns array exists
        assert "recent_returns" in data
        assert isinstance(data["recent_returns"], list)
    
    def test_dashboard_returns_payment_info(self):
        """Test dashboard returns masked payment info"""
        response = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify payment info is masked
        partner = data["partner"]
        assert "payment_info" in partner
        assert "clabe_last4" in partner
        # Full CLABE should not be exposed
        assert partner.get("clabe") is None


class TestProjectionEndpoint:
    """Test 48-month projection endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get partner token"""
        response = requests.post(
            f"{BASE_URL}/api/partners/login",
            json={"email": TEST_PARTNER_EMAIL, "password": TEST_PARTNER_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_projection_returns_48_months(self):
        """Test projection endpoint returns 48 months of data"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=true&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify 48 months of projection
        assert "projection" in data
        assert len(data["projection"]) == 48
        
        # Verify first month
        first_month = data["projection"][0]
        assert first_month["month"] == 1
        
        # Verify last month
        last_month = data["projection"][-1]
        assert last_month["month"] == 48
    
    def test_projection_kpis_correct(self):
        """Test projection KPIs are calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=true&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        
        # Verify initial values
        assert kpis["initial_investment"] == 40000
        assert kpis["initial_lots"] == 10
        assert kpis["initial_monthly_dividend"] == 1000  # 10 lots * $100
        
        # Verify growth with reinvestment
        assert kpis["final_lots"] > kpis["initial_lots"]
        assert kpis["lots_growth"] == kpis["final_lots"] - kpis["initial_lots"]
        
        # Verify ROI is positive
        assert kpis["roi_percentage"] > 0
        
        # Verify final portfolio value
        assert kpis["final_portfolio_value"] > kpis["initial_investment"]
    
    def test_projection_monthly_data_structure(self):
        """Test each month has correct data structure"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=true&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check first month structure
        month_data = data["projection"][0]
        required_fields = [
            "month", "lots_start", "lots_end", "monthly_dividend",
            "interest_earned", "lots_purchased", "portfolio_value",
            "roi_percentage", "recovered"
        ]
        for field in required_fields:
            assert field in month_data, f"Missing field: {field}"
    
    def test_projection_without_reinvestment(self):
        """Test projection without reinvestment"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=false",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        
        # Without reinvestment, lots should stay the same
        assert kpis["final_lots"] == kpis["initial_lots"]
        assert kpis["lots_growth"] == 0
        assert kpis["total_lots_purchased"] == 0
    
    def test_projection_config_returned(self):
        """Test projection returns configuration"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=true&reinvest_until_month=24",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "config" in data
        config = data["config"]
        assert config["reinvest_enabled"] == True
        assert config["reinvest_until_month"] == 24
        assert config["current_lot_price"] == 4000
        assert config["dividend_per_lot"] == 100
        assert config["total_months"] == 48


class TestReinvestmentSettings:
    """Test reinvestment settings endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get partner token"""
        response = requests.post(
            f"{BASE_URL}/api/partners/login",
            json={"email": TEST_PARTNER_EMAIL, "password": TEST_PARTNER_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_update_reinvestment_enabled(self):
        """Test updating reinvestment enabled setting"""
        # Enable reinvestment
        response = requests.put(
            f"{BASE_URL}/api/partners/reinvestment-settings?reinvest_enabled=true&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reinvest_enabled"] == True
        
        # Verify in dashboard
        dashboard = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers=self.headers
        ).json()
        assert dashboard["partner"]["reinvest_enabled"] == True
    
    def test_update_reinvestment_disabled(self):
        """Test disabling reinvestment"""
        response = requests.put(
            f"{BASE_URL}/api/partners/reinvestment-settings?reinvest_enabled=false&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reinvest_enabled"] == False
        
        # Re-enable for other tests
        requests.put(
            f"{BASE_URL}/api/partners/reinvestment-settings?reinvest_enabled=true&reinvest_until_month=36",
            headers=self.headers
        )
    
    def test_update_reinvest_until_month(self):
        """Test updating reinvest_until_month setting"""
        response = requests.put(
            f"{BASE_URL}/api/partners/reinvestment-settings?reinvest_enabled=true&reinvest_until_month=24",
            headers=self.headers
        )
        assert response.status_code == 200
        
        # Verify in dashboard
        dashboard = requests.get(
            f"{BASE_URL}/api/partners/dashboard",
            headers=self.headers
        ).json()
        assert dashboard["partner"]["reinvest_until_month"] == 24
        
        # Reset to default
        requests.put(
            f"{BASE_URL}/api/partners/reinvestment-settings?reinvest_enabled=true&reinvest_until_month=36",
            headers=self.headers
        )
    
    def test_reinvestment_requires_auth(self):
        """Test reinvestment endpoint requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/partners/reinvestment-settings?reinvest_enabled=true&reinvest_until_month=36"
        )
        assert response.status_code == 403 or response.status_code == 401


class TestProjectionCalculations:
    """Test projection calculation accuracy"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get partner token"""
        response = requests.post(
            f"{BASE_URL}/api/partners/login",
            json={"email": TEST_PARTNER_EMAIL, "password": TEST_PARTNER_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_dividend_calculation(self):
        """Test monthly dividend is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=false",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # First month dividend should be 10 lots * $100 = $1000
        first_month = data["projection"][0]
        assert first_month["monthly_dividend"] == 1000
    
    def test_roi_calculation(self):
        """Test ROI percentage is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=true&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        
        # ROI = (final_value - initial_investment) / initial_investment * 100
        expected_roi = (kpis["final_portfolio_value"] - kpis["initial_investment"]) / kpis["initial_investment"] * 100
        assert abs(kpis["roi_percentage"] - expected_roi) < 0.1  # Allow small rounding difference
    
    def test_lots_growth_with_reinvestment(self):
        """Test lots grow when reinvestment is enabled"""
        response = requests.get(
            f"{BASE_URL}/api/partners/projection?reinvest=true&reinvest_until_month=36",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        
        # With 10 lots at $100/month, should accumulate enough to buy more lots
        # $4000 per lot, so after ~4 months should have first new lot
        assert kpis["total_lots_purchased"] > 0
        assert kpis["final_lots"] > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
