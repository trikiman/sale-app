"""Unit tests for cart.bridge_semaphore (Phase 63).

Covers:
  - cart_add_slot context manager acquires/releases
  - scraper_slot waits for an in-flight cart-add then acquires
  - scraper_slot times out gracefully and proceeds on timeout
  - is_pending_cache_fresh: within/outside 12 s window, missing snapshot,
    missing record

These reach into module internals (_emit_event, CART_ADD_IN_FLIGHT). That is
intentional - the contract is low-level.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time

import pytest

# Ensure project root is on sys.path so `from cart import ...` works under
# `python -m pytest tests/...` from any CWD.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from cart import bridge_semaphore as bs  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_semaphore(tmp_path, monkeypatch):
    """Point events file into tmp_path and install a fresh BoundedSemaphore
    before each test so acquire/release state can't leak between tests."""
    monkeypatch.setattr(
        bs, "PROXY_EVENTS_PATH", str(tmp_path / "proxy_events.jsonl")
    )
    # Replace the module-level semaphore with a fresh one. Helpers look up
    # CART_ADD_IN_FLIGHT via module-global resolution, so this swap takes
    # effect immediately.
    monkeypatch.setattr(bs, "CART_ADD_IN_FLIGHT", threading.BoundedSemaphore(1))
    yield


# ---------------------------------------------------------------------------
# 1. cart_add_slot acquires then releases
# ---------------------------------------------------------------------------
def test_cart_add_slot_acquires_and_releases():
    # Initially not held - a non-blocking acquire should succeed.
    assert bs.CART_ADD_IN_FLIGHT.acquire(blocking=False) is True
    bs.CART_ADD_IN_FLIGHT.release()

    with bs.cart_add_slot():
        # Slot held: a concurrent non-blocking acquire must fail.
        assert bs.CART_ADD_IN_FLIGHT.acquire(blocking=False) is False

    # Slot released after context exit - should be acquirable again.
    assert bs.CART_ADD_IN_FLIGHT.acquire(blocking=False) is True
    bs.CART_ADD_IN_FLIGHT.release()


# ---------------------------------------------------------------------------
# 2. scraper_slot waits for an in-flight holder, then acquires
# ---------------------------------------------------------------------------
def test_scraper_slot_waits_then_acquires():
    hold_duration_s = 0.3

    async def run():
        holder_released = threading.Event()

        def _hold():
            bs.CART_ADD_IN_FLIGHT.acquire(blocking=True)
            time.sleep(hold_duration_s)
            bs.CART_ADD_IN_FLIGHT.release()
            holder_released.set()

        holder = threading.Thread(target=_hold, daemon=True)
        holder.start()
        # Give the holder a moment to acquire the semaphore.
        await asyncio.sleep(0.05)
        start = time.monotonic()
        async with bs.scraper_slot("scrape_test_wait", timeout=2.0):
            # Reached here only after holder released.
            pass
        elapsed = time.monotonic() - start
        holder.join(timeout=1.0)
        assert holder_released.is_set()
        return elapsed

    elapsed = asyncio.run(run())
    # Should have waited at least the remaining hold window, well under the
    # timeout budget.
    assert 0.15 <= elapsed <= 1.5, f"elapsed={elapsed}"


# ---------------------------------------------------------------------------
# 3. scraper_slot times out and proceeds anyway (graceful degradation)
# ---------------------------------------------------------------------------
def test_scraper_slot_timeout_then_proceeds():
    async def run():
        # Acquire in main thread and never release within the timeout.
        bs.CART_ADD_IN_FLIGHT.acquire(blocking=True)
        try:
            start = time.monotonic()
            proceeded = False
            async with bs.scraper_slot("scrape_timeout", timeout=0.3):
                proceeded = True
            elapsed = time.monotonic() - start
            return elapsed, proceeded
        finally:
            bs.CART_ADD_IN_FLIGHT.release()

    elapsed, proceeded = asyncio.run(run())
    assert proceeded is True, "scraper_slot should yield even on timeout"
    # Timeout configured to 0.3 s. Allow broad tolerance for scheduler jitter.
    assert 0.2 <= elapsed <= 2.0, f"elapsed={elapsed}"


# ---------------------------------------------------------------------------
# 4-7. is_pending_cache_fresh truth table
# ---------------------------------------------------------------------------
def test_is_pending_cache_fresh_within_12s():
    now = time.monotonic()
    record = {
        "cart_items": 3,
        "cart_total": 450,
        "last_known_cart_at_monotonic": now - 10.0,
    }
    assert bs.is_pending_cache_fresh(record, now) is True


def test_is_pending_cache_fresh_stale_at_12_1s():
    now = time.monotonic()
    record = {
        "cart_items": 3,
        "cart_total": 450,
        "last_known_cart_at_monotonic": now - 12.1,
    }
    assert bs.is_pending_cache_fresh(record, now) is False


def test_is_pending_cache_fresh_missing_snapshot():
    now = time.monotonic()
    # Snapshot timestamp present but cart_items/cart_total missing - treat as
    # not-fresh so caller falls through to basket_recalc.
    record = {
        "cart_items": None,
        "cart_total": None,
        "last_known_cart_at_monotonic": now - 1.0,
    }
    assert bs.is_pending_cache_fresh(record, now) is False


def test_is_pending_cache_fresh_no_record():
    assert bs.is_pending_cache_fresh(None) is False
    assert bs.is_pending_cache_fresh({}) is False
    # Record has snapshot but no timestamp - treat as not-fresh.
    assert bs.is_pending_cache_fresh({"cart_items": 1, "cart_total": 100}) is False
