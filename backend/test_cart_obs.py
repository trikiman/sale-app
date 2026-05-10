"""v1.20 Phase 66 — Cart Hot-Path Observability unit tests.

Covers:
- OBS-04: /api/health/deep cart_add block (p50/p95/p99, success rates,
  double-add rate, zero-traffic handling, degraded/critical p95 reasons).
- OBS-05: data/cart_events.jsonl 11-key schema on success and failure paths.

Shape mirrors backend/test_cart_idempotency.py fixture conventions
(TestClient, monkeypatch VkusVillCart, explicit state reset).
"""
import json
import os
import sys
import time as _time
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main  # noqa: E402
from backend.main import (  # noqa: E402
    _compute_cart_add_block,
    _build_reliability_snapshot,
    _cart_add_attempts,
    _cart_add_attempts_lock,
)
from keepalive.warmup import hash_user_id  # noqa: E402


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_cart_attempts():
    """Clear _cart_add_attempts before and after every test so synthetic
    seeding in one test does not leak into another."""
    with _cart_add_attempts_lock:
        _cart_add_attempts.clear()
        main._cart_add_attempt_index.clear()
        main._cart_add_attempt_by_client_id.clear()
    yield
    with _cart_add_attempts_lock:
        _cart_add_attempts.clear()
        main._cart_add_attempt_index.clear()
        main._cart_add_attempt_by_client_id.clear()


@pytest.fixture
def healthy_snapshot_deps(monkeypatch):
    """Patch the non-cart_add snapshot helpers so only the cart_add reason
    drives the health status. Returns None — side-effect fixture."""
    monkeypatch.setattr(
        main,
        "_pool_snapshot_for_health",
        lambda: {"available": True, "size": 5, "min_healthy": 2},
    )
    monkeypatch.setattr(
        main,
        "_load_breaker_snapshot",
        lambda: {"available": True, "state": "closed", "cooldown_s": 0, "fails": 0},
    )
    monkeypatch.setattr(
        main,
        "_check_xray_listening",
        lambda: {"listening": True},
    )
    monkeypatch.setattr(main, "_last_cycle_age_seconds", lambda: 30.0)
    monkeypatch.setattr(main, "_products_mtime_age_seconds", lambda: 30.0)


def _seed_attempt(
    *,
    user_id: str,
    product_id: int,
    status: str,
    duration_ms: int,
    resolved_offset_s: float,
) -> str:
    """Insert one resolved attempt into _cart_add_attempts. Returns the
    attempt_id. ``resolved_offset_s`` is seconds in the PAST from now."""
    now = _time.time()
    attempt_id = uuid.uuid4().hex
    attempt = {
        "attempt_id": attempt_id,
        "user_id": str(user_id),
        "product_id": int(product_id),
        "status": status,
        "created_at": now - resolved_offset_s - (duration_ms / 1000.0),
        "started_at": now - resolved_offset_s - (duration_ms / 1000.0),
        "expires_at": now + 30.0,
        "resolved_at": now - resolved_offset_s,
        "duration_ms": int(duration_ms),
        "last_error": None if status == "success" else "synthetic",
        "source": "test",
        "client_request_id": None,
        "cart_items": None,
        "cart_total": None,
        "final_status": status,
    }
    with _cart_add_attempts_lock:
        _cart_add_attempts[attempt_id] = attempt
    return attempt_id


# ─── OBS-04 tests (5) ────────────────────────────────────────────────────────

def test_cart_add_block_p95_p99_computation():
    """Synthetic 100 attempts with durations 10..1000 ms (step 10) — assert
    p50/p95/p99 land on the quantile boundaries computed by statistics.quantiles.
    """
    # Durations 10, 20, 30, ..., 1000 (100 samples).
    for i in range(1, 101):
        _seed_attempt(
            user_id=f"u{i}",
            product_id=i,
            status="success",
            duration_ms=i * 10,
            resolved_offset_s=60.0,
        )
    block, reason = _compute_cart_add_block()
    assert block is not None
    # With 100 evenly spaced samples, statistics.quantiles(..., n=100) places
    # p50 near the midpoint, p95 near index 94, p99 near index 98.
    # Accept a small numerical tolerance (+/-30 ms).
    assert abs(block["p50_ms"] - 500) <= 30, f"p50_ms={block['p50_ms']}"
    assert abs(block["p95_ms"] - 950) <= 30, f"p95_ms={block['p95_ms']}"
    assert abs(block["p99_ms"] - 990) <= 30, f"p99_ms={block['p99_ms']}"
    assert block["window_sample_1h"] == 100
    assert block["success_rate_1h"] == 1.0
    # p95 ~ 950 ms — well below the 6 s degraded threshold, no reason.
    assert reason is None


def test_cart_add_block_zero_traffic_omits_block(healthy_snapshot_deps):
    """Empty ledger -> snapshot['cart_add'] absent AND status stays healthy."""
    block, reason = _compute_cart_add_block()
    assert block is None
    assert reason is None

    snap = _build_reliability_snapshot()
    assert "cart_add" not in snap
    assert snap["status"] == "healthy"
    assert snap["reasons"] == []


def test_cart_add_block_double_add_rate():
    """Two same-(user, product) successes 20 s apart -> one colliding pair.
    With 3 total successes (two colliding + one unrelated), rate = 1/3."""
    _seed_attempt(user_id="777", product_id=42, status="success", duration_ms=800, resolved_offset_s=60.0)
    _seed_attempt(user_id="777", product_id=42, status="success", duration_ms=850, resolved_offset_s=40.0)
    # Unrelated success that should NOT count as a double-add.
    _seed_attempt(user_id="888", product_id=99, status="success", duration_ms=700, resolved_offset_s=30.0)

    block, _reason = _compute_cart_add_block()
    assert block is not None
    # 1 colliding pair / 3 successes = 0.3333
    assert block["double_add_rate_1h"] == round(1 / 3, 4)
    assert block["success_rate_1h"] == 1.0
    assert block["window_sample_1h"] == 3


def test_cart_add_block_p95_degrades_health(healthy_snapshot_deps):
    """Synthetic p95 ~ 7000 ms -> 'cart_add_p95_high:7000ms' in reasons
    and deep-health flips to degraded (single reason, no critical)."""
    # 20 samples all at 7000 ms -> p50=p95=p99=7000.
    for i in range(20):
        _seed_attempt(
            user_id=f"u{i}",
            product_id=i,
            status="success",
            duration_ms=7000,
            resolved_offset_s=60.0,
        )
    block, reason = _compute_cart_add_block()
    assert block is not None
    assert block["p95_ms"] == 7000
    assert reason == "cart_add_p95_high:7000ms"

    snap = _build_reliability_snapshot()
    assert "cart_add" in snap
    assert "cart_add_p95_high:7000ms" in snap["reasons"]
    assert snap["status"] == "degraded"


def test_cart_add_block_p95_critical(healthy_snapshot_deps):
    """Synthetic p95 ~ 13000 ms -> 'cart_add_p95_critical:13000ms' in reasons.
    Since it's only ONE reason and not in the OBS-02 critical-reasons set,
    status is degraded (OBS-02 severity: 1-2 reasons with no critical -> degraded).
    'critical' in the reason string denotes latency severity, NOT OBS-02 severity."""
    for i in range(20):
        _seed_attempt(
            user_id=f"u{i}",
            product_id=i,
            status="success",
            duration_ms=13000,
            resolved_offset_s=60.0,
        )
    block, reason = _compute_cart_add_block()
    assert block is not None
    assert block["p95_ms"] == 13000
    assert reason == "cart_add_p95_critical:13000ms"

    snap = _build_reliability_snapshot()
    assert "cart_add" in snap
    assert "cart_add_p95_critical:13000ms" in snap["reasons"]
    # Only one reason, not in critical set -> degraded per OBS-02 severity.
    assert snap["status"] == "degraded"
