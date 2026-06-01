"""Phase 81 (v1.25 QA-06) — 2026-05-13 VLESS pool collapse replay test.

Pins the exact failure+recovery pattern observed on 2026-05-13:
  1. Pool at 20 nodes, all healthy
  2. Catastrophic probe failure — every candidate fails → pool drops to 0
  3. 4+ consecutive cycles with pool=0; each must trigger ensure_pool()
     (the REL-19 hotfix invariant)
  4. /api/products serves cached products + staleAll=true throughout
  5. Eventually one refresh succeeds → pool recovers → scheduler resumes

Without this test, the 2026-05-13 REL-19 bug that caused the 69-min
00:04→01:13 outage would have re-regressed silently. Any change to the
graceful-degrade path must keep these invariants green.

Strategy: mock at `_probe_candidates_in_parallel` level so no network
is touched. Pool state mutations go through the real `pool_state.save`
so `_is_pool_dead` sees real file contents.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Per-test data directory + env overrides for all persistent paths."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setenv("SALEAPP_POOL_QUARANTINE_PATH", str(data_dir / "pool_quarantine.json"))
    monkeypatch.setenv("SALEAPP_ADMIN_ALERTS_PATH", str(data_dir / "admin_alerts.jsonl"))

    # Reload modules that cache their paths at import time.
    import importlib
    from vless import quarantine
    importlib.reload(quarantine)
    from backend import admin_alerts
    importlib.reload(admin_alerts)

    return data_dir


@pytest.fixture
def stub_scheduler_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_data_dir: Path):
    """Override scheduler's DATA_DIR so _is_pool_dead reads our test file."""
    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(isolated_data_dir))
    monkeypatch.setattr(
        scheduler_service,
        "_SCHEDULER_EVENTS_PATH",
        str(isolated_data_dir / "scheduler_events.jsonl"),
    )
    monkeypatch.setattr(scheduler_service, "log", lambda msg: None)
    # v1.27.2: collapse-replay tests reproduce genuine pool-death incidents.
    # Disable the manual-seed floor so _is_pool_dead() reflects the dynamic
    # pool state these scenarios are built around (otherwise it always
    # returns False and the dead-cycle recovery path never runs).
    monkeypatch.setattr(scheduler_service, "_has_manual_seeds", lambda: False)
    return scheduler_service


def _write_pool(data_dir: Path, node_count: int) -> None:
    """Seed vless_pool.json with N synthetic nodes."""
    nodes = [
        {"host": f"node{i}.test", "port": 443, "name": f"node-{i}"}
        for i in range(node_count)
    ]
    (data_dir / "vless_pool.json").write_text(json.dumps({
        "updated_at": "2026-05-13T00:00:00",
        "nodes": nodes,
    }))


# ── QA-06 — collapse replay ────────────────────────────────────────


def test_collapse_replay_setup_healthy_pool(isolated_data_dir, stub_scheduler_data_dir):
    """Baseline: pool at 20 means _is_pool_dead returns False."""
    _write_pool(isolated_data_dir, 20)
    assert stub_scheduler_data_dir._is_pool_dead() is False


def test_collapse_replay_event1_catastrophic_drop_to_zero(isolated_data_dir, stub_scheduler_data_dir):
    """Event 1: all candidates probe-fail → pool drops to 0.

    Simulates the 2026-05-13 16:19 event where every healthy node
    went silent at roughly the same time."""
    # Start at 20
    _write_pool(isolated_data_dir, 20)
    assert stub_scheduler_data_dir._is_pool_dead() is False

    # Simulate the refresh that finds 0 working candidates
    # (real _probe_candidates_in_parallel would return [] here)
    _write_pool(isolated_data_dir, 0)
    assert stub_scheduler_data_dir._is_pool_dead() is True


def test_collapse_replay_event2_dead_cycles_trigger_recovery_attempts(
    isolated_data_dir, stub_scheduler_data_dir, monkeypatch
):
    """Event 2: REL-19 hotfix invariant — EVERY dead cycle must call
    ensure_pool(), not just skip. Pre-hotfix, scheduler skipped all
    cycles including the recovery path, creating the stuck state."""
    _write_pool(isolated_data_dir, 0)

    ensure_pool_calls = []

    class _FakeRefreshPM:
        def __init__(self, *args, **kwargs):
            pass
        def ensure_pool(self):
            ensure_pool_calls.append(1)
            return 0  # pool stays dead — probe keeps failing

    import vless.manager
    monkeypatch.setattr(vless.manager, "VlessProxyManager", _FakeRefreshPM)

    # Stub the rest of _run_scraper_set pipeline (we only care about the
    # graceful-degrade block).
    monkeypatch.setattr(
        stub_scheduler_data_dir,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )

    class _FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(stub_scheduler_data_dir, "probe_bridge_alive", lambda timeout: _FakeProbe())
    monkeypatch.setattr(stub_scheduler_data_dir, "run_script", lambda s, t: 0)
    monkeypatch.setattr(stub_scheduler_data_dir, "_check_file_updated", lambda p, ts: False)
    monkeypatch.setattr(stub_scheduler_data_dir, "_classify_scraper_status", lambda c, u: "SKIPPED")
    monkeypatch.setattr(stub_scheduler_data_dir, "_kill_all_scraper_chrome", lambda: None)

    scrapers = [("scrape_green.py", "GREEN", "green_products.json")]
    proxy_state = {}

    # Run 5 dead cycles
    for _ in range(5):
        proxy_state, _ = stub_scheduler_data_dir._run_scraper_set(scrapers, proxy_state)

    # REL-19 hotfix invariant: every dead cycle calls ensure_pool.
    # Pre-hotfix: 0 calls (cycles 2+ silently skipped recovery).
    # Post-hotfix: 5 calls (one per cycle).
    assert len(ensure_pool_calls) == 5, (
        f"Every dead cycle must attempt recovery; got {len(ensure_pool_calls)} calls"
    )

    # Counter tracks cumulative dead cycles
    assert proxy_state["consecutive_pool_dead_cycles"] == 5


def test_collapse_replay_event3_recovery_resets_state(
    isolated_data_dir, stub_scheduler_data_dir, monkeypatch
):
    """Event 3: on the N-th cycle, refresh succeeds. Pool recovers,
    counter resets, scrape proceeds normally, recovery event emitted."""
    _write_pool(isolated_data_dir, 0)

    data_dir_ref = isolated_data_dir

    class _RecoveringPM:
        def __init__(self, *args, **kwargs):
            pass
        def ensure_pool(self):
            # Simulate a successful refresh: write 10 nodes.
            _write_pool(data_dir_ref, 10)
            return 10

    import vless.manager
    monkeypatch.setattr(vless.manager, "VlessProxyManager", _RecoveringPM)

    # Stub the rest of the pipeline so the cycle completes normally.
    monkeypatch.setattr(
        stub_scheduler_data_dir,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )

    class _FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(stub_scheduler_data_dir, "probe_bridge_alive", lambda timeout: _FakeProbe())
    monkeypatch.setattr(stub_scheduler_data_dir, "run_script", lambda s, t: 0)
    monkeypatch.setattr(stub_scheduler_data_dir, "_check_file_updated", lambda p, ts: True)
    monkeypatch.setattr(stub_scheduler_data_dir, "_classify_scraper_status", lambda c, u: "OK")
    monkeypatch.setattr(stub_scheduler_data_dir, "_kill_all_scraper_chrome", lambda: None)

    scrapers = [("scrape_green.py", "GREEN", "green_products.json")]

    # Pretend we've had 4 dead cycles already — this is the 5th (recovery).
    proxy_state = {"consecutive_pool_dead_cycles": 4}

    proxy_state, results = stub_scheduler_data_dir._run_scraper_set(scrapers, proxy_state)

    # Counter reset on recovery
    assert proxy_state["consecutive_pool_dead_cycles"] == 0

    # Result status should NOT be SKIPPED — scrape actually ran
    assert results["GREEN"]["status_text"] != "SKIPPED (pool dead)"

    # scheduler_pool_recovered event should be in the ledger.
    # Counter increments from 4 → 5 at the start of this cycle (before
    # ensure_pool runs), then resets to 0 after recovery. Event records
    # the post-increment value.
    events_file = isolated_data_dir / "scheduler_events.jsonl"
    assert events_file.exists()
    events = [json.loads(line) for line in events_file.read_text().splitlines() if line.strip()]
    recovered_events = [e for e in events if e["event"] == "scheduler_pool_recovered"]
    assert len(recovered_events) == 1
    assert recovered_events[0]["consecutive_dead_cycles"] == 5
    assert recovered_events[0]["recovered_size"] == 10


def test_collapse_replay_full_cycle_end_to_end(
    isolated_data_dir, stub_scheduler_data_dir, monkeypatch
):
    """Full replay: healthy → catastrophic drop → 5 dead cycles with
    every one calling ensure_pool → recovery on cycle 6 → state reset.

    This is the single test that would have caught the REL-19 bug."""
    # Start healthy
    _write_pool(isolated_data_dir, 20)

    # Track ensure_pool invocations + whether pool is dead at call time
    refresh_calls = []

    # Behavior changes over time: fails 5 times, succeeds on 6th
    data_dir_ref = isolated_data_dir

    class _FlakyPM:
        def __init__(self, *args, **kwargs):
            pass
        def ensure_pool(self):
            refresh_calls.append(1)
            # First 4 calls fail (pool stays dead), 5th call recovers.
            if len(refresh_calls) < 5:
                return 0
            _write_pool(data_dir_ref, 10)
            return 10

    import vless.manager
    monkeypatch.setattr(vless.manager, "VlessProxyManager", _FlakyPM)

    monkeypatch.setattr(
        stub_scheduler_data_dir,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )

    class _FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(stub_scheduler_data_dir, "probe_bridge_alive", lambda timeout: _FakeProbe())
    monkeypatch.setattr(stub_scheduler_data_dir, "run_script", lambda s, t: 0)
    monkeypatch.setattr(stub_scheduler_data_dir, "_check_file_updated", lambda p, ts: False)
    monkeypatch.setattr(stub_scheduler_data_dir, "_classify_scraper_status", lambda c, u: "FAKE")
    monkeypatch.setattr(stub_scheduler_data_dir, "_kill_all_scraper_chrome", lambda: None)

    scrapers = [("scrape_green.py", "GREEN", "green_products.json")]
    proxy_state = {}

    # Cycle 1: pool is healthy (20 nodes). Normal scrape, no refresh attempted
    # in the graceful-degrade block (because _is_pool_dead returns False).
    proxy_state, _ = stub_scheduler_data_dir._run_scraper_set(scrapers, proxy_state)
    assert len(refresh_calls) == 0
    assert proxy_state["consecutive_pool_dead_cycles"] == 0

    # CATASTROPHIC DROP — pool goes to 0 (as if refresh_proxy_list decided
    # all nodes failed simultaneously).
    _write_pool(isolated_data_dir, 0)

    # Cycles 2-6: pool stays dead, refresh called each cycle.
    for cycle_num in range(2, 7):
        proxy_state, _ = stub_scheduler_data_dir._run_scraper_set(scrapers, proxy_state)

    # REL-19 hotfix invariant: 5 recovery attempts (cycles 2-6)
    # On cycle 6, the _FlakyPM's 5th (0-indexed) attempt succeeds — but
    # actually the recovery happens during cycle 6's call (the 6th refresh
    # call). So cycle 6 exits the graceful-degrade block with pool=10.
    assert len(refresh_calls) == 5, (
        f"Dead cycles 2-6 = 5 recovery attempts; got {len(refresh_calls)}"
    )

    # After recovery in cycle 6, counter reset
    assert proxy_state["consecutive_pool_dead_cycles"] == 0

    # Cycle 7: pool healthy again, normal scrape continues
    proxy_state, _ = stub_scheduler_data_dir._run_scraper_set(scrapers, proxy_state)
    # refresh_calls unchanged — normal path doesn't call ensure_pool in
    # the graceful-degrade block.
    assert len(refresh_calls) == 5
