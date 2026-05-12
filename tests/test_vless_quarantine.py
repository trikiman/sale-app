"""Phase 77 (v1.24 REL-16/17/18) — quarantine + throttle + rate-of-decline tests.

Verifies:
- Quarantine TTL expiry (20 min default, 4h for repeat offenders)
- `record_probe_failures` batch-records + escalates fail_count correctly
- `get_quarantined_hosts` excludes expired entries
- `VlessProxyManager.ensure_pool` throttles within REFRESH_MIN_INTERVAL_S
- Rate-of-decline check triggers refresh when pool lost ≥3 in 5 min

Test strategy:
- Use ``SALEAPP_POOL_QUARANTINE_PATH`` env var to redirect deadlist to tmp_path
- Monkeypatch time.time / time.monotonic for TTL tests
- Monkeypatch ``VlessProxyManager.refresh_proxy_list`` to avoid real network
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

# Pytest's monkeypatch runs before module import, so set env var via fixture.


@pytest.fixture
def tmp_quarantine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the quarantine file to a per-test tmp path."""
    path = tmp_path / "pool_quarantine.json"
    monkeypatch.setenv("SALEAPP_POOL_QUARANTINE_PATH", str(path))
    # Reload module so QUARANTINE_PATH picks up the env override.
    import importlib
    from vless import quarantine
    importlib.reload(quarantine)
    monkeypatch.setattr(quarantine, "QUARANTINE_PATH", str(path))
    yield path


def test_record_probe_failure_persists_with_default_ttl(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    monkeypatch.setattr(time, "time", lambda: 1000.0)
    quarantine.record_probe_failure("1.2.3.4:443", reason="probe_timeout")

    assert tmp_quarantine.exists()
    data = json.loads(tmp_quarantine.read_text())
    entry = data["quarantined"]["1.2.3.4:443"]
    assert entry["reason"] == "probe_timeout"
    assert entry["fail_count"] == 1
    assert entry["first_failed_at"] == 1000.0
    assert entry["last_failed_at"] == 1000.0
    assert entry["expires_at"] == 1000.0 + quarantine.QUARANTINE_TTL_S


def test_repeat_offender_gets_longer_ttl(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    # Fail 3 times → should hit repeat-offender TTL on the 3rd failure.
    timestamps = [1000.0, 1010.0, 1020.0]

    for ts in timestamps:
        monkeypatch.setattr(time, "time", lambda ts=ts: ts)
        quarantine.record_probe_failure("5.6.7.8:443")

    data = json.loads(tmp_quarantine.read_text())
    entry = data["quarantined"]["5.6.7.8:443"]
    assert entry["fail_count"] == 3
    assert entry["first_failed_at"] == 1000.0  # preserved across re-records
    assert entry["last_failed_at"] == 1020.0
    # 3rd failure triggers 4h TTL
    assert entry["expires_at"] == 1020.0 + quarantine.REPEAT_OFFENDER_TTL_S


def test_get_quarantined_hosts_prunes_expired(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    # Write an entry that expired in the past
    tmp_quarantine.write_text(json.dumps({
        "quarantined": {
            "expired.host:443": {
                "reason": "probe_timeout",
                "first_failed_at": 1000.0,
                "last_failed_at": 1000.0,
                "fail_count": 1,
                "expires_at": 1500.0,  # expired
            },
            "alive.host:443": {
                "reason": "probe_timeout",
                "first_failed_at": 2000.0,
                "last_failed_at": 2000.0,
                "fail_count": 1,
                "expires_at": 9999999999.0,  # far future
            },
        }
    }))

    monkeypatch.setattr(time, "time", lambda: 3000.0)
    hosts = quarantine.get_quarantined_hosts()
    assert hosts == {"alive.host:443"}


def test_record_probe_failures_batch(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    monkeypatch.setattr(time, "time", lambda: 5000.0)
    quarantine.record_probe_failures(
        ["a.host:443", "b.host:443", "c.host:443"],
        reason="probe_error"
    )

    data = json.loads(tmp_quarantine.read_text())
    assert len(data["quarantined"]) == 3
    for host in ["a.host:443", "b.host:443", "c.host:443"]:
        assert data["quarantined"][host]["reason"] == "probe_error"
        assert data["quarantined"][host]["fail_count"] == 1


def test_release_removes_entry(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    monkeypatch.setattr(time, "time", lambda: 1000.0)
    quarantine.record_probe_failure("remove.me:443")
    assert quarantine.is_quarantined("remove.me:443")

    quarantine.release("remove.me:443")
    assert not quarantine.is_quarantined("remove.me:443")


def test_clear_all_wipes_quarantine(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    monkeypatch.setattr(time, "time", lambda: 1000.0)
    quarantine.record_probe_failures(["a:1", "b:2", "c:3"])
    assert len(quarantine.get_quarantined_hosts()) == 3

    quarantine.clear_all()
    assert len(quarantine.get_quarantined_hosts()) == 0


def test_snapshot_returns_count_and_hosts(tmp_quarantine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vless import quarantine

    monkeypatch.setattr(time, "time", lambda: 1000.0)
    quarantine.record_probe_failures(["host1:443", "host2:443"])

    snap = quarantine.snapshot()
    assert snap["count"] == 2
    assert "host1:443" in snap["hosts"]
    assert "host2:443" in snap["hosts"]
    assert set(snap["entries"].keys()) == {"host1:443", "host2:443"}


def test_io_errors_are_swallowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quarantine must never crash the caller on I/O errors."""
    from vless import quarantine

    # Point at a path that cannot be written (root of nonexistent drive)
    bad_path = str(tmp_path / "nonexistent_dir" / "sub" / "quarantine.json")
    monkeypatch.setattr(quarantine, "QUARANTINE_PATH", bad_path)

    # This should work — we create parent dir
    quarantine.record_probe_failure("test:443")

    # Now simulate load error by writing garbage
    bad_file = Path(bad_path)
    bad_file.write_text("{garbage")

    # Should return empty set, not crash
    hosts = quarantine.get_quarantined_hosts()
    assert hosts == set()


# ── VlessProxyManager integration ─────────────────────────────────


def test_ensure_pool_throttles_rapid_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-17: second ensure_pool() within REFRESH_MIN_INTERVAL_S is a no-op."""
    from vless import manager as mgr_module
    from vless.manager import VlessProxyManager

    # Minimum mock surface — don't actually start xray, don't fetch VLESS list.
    monkeypatch.setattr(VlessProxyManager, "_prune_expired_cooldowns", lambda self: None)

    refresh_calls = []

    def fake_refresh(self, exclude=None):
        refresh_calls.append(time.monotonic())
        return 0

    monkeypatch.setattr(VlessProxyManager, "refresh_proxy_list", fake_refresh)
    monkeypatch.setattr(VlessProxyManager, "_load_cooldowns", lambda self: {})
    monkeypatch.setattr(VlessProxyManager, "pool_count", lambda self: 0)
    monkeypatch.setattr(VlessProxyManager, "is_cache_stale", lambda self: False)

    pm = VlessProxyManager(
        log_func=lambda msg: None,
        pool_path=tmp_path / "pool.json",
        cooldowns_path=tmp_path / "cooldowns.json",
        events_path=tmp_path / "events.jsonl",
        xray_config_path=tmp_path / "xray.json",
        xray_log_path=tmp_path / "xray.log",
        register_atexit=False,
    )

    # Stub the monotonic clock to make the test deterministic.
    fake_now = [100.0]
    monkeypatch.setattr(VlessProxyManager, "_monotonic", staticmethod(lambda: fake_now[0]))

    # Call 1 — pool is 0, should refresh.
    pm.ensure_pool()
    assert len(refresh_calls) == 1

    # Call 2 at +10s — should be throttled (no new refresh).
    fake_now[0] = 110.0
    pm.ensure_pool()
    assert len(refresh_calls) == 1, "Second call within 60s window must be throttled"

    # Call 3 at +61s — should refresh.
    fake_now[0] = 161.0
    pm.ensure_pool()
    assert len(refresh_calls) == 2


def test_ensure_pool_rate_of_decline_triggers_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-18: pool losing ≥3 nodes in 5 min triggers refresh even if size > MIN_HEALTHY."""
    from vless import manager as mgr_module
    from vless.manager import VlessProxyManager

    monkeypatch.setattr(VlessProxyManager, "_prune_expired_cooldowns", lambda self: None)
    monkeypatch.setattr(VlessProxyManager, "_load_cooldowns", lambda self: {})
    monkeypatch.setattr(VlessProxyManager, "is_cache_stale", lambda self: False)

    refresh_calls = []
    monkeypatch.setattr(
        VlessProxyManager,
        "refresh_proxy_list",
        lambda self, exclude=None: refresh_calls.append(1) or 0,
    )

    # Pool size controlled by fake_count — change per call phase.
    fake_count = {"v": 20}
    monkeypatch.setattr(VlessProxyManager, "pool_count", lambda self: fake_count["v"])

    pm = VlessProxyManager(
        log_func=lambda msg: None,
        pool_path=tmp_path / "pool.json",
        cooldowns_path=tmp_path / "cooldowns.json",
        events_path=tmp_path / "events.jsonl",
        xray_config_path=tmp_path / "xray.json",
        xray_log_path=tmp_path / "xray.log",
        register_atexit=False,
    )

    # Control monotonic time across 3 ensure_pool() calls spanning 6 min.
    fake_now = [0.0]
    monkeypatch.setattr(VlessProxyManager, "_monotonic", staticmethod(lambda: fake_now[0]))

    # t=0: pool 20, no refresh needed (above MIN_HEALTHY=10, no history yet)
    pm.ensure_pool()
    assert len(refresh_calls) == 0

    # t=310 (5min10s later): pool still 20
    fake_now[0] = 310.0
    pm.ensure_pool()
    assert len(refresh_calls) == 0

    # t=370 (6min10s from start): pool now 17 — lost 3 over 6 min.
    # Should trigger rate-of-decline refresh despite 17 >= MIN_HEALTHY=10.
    fake_now[0] = 370.0
    fake_count["v"] = 17
    pm.ensure_pool()
    assert len(refresh_calls) == 1, f"Pool decline of 3+ in 5 min must trigger refresh; history={list(pm._pool_size_history)}"


# ── Scheduler graceful degrade (REL-19) ────────────────────────────


def test_is_pool_dead_returns_true_when_pool_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-19: `_is_pool_dead` helper returns True when vless_pool.json is empty."""
    # Write an empty pool file
    pool_file = tmp_path / "vless_pool.json"
    pool_file.write_text(json.dumps({"nodes": []}))

    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))

    assert scheduler_service._is_pool_dead() is True


def test_is_pool_dead_returns_false_when_pool_has_nodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-19: `_is_pool_dead` returns False when pool has at least 1 node."""
    pool_file = tmp_path / "vless_pool.json"
    pool_file.write_text(json.dumps({"nodes": [{"host": "1.2.3.4", "port": 443}]}))

    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))

    assert scheduler_service._is_pool_dead() is False


def test_is_pool_dead_returns_true_when_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-19: missing pool file treated as dead (safer default)."""
    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))

    assert scheduler_service._is_pool_dead() is True


def test_scheduler_skips_scrape_after_two_dead_cycles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-19: 2nd consecutive dead-pool cycle → skip with exit 0 + event."""
    pool_file = tmp_path / "vless_pool.json"
    pool_file.write_text(json.dumps({"nodes": []}))

    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(scheduler_service, "_SCHEDULER_EVENTS_PATH", str(tmp_path / "scheduler_events.jsonl"))
    monkeypatch.setattr(scheduler_service, "log", lambda msg: None)

    scrapers = [
        ("scrape_green.py", "GREEN", "green_products.json"),
        ("scrape_red.py", "RED", "red_products.json"),
    ]

    # Cycle 1 — first dead cycle, consecutive=1, should NOT skip yet.
    proxy_state = {}
    # We need to intercept _prepare_proxy_connectivity to avoid real work.
    # But the graceful-degrade check runs BEFORE that — so we need to ensure
    # the function returns before reaching _prepare_proxy_connectivity.
    # Cycle 1 doesn't skip, so it would reach _prepare_proxy_connectivity.
    # Monkeypatch it to a no-op returning (None, proxy_state) so the rest
    # of _run_scraper_set doesn't execute either.
    monkeypatch.setattr(
        scheduler_service,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )
    # Also stub probe_bridge_alive to prevent real network
    class FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(scheduler_service, "probe_bridge_alive", lambda timeout: FakeProbe())
    monkeypatch.setattr(scheduler_service, "run_script", lambda script, tag: 0)
    monkeypatch.setattr(scheduler_service, "_check_file_updated", lambda path, before_ts: False)
    monkeypatch.setattr(scheduler_service, "_classify_scraper_status", lambda code, updated: "FAKE")
    monkeypatch.setattr(scheduler_service, "_kill_all_scraper_chrome", lambda: None)

    # Cycle 1 — pool is dead but consecutive=1 → no skip yet
    proxy_state, results = scheduler_service._run_scraper_set(scrapers, proxy_state)
    assert proxy_state["consecutive_pool_dead_cycles"] == 1
    # Didn't skip — all scrapers returned the run_script=0 result
    for tag in ("GREEN", "RED"):
        assert results[tag]["status_text"] != "SKIPPED (pool dead)"

    # Cycle 2 — 2nd consecutive dead cycle → skip
    proxy_state, results = scheduler_service._run_scraper_set(scrapers, proxy_state)
    assert proxy_state["consecutive_pool_dead_cycles"] == 2
    for tag in ("GREEN", "RED"):
        assert results[tag]["status_text"] == "SKIPPED (pool dead)"
        assert results[tag]["code"] == 0  # graceful — not a failure

    # Verify scheduler_pool_dead event was emitted
    events_file = tmp_path / "scheduler_events.jsonl"
    assert events_file.exists()
    events = [json.loads(line) for line in events_file.read_text().splitlines() if line.strip()]
    dead_events = [e for e in events if e["event"] == "scheduler_pool_dead"]
    assert len(dead_events) == 1
    assert dead_events[0]["consecutive_dead_cycles"] == 2
    assert set(dead_events[0]["scrapers_skipped"]) == {"GREEN", "RED"}


def test_scheduler_resets_counter_when_pool_recovers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REL-19: consecutive-dead counter resets when pool has nodes again."""
    pool_file = tmp_path / "vless_pool.json"

    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(scheduler_service, "_SCHEDULER_EVENTS_PATH", str(tmp_path / "scheduler_events.jsonl"))
    monkeypatch.setattr(scheduler_service, "log", lambda msg: None)
    monkeypatch.setattr(
        scheduler_service,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )

    class FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(scheduler_service, "probe_bridge_alive", lambda timeout: FakeProbe())
    monkeypatch.setattr(scheduler_service, "run_script", lambda script, tag: 0)
    monkeypatch.setattr(scheduler_service, "_check_file_updated", lambda path, before_ts: False)
    monkeypatch.setattr(scheduler_service, "_classify_scraper_status", lambda code, updated: "FAKE")
    monkeypatch.setattr(scheduler_service, "_kill_all_scraper_chrome", lambda: None)

    scrapers = [("scrape_green.py", "GREEN", "green_products.json")]

    # Dead cycle 1
    pool_file.write_text(json.dumps({"nodes": []}))
    proxy_state, _ = scheduler_service._run_scraper_set(scrapers, {})
    assert proxy_state["consecutive_pool_dead_cycles"] == 1

    # Pool recovers
    pool_file.write_text(json.dumps({"nodes": [{"host": "1.2.3.4", "port": 443}]}))
    proxy_state, _ = scheduler_service._run_scraper_set(scrapers, proxy_state)
    assert proxy_state["consecutive_pool_dead_cycles"] == 0, "Counter must reset on pool recovery"


# ── v1.25 HOTFIX: graceful-degrade-must-also-recover regression ────────


def test_pool_refresh_attempted_on_every_dead_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REGRESSION 2026-05-13: when pool is dead, scheduler MUST still
    call ensure_pool() on each cycle — otherwise recovery becomes a
    terminal stuck state (observed 72-min outage, pool stayed at 0).

    This test pins the invariant: every _run_scraper_set call with
    pool=0 must trigger ensure_pool(), whether or not it decides to
    skip the scrape afterward."""
    pool_file = tmp_path / "vless_pool.json"
    pool_file.write_text(json.dumps({"nodes": []}))

    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(scheduler_service, "_SCHEDULER_EVENTS_PATH", str(tmp_path / "scheduler_events.jsonl"))
    monkeypatch.setattr(scheduler_service, "log", lambda msg: None)

    # Track ensure_pool calls
    ensure_pool_calls = []

    class _FakePM:
        def __init__(self, *args, **kwargs):
            pass
        def ensure_pool(self):
            ensure_pool_calls.append(1)
            return 0  # Pool stays dead

    # Intercept VlessProxyManager construction in the graceful-degrade block
    import vless.manager
    monkeypatch.setattr(vless.manager, "VlessProxyManager", _FakePM)

    # Stub downstream path that runs when cycle falls through (consecutive<2).
    # We only care about the ensure_pool call count, not the full pipeline.
    monkeypatch.setattr(
        scheduler_service,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )
    class FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(scheduler_service, "probe_bridge_alive", lambda timeout: FakeProbe())
    monkeypatch.setattr(scheduler_service, "run_script", lambda script, tag: 0)
    monkeypatch.setattr(scheduler_service, "_check_file_updated", lambda path, before_ts: False)
    monkeypatch.setattr(scheduler_service, "_classify_scraper_status", lambda code, updated: "FAKE")
    monkeypatch.setattr(scheduler_service, "_kill_all_scraper_chrome", lambda: None)

    scrapers = [("scrape_green.py", "GREEN", "green_products.json")]

    # Run 3 dead cycles — each must attempt pool refresh
    proxy_state = {}
    for i in range(3):
        proxy_state, results = scheduler_service._run_scraper_set(scrapers, proxy_state)

    # CRITICAL: 3 ensure_pool calls — one per dead cycle.
    # Pre-hotfix behavior: 0 calls (scheduler skipped everything including refresh).
    assert len(ensure_pool_calls) == 3, (
        f"Pool refresh must be attempted on every dead cycle; got {len(ensure_pool_calls)} calls"
    )


def test_pool_recovery_flows_through_to_normal_scrape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REGRESSION 2026-05-13: when ensure_pool() recovers the pool during
    a dead cycle, _run_scraper_set must fall through to the normal scrape
    path instead of continuing to skip."""
    pool_file = tmp_path / "vless_pool.json"
    pool_file.write_text(json.dumps({"nodes": []}))  # start dead

    import scheduler_service
    monkeypatch.setattr(scheduler_service, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(scheduler_service, "_SCHEDULER_EVENTS_PATH", str(tmp_path / "scheduler_events.jsonl"))
    monkeypatch.setattr(scheduler_service, "log", lambda msg: None)

    class _RecoveringPM:
        def __init__(self, *args, **kwargs):
            pass
        def ensure_pool(self):
            # Simulate successful pool refresh — write non-empty pool file.
            pool_file.write_text(json.dumps({"nodes": [{"host": "1.2.3.4", "port": 443}]}))
            return 1

    import vless.manager
    monkeypatch.setattr(vless.manager, "VlessProxyManager", _RecoveringPM)

    # Stub the rest of the scraper pipeline
    monkeypatch.setattr(
        scheduler_service,
        "_prepare_proxy_connectivity",
        lambda state: (None, state),
    )

    class FakeProbe:
        ok = True
        cached = True
        reason = "cached"
        status = 200
        elapsed_s = 0.0
    monkeypatch.setattr(scheduler_service, "probe_bridge_alive", lambda timeout: FakeProbe())
    monkeypatch.setattr(scheduler_service, "run_script", lambda script, tag: 0)
    monkeypatch.setattr(scheduler_service, "_check_file_updated", lambda path, before_ts: True)
    monkeypatch.setattr(scheduler_service, "_classify_scraper_status", lambda code, updated: "OK (data updated)")
    monkeypatch.setattr(scheduler_service, "_kill_all_scraper_chrome", lambda: None)

    scrapers = [("scrape_green.py", "GREEN", "green_products.json")]

    # 1st cycle marks pool dead (consecutive=1). Since 1<2, it would normally
    # fall through anyway. Let's force consecutive=1 upfront.
    proxy_state = {"consecutive_pool_dead_cycles": 1}

    # On this cycle, _is_pool_dead is initially True but ensure_pool recovers
    # it. _run_scraper_set should proceed with the normal scrape path.
    proxy_state, results = scheduler_service._run_scraper_set(scrapers, proxy_state)

    # Counter reset because pool recovered
    assert proxy_state["consecutive_pool_dead_cycles"] == 0, (
        f"consecutive counter should reset after recovery, got {proxy_state['consecutive_pool_dead_cycles']}"
    )

    # GREEN result should NOT be "SKIPPED (pool dead)" — scrape actually ran
    assert results["GREEN"]["status_text"] != "SKIPPED (pool dead)", (
        "Pool recovered mid-cycle — must fall through to normal scrape"
    )
