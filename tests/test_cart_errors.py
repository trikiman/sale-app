"""Unit tests for cart-add endpoint error classification.

Verifies that cart_add_endpoint returns JSONResponse with error_type
field for all failure paths instead of generic HTTPException.
"""
import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)

HEADERS = {"x-telegram-user-id": "12345"}
PAYLOAD = {
    "user_id": "12345",
    "product_id": 731,
    "price_type": 1,
    "is_green": 0,
}


def _mock_cart(result_dict):
    """Create a mock VkusVillCart that returns result_dict from add()."""
    mock_cart_instance = MagicMock()
    mock_cart_instance.add.return_value = result_dict
    mock_cart_class = MagicMock(return_value=mock_cart_instance)
    return mock_cart_class


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_auth_expired_returns_401_with_error_type(mock_cart_cls, mock_exists, mock_resolve):
    """auth_expired error_type should return 401 with error_type in JSON body."""
    mock_cart_cls.return_value = _mock_cart(
        {"success": False, "error": "No sessid available", "error_type": "auth_expired"}
    ).return_value
    resp = client.post("/api/cart/add", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "auth_expired"


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_product_gone_returns_410_with_error_type(mock_cart_cls, mock_exists, mock_resolve):
    """product_gone error_type should return 410 with error_type in JSON body."""
    mock_cart_cls.return_value = _mock_cart(
        {"success": False, "error": "Product unavailable", "error_type": "product_gone"}
    ).return_value
    resp = client.post("/api/cart/add", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 410
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "product_gone"


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_transient_returns_502_with_error_type(mock_cart_cls, mock_exists, mock_resolve):
    """transient error_type should return 502 with error_type in JSON body."""
    mock_cart_cls.return_value = _mock_cart(
        {"success": False, "error": "Connection failed", "error_type": "transient"}
    ).return_value
    resp = client.post("/api/cart/add", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 502
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "transient"


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_pending_timeout_with_allow_pending_returns_202(mock_cart_cls, mock_exists, mock_resolve):
    """pending_timeout with allow_pending should return 202."""
    mock_cart_cls.return_value = _mock_cart(
        {"success": False, "error": "pending_timeout", "error_type": "pending_timeout", "pending": True}
    ).return_value
    payload = {**PAYLOAD, "allow_pending": True, "client_request_id": "test-req-1"}
    resp = client.post("/api/cart/add", json=payload, headers=HEADERS)
    assert resp.status_code == 202


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_timeout_returns_504_with_error_type(mock_cart_cls, mock_exists, mock_resolve):
    """timeout error_type should return 504 with error_type in JSON body."""
    mock_cart_cls.return_value = _mock_cart(
        {"success": False, "error": "Cart API timed out", "error_type": "timeout"}
    ).return_value
    resp = client.post("/api/cart/add", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 504
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "timeout"


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_generic_api_error_returns_400_with_error_type(mock_cart_cls, mock_exists, mock_resolve):
    """Generic API error should return 400 with error_type in JSON body."""
    mock_cart_cls.return_value = _mock_cart(
        {"success": False, "error": "Some API error", "error_type": "api"}
    ).return_value
    resp = client.post("/api/cart/add", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "api"


@patch("backend.main._resolve_cart_cookies_path", return_value="/tmp/fake_cookies.json")
@patch("os.path.exists", return_value=True)
@patch("backend.main.VkusVillCart")
def test_exception_returns_500_with_error_type(mock_cart_cls, mock_exists, mock_resolve):
    """Unhandled exception should return 500 with error_type 'unknown' in JSON body."""
    mock_cart_cls.return_value.__enter__ = MagicMock()
    mock_cart_cls.return_value.__exit__ = MagicMock()
    mock_cart_cls.return_value.add.side_effect = RuntimeError("Unexpected crash")
    mock_cart_cls.return_value.close = MagicMock()
    resp = client.post("/api/cart/add", json=PAYLOAD, headers=HEADERS)
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "unknown"
