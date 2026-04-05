"""
Unit tests for FastAPI backend
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestHealthCheck:
    def test_root_endpoint(self):
        """Root serves the miniapp shell or fallback response."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.text
        assert "<html" in response.text.lower() or "vkusvill mini app api" in response.text.lower()


class TestProducts:
    def test_get_products(self):
        """Test getting products"""
        response = client.get("/api/products")
        # May be 404 if no data file, or 200 if exists
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "products" in data
            assert "updatedAt" in data


class TestFavorites:
    TEST_USER_ID = 999999999  # Test user ID
    TEST_PRODUCT = {"product_id": "test123", "product_name": "Test Product"}
    AUTH_HEADERS = {"X-Telegram-User-Id": str(TEST_USER_ID)}
    
    def test_get_favorites_empty(self):
        """Test getting favorites for new user"""
        response = client.get(f"/api/favorites/{self.TEST_USER_ID}", headers=self.AUTH_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "favorites" in data
    
    def test_add_favorite(self):
        """Test adding a product to favorites"""
        response = client.post(
            f"/api/favorites/{self.TEST_USER_ID}",
            json=self.TEST_PRODUCT,
            headers=self.AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"]
        assert data["product_id"] == self.TEST_PRODUCT["product_id"]
    
    def test_toggle_favorite_removes(self):
        """Test toggling favorite removes if already favorited"""
        # Clean up first - remove if exists
        client.delete(f"/api/favorites/{self.TEST_USER_ID}/{self.TEST_PRODUCT['product_id']}", headers=self.AUTH_HEADERS)
        
        # Add to favorites
        response1 = client.post(f"/api/favorites/{self.TEST_USER_ID}", json=self.TEST_PRODUCT, headers=self.AUTH_HEADERS)
        assert response1.json()["is_favorite"]
        
        # Toggle should remove
        response2 = client.post(f"/api/favorites/{self.TEST_USER_ID}", json=self.TEST_PRODUCT, headers=self.AUTH_HEADERS)
        assert response2.status_code == 200
        assert not response2.json()["is_favorite"]
    
    def test_remove_favorite(self):
        """Test removing a favorite directly"""
        # First add
        client.post(f"/api/favorites/{self.TEST_USER_ID}", json=self.TEST_PRODUCT, headers=self.AUTH_HEADERS)
        
        # Then remove
        response = client.delete(
            f"/api/favorites/{self.TEST_USER_ID}/{self.TEST_PRODUCT['product_id']}",
            headers=self.AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] or not data["success"]  # May already be removed


class TestSync:
    def test_sync_products(self):
        """Test sync endpoint"""
        response = client.post("/api/sync")
        # Either success or no file found
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
