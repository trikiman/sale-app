import requests
from fastapi.testclient import TestClient

import backend.main as main


client = TestClient(main.app)


def test_cart_items_returns_fast_fallback_on_upstream_timeout(monkeypatch, tmp_path):
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    calls = {"count": 0}

    class BoomCart:
        def __init__(self, cookies_path):
            self.cookies_path = cookies_path

        def get_cart(self):
            calls["count"] += 1
            return {"success": False, "error": str(requests.ConnectTimeout("timeout"))}

        def close(self):
            return None

    monkeypatch.setattr(main, "_vkusvill_backoff_until", 0.0)
    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", BoomCart)

    first = client.get("/api/cart/items/123")
    second = client.get("/api/cart/items/123")

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
