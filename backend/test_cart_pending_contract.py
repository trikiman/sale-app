import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main


client = TestClient(main.app)


def _clear_attempt_state():
    main._cart_add_attempts.clear()
    main._cart_add_attempt_index.clear()


def test_cart_add_allow_pending_returns_202_with_attempt_id(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class PendingCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def add(self, product_id, price_type=1, is_green=0):
            return {"success": False, "pending": True, "error": "pending_timeout", "error_type": "pending_timeout"}

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", PendingCart)

    response = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={
            "user_id": "123",
            "product_id": 33243,
            "is_green": 1,
            "price_type": 222,
            "allow_pending": True,
        },
    )

    body = response.json()
    assert response.status_code == 202
    assert body["pending"] is True
    assert body["status"] == "pending"
    assert body["attempt_id"]
    assert body["product_id"] == 33243
    assert body["user_id"] == "123"
    assert body["started_at"] is not None
    assert body["resolved_at"] is None
    assert body["duration_ms"] is None


def test_cart_add_allow_pending_can_return_immediate_success(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class ImmediateSuccessCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def add(self, product_id, price_type=1, is_green=0):
            return {"success": True, "cart_items": 4, "cart_total": 310}

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", ImmediateSuccessCart)

    response = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 33243, "allow_pending": True},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["cart_items"] == 4
    assert body["cart_total"] == 310


def test_duplicate_pending_adds_reuse_same_attempt_id(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")
    calls = {"count": 0}

    class PendingCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def add(self, product_id, price_type=1, is_green=0):
            calls["count"] += 1
            return {"success": False, "pending": True, "error": "pending_timeout", "error_type": "pending_timeout"}

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", PendingCart)

    first = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 55, "allow_pending": True},
    )
    second = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 55, "allow_pending": True},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["attempt_id"] == second.json()["attempt_id"]
    assert calls["count"] == 1


def test_cart_add_status_can_transition_pending_to_success(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class PendingThenSuccessCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def add(self, product_id, price_type=1, is_green=0):
            return {"success": False, "pending": True, "error": "pending_timeout", "error_type": "pending_timeout"}

        def get_cart(self):
            return {
                "success": True,
                "items_count": 3,
                "total_price": 145,
                "raw": {
                    "basket": {
                        "77_0": {
                            "PRODUCT_ID": 77,
                            "NAME": "Test Product",
                            "Q": 1,
                        }
                    }
                },
            }

        def _find_cart_item(self, cart_payload, product_id):
            return cart_payload["raw"]["basket"]["77_0"]

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", PendingThenSuccessCart)

    pending = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 77, "allow_pending": True},
    )

    attempt_id = pending.json()["attempt_id"]
    response = client.get(f"/api/cart/add-status/{attempt_id}", headers={"X-Telegram-User-Id": "123"})

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["cart_items"] == 3
    assert body["cart_total"] == 145
    assert body["source"] == "status_lookup_cart"
    assert body["resolved_at"] is not None
    assert body["duration_ms"] is not None


def test_cart_add_status_can_transition_pending_to_failed(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class PendingThenMissingCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def add(self, product_id, price_type=1, is_green=0):
            return {"success": False, "pending": True, "error": "pending_timeout", "error_type": "pending_timeout"}

        def get_cart(self):
            return {
                "success": True,
                "items_count": 0,
                "total_price": 0,
                "raw": {"basket": {}},
            }

        def _find_cart_item(self, cart_payload, product_id):
            return None

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", PendingThenMissingCart)

    pending = client.post(
        "/api/cart/add",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 88, "allow_pending": True},
    )

    attempt_id = pending.json()["attempt_id"]
    response = client.get(f"/api/cart/add-status/{attempt_id}", headers={"X-Telegram-User-Id": "123"})

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "failed"
    assert body["source"] == "status_lookup_cart"
    assert body["last_error"] == "product_not_found_in_cart"
    assert body["resolved_at"] is not None
    assert body["duration_ms"] is not None


def test_cart_items_preserve_decimal_quantity_fields(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class DecimalCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def get_cart(self):
            return {
                "success": True,
                "items_count": 1,
                "total_price": 91,
                "items": {
                    "500_0": {
                        "PRODUCT_ID": 500,
                        "NAME": "Apples",
                        "PRICE": 91,
                        "BASE_PRICE": 100,
                        "Q": "0.73",
                        "MAX_Q": "12.3",
                        "UNIT": "кг",
                        "STEP": "0.01",
                        "KOEF": "0.01",
                        "CAN_BUY": "Y",
                    }
                },
            }

        def close(self):
            return None

    monkeypatch.setattr(main, "_vkusvill_backoff_until", 0.0)
    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", DecimalCart)

    response = client.get("/api/cart/items/123", headers={"X-Telegram-User-Id": "123"})

    body = response.json()
    assert response.status_code == 200
    assert body["items"][0]["basket_key"] == "500_0"
    assert body["items"][0]["quantity"] == 0.73
    assert body["items"][0]["max_q"] == 12.3
    assert body["items"][0]["unit"] == "кг"
    assert body["items"][0]["step"] == 0.01
    assert body["items"][0]["koef"] == 0.01


def test_cart_set_quantity_route_delegates_to_cart_client(monkeypatch, tmp_path):
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")
    seen = {}

    class QuantityCart:
        def __init__(self, cookies_path, proxy_manager=None):
            self.cookies_path = cookies_path

        def set_quantity(self, product_id, quantity):
            seen["product_id"] = product_id
            seen["quantity"] = quantity
            return {
                "success": True,
                "items_count": 2,
                "total_price": 182,
                "quantity": quantity,
                "max_q": 12.3,
            }

        def close(self):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", QuantityCart)

    response = client.post(
        "/api/cart/set-quantity",
        headers={"X-Telegram-User-Id": "123"},
        json={"user_id": "123", "product_id": 500, "quantity": 0.73},
    )

    body = response.json()
    assert response.status_code == 200
    assert seen == {"product_id": 500, "quantity": 0.73}
    assert body["quantity"] == 0.73
    assert body["max_q"] == 12.3
