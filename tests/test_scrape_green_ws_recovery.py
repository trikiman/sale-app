"""Phase 58-02 unit tests for the CDP-WebSocket recovery helpers.

The Chromium DevTools WebSocket can drop with ``HTTP 500`` after a
force-reload (Chromium swaps the target while we still hold the old
handle). Pre-58-02 the very next ``page.evaluate`` call crashed the
whole scraper cycle. The helpers under test here detect that failure
and re-acquire a fresh tab handle before retrying.
"""
from __future__ import annotations

import asyncio

import pytest

from scrape_green import (
    _is_dead_ws_error,
    _navigate_and_settle,
    _refresh_page_handle,
    _safe_js,
)


# ── _is_dead_ws_error ────────────────────────────────────────────────


def test_is_dead_ws_error_matches_http_500_message() -> None:
    exc = RuntimeError("server rejected WebSocket connection: HTTP 500")
    assert _is_dead_ws_error(exc) is True


def test_is_dead_ws_error_matches_connection_closed_class() -> None:
    class ConnectionClosed(Exception):
        pass

    assert _is_dead_ws_error(ConnectionClosed("peer gone")) is True


def test_is_dead_ws_error_ignores_unrelated_errors() -> None:
    assert _is_dead_ws_error(ValueError("bad selector")) is False
    assert _is_dead_ws_error(TimeoutError("nav timeout")) is False


# ── Fakes ────────────────────────────────────────────────────────────


class _DeadTab:
    """Tab whose first evaluate raises the WS-HTTP-500 marker."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def evaluate(self, script: str):
        self.calls.append(script)
        raise RuntimeError("server rejected WebSocket connection: HTTP 500")


class _LiveTab:
    """Tab that always succeeds; records every evaluate."""

    def __init__(self, return_value=None) -> None:
        self.return_value = return_value
        self.calls: list[str] = []

    async def evaluate(self, script: str):
        self.calls.append(script)
        return self.return_value


class _FakeBrowser:
    """Minimal browser stand-in exposing ``tabs`` + ``get``."""

    def __init__(self, tabs: list, fresh_tab=None) -> None:
        self.tabs = list(tabs)
        self._fresh_tab = fresh_tab
        self.get_calls: list[str] = []

    async def get(self, url: str):
        self.get_calls.append(url)
        if self._fresh_tab is None:
            self._fresh_tab = _LiveTab()
        self.tabs.append(self._fresh_tab)
        return self._fresh_tab


# ── _refresh_page_handle ─────────────────────────────────────────────


def test_refresh_page_handle_prefers_live_tab_over_navigation() -> None:
    live = _LiveTab(return_value="ok")
    browser = _FakeBrowser(tabs=[_DeadTab(), live])
    result = asyncio.run(_refresh_page_handle(browser))
    assert result is live
    assert browser.get_calls == []


def test_refresh_page_handle_falls_back_to_browser_get() -> None:
    fresh = _LiveTab()
    browser = _FakeBrowser(tabs=[_DeadTab()], fresh_tab=fresh)
    result = asyncio.run(_refresh_page_handle(browser, fallback_url="https://x"))
    assert result is fresh
    assert browser.get_calls == ["https://x"]


# ── _safe_js ─────────────────────────────────────────────────────────


def test_safe_js_returns_immediately_when_page_alive() -> None:
    live = _LiveTab(return_value="HTML title")
    browser = _FakeBrowser(tabs=[live])
    result, page = asyncio.run(_safe_js(live, browser, "document.title"))
    assert result == "HTML title"
    assert page is live
    assert browser.get_calls == []


def test_safe_js_recovers_from_dead_ws_with_fresh_tab() -> None:
    dead = _DeadTab()
    live = _LiveTab(return_value="42")
    browser = _FakeBrowser(tabs=[dead, live])
    result, page = asyncio.run(_safe_js(dead, browser, "1+1"))
    assert result == "42"
    assert page is live  # caller gets the refreshed handle back
    assert dead.calls == ["1+1"]
    # live tab is hit twice: once by the WS-liveness probe inside
    # _refresh_page_handle, once by the actual retry of the user script.
    assert live.calls == ["1", "1+1"]
    assert browser.get_calls == []  # didn't have to navigate; live tab existed


def test_safe_js_propagates_unrelated_errors() -> None:
    class _RaisingTab:
        async def evaluate(self, script: str):
            raise ValueError("bad script")

    bad = _RaisingTab()
    browser = _FakeBrowser(tabs=[bad])
    with pytest.raises(ValueError):
        asyncio.run(_safe_js(bad, browser, "syntax error"))


# ── _navigate_and_settle ─────────────────────────────────────────────


class _NavBrowser:
    """Browser whose ``get(url)`` returns a configurable tab."""

    def __init__(self, post_nav_tab, fallback_tab=None) -> None:
        self._post_nav = post_nav_tab
        self._fallback = fallback_tab
        self.tabs: list = []
        self.get_calls: list[str] = []

    async def get(self, url: str):
        self.get_calls.append(url)
        # First call returns the post-nav tab (possibly dead). A second
        # call (the recovery navigate) returns the fallback.
        if len(self.get_calls) == 1:
            self.tabs.append(self._post_nav)
            return self._post_nav
        tab = self._fallback or _LiveTab()
        self.tabs.append(tab)
        return tab


def test_navigate_and_settle_returns_post_nav_tab_when_alive(monkeypatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _noop())
    live = _LiveTab(return_value=1)
    browser = _NavBrowser(post_nav_tab=live)
    result = asyncio.run(_navigate_and_settle(browser, "https://x", sleep_seconds=0))
    assert result is live
    assert browser.get_calls == ["https://x"]


def test_navigate_and_settle_re_acquires_when_post_nav_tab_dead(monkeypatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _noop())
    dead = _DeadTab()
    fallback = _LiveTab()
    browser = _NavBrowser(post_nav_tab=dead, fallback_tab=fallback)
    result = asyncio.run(_navigate_and_settle(browser, "https://x", sleep_seconds=0))
    # First nav returns the dead tab; recovery walks tabs (only `dead`
    # so far) then falls back to a fresh `browser.get(url)` returning
    # the fallback tab.
    assert result is fallback
    assert browser.get_calls == ["https://x", "https://x"]


async def _noop():
    return None
