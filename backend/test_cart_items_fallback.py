import httpx
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main
from cart.vkusvill_api import VkusVillCart


client = TestClient(main.app)


def test_cart_items_returns_fast_fallback_on_upstream_timeout(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    calls = {"count": 0}

    class BoomCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def get_cart(self):
            calls["count"] += 1
            return {"success": False, "error": str(httpx.ConnectTimeout("timeout"))}

        def close(self):
            return None

    monkeypatch.setattr(main, "_vkusvill_backoff_until", 0.0)
    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", BoomCart)

    first = client.get("/api/cart/items/123", headers={"X-Telegram-User-Id": "123"})
    second = client.get("/api/cart/items/123", headers={"X-Telegram-User-Id": "123"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert first.json() == {
        "items_count": 0,
        "total_price": 0,
        "items": [],
        "source_unavailable": True,
        "source_error": "timeout",
    }
    assert second.json()["source_unavailable"] is True
    assert second.json()["source_error"] == "VkusVill temporarily unreachable"


def test_cart_add_maps_upstream_timeout_to_504(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class SlowCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def add(self, product_id, price_type=1, is_green=0):
            return {"success": False, "error": "timed out", "error_type": "timeout"}

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", SlowCart)

    response = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 33243, "is_green": 1, "price_type": 222},
    )

    assert response.status_code == 504
    assert response.json() == {"detail": "Cart API timeout"}


def test_cart_uses_cached_proxy_without_refresh(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class DummyProxyManager:
        def __init__(self):
            self.calls = []

        def get_working_proxy(self, allow_refresh=True):
            self.calls.append(allow_refresh)
            return "127.0.0.1:1080"

    pm = DummyProxyManager()
    cart = VkusVillCart(str(cookies_path), proxy_manager=pm)

    assert cart._get_proxy_url() == "socks5://127.0.0.1:1080"
    assert pm.calls == [False]


def test_cart_timeout_can_be_recovered_from_cart_state(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    cart = VkusVillCart(str(cookies_path), user_id=1, sessid="sess")
    monkeypatch.setattr(cart, "_ensure_session", lambda: None)

    calls = {"count": 0}

    def fake_request(url, data, referer="/"):
        calls["count"] += 1
        raise httpx.ReadTimeout("timed out")

    def fake_get_cart():
        return {
            "success": True,
            "items_count": 1,
            "total_price": 49,
            "raw": {
                "basket": {
                    "26198_0": {
                        "PRODUCT_ID": 26198,
                        "NAME": "Bread",
                        "Q": 1,
                        "PRICE": 49,
                        "CAN_BUY": "Y",
                        "MAX_Q": 1,
                    }
                }
            },
        }

    monkeypatch.setattr(cart, "_request", fake_request)
    monkeypatch.setattr(cart, "get_cart", fake_get_cart)

    result = cart.add(26198, price_type=222, is_green=1)

    assert calls["count"] == 1
    assert result["success"] is True
    assert result["product_id"] == 26198
    assert result["cart_items"] == 1
