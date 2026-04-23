import json
from pathlib import Path

import httpx

import cart.vkusvill_api as vv


def _write_cookies(path: Path, *, sessid="abc", user_id=123, sessid_ts=0):
    path.write_text(json.dumps({
        "cookies": [{"name": "UF_USER_AUTH", "value": "Y"}],
        "sessid": sessid,
        "user_id": user_id,
        "sessid_ts": sessid_ts,
    }), encoding="utf-8")


def test_stale_session_does_not_auto_refresh_on_init(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.json"
    _write_cookies(cookies, sessid_ts=1)

    called = {"refresh": False}

    def fake_refresh(self):
        called["refresh"] = True

    monkeypatch.setattr(vv.time, "time", lambda: vv.SESSID_STALE_SECONDS + 100)
    monkeypatch.setattr(vv.VkusVillCart, "_refresh_stale_session", fake_refresh)

    cart = vv.VkusVillCart(cookies_path=str(cookies), proxy_manager=None)
    cart._ensure_session()

    assert cart._session_stale is True
    assert called["refresh"] is False


def test_transport_candidates_prefer_direct_when_direct_is_healthy(tmp_path):
    cookies = tmp_path / "cookies.json"
    _write_cookies(cookies, sessid_ts=vv.time.time())

    class FakeProxyManager:
        def check_direct_cached(self):
            return True

        def get_working_proxy(self, allow_refresh=False):
            return "1.2.3.4:1080"

    cart = vv.VkusVillCart(cookies_path=str(cookies), proxy_manager=FakeProxyManager())
    assert cart._transport_candidates() == [None]


def test_perform_http_request_falls_back_from_proxy_to_direct(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.json"
    _write_cookies(cookies, sessid_ts=vv.time.time())

    calls = []
    removed = []
    direct_notes = []

    class FakeProxyManager:
        def check_direct_cached(self):
            return False

        def get_working_proxy(self, allow_refresh=False):
            return "1.2.3.4:1080"

        def remove_proxy(self, addr):
            removed.append(addr)

        def note_direct_result(self, ok):
            direct_notes.append(ok)

    class FakeResponse:
        status_code = 200
        text = "{}"

    class FakeClient:
        def __init__(self, **kwargs):
            self.proxy = kwargs.get("proxy")
            calls.append(self.proxy)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data=None, headers=None, follow_redirects=False):
            if self.proxy:
                raise httpx.TimeoutException("proxy timeout")
            return FakeResponse()

    monkeypatch.setattr(vv.httpx, "Client", FakeClient)

    cart = vv.VkusVillCart(cookies_path=str(cookies), proxy_manager=FakeProxyManager())
    response = cart._perform_http_request("POST", "https://example.com", headers={}, data={})

    assert response.status_code == 200
    # xray round-robins per fresh connection, so proxied TLS timeouts are
    # retried _BRIDGE_RETRY_ATTEMPTS times before we fall back to direct.
    assert calls == (
        ["socks5://1.2.3.4:1080"] * vv._BRIDGE_RETRY_ATTEMPTS + [None]
    )
    assert removed == ["1.2.3.4:1080"]
    assert direct_notes[-1] is True
