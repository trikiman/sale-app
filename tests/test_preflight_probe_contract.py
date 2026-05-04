"""Contract tests for ``vless.preflight.probe_bridge_alive``.

Covers REL-01 (probe exists + runs), REL-04 (accepted-status handling),
REL-05 (30 s cache), and failure categorization. All tests mock httpx — no
real network.
"""
from __future__ import annotations

import sys
import time
import types

import pytest


def _install_httpx_stub_if_missing():
    if "httpx" in sys.modules:
        return
    try:
        import httpx  # noqa: F401
        return
    except Exception:
        pass
    fake = types.ModuleType("httpx")

    class _Err(Exception):
        pass

    fake.Client = type("Client", (), {})
    fake.ConnectTimeout = type("ConnectTimeout", (_Err,), {})
    fake.ReadTimeout = type("ReadTimeout", (_Err,), {})
    fake.ConnectError = type("ConnectError", (_Err,), {})
    fake.HTTPError = _Err
    sys.modules["httpx"] = fake


_install_httpx_stub_if_missing()

import httpx  # noqa: E402
from vless import preflight  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_cache():
    preflight.reset_probe_cache()
    yield
    preflight.reset_probe_cache()


def _fake_httpx_client(status_code=200, raise_exc=None):
    class _R:
        def __init__(self, code):
            self.status_code = code

    class _C:
        def __init__(self, *, proxy=None, timeout=None, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def get(self, url):
            if raise_exc is not None:
                raise raise_exc
            return _R(status_code)

    return _C


# --- Accepted status categorization (REL-04) ---

@pytest.mark.parametrize("code", [200, 204, 304, 403, 404])
def test_accepted_statuses_yield_ok(monkeypatch, code):
    monkeypatch.setattr(preflight.httpx, "Client", _fake_httpx_client(status_code=code))
    r = preflight.probe_bridge_alive()
    assert r.ok is True
    assert r.status == code
    assert r.reason == "ok"


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_5xx_is_not_ok(monkeypatch, code):
    monkeypatch.setattr(preflight.httpx, "Client", _fake_httpx_client(status_code=code))
    r = preflight.probe_bridge_alive()
    assert r.ok is False
    assert r.status == code
    assert r.reason == f"http_{code}"


# --- Failure categorization ---

def test_connect_timeout_reason_is_timeout(monkeypatch):
    monkeypatch.setattr(
        preflight.httpx,
        "Client",
        _fake_httpx_client(raise_exc=preflight.httpx.ConnectTimeout("probe ct")),
    )
    r = preflight.probe_bridge_alive()
    assert r.ok is False
    assert r.reason == "timeout"
    assert r.status is None


def test_read_timeout_reason_is_timeout(monkeypatch):
    monkeypatch.setattr(
        preflight.httpx,
        "Client",
        _fake_httpx_client(raise_exc=preflight.httpx.ReadTimeout("probe rt")),
    )
    r = preflight.probe_bridge_alive()
    assert r.ok is False
    assert r.reason == "timeout"


def test_dns_failure_reason(monkeypatch):
    monkeypatch.setattr(
        preflight.httpx,
        "Client",
        _fake_httpx_client(
            raise_exc=preflight.httpx.ConnectError("Name or service not known")
        ),
    )
    r = preflight.probe_bridge_alive()
    assert r.ok is False
    assert r.reason == "dns_fail"


def test_generic_connect_error(monkeypatch):
    monkeypatch.setattr(
        preflight.httpx,
        "Client",
        _fake_httpx_client(raise_exc=preflight.httpx.ConnectError("ECONNREFUSED")),
    )
    r = preflight.probe_bridge_alive()
    assert r.ok is False
    assert r.reason == "connect_error"


# --- Cache (REL-05) ---

def test_second_probe_within_cache_ttl_returns_cached(monkeypatch):
    monkeypatch.setattr(preflight.httpx, "Client", _fake_httpx_client(status_code=200))

    r1 = preflight.probe_bridge_alive()
    assert r1.ok is True
    assert r1.cached is False

    r2 = preflight.probe_bridge_alive()
    assert r2.ok is True
    assert r2.cached is True
    assert r2.reason == "cached"


def test_cache_expires_after_ttl(monkeypatch):
    monkeypatch.setattr(preflight.httpx, "Client", _fake_httpx_client(status_code=200))
    # First probe: real
    r1 = preflight.probe_bridge_alive()
    assert r1.cached is False
    # Advance monotonic clock past TTL
    real_monotonic = time.monotonic
    fake_now = [real_monotonic() + preflight._CACHE_TTL_S + 1.0]
    monkeypatch.setattr(preflight.time, "monotonic", lambda: fake_now[0])
    r2 = preflight.probe_bridge_alive()
    assert r2.cached is False  # cache expired; real probe runs


def test_failed_probe_clears_cache(monkeypatch):
    # First: success populates cache
    monkeypatch.setattr(preflight.httpx, "Client", _fake_httpx_client(status_code=200))
    preflight.probe_bridge_alive()
    assert preflight._LAST_SUCCESS_AT is not None

    # Advance the monotonic clock past the cache TTL so the next probe
    # actually runs the network path (otherwise the cache short-circuits
    # and the failure branch never executes).
    real_monotonic = time.monotonic
    fake_now = [real_monotonic() + preflight._CACHE_TTL_S + 1.0]
    monkeypatch.setattr(preflight.time, "monotonic", lambda: fake_now[0])

    # Second: failure clears cache
    monkeypatch.setattr(
        preflight.httpx,
        "Client",
        _fake_httpx_client(raise_exc=preflight.httpx.ConnectTimeout("t")),
    )
    preflight.probe_bridge_alive()
    assert preflight._LAST_SUCCESS_AT is None


# --- Never-raises contract ---

def test_probe_never_raises_on_any_httpx_error(monkeypatch):
    """Contract: probe_bridge_alive returns a ProbeResult no matter what."""
    # Use a generic HTTPError subclass (covers any httpx exception not in the
    # specific except branches above).
    class _Weird(preflight.httpx.HTTPError):
        def __init__(self):
            try:
                super().__init__("weird")
            except TypeError:
                # Stub HTTPError in some envs uses (Exception) signature
                pass

    monkeypatch.setattr(
        preflight.httpx,
        "Client",
        _fake_httpx_client(raise_exc=_Weird()),
    )
    r = preflight.probe_bridge_alive()
    assert r.ok is False
    assert isinstance(r, preflight.ProbeResult)
