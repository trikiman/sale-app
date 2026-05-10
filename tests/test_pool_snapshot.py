"""Phase 61 REL-12 + OBS-02 + OBS-03: pool_snapshot() accessor and
proxy_events.jsonl enrichment.

All tests mocked / fixture-driven; no real xray, no real network.
"""
from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

import pytest


# Provide a stub httpx module if httpx isn't installed so we can import
# vless.manager without needing the full install. Pattern mirrors Phase
# 59's preflight tests.
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

from vless.manager import VlessProxyManager, MIN_HEALTHY, VKUSVILL_COOLDOWN_S


@pytest.fixture
def pm(tmp_path):
    """A VlessProxyManager writing to isolated tmp paths. No xray touched."""
    pool_path = tmp_path / "vless_pool.json"
    cooldowns_path = tmp_path / "vkusvill_cooldowns.json"
    events_path = tmp_path / "proxy_events.jsonl"
    xray_config = tmp_path / "active.json"
    xray_log = tmp_path / "xray.log"

    manager = VlessProxyManager(
        log_func=lambda msg: None,
        pool_path=pool_path,
        cooldowns_path=cooldowns_path,
        events_path=events_path,
        xray_config_path=xray_config,
        xray_log_path=xray_log,
        register_atexit=False,
    )
    return manager


def _seed_pool(pm_, hosts):
    """Inject synthetic nodes into the pool — bypasses the real refresh."""
    pm_._pool = {
        "updated_at": "2026-05-05T15:00:00",
        "nodes": [{"host": h, "port": 443, "name": f"node-{h}"} for h in hosts],
    }


# --- pool_snapshot() shape + values (REL-12) ------------------------------


def test_pool_snapshot_shape_on_empty_pool(pm):
    snap = pm.pool_snapshot()
    assert set(snap.keys()) == {
        "size", "min_healthy", "quarantined_count",
        "active_outbounds", "last_refresh_at",
    }
    assert snap["size"] == 0
    assert snap["min_healthy"] == MIN_HEALTHY
    assert snap["quarantined_count"] == 0
    assert snap["active_outbounds"] == 0
    assert snap["last_refresh_at"] is None


def test_pool_snapshot_reflects_pool_size(pm):
    _seed_pool(pm, ["1.2.3.4", "1.2.3.5", "1.2.3.6"])
    snap = pm.pool_snapshot()
    assert snap["size"] == 3
    assert snap["active_outbounds"] == 3
    assert snap["quarantined_count"] == 0
    assert snap["last_refresh_at"] == "2026-05-05T15:00:00"


def test_pool_snapshot_counts_active_cooldowns(pm):
    _seed_pool(pm, ["1.2.3.4", "1.2.3.5"])
    now = time.time()
    # Active cooldown: blocked 10s ago
    pm._cooldowns["1.2.3.4"] = {"blocked_at": now - 10, "reason": "test"}
    # Expired cooldown: blocked > VKUSVILL_COOLDOWN_S ago -> NOT counted
    pm._cooldowns["9.9.9.9"] = {"blocked_at": now - VKUSVILL_COOLDOWN_S - 60, "reason": "old"}

    snap = pm.pool_snapshot()
    assert snap["quarantined_count"] == 1  # only the active one
    # Node 1.2.3.4 is in pool AND in cooldown -> not in active_outbounds
    # Node 1.2.3.5 is in pool and NOT in cooldown -> in active_outbounds
    assert snap["active_outbounds"] == 1


def test_pool_snapshot_active_outbounds_never_exceeds_size(pm):
    _seed_pool(pm, ["1.2.3.4"])
    # Cooldown a host that's NOT in the pool — shouldn't inflate outbounds
    pm._cooldowns["7.7.7.7"] = {"blocked_at": time.time(), "reason": "test"}
    snap = pm.pool_snapshot()
    assert snap["size"] == 1
    assert snap["active_outbounds"] == 1  # the one pool node is not in cooldown
    assert snap["quarantined_count"] == 1  # but we still track the cooldown


def test_pool_snapshot_is_thread_safe_under_lock(pm):
    """pool_snapshot must take self._lock so concurrent refresh is safe."""
    import threading
    _seed_pool(pm, ["1.2.3.4"])
    results = []
    done = threading.Event()

    def reader():
        for _ in range(100):
            results.append(pm.pool_snapshot()["size"])
        done.set()

    t = threading.Thread(target=reader)
    t.start()
    # While reader is running, mutate the pool dict under the lock
    for _ in range(50):
        with pm._lock:
            pm._pool["nodes"].append(
                {"host": f"99.99.99.{len(pm._pool['nodes'])}", "port": 443}
            )
    t.join(timeout=5)
    assert done.is_set()
    # All snapshots should have seen a consistent size >= 1 (never negative,
    # never missing the lock-protected mutations)
    assert all(r >= 1 for r in results)


# --- _track_event enrichment (OBS-02) -------------------------------------

def test_track_event_injects_pool_counters_into_jsonl(pm):
    _seed_pool(pm, ["1.2.3.4", "1.2.3.5"])
    pm._cooldowns["1.2.3.4"] = {"blocked_at": time.time(), "reason": "test"}

    pm._track_event("vless_node_admitted", {"host": "1.2.3.5"})

    lines = pm._events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    # Original fields still present
    assert entry["event"] == "vless_node_admitted"
    assert entry["host"] == "1.2.3.5"
    # Pool counters auto-injected
    assert entry["pool_size"] == 2
    assert entry["quarantined_count"] == 1
    assert entry["active_outbounds_count"] == 1


def test_track_event_does_not_overwrite_explicit_pool_fields(pm):
    """If a caller passes pool_size explicitly, respect it (setdefault semantics)."""
    _seed_pool(pm, ["1.2.3.4"])
    pm._track_event("found", {"addr": "x", "pool_size": 999})

    lines = pm._events_path.read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(lines[0])
    assert entry["pool_size"] == 999  # caller's value wins


def test_track_event_never_raises_if_snapshot_fails(pm, monkeypatch):
    """Snapshot failure inside _track_event must NOT propagate."""
    def boom(self):
        raise RuntimeError("intentional")
    monkeypatch.setattr(VlessProxyManager, "pool_snapshot", boom)

    # Should NOT raise
    pm._track_event("noop", {"addr": "x"})

    # Event still written (without the pool_* fields)
    lines = pm._events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "noop"
    # No pool_size / quarantined_count / active_outbounds_count since snapshot failed
    assert "pool_size" not in entry
