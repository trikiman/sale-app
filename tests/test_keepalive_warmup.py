"""Unit tests for keepalive/warmup.py (Phase 62).

Tests reach into module internals (_STATE_LOCK, _LAST_WARMUP_AT,
_run_cycle, _emit_event, _warmup_single_user). This is intentional
test-only access — the module's public API is just start_warmup_loop.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Ensure project root on sys.path so `import keepalive.warmup` works under
# `python -m pytest tests/...` from any CWD.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from keepalive import warmup  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state(tmp_path, monkeypatch):
    """Clear module state between tests; redirect JSONL into tmp_path."""
    warmup.reset_state_for_tests()
    monkeypatch.setattr(warmup, "WARMUP_JSONL_PATH",
                        str(tmp_path / "warmup_events.jsonl"))
    monkeypatch.setattr(warmup, "BOOT_GRACE_S", 0.0)
    # Shrink cycle interval so the shutdown test doesn't wait 20 min.
    monkeypatch.setattr(warmup, "CYCLE_INTERVAL_S", 0.5)
    yield
    warmup.reset_state_for_tests()


@pytest.fixture
def three_linked_users(tmp_path, monkeypatch):
    """Fake 3 users with cookies.json; monkeypatch _collect_linked_users."""
    users = []
    for tg_id in ("111", "222", "333"):
        p = tmp_path / f"{tg_id}.json"
        p.write_text(json.dumps({
            "cookies": [],
            "sessid": f"old-{tg_id}",
            "user_id": int(tg_id),
            "sessid_ts": 1,
        }))
        users.append((warmup.hash_user_id(tg_id), str(p)))
    monkeypatch.setattr(warmup, "_collect_linked_users", lambda: list(users))
    return users


def _read_jsonl() -> list:
    path = warmup.WARMUP_JSONL_PATH
    if not os.path.exists(path):
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]


# ---------------------------------------------------------------------------
# 1. test_jsonl_schema
# ---------------------------------------------------------------------------
def test_jsonl_schema(three_linked_users, monkeypatch):
    """Every emitted line has the 8 required keys + correct types."""
    monkeypatch.setattr(warmup, "_pool_is_healthy", lambda: True)

    def fake_warm(h, p, t, e):
        warmup._emit_event({
            "timestamp_iso": warmup._now_iso(),
            "user_id_hash": h,
            "trigger": t,
            "endpoint": warmup.WARMUP_ENDPOINT_LABEL,
            "success": True,
            "outcome": "ok",
            "latency_ms": 100,
            "sessid_changed": True,
        })

    monkeypatch.setattr(warmup, "_warmup_single_user", fake_warm)

    warmup._run_cycle(threading.Event())

    events = _read_jsonl()
    assert len(events) == 3
    required = {"timestamp_iso", "user_id_hash", "trigger", "endpoint",
                "success", "outcome", "latency_ms", "sessid_changed"}
    for e in events:
        assert required <= set(e.keys()), f"missing keys: {required - set(e.keys())}"
        assert isinstance(e["latency_ms"], int)
        assert isinstance(e["sessid_changed"], bool)
        assert isinstance(e["success"], bool)
        assert isinstance(e["endpoint"], str)
        assert e["trigger"] in {"scheduler", "app_open"}
        assert e["outcome"] in {
            "ok", "timeout", "http_error", "skipped_unhealthy",
            "skipped_recent", "cancelled_by_cart_add", "raced",
        }


# ---------------------------------------------------------------------------
# 2. test_anti_spam_ceiling
# ---------------------------------------------------------------------------
def test_anti_spam_ceiling(three_linked_users, monkeypatch):
    """Two cycles 10 min apart -> 1 ok + 1 skipped_recent per user."""
    monkeypatch.setattr(warmup, "_pool_is_healthy", lambda: True)

    call_count = {"n": 0}

    def fake_warm(hash_id, path, trigger, stop_event):
        call_count["n"] += 1
        with warmup._STATE_LOCK:
            warmup._LAST_WARMUP_AT[hash_id] = time.monotonic()
        warmup._emit_event({
            "timestamp_iso": warmup._now_iso(),
            "user_id_hash": hash_id,
            "trigger": trigger,
            "endpoint": warmup.WARMUP_ENDPOINT_LABEL,
            "success": True,
            "outcome": "ok",
            "latency_ms": 100,
            "sessid_changed": True,
        })

    monkeypatch.setattr(warmup, "_warmup_single_user", fake_warm)

    # First cycle: all 3 users warmed
    warmup._run_cycle(threading.Event())
    assert call_count["n"] == 3

    # Fast-forward monotonic clock by 10 min (< ANTI_SPAM_WINDOW_S = 15 min)
    real_monotonic = time.monotonic
    shift = 10 * 60
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + shift)

    warmup._run_cycle(threading.Event())
    # No new warmups — all 3 should have been anti-spam-skipped
    assert call_count["n"] == 3

    events = _read_jsonl()
    outcomes = [e["outcome"] for e in events]
    assert outcomes.count("ok") == 3
    assert outcomes.count("skipped_recent") == 3


# ---------------------------------------------------------------------------
# 3. test_pool_unhealthy_gate
# ---------------------------------------------------------------------------
def test_pool_unhealthy_gate(three_linked_users, monkeypatch):
    """Pool unhealthy -> all users skipped_unhealthy, 0 HTTP."""
    monkeypatch.setattr(warmup, "_pool_is_healthy", lambda: False)
    called = {"n": 0}

    def fake_warm(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(warmup, "_warmup_single_user", fake_warm)

    warmup._run_cycle(threading.Event())

    assert called["n"] == 0
    events = _read_jsonl()
    assert [e["outcome"] for e in events] == ["skipped_unhealthy"] * 3


# ---------------------------------------------------------------------------
# 4. test_breaker_open_gate
# ---------------------------------------------------------------------------
def test_breaker_open_gate(three_linked_users, monkeypatch):
    """Breaker state='open' -> cycle skipped via real _pool_is_healthy branch.

    Patches scheduler_service._load_breaker_state to return state='open',
    stubs vless.manager.VlessProxyManager.pool_snapshot to return healthy
    pool + external xray, and leaves _pool_is_healthy() real so the
    breaker branch actually executes.
    """
    import scheduler_service

    class FakeBreaker:
        state = "open"

    monkeypatch.setattr(scheduler_service, "_load_breaker_state",
                        lambda: FakeBreaker())

    # Stub pool so the first two gates PASS; only the breaker should trip.
    from vless import manager as vless_manager

    def _fake_snapshot(self):
        return {
            "size": 10,
            "min_healthy": 5,
            "quarantined_count": 0,
            "active_outbounds": 10,
            "last_refresh_at": "2026-05-05T00:00:00+00:00",
        }

    monkeypatch.setattr(vless_manager.VlessProxyManager,
                        "pool_snapshot", _fake_snapshot, raising=False)
    monkeypatch.setattr(vless_manager.VlessProxyManager,
                        "_external_xray_listening",
                        lambda self: True, raising=False)

    # _pool_is_healthy remains REAL — exercises the breaker branch.
    warmup._run_cycle(threading.Event())

    events = _read_jsonl()
    assert len(events) == 3
    assert all(e["outcome"] == "skipped_unhealthy" for e in events)


# ---------------------------------------------------------------------------
# 5. test_cart_add_active_cancellation
# ---------------------------------------------------------------------------
def test_cart_add_active_cancellation(three_linked_users, monkeypatch):
    """Pre-set CART_ADD_ACTIVE[hash] -> cancelled_by_cart_add; 0 HTTP for that user.

    Other two users still warm through the real _warmup_single_user path,
    but httpx.post is stubbed so no real network is hit.
    """
    monkeypatch.setattr(warmup, "_pool_is_healthy", lambda: True)

    http_called = {"n": 0}

    def fake_post(url, **kwargs):
        http_called["n"] += 1

        class _Resp:
            status_code = 200
            text = '{"success":"Y","error":"","basket":{}}'

        return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "post", fake_post)

    # Flag the first user as having an active cart-add.
    flagged_hash = three_linked_users[0][0]
    with warmup._STATE_LOCK:
        warmup.CART_ADD_ACTIVE[flagged_hash] = time.monotonic()

    warmup._run_cycle(threading.Event())

    events = _read_jsonl()
    cancelled = [e for e in events if e["outcome"] == "cancelled_by_cart_add"]
    assert len(cancelled) == 1
    assert cancelled[0]["user_id_hash"] == flagged_hash
    assert cancelled[0]["latency_ms"] == 0
    assert cancelled[0]["success"] is False

    # Other two users should have hit httpx.post once each
    assert http_called["n"] == 2


# ---------------------------------------------------------------------------
# 6. test_stop_event_clean_shutdown
# ---------------------------------------------------------------------------
def test_stop_event_clean_shutdown(three_linked_users, monkeypatch):
    """stop_event.set() mid-work -> thread returns within 5 s."""
    monkeypatch.setattr(warmup, "_pool_is_healthy", lambda: True)

    def slow_warm(*a, **k):
        time.sleep(0.2)

    monkeypatch.setattr(warmup, "_warmup_single_user", slow_warm)

    stop = threading.Event()
    t = threading.Thread(target=warmup.start_warmup_loop,
                         args=(stop,), daemon=True)
    t.start()
    # let it enter the loop
    time.sleep(0.3)
    stop.set()
    t.join(timeout=5.0)
    assert not t.is_alive(), "thread did not exit within 5s of stop_event"


# ---------------------------------------------------------------------------
# 7. test_jsonl_rotation_at_ten_mb
# ---------------------------------------------------------------------------
def test_jsonl_rotation_at_ten_mb():
    """10.1 MB JSONL + 1 emit -> .1 rotation + primary has exactly 1 line."""
    p = Path(warmup.WARMUP_JSONL_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Seed just over 10 MB with valid-looking JSONL
    seed_line = b'{"x":1}\n'
    repeat = (warmup.JSONL_MAX_BYTES // len(seed_line)) + 1000
    p.write_bytes(seed_line * repeat)
    assert p.stat().st_size > warmup.JSONL_MAX_BYTES

    warmup._emit_event({
        "timestamp_iso": warmup._now_iso(),
        "user_id_hash": "h" * 12,
        "trigger": "scheduler",
        "endpoint": warmup.WARMUP_ENDPOINT_LABEL,
        "success": True,
        "outcome": "ok",
        "latency_ms": 1,
        "sessid_changed": False,
    })

    rotated = Path(str(p) + ".1")
    assert rotated.exists(), "rotation did not produce .1"
    assert p.exists(), "primary file should be recreated with 1 line"
    new_lines = p.read_text(encoding="utf-8").splitlines()
    assert len(new_lines) == 1
    loaded = json.loads(new_lines[0])
    assert loaded["outcome"] == "ok"


# ---------------------------------------------------------------------------
# 8. test_skips_when_session_metadata_missing (Phase 66.3)
# ---------------------------------------------------------------------------
def test_skips_when_session_metadata_missing(tmp_path, monkeypatch):
    """basket_recalc requires user_id + sessid form fields. If either is
    missing in cookies.json, warmup should skip cleanly (not fire an
    unauthenticated POST) and emit outcome='skipped_missing_session'."""
    monkeypatch.setattr(warmup, "_pool_is_healthy", lambda: True)

    # Cookie doc WITHOUT sessid / user_id (freshly seeded, not yet extracted).
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps({
        "cookies": [{"name": "BITRIX_SM_SALE_UID", "value": "abc123"}],
        # sessid missing
        # user_id missing
    }))
    uid_hash = warmup.hash_user_id("444")
    monkeypatch.setattr(
        warmup, "_collect_linked_users", lambda: [(uid_hash, str(p))]
    )

    # httpx.post must NOT be called.
    calls = {"n": 0}

    def boom(*a, **kw):
        calls["n"] += 1
        raise AssertionError("httpx.post called despite missing session metadata")

    import httpx
    monkeypatch.setattr(httpx, "post", boom)

    warmup._run_cycle(threading.Event())

    assert calls["n"] == 0, "warmup must not POST when session metadata missing"
    events = _read_jsonl()
    skipped = [e for e in events if e.get("outcome") == "skipped_missing_session"]
    assert len(skipped) == 1, f"expected 1 skipped_missing_session, got {len(skipped)}: {events}"
    assert skipped[0]["user_id_hash"] == uid_hash
    assert skipped[0]["latency_ms"] == 0
    assert skipped[0]["success"] is False
    assert skipped[0]["endpoint"] == warmup.WARMUP_ENDPOINT_LABEL
