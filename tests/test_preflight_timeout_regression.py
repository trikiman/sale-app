"""Regression guard: probe timeout floor must stay at or above empirical
healthy-node latency. See
``.planning/phases/59-corrected-preflight-vless-probe/59-CONTEXT.md`` D-02
and D-11.

Measurement evidence (2026-05-03, EC2 ubuntu@13.60.174.46, through the live
VLESS SOCKS5 bridge at 127.0.0.1:10808):

    n=5 healthy-node probes to https://vkusvill.ru/favicon.ico
    elapsed_s: [7.4, 9.2, 7.8, 8.1, 8.6]
    p95 ~= 9.2 s
    floor = p95 * 1.30 = 12.0 s

If a contributor lowers ``_PROBE_TIMEOUT_S_FLOOR`` below 12.0 without
re-measuring the healthy-node p95 on the live bridge AND updating this file
with new evidence, this test fails. That is the point. The PR #25 revert
(2026-04-29) happened because a 5 s timeout false-negatived every healthy
probe; the fix was not just "use 12" but "guard the constant so nobody
un-does this again."
"""
from __future__ import annotations

import inspect
import sys
import types

import pytest

# Provide a stub httpx module if httpx isn't installed in the test
# environment, so we can still exercise the constant and signature
# regression guards. The probe-behavior tests live in the contract
# test module and skip if httpx is unavailable in the real way there.
if "httpx" not in sys.modules:
    try:
        import httpx  # noqa: F401
    except Exception:
        fake = types.ModuleType("httpx")

        class _Err(Exception):
            pass

        fake.Client = type("Client", (), {})
        fake.ConnectTimeout = type("ConnectTimeout", (_Err,), {})
        fake.ReadTimeout = type("ReadTimeout", (_Err,), {})
        fake.ConnectError = type("ConnectError", (_Err,), {})
        fake.HTTPError = _Err
        sys.modules["httpx"] = fake

from vless import preflight  # noqa: E402


def test_probe_timeout_floor_is_at_least_twelve_seconds():
    """The module-level floor MUST stay >= 12.0. Lowering requires new measurement."""
    assert preflight._PROBE_TIMEOUT_S_FLOOR >= 12.0, (
        "Probe timeout floor lowered below empirical p95 safety margin. "
        "See tests/test_preflight_timeout_regression.py docstring for the "
        "measurement protocol. Re-measure on live EC2 bridge before changing."
    )


def test_probe_default_argument_is_at_least_floor():
    """The function signature default MUST also be >= floor (defence in depth)."""
    sig = inspect.signature(preflight.probe_bridge_alive)
    default = sig.parameters["timeout"].default
    assert default >= preflight._PROBE_TIMEOUT_S_FLOOR, (
        f"probe_bridge_alive(timeout={default}) is below floor "
        f"{preflight._PROBE_TIMEOUT_S_FLOOR}. Both should move together."
    )


def test_runtime_floor_is_enforced_even_if_caller_passes_low_timeout(monkeypatch):
    """If a caller passes timeout=5, the runtime must bump to the 12 s floor."""
    captured = {}

    class _FakeResponse:
        status_code = 200

    class _FakeClient:
        def __init__(self, *, proxy=None, timeout=None, **kwargs):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def get(self, url):
            return _FakeResponse()

    monkeypatch.setattr(preflight.httpx, "Client", _FakeClient)
    preflight.reset_probe_cache()

    result = preflight.probe_bridge_alive(timeout=5.0)
    assert result.ok is True
    # httpx.Client received the floor, not the caller's 5.0
    assert captured["timeout"] >= preflight._PROBE_TIMEOUT_S_FLOOR, (
        f"Runtime floor not enforced: httpx.Client received timeout="
        f"{captured['timeout']} instead of {preflight._PROBE_TIMEOUT_S_FLOOR}"
    )
