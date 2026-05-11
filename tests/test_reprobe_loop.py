"""Unit tests for v1.21 Phase 67 — Admitted-Node Self-Healing Loop.

Split across two commits:

* 67-01 (this file's first 4 tests): per-host ``success_rate`` tracking in
  :class:`vless.manager.VlessProxyManager` + dead-node exclusion from
  ``pool_snapshot`` / ``refresh_proxy_list``.
* 67-02 (tests 5-6, appended by the second commit): the
  :mod:`keepalive.reprobe` daemon — re-probe cycle routes failures into the
  existing VkusVill cooldown + the boot-grace window is respected.

Tests reach into module internals (``_outcomes``, ``_run_cycle``,
``REPROBE_BOOT_GRACE_S``, etc.). That's intentional test-only access — the
public surface for callers is ``record_outcome`` / ``success_rate`` /
``iter_admitted_hosts`` / ``start_reprobe_loop``.
"""
from __future__ import annotations

import os
import sys
import threading

import pytest

# Ensure project root on sys.path so `import vless.manager` works under
# `python -m pytest tests/...` from any CWD.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from vless.manager import (  # noqa: E402
    VlessProxyManager,
    SUCCESS_RATE_WINDOW,
    SUCCESS_RATE_MIN_SAMPLES,
    SUCCESS_RATE_DEAD_THRESHOLD,
)


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """Fresh manager with isolated pool/cooldown state.

    Seeds a 2-node pool (``1.2.3.4`` and ``5.6.7.8``) so tests that exercise
    ``pool_snapshot`` and ``iter_admitted_hosts`` see deterministic hosts.
    Bypasses xray config writes via the module-level ``_atomic_write_text``
    monkeypatch — tests never spin up xray.
    """
    pool_path = tmp_path / "vless_pool.json"
    pool_path.write_text(
        '{"nodes": ['
        '{"host": "1.2.3.4", "port": 443, "uuid": "u1", "name": "n1"},'
        '{"host": "5.6.7.8", "port": 443, "uuid": "u2", "name": "n2"}'
        '], "updated_at": "2026-05-12T00:00:00"}',
        encoding="utf-8",
    )
    cooldowns_path = tmp_path / "cooldowns.json"
    cooldowns_path.write_text("{}", encoding="utf-8")
    events_path = tmp_path / "events.jsonl"
    xray_path = tmp_path / "active.json"
    monkeypatch.setattr("vless.manager._atomic_write_text", lambda path, content: None)
    return VlessProxyManager(
        log_func=lambda _msg: None,
        pool_path=pool_path,
        cooldowns_path=cooldowns_path,
        events_path=events_path,
        xray_config_path=xray_path,
        register_atexit=False,
    )


# ---------------------------------------------------------------------------
# 1. FIFO sliding window
# ---------------------------------------------------------------------------
def test_record_outcome_fifo_window(pm):
    """Exactly SUCCESS_RATE_WINDOW=100 samples max, oldest dropped first."""
    for i in range(150):
        pm.record_outcome("1.2.3.4", success=(i % 2 == 0))
    samples = pm._outcomes["1.2.3.4"]
    assert len(samples) == SUCCESS_RATE_WINDOW == 100
    # Last sample should be i=149 (odd -> False)
    assert samples[-1] is False
    # First retained sample should be i=50 (even -> True) — we dropped i=0..49
    assert samples[0] is True


# ---------------------------------------------------------------------------
# 2. Low-sample guard returns None
# ---------------------------------------------------------------------------
def test_success_rate_unknown_below_20_samples(pm):
    for _ in range(SUCCESS_RATE_MIN_SAMPLES - 1):
        pm.record_outcome("1.2.3.4", success=True)
    assert pm.success_rate("1.2.3.4") is None


# ---------------------------------------------------------------------------
# 3. Rate is computed at the threshold
# ---------------------------------------------------------------------------
def test_success_rate_computed_above_20_samples(pm):
    for _ in range(5):
        pm.record_outcome("1.2.3.4", success=True)
    for _ in range(15):
        pm.record_outcome("1.2.3.4", success=False)
    rate = pm.success_rate("1.2.3.4")
    assert rate is not None
    assert abs(rate - 0.25) < 0.001


# ---------------------------------------------------------------------------
# 4. Dead-node exclusion from pool_snapshot
# ---------------------------------------------------------------------------
def test_dead_node_excluded_from_active_outbounds(pm):
    """Node with success_rate < 0.1 (and >= 20 samples) dropped from snapshot."""
    # 20 samples at 5% success -> rate=0.05 < 0.1 -> dead
    for i in range(SUCCESS_RATE_MIN_SAMPLES):
        pm.record_outcome("1.2.3.4", success=(i == 0))
    assert pm.success_rate("1.2.3.4") is not None
    assert pm.success_rate("1.2.3.4") < SUCCESS_RATE_DEAD_THRESHOLD
    # Other node has no samples -> unknown -> alive
    snap = pm.pool_snapshot()
    assert snap["size"] == 2
    assert snap["dead_by_success_rate_count"] == 1
    assert snap["active_outbounds"] == 1  # only 5.6.7.8 is alive
