"""Tests for the pre-flight VLESS proxy probe in scheduler_service."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reload_scheduler(monkeypatch):
    """Import scheduler_service fresh for each test so module-level state stays
    contained and we can monkeypatch httpx without leaking between tests."""
    if "scheduler_service" in sys.modules:
        del sys.modules["scheduler_service"]
    import scheduler_service as svc  # noqa: WPS433 — local import is intentional
    yield svc


def _stub_httpx(monkeypatch, status_code: int = 200, raises: bool = False, final_url: str = "https://vkusvill.ru/"):
    class _Resp:
        def __init__(self):
            self.status_code = status_code
            self.url = final_url

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, *args, **kwargs):
            if raises:
                raise RuntimeError("boom")
            return _Resp()

    fake = types.ModuleType("httpx")
    fake.Client = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)


def test_probe_returns_true_on_200(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=200)
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is True


def test_probe_returns_false_on_500(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=503)
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is False


def test_probe_returns_false_on_403(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=403)
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is False


def test_probe_returns_false_on_429(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=429)
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is False


def test_probe_returns_false_on_vpn_detected(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=200, final_url="https://vkusvill.ru/vpn-detected/")
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is False


def test_probe_returns_false_on_exception(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, raises=True)
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is False


def test_ensure_healthy_proxy_passes_through_when_healthy(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=200)
    pm = MagicMock()
    result = reload_scheduler._ensure_healthy_proxy(pm, "socks5://127.0.0.1:10808")
    assert result == "socks5://127.0.0.1:10808"
    pm.next_proxy.assert_not_called()


def test_ensure_healthy_proxy_rotates_until_alive(reload_scheduler, monkeypatch):
    """First two probes fail, third succeeds → returns the rotated address."""
    call_count = {"n": 0}

    class _Resp:
        def __init__(self, status):
            self.status_code = status
            self.url = "https://vkusvill.ru/"

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, *args, **kwargs):
            call_count["n"] += 1
            return _Resp(503 if call_count["n"] <= 2 else 200)

    fake = types.ModuleType("httpx")
    fake.Client = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)

    pm = MagicMock()
    pm.next_proxy.side_effect = ["127.0.0.1:10808", "127.0.0.1:10808"]

    result = reload_scheduler._ensure_healthy_proxy(pm, "socks5://127.0.0.1:10808")
    assert result == "socks5://127.0.0.1:10808"
    assert pm.next_proxy.call_count == 2


def test_ensure_healthy_proxy_returns_none_when_pool_exhausted(reload_scheduler, monkeypatch):
    _stub_httpx(monkeypatch, status_code=503)
    pm = MagicMock()
    pm.next_proxy.return_value = None
    result = reload_scheduler._ensure_healthy_proxy(pm, "socks5://127.0.0.1:10808")
    assert result is None


def test_ensure_healthy_proxy_returns_last_candidate_after_max_rotations(reload_scheduler, monkeypatch):
    """If every probe fails for ``MAX_ROTATIONS`` rounds, fall back to the
    last candidate so the cycle isn't aborted entirely (the scraper itself
    handles its own kill+retry path)."""
    _stub_httpx(monkeypatch, status_code=503)
    pm = MagicMock()
    pm.next_proxy.return_value = "127.0.0.1:10808"
    result = reload_scheduler._ensure_healthy_proxy(pm, "socks5://127.0.0.1:10808")
    assert result == "socks5://127.0.0.1:10808"
    assert pm.next_proxy.call_count == reload_scheduler.PROXY_PROBE_MAX_ROTATIONS


def test_probe_returns_true_when_httpx_missing(reload_scheduler, monkeypatch):
    """Conservative fallback: if httpx isn't installed (shouldn't happen but
    guard anyway), the probe must not block the cycle."""
    monkeypatch.setitem(sys.modules, "httpx", None)
    assert reload_scheduler._probe_proxy_alive("socks5://127.0.0.1:10808") is True
