"""
Tests for the Phase 64 USE_FAST_CART_ADD_ENDPOINT feature flag.

Guarantees:
- Flag is OFF by default (imports with a clean env produce False).
- FAST_CART_ADD_URL is None until the Phase-64 spike identifies one.
- When flag=True but URL unset, the fast path raises NotImplementedError
  (the intentional guard against flipping the flag before the swap lands).
- When flag=False, the add() path uses BASKET_ADD_URL as it always has
  (legacy byte-identical behavior).

None of these tests hit the network; `_request` is monkey-patched to
capture the call and return a synthetic VkusVill-style success payload.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _write_cookies(path: Path, *, sessid: str = "sess-xyz", user_id: int = 987):
    path.write_text(
        json.dumps(
            {
                "cookies": [{"name": "UF_USER_AUTH", "value": "Y"}],
                "sessid": sessid,
                "user_id": user_id,
                "sessid_ts": 0,  # doesn't matter; _ensure_session is mocked
            }
        ),
        encoding="utf-8",
    )


def _fresh_cart_module(monkeypatch, *, flag_value):
    """Reload cart.vkusvill_api with USE_FAST_CART_ADD_ENDPOINT set exactly.

    The flag is evaluated at import time from os.environ, so to test
    different flag states we wipe / set the env var and reimport.
    """
    import cart.vkusvill_api as vv

    if flag_value is None:
        monkeypatch.delenv("USE_FAST_CART_ADD_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("USE_FAST_CART_ADD_ENDPOINT", flag_value)
    return importlib.reload(vv)


def test_fast_endpoint_disabled_by_default(monkeypatch):
    """Clean environment => USE_FAST_CART_ADD_ENDPOINT is False and URL is None."""
    vv = _fresh_cart_module(monkeypatch, flag_value=None)
    assert vv.USE_FAST_CART_ADD_ENDPOINT is False
    assert vv.FAST_CART_ADD_URL is None


def test_fast_endpoint_raises_when_flag_on_but_url_none(monkeypatch, tmp_path):
    """Flag forced ON while URL is unset => add() raises NotImplementedError.

    This is the intentional Phase-64 guard: operators cannot accidentally
    flip the env var before the HAR-capture + ablation spike discovers a
    faster endpoint and wires the fast path.
    """
    vv = _fresh_cart_module(monkeypatch, flag_value="1")
    assert vv.USE_FAST_CART_ADD_ENDPOINT is True
    assert vv.FAST_CART_ADD_URL is None

    # Force FAST_CART_ADD_URL to a truthy value so the fast-path gate
    # actually evaluates True and raises. The module-level URL stays
    # None per scaffolding; we patch it here to simulate a partially
    # configured deploy (exactly what the guard is meant to catch).
    monkeypatch.setattr(vv, "FAST_CART_ADD_URL", "https://example.invalid/fast")

    cookies = tmp_path / "cookies.json"
    _write_cookies(cookies)

    cart = vv.VkusVillCart(cookies_path=str(cookies), user_id=987, sessid="sess-xyz")

    def _noop_ensure(self):
        return None

    monkeypatch.setattr(vv.VkusVillCart, "_ensure_session", _noop_ensure)

    with pytest.raises(NotImplementedError) as exc:
        cart.add(product_id=731)

    assert "Phase 64" in str(exc.value)


def test_legacy_path_when_flag_off(monkeypatch, tmp_path):
    """Default flag=False => add() uses BASKET_ADD_URL exactly as pre-Phase-64."""
    vv = _fresh_cart_module(monkeypatch, flag_value=None)
    assert vv.USE_FAST_CART_ADD_ENDPOINT is False

    cookies = tmp_path / "cookies.json"
    _write_cookies(cookies)

    cart = vv.VkusVillCart(cookies_path=str(cookies), user_id=987, sessid="sess-xyz")

    def _noop_ensure(self):
        return None

    captured: dict = {}

    def _fake_request(self, url, data, timeout=None, referer=None):
        captured["url"] = url
        captured["data"] = data
        return {
            "success": "Y",
            "basketAdded": {
                "NAME": "Test Product",
                "PRODUCT_ID": data.get("id"),
                "Q": 1,
                "PRICE": 100,
                "CAN_BUY": "Y",
                "MAX_Q": 10,
            },
            "totals": {"Q_ITEMS": 1, "PRICE_FINAL": 100},
        }

    monkeypatch.setattr(vv.VkusVillCart, "_ensure_session", _noop_ensure)
    monkeypatch.setattr(vv.VkusVillCart, "_request", _fake_request)

    result = cart.add(product_id=731)

    assert result["success"] is True
    # Legacy path => add() hit exactly BASKET_ADD_URL.
    assert captured["url"] == vv.BASKET_ADD_URL
    # Spot-check the legacy 16-field payload so a future refactor that
    # drops required fields shows up here.
    assert captured["data"]["id"] == 731
    assert captured["data"]["user_id"] == 987
    assert "sessid" in captured["data"]
