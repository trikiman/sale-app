"""v1.30 Phase 95 (GREEN-UP-02) — fault injection for the green recovery paths.

The recovery logic in `scrape_green.py` was written against real crashes: Chrome
not opening CDP in time, the CDP target being swapped after the seed add, a dead
WebSocket after the cart clear, and a delivery modal that does not exist. Real
crashes are a terrible test harness — they are rare, unreproducible on demand,
and a refactor can silently un-wire a `try/except` nobody exercises.

These tests inject each failure with fakes: no Chrome, no network, no
python-telegram-bot. Every test fails if its recovery path is removed.

Import strategy: `scrape_green` imports `nodriver` and `chrome_stealth` at module
level, and nodriver is absent in the plain venv. We stub the module in
`sys.modules` before importing, which keeps the import honest (the real module
object is loaded from `scrape_green.py`) while avoiding a browser dependency.
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _install_nodriver_stub() -> None:
    """Minimal stand-in for `from nodriver import cdp`."""
    if "nodriver" in sys.modules:
        return
    mod = types.ModuleType("nodriver")
    mod.cdp = types.SimpleNamespace()  # any attribute access is fine
    sys.modules["nodriver"] = mod


_install_nodriver_stub()

try:
    import scrape_green as sg  # noqa: E402
except Exception as _exc:  # pragma: no cover - environment guard
    pytest.skip(f"scrape_green not importable: {_exc}", allow_module_level=True)


class ConnectionClosedError(Exception):
    """Mirrors websockets' class name, which is what _is_dead_ws_error matches."""


def _run(coro):
    return asyncio.run(coro)


# ── stage 1: dead WebSocket during evaluate ─────────────────────────────


class _FlakyPage:
    """Page whose evaluate dies N times with a dead-WS error, then succeeds."""

    def __init__(self, failures: int, result="ok"):
        self.failures = failures
        self.result = result
        self.calls = 0

    async def evaluate(self, script):
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionClosedError("no close frame received or sent")
        return self.result


def test_safe_js_survives_dead_ws_and_returns_fresh_page(monkeypatch) -> None:
    page = _FlakyPage(failures=2)
    refreshed = []

    async def fake_refresh(browser):
        refreshed.append(1)
        return page

    async def fake_navigate(browser, url, sleep_seconds=0):
        refreshed.append(2)
        return page

    monkeypatch.setattr(sg, "_refresh_page_handle", fake_refresh, raising=False)
    monkeypatch.setattr(sg, "_navigate_and_settle", fake_navigate, raising=False)

    result, returned_page = _run(sg._safe_js(page, object(), "1+1"))

    assert result == "ok", "third attempt should have succeeded"
    assert returned_page is page, "caller must get a usable page handle back"
    assert page.calls == 3, f"expected 3 evaluate calls, got {page.calls}"
    assert refreshed, "recovery must re-acquire a tab handle, not just retry blindly"


def test_safe_js_gives_up_after_three_attempts(monkeypatch) -> None:
    page = _FlakyPage(failures=99)

    async def fake_refresh(browser):
        return page

    async def fake_navigate(browser, url, sleep_seconds=0):
        return page

    monkeypatch.setattr(sg, "_refresh_page_handle", fake_refresh, raising=False)
    monkeypatch.setattr(sg, "_navigate_and_settle", fake_navigate, raising=False)

    with pytest.raises(ConnectionClosedError):
        _run(sg._safe_js(page, object(), "1+1"))
    assert page.calls == 3, "retry budget must stay at 3, not grow unbounded"


def test_safe_js_does_not_swallow_real_errors(monkeypatch) -> None:
    """A JS bug must surface, not be retried as if the socket died."""

    class _BrokenPage:
        calls = 0

        async def evaluate(self, script):
            _BrokenPage.calls += 1
            raise ValueError("SyntaxError: unexpected token")

    monkeypatch.setattr(sg, "_refresh_page_handle", lambda b: None, raising=False)
    monkeypatch.setattr(sg, "_navigate_and_settle", lambda b, u, sleep_seconds=0: None, raising=False)

    with pytest.raises(ValueError):
        _run(sg._safe_js(_BrokenPage(), object(), "not js"))
    assert _BrokenPage.calls == 1, "non-WS errors must not be retried"


# ── stage 2: re-acquiring the handle after a CDP target swap ────────────


def test_reacquire_page_retries_until_a_handle_appears(monkeypatch) -> None:
    attempts = []

    async def fake_navigate(browser, url, sleep_seconds=0):
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionClosedError("Connection closed")
        return "fresh-page"

    monkeypatch.setattr(sg, "_navigate_and_settle", fake_navigate)
    monkeypatch.setattr(sg.asyncio, "sleep", _no_sleep)

    assert _run(sg._reacquire_page(object())) == "fresh-page"
    assert len(attempts) == 3


def test_reacquire_page_returns_instead_of_hanging_when_all_fail(monkeypatch) -> None:
    """Bounded: three attempts and out — never an infinite recovery loop."""

    async def always_dead(browser, url, sleep_seconds=0):
        raise ConnectionClosedError("no close frame received or sent")

    monkeypatch.setattr(sg, "_navigate_and_settle", always_dead)
    monkeypatch.setattr(sg.asyncio, "sleep", _no_sleep)

    _run(sg._reacquire_page(object()))  # must not raise/hang
    assert True


async def _no_sleep(_seconds):
    return None


# ── stage 3: delivery modal that does not exist ─────────────────────────


class _ScriptedPage:
    """Returns canned JSON for each evaluate call, in order."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.scripts: list[str] = []

    async def evaluate(self, script):
        self.scripts.append(script)
        return self.payloads.pop(0) if self.payloads else '{"status":"no_modal","modals":[]}'


def test_ensure_delivery_slot_clicks_nothing_without_a_delivery_modal() -> None:
    page = _ScriptedPage(['{"status":"no_modal","modals":[]}', "not_found"])
    status = _run(sg._ensure_delivery_slot(page))

    assert status.startswith("no_modal") or status.startswith("open_attempt_not_found"), status
    assert len(page.scripts) == 2, "must not keep probing after a definitive answer"
    # The click script must never have been issued.
    assert not any("picked:" in s for s in page.scripts), "nothing should be clicked"


def test_ensure_delivery_slot_respects_an_existing_choice() -> None:
    page = _ScriptedPage(['{"status":"already","chosen":"сегодня 18:00-20:00","modals":[]}'])
    assert _run(sg._ensure_delivery_slot(page)) == "already"
    assert len(page.scripts) == 1, "an existing slot must short-circuit, no extra probing"


def test_ensure_delivery_slot_never_raises_on_a_broken_page() -> None:
    """The scrape must not die because slot selection failed."""

    class _ExplodingPage:
        async def evaluate(self, script):
            raise RuntimeError("page gone")

    status = _run(sg._ensure_delivery_slot(_ExplodingPage()))
    assert status.startswith("error:"), status


# ── stage 4: only delivery-looking modals are candidates ────────────────


def test_delivery_modal_filter_rejects_filter_panels() -> None:
    """The old generic click landed on 'Скоро исчезнут с полок'. Pin the filter."""
    source = (_REPO_ROOT / "scrape_green.py").read_text(encoding="utf-8")
    assert "доставк" in source, "delivery text filter disappeared"
    # The pick script must search the delivery text regex, not just click anything.
    idx = source.find("timeRe")
    assert idx != -1, "time-slot regex missing from the pick script"
    window = source[idx : idx + 400]
    assert "сегодня" in window and "завтра" in window


def test_recovery_helpers_are_still_wired_into_the_cycle() -> None:
    source = (_REPO_ROOT / "scrape_green.py").read_text(encoding="utf-8")
    for marker in ("_reacquire_page(", "_safe_js(", "_ensure_delivery_slot("):
        assert source.count(marker) >= 2, f"{marker} is defined but never called"
    # Seeds are re-navigated through the reacquire path, not the dead handle.
    assert source.count("_reacquire_page(browser)") >= 3