"""
Unit tests for Notifier
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.notifier import Notifier


class TestNotifier:
    def test_notifier_init(self):
        """Test notifier initializes without errors"""
        notifier = Notifier()
        assert notifier.db is not None
        assert notifier.data_dir is not None
    
    def test_load_products(self):
        """Test loading products from JSON"""
        notifier = Notifier()
        products = notifier.load_products()
        # May be empty if no data file, but shouldn't error
        assert isinstance(products, list)
    
    def test_detect_new_products(self):
        """Test new product detection"""
        notifier = Notifier()
        new_products = notifier.detect_new_products()
        assert isinstance(new_products, list)
    
    def test_format_product_message(self):
        """Test message formatting"""
        notifier = Notifier()
        product = {
            'id': '123',
            'name': 'Test Product',
            'currentPrice': '100',
            'oldPrice': '200',
            'stock': 5,
            'unit': 'шт',
            'type': 'green',
            'url': 'https://vkusvill.ru/test'
        }
        message = notifier.format_product_message(product)
        assert 'Test Product' in message
        assert '100₽' in message
        assert '🟢' in message
    
    def test_get_favorite_alerts(self):
        """Test favorite alerts"""
        notifier = Notifier()
        alerts = notifier.get_favorite_alerts()
        assert isinstance(alerts, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
