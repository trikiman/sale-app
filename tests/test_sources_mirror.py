"""The VLESS pool refresh must survive a blocked raw.githubusercontent.com.

Measured 2026-11-17: the RU network drops the TLS handshake to raw.githubusercontent
(DPI), while cdn.jsdelivr.net serves the same file in 0.1 s. A pool refresh that
only knows the raw URL comes back empty and the pool stays at 0 — which is exactly
the state the server was in.
"""
from __future__ import annotations

import urllib.error

import pytest

from vless import sources


def test_mirror_url_rewrites_raw_github() -> None:
    assert (
        sources.mirror_url(
            "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt"
        )
        == "https://cdn.jsdelivr.net/gh/igareck/vpn-configs-for-russia@main/BLACK_VLESS_RUS.txt"
    )


def test_mirror_url_keeps_nested_paths() -> None:
    assert (
        sources.mirror_url(
            "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/subscriptions/sni_filtered.txt"
        )
        == "https://cdn.jsdelivr.net/gh/kort0881/vpn-vless-configs-russia@main/subscriptions/sni_filtered.txt"
    )


def test_mirror_url_never_rewrites_subscription_endpoints() -> None:
    """A keyed subscription must not be proxied through a third party."""
    assert (
        sources.mirror_url("https://www.v2nodes.com/subscriptions/country/ru/?key=SECRET")
        is None
    )


def test_mirror_url_rejects_malformed_paths() -> None:
    assert sources.mirror_url("https://raw.githubusercontent.com/only-owner") is None
    assert sources.mirror_url("https://example.com/a/b/c") is None


def test_fetch_one_falls_back_to_mirror_on_network_error(monkeypatch) -> None:
    """A TLS handshake failure on raw GitHub must not lose the file."""
    calls: list[str] = []

    class _Resp:
        headers = type("H", (), {"get_content_charset": staticmethod(lambda: "utf-8")})()

        def read(self) -> bytes:
            return b"vless://node-1\n"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        url = req.full_url
        calls.append(url)
        if "raw.githubusercontent.com" in url:
            raise urllib.error.URLError("ssl: handshake timed out")
        return _Resp()

    monkeypatch.setattr(sources.urllib.request, "urlopen", fake_urlopen)
    body = sources._fetch_one(
        "https://raw.githubusercontent.com/o/r/main/list.txt", timeout=5.0
    )
    assert "vless://" in body
    assert len(calls) == 2
    assert calls[1].startswith("https://cdn.jsdelivr.net/gh/o/r@main/"), calls[1]


def test_fetch_one_does_not_retry_non_github_urls(monkeypatch) -> None:
    def fake_urlopen(req, timeout=0):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(sources.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.URLError):
        sources._fetch_one("https://www.v2nodes.com/subscriptions/x?key=SECRET", timeout=5.0)
