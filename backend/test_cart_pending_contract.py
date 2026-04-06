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
