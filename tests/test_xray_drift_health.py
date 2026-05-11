"""v1.21 Phase 69 — xray drift block in /api/health/deep.

Covers:
  * ``_compute_xray_drift_block`` — helper that produces the xray_drift
    block + reason + critical flag, with first-seen tracking
  * ``_build_reliability_snapshot`` wiring — attach block, inject reason,
    bump severity (added in 69-02)

Pure unit tests. No HTTP, no real xray config loading (monkeypatched).
Live proof via ``scripts/verify_v1.21.sh 69`` + ``69-VERIFICATION.md``.
"""
from __future__ import annotations

import time as _time

import pytest

import backend.main as bm


@pytest.fixture(autouse=True)
def _reset_drift_state():
    """Each test starts with an empty _DRIFT_FIRST_SEEN dict."""
    bm._DRIFT_FIRST_SEEN.clear()
    yield
    bm._DRIFT_FIRST_SEEN.clear()


# ── _compute_xray_drift_block (69-01) ─────────────────────────────────────

def test_xray_drift_block_absent_when_pool_unavailable():
    """No pool snapshot → no drift block (same no-ledger fallback as cart_add)."""
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": False}, cycle_age=None
    )
    assert block is None
    assert reason is None
    assert critical is False


def test_xray_drift_block_absent_when_config_unreadable(monkeypatch):
    """Missing/malformed active.json → block absent, no drift reported."""
    monkeypatch.setattr(bm, "_extract_running_xray_hosts_for_health", lambda: None)
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": True, "size": 3}, cycle_age=60.0
    )
    assert block is None
    assert reason is None
    assert critical is False


def test_xray_drift_block_absent_when_admitted_unreadable(monkeypatch):
    """Missing/malformed vless_pool.json → block absent."""
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: None)
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": True, "size": 3}, cycle_age=60.0
    )
    assert block is None


def test_xray_drift_block_zero_when_sets_match(monkeypatch):
    """Healthy steady-state: admitted == running, drift_count=0, no reason."""
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a", "b", "c"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"a", "b", "c"})
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": True, "size": 3}, cycle_age=60.0
    )
    assert block == {
        "admitted_hosts": 3,
        "active_outbounds": 3,
        "drift_count": 0,
        "drifted_hosts": [],
        "first_seen_at": None,
    }
    assert reason is None
    assert critical is False


def test_xray_drift_block_reports_symmetric_difference(monkeypatch):
    """admitted={b,c,d}, running={a,b} → drift={a,c,d}, sorted."""
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a", "b"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"b", "c", "d"})
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": True, "size": 3}, cycle_age=60.0
    )
    assert block["drift_count"] == 3
    assert block["drifted_hosts"] == ["a", "c", "d"]
    assert block["admitted_hosts"] == 3
    assert block["active_outbounds"] == 2
    assert block["first_seen_at"] is not None
    # Just-detected drift within grace window → no reason yet
    assert reason is None
    assert critical is False


def test_xray_drift_reason_added_after_5_min(monkeypatch):
    """Persisted drift > 5 min → reasons gets xray_stale_config:{N}_nodes_drifted."""
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"b"})
    # Seed first-seen to simulate drift persisted > 5 min without sleeping.
    now = _time.monotonic()
    bm._DRIFT_FIRST_SEEN[frozenset({"a", "b"})] = (now - 301, "2026-05-12T19:00:00")
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": True, "size": 1}, cycle_age=60.0
    )
    assert block["drift_count"] == 2
    assert reason == "xray_stale_config:2_nodes_drifted"
    assert critical is False   # cycle_age still fresh


def test_xray_drift_unhealthy_when_also_stale_cycle(monkeypatch):
    """drift persisted > 5min AND cycle_age > 10min → is_critical=True."""
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"b"})
    now = _time.monotonic()
    bm._DRIFT_FIRST_SEEN[frozenset({"a", "b"})] = (now - 310, "2026-05-12T19:00:00")
    block, reason, critical = bm._compute_xray_drift_block(
        {"available": True, "size": 1}, cycle_age=700.0
    )
    assert reason == "xray_stale_config:2_nodes_drifted"
    assert critical is True


def test_xray_drift_first_seen_resets_on_set_change(monkeypatch):
    """Drift set changes → stale entry pruned, new entry recorded with fresh timestamp."""
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"b"})
    bm._compute_xray_drift_block(
        {"available": True, "size": 1}, cycle_age=60.0
    )
    assert frozenset({"a", "b"}) in bm._DRIFT_FIRST_SEEN

    # Change admitted host → new drift key → old entry must be pruned.
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"c"})
    bm._compute_xray_drift_block(
        {"available": True, "size": 1}, cycle_age=60.0
    )
    assert frozenset({"a", "b"}) not in bm._DRIFT_FIRST_SEEN
    assert frozenset({"a", "c"}) in bm._DRIFT_FIRST_SEEN


def test_xray_drift_thresholds_locked():
    """SPEC Lock: OBS-06 thresholds must match 69-CONTEXT.md (EC2 smoke 69-A)."""
    assert bm._DEEP_DRIFT_DEGRADED_S == 300
    assert bm._DEEP_DRIFT_UNHEALTHY_CYCLE_AGE_S == 600


# ── _build_reliability_snapshot wiring (69-02) ────────────────────────────


def test_reliability_snapshot_attaches_drift_block_when_present(monkeypatch):
    """/api/health/deep body gains xray_drift key when pool + config available."""
    monkeypatch.setattr(
        bm,
        "_pool_snapshot_for_health",
        lambda: {"available": True, "size": 3, "min_healthy": 3},
    )
    monkeypatch.setattr(
        bm, "_load_breaker_snapshot", lambda: {"available": True, "state": "closed"}
    )
    monkeypatch.setattr(
        bm, "_check_xray_listening", lambda: {"listening": True, "port": 10808}
    )
    monkeypatch.setattr(bm, "_last_cycle_age_seconds", lambda: 60.0)
    monkeypatch.setattr(bm, "_products_mtime_age_seconds", lambda: 60.0)
    monkeypatch.setattr(bm, "_compute_cart_add_block", lambda: (None, None))
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a", "b", "c"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"a", "b", "c"})

    snap = bm._build_reliability_snapshot()
    assert "xray_drift" in snap
    assert snap["xray_drift"]["drift_count"] == 0
    assert snap["xray_drift"]["drifted_hosts"] == []
    assert snap["status"] == "healthy"
    assert "xray_stale_config" not in " ".join(snap["reasons"])


def test_reliability_snapshot_degraded_when_drift_persisted(monkeypatch):
    """When drift has persisted > 5 min, reasons gets xray_stale_config; status=degraded."""
    monkeypatch.setattr(
        bm,
        "_pool_snapshot_for_health",
        lambda: {"available": True, "size": 1, "min_healthy": 1},
    )
    monkeypatch.setattr(
        bm, "_load_breaker_snapshot", lambda: {"available": True, "state": "closed"}
    )
    monkeypatch.setattr(
        bm, "_check_xray_listening", lambda: {"listening": True, "port": 10808}
    )
    monkeypatch.setattr(bm, "_last_cycle_age_seconds", lambda: 60.0)
    monkeypatch.setattr(bm, "_products_mtime_age_seconds", lambda: 60.0)
    monkeypatch.setattr(bm, "_compute_cart_add_block", lambda: (None, None))
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"b"})
    # Seed drift persistence > 5 min without sleeping.
    now = _time.monotonic()
    bm._DRIFT_FIRST_SEEN[frozenset({"a", "b"})] = (now - 320, "2026-05-12T19:00:00")

    snap = bm._build_reliability_snapshot()
    assert "xray_stale_config:2_nodes_drifted" in snap["reasons"]
    assert snap["status"] == "degraded"
    assert snap["xray_drift"]["drift_count"] == 2


def test_reliability_snapshot_unhealthy_when_drift_plus_stale_cycle(monkeypatch):
    """drift > 5 min AND cycle_age > 10 min → status=unhealthy."""
    monkeypatch.setattr(
        bm,
        "_pool_snapshot_for_health",
        lambda: {"available": True, "size": 1, "min_healthy": 1},
    )
    monkeypatch.setattr(
        bm, "_load_breaker_snapshot", lambda: {"available": True, "state": "closed"}
    )
    monkeypatch.setattr(
        bm, "_check_xray_listening", lambda: {"listening": True, "port": 10808}
    )
    # cycle_age also triggers existing stale_cycle reason — the 3-reason
    # path to unhealthy. Additionally drift_is_critical sets has_critical.
    monkeypatch.setattr(bm, "_last_cycle_age_seconds", lambda: 700.0)
    monkeypatch.setattr(bm, "_products_mtime_age_seconds", lambda: 60.0)
    monkeypatch.setattr(bm, "_compute_cart_add_block", lambda: (None, None))
    monkeypatch.setattr(
        bm, "_extract_running_xray_hosts_for_health", lambda: {"a"}
    )
    monkeypatch.setattr(bm, "_load_admitted_host_set", lambda: {"b"})
    now = _time.monotonic()
    bm._DRIFT_FIRST_SEEN[frozenset({"a", "b"})] = (now - 320, "2026-05-12T19:00:00")

    snap = bm._build_reliability_snapshot()
    assert snap["status"] == "unhealthy"
    assert "xray_stale_config:2_nodes_drifted" in snap["reasons"]
