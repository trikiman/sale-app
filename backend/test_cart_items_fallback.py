import json
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


def test_cart_bootstrap_uses_saved_metadata_without_warmup(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text(
        json.dumps(
            {
                "cookies": [{"name": "UF_USER_AUTH", "value": "Y"}],
                "sessid": "saved-sessid",
                "user_id": 991,
            }
        ),
        encoding="utf-8",
    )

    cart = VkusVillCart(str(cookies_path))

    calls = {"extract": 0}

    def should_not_extract():
        calls["extract"] += 1
        raise AssertionError("_extract_session_params should not be called when metadata exists")

    monkeypatch.setattr(cart, "_extract_session_params", should_not_extract)

    cart._ensure_session()

    assert calls["extract"] == 0
    assert cart.sessid == "saved-sessid"
    assert cart.user_id == 991


def test_cart_timeout_returns_pending_without_inline_cart_check(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    cart = VkusVillCart(str(cookies_path), user_id=1, sessid="sess")
    monkeypatch.setattr(cart, "_ensure_session", lambda: None)

    calls = {"request": 0, "get_cart": 0}

    def fake_request(url, data, referer="/", timeout=None):
        calls["request"] += 1
        raise httpx.ReadTimeout("timed out")

    def should_not_get_cart():
        calls["get_cart"] += 1
        raise AssertionError("get_cart should not be called from the timeout path")

    monkeypatch.setattr(cart, "_request", fake_request)
    monkeypatch.setattr(cart, "get_cart", should_not_get_cart)

    result = cart.add(26198, price_type=222, is_green=1)

    assert calls["request"] == 1
    assert calls["get_cart"] == 0
    assert result["success"] is False
    assert result["pending"] is True
    assert result["error_type"] == "pending_timeout"
