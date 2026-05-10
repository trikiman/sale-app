"""v1.20 Phase 65 UX-03: client_request_id idempotency unit tests.

Covers:
- Same client_request_id returns same attempt_id + only 1 VkusVillCart.add call.
- Different client_request_ids get different attempt_ids.
- GET /api/cart/add-status-by-client-id/{cri} returns the attempt; 404 on unknown.

Shape intentionally mirrors backend/test_cart_pending_contract.py so the
fixture conventions (TestClient, monkeypatch VkusVillCart, _clear_attempt_state)
stay consistent across the cart test suite.
"""
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main


client = TestClient(main.app)


def _clear_attempt_state():
    main._cart_add_attempts.clear()
    main._cart_add_attempt_index.clear()
    main._cart_add_attempt_by_client_id.clear()


class _PendingCart:
    """Fake VkusVillCart that always reports the upstream timed out — forces
    the endpoint down the `allow_pending` branch so the attempt stays pending
    and the client_request_id index stays populated for the duration of the
    test (dedupe window is 5 s)."""

    def __init__(self, cookies_path, proxy_manager=None):
        self.cookies_path = cookies_path

    def add(self, product_id, price_type=1, is_green=0):
        # Count calls on the class so fixtures can reset between tests.
        type(self).calls += 1
        return {
            "success": False,
            "pending": True,
            "error": "pending_timeout",
            "error_type": "pending_timeout",
        }

    def close(self):
        return None


def test_client_request_id_dedupe_returns_same_attempt(monkeypatch, tmp_path):
    """Two POSTs with the same client_request_id within 100 ms must map to
    the same attempt_id AND must fire exactly one VkusVillCart.add call
    (UX-03: no double basket_add.php to VkusVill on frontend retry)."""
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class Cart(_PendingCart):
        calls = 0

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", Cart)

    cri = "client-req-abc-123"
    body = {
        "user_id": "777",
        "product_id": 42,
        "allow_pending": True,
        "client_request_id": cri,
    }
    headers = {"X-Telegram-User-Id": "777"}

    first = client.post("/api/cart/add", headers=headers, json=body)
    second = client.post("/api/cart/add", headers=headers, json=body)

    assert first.status_code == 202, first.json()
    assert second.status_code == 202, second.json()
    first_body = first.json()
    second_body = second.json()
    assert first_body["attempt_id"] == second_body["attempt_id"], (
        f"expected same attempt_id; got first={first_body['attempt_id']} "
        f"second={second_body['attempt_id']}"
    )
    # Only the first POST reaches VkusVill. Second is deduped by client_request_id.
    assert Cart.calls == 1, f"expected 1 VkusVill call; got {Cart.calls}"
    # Secondary index populated under the expected key.
    assert main._cart_add_attempt_by_client_id.get(cri) == first_body["attempt_id"]
    # Dedupe source flag is set so operators can see which gate fired.
    assert second_body.get("source") == "client_request_id_dedupe"


def test_client_request_id_different_creates_new_attempt(monkeypatch, tmp_path):
    """Different client_request_ids must produce distinct attempts even for
    the same user — the pair-based dedupe window still works the same as
    before for clients that did NOT send a client_request_id."""
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class Cart(_PendingCart):
        calls = 0

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", Cart)

    headers = {"X-Telegram-User-Id": "888"}
    # Use different product_ids so the (user_id, product_id) pair dedupe
    # does not merge them — we want to prove client_request_id is the
    # discriminator for THIS scenario.
    first = client.post(
        "/api/cart/add",
        headers=headers,
        json={"user_id": "888", "product_id": 11, "allow_pending": True, "client_request_id": "cri-one"},
    )
    second = client.post(
        "/api/cart/add",
        headers=headers,
        json={"user_id": "888", "product_id": 22, "allow_pending": True, "client_request_id": "cri-two"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    first_id = first.json()["attempt_id"]
    second_id = second.json()["attempt_id"]
    assert first_id != second_id, "expected different attempt_ids for different client_request_ids"
    assert Cart.calls == 2, f"expected 2 VkusVill calls; got {Cart.calls}"
    # Both client_request_ids live in the secondary index.
    assert main._cart_add_attempt_by_client_id.get("cri-one") == first_id
    assert main._cart_add_attempt_by_client_id.get("cri-two") == second_id


def test_cart_add_status_by_client_id_lookup(monkeypatch, tmp_path):
    """GET /api/cart/add-status-by-client-id/{cri} returns the pending
    attempt payload; 404 for unknown client_request_id."""
    _clear_attempt_state()
    cookies_path = tmp_path / "cookies.json"
    cookies_path.write_text("[]", encoding="utf-8")

    class Cart(_PendingCart):
        calls = 0

        def get_cart(self):
            # Called by cart_add_status_endpoint when it polls upstream.
            # Return "no basket found" so the attempt stays pending.
            return {"success": False, "error": "no_basket_yet"}

        def _find_cart_item(self, cart_payload, product_id):
            return None

    monkeypatch.setattr(main, "_get_phone_for_user", lambda user_id: None)
    monkeypatch.setattr(main, "get_user_cookies_path", lambda user_id: str(cookies_path))
    monkeypatch.setattr(main, "VkusVillCart", Cart)

    cri = "lookup-cri-xyz"
    headers = {"X-Telegram-User-Id": "999"}

    # Create a pending attempt by POSTing /api/cart/add once.
    post_resp = client.post(
        "/api/cart/add",
        headers=headers,
        json={"user_id": "999", "product_id": 5150, "allow_pending": True, "client_request_id": cri},
    )
    assert post_resp.status_code == 202
    created_attempt_id = post_resp.json()["attempt_id"]

    # Happy path: GET by client_request_id returns the same attempt.
    status_resp = client.get(f"/api/cart/add-status-by-client-id/{cri}", headers=headers)
    assert status_resp.status_code == 200, status_resp.json()
    body = status_resp.json()
    assert body["attempt_id"] == created_attempt_id
    assert body["product_id"] == 5150
    assert body["user_id"] == "999"
    # Attempt is still pending (get_cart returned no basket); schema matches
    # the existing /api/cart/add-status/{attempt_id} serializer.
    assert "status" in body
    assert "pending" in body
    assert "started_at" in body

    # 404 for an unknown client_request_id.
    missing_resp = client.get(
        "/api/cart/add-status-by-client-id/does-not-exist",
        headers=headers,
    )
    assert missing_resp.status_code == 404
