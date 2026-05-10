"""Phase 60 REL-07..10: circuit breaker state machine + persistence.

All tests mocked; no real network, no xray subprocess. Tests the
BreakerState class and the module-level _load / _persist helpers in
scheduler_service.py. Python 3.9+ (the same from-future-annotations
scheduler_service gets).
"""
from __future__ import annotations

import json
import sys
import types

import pytest


def _install_httpx_stub_if_missing():
    if "httpx" in sys.modules:
        return
    try:
        import httpx  # noqa: F401
        return
    except ImportError:
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

import scheduler_service as sch  # noqa: E402


@pytest.fixture
def tmp_state_file(monkeypatch, tmp_path):
    """Redirect BREAKER_STATE_FILE to a per-test temp path."""
    p = tmp_path / "scheduler_state.json"
    monkeypatch.setattr(sch, "BREAKER_STATE_FILE", str(p))
    monkeypatch.setattr(sch, "DATA_DIR", str(tmp_path))
    return p


# --- State transitions (REL-07) -------------------------------------------

def test_fresh_breaker_starts_closed():
    b = sch.BreakerState()
    assert b.state == "closed"
    assert b.fails == 0
    assert b.cooldown_s == sch.BREAKER_BASE_COOLDOWN_S
    assert b.cooldown_until_ts == 0.0


def test_closed_trips_to_open_after_threshold_all_fail_cycles():
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD):
        b.record_all_failed()
    assert b.state == "open"
    assert b.cooldown_until_ts > 0
    assert b.cooldown_s == sch.BREAKER_BASE_COOLDOWN_S


def test_closed_does_not_trip_before_threshold():
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD - 1):
        b.record_all_failed()
    assert b.state == "closed"
    assert b.fails == sch.BREAKER_TRIP_THRESHOLD - 1


def test_open_transitions_to_half_open_after_cooldown(monkeypatch):
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD):
        b.record_all_failed()
    monkeypatch.setattr(sch.time, "time", lambda: b.cooldown_until_ts + 1)
    b.tick()
    assert b.state == "half_open"


def test_open_stays_open_before_cooldown_expires(monkeypatch):
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD):
        b.record_all_failed()
    monkeypatch.setattr(sch.time, "time", lambda: b.cooldown_until_ts - 10)
    b.tick()
    assert b.state == "open"


def test_half_open_success_resets_to_closed(monkeypatch):
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD):
        b.record_all_failed()
    monkeypatch.setattr(sch.time, "time", lambda: b.cooldown_until_ts + 1)
    b.tick()
    assert b.state == "half_open"

    b.record_any_success()
    assert b.state == "closed"
    assert b.fails == 0
    assert b.cooldown_s == sch.BREAKER_BASE_COOLDOWN_S


def test_half_open_fail_trips_back_to_open_with_doubled_cooldown(monkeypatch):
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD):
        b.record_all_failed()
    initial_cooldown = b.cooldown_s
    monkeypatch.setattr(sch.time, "time", lambda: b.cooldown_until_ts + 1)
    b.tick()

    b.record_all_failed()
    assert b.state == "open"
    assert b.cooldown_s == initial_cooldown * 2


# --- Exponential backoff + cap (REL-08) -----------------------------------

def test_first_trip_uses_base_cooldown():
    b = sch.BreakerState()
    for _ in range(sch.BREAKER_TRIP_THRESHOLD):
        b.record_all_failed()
    assert b.cooldown_s == sch.BREAKER_BASE_COOLDOWN_S


def test_cooldown_capped_at_thirty_minutes(monkeypatch):
    """Starting at the cap, a half_open fail must NOT exceed the cap."""
    now = 1_000_000.0
    monkeypatch.setattr(sch.time, "time", lambda: now)
    b = sch.BreakerState(
        state="half_open", cooldown_s=sch.BREAKER_MAX_COOLDOWN_S
    )
    b.record_all_failed()
    assert b.cooldown_s == sch.BREAKER_MAX_COOLDOWN_S
    assert b.cooldown_until_ts == now + sch.BREAKER_MAX_COOLDOWN_S


def test_cooldown_near_cap_doubles_up_to_cap(monkeypatch):
    """cooldown near the cap doubles but clamps at the ceiling."""
    now = 1_000_000.0
    monkeypatch.setattr(sch.time, "time", lambda: now)
    near_cap = sch.BREAKER_MAX_COOLDOWN_S - 60  # e.g. 29m
    b = sch.BreakerState(state="half_open", cooldown_s=near_cap)
    b.record_all_failed()
    # 29m * 2 = 58m > cap -> clamps to cap
    assert b.cooldown_s == sch.BREAKER_MAX_COOLDOWN_S


# --- Any-success reset (REL-09) -------------------------------------------

def test_any_scraper_success_resets_breaker_from_open():
    b = sch.BreakerState(state="open", fails=5, cooldown_s=600)
    b.record_any_success()
    assert b.state == "closed"
    assert b.fails == 0
    assert b.cooldown_s == sch.BREAKER_BASE_COOLDOWN_S


def test_any_success_is_idempotent_on_already_clean_breaker():
    b = sch.BreakerState()
    prior = b.to_dict()
    b.record_any_success()
    assert b.to_dict() == prior  # no-op when already fully reset


# --- Persistence (REL-10) -------------------------------------------------

def test_breaker_roundtrip_through_json_file(tmp_state_file):
    b_in = sch.BreakerState(
        state="open",
        cooldown_s=480,
        fails=4,
        cooldown_until_ts=1234567890.5,
        last_transition_ts=1234567880.0,
    )
    sch._persist_breaker_state(b_in)
    b_out = sch._load_breaker_state()
    assert b_out.state == "open"
    assert b_out.cooldown_s == 480
    assert b_out.fails == 4
    assert b_out.cooldown_until_ts == 1234567890.5
    assert b_out.last_transition_ts == 1234567880.0


def test_corrupt_json_falls_back_to_fresh_closed(tmp_state_file):
    tmp_state_file.write_text("{not valid json")
    b = sch._load_breaker_state()
    assert b.state == "closed"
    assert b.fails == 0
    assert b.cooldown_s == sch.BREAKER_BASE_COOLDOWN_S


def test_invalid_state_string_falls_back_to_fresh_closed(tmp_state_file):
    tmp_state_file.write_text(json.dumps({"state": "UNKNOWN_STATE"}))
    b = sch._load_breaker_state()
    assert b.state == "closed"


def test_missing_state_file_falls_back_to_fresh_closed(tmp_state_file):
    assert not tmp_state_file.exists()
    b = sch._load_breaker_state()
    assert b.state == "closed"


def test_write_is_atomic_preserves_prior_file_on_error(tmp_state_file, monkeypatch):
    # Write a valid state first
    valid = sch.BreakerState(state="open", fails=3, cooldown_s=240,
                              cooldown_until_ts=1e9)
    sch._persist_breaker_state(valid)
    assert tmp_state_file.exists()

    # Monkeypatch os.replace to raise mid-write
    def _boom(*a, **kw):
        raise OSError("simulated disk error")

    monkeypatch.setattr(sch.os, "replace", _boom)

    # Attempt another persist with different state — should not corrupt file
    sch._persist_breaker_state(sch.BreakerState(state="half_open"))
    reloaded = sch._load_breaker_state()

    # Still the prior valid state (open), not garbage and not half_open
    assert reloaded.state == "open"
    assert reloaded.fails == 3
    assert reloaded.cooldown_s == 240
