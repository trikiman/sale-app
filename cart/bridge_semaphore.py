"""Bridge contention guards for v1.20 Phase 63.

CART_ADD_IN_FLIGHT serializes cart-add vs. scrapers on the shared VLESS bridge.
CART_ITEMS_CACHE_TTL_S bounds the freshness window for cached cart-items returns.

Exports
-------
- CART_ADD_IN_FLIGHT : ``threading.BoundedSemaphore(1)`` guarding the single
  VLESS SOCKS5 bridge. Cart-add holds it for the duration of ``VkusVillCart.add()``;
  scrapers try to acquire with a 10 s timeout before their detail-fetch batch.
- ``cart_add_slot()`` : sync context manager for cart-add.
- ``scraper_slot(name, timeout=...)`` : async context manager for scrapers that
  proceeds anyway on timeout (graceful degradation).
- ``is_pending_cache_fresh(attempt, now_monotonic=None)`` : used by
  ``/api/cart/items`` to decide whether the pending ``_cart_add_attempts``
  record can short-circuit ``basket_recalc.php``.

Events emitted to ``data/proxy_events.jsonl`` (existing v1.19 stream)
-------------------------------------------------------------------
- ``scraper_paused_for_cart_add`` ``{scraper, waited_ms, timed_out}``
- ``cart_items_cache_hit`` ``{user_id_hash, age_ms}``
- ``cart_items_cache_miss`` ``{user_id_hash, reason: "stale" | "no_record" | "no_snapshot"}``

The module is import-side-effect-free apart from binding the semaphore,
so it is safe to import lazily from hot paths (cart endpoints, scrapers).
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# cart/ is a sibling of data/; walk up one directory from this file.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_THIS_DIR)
PROXY_EVENTS_PATH = os.path.join(BASE_DIR, "data", "proxy_events.jsonl")

# SPEC-locked constants from 63-CONTEXT.md.
CART_ITEMS_CACHE_TTL_S: float = 12.0
SCRAPER_BRIDGE_TIMEOUT_S: float = 10.0

# Single global semaphore guarding the shared VLESS bridge. BoundedSemaphore
# so double-release is caught loudly; we also catch ValueError in the release
# path in case a race (e.g. timeout then proceed + concurrent release) slips
# through — being resilient matters more than strict guarding here.
CART_ADD_IN_FLIGHT: threading.BoundedSemaphore = threading.BoundedSemaphore(1)


def _hash_user_id(uid: str) -> str:
    """Short deterministic hash for user_id_hash JSONL fields. 12 hex chars."""
    return hashlib.sha256(str(uid).encode()).hexdigest()[:12]


def _emit_event(event: str, payload: dict) -> None:
    """Append a single JSON line to ``data/proxy_events.jsonl``. Best-effort.

    Never raises. A disk failure here must not block cart-add / scrapers.
    """
    try:
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **payload,
            },
            ensure_ascii=False,
        )
        os.makedirs(os.path.dirname(PROXY_EVENTS_PATH), exist_ok=True)
        with open(PROXY_EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        logger.debug("bridge_semaphore: event emit failed", exc_info=False)


@contextlib.contextmanager
def cart_add_slot():
    """Acquire ``CART_ADD_IN_FLIGHT`` for the duration of the block.

    Blocks if another cart-add is already holding the semaphore. Cart-add is
    the priority holder — scrapers yield to it via the timeout path below.
    """
    acquired = False
    try:
        CART_ADD_IN_FLIGHT.acquire(blocking=True)
        acquired = True
        yield
    finally:
        if acquired:
            try:
                CART_ADD_IN_FLIGHT.release()
            except ValueError:
                # Already released by another path — defensive, shouldn't happen.
                pass


@contextlib.asynccontextmanager
async def scraper_slot(scraper_name: str, timeout: float = SCRAPER_BRIDGE_TIMEOUT_S):
    """Async context manager: try to acquire ``CART_ADD_IN_FLIGHT`` with timeout.

    On acquisition: yield, release on exit.
    On timeout: emit ``scraper_paused_for_cart_add{timed_out: true}`` and yield
    anyway. Graceful degradation — scrapers must never starve completely.

    Usage in a scraper::

        async with scraper_slot("scrape_green"):
            ...detail-fetch batch...

    The bounded ``threading.BoundedSemaphore.acquire(blocking=True, timeout=...)``
    is run via ``asyncio.to_thread`` so the event loop is not blocked while
    waiting.
    """
    start = time.monotonic()
    acquired: bool = await asyncio.to_thread(
        CART_ADD_IN_FLIGHT.acquire, True, timeout
    )
    waited_ms = int((time.monotonic() - start) * 1000)
    _emit_event(
        "scraper_paused_for_cart_add",
        {
            "scraper": scraper_name,
            "waited_ms": waited_ms,
            "timed_out": not acquired,
        },
    )
    try:
        yield
    finally:
        if acquired:
            try:
                CART_ADD_IN_FLIGHT.release()
            except ValueError:
                pass


def is_pending_cache_fresh(
    attempt: dict | None,
    now_monotonic: float | None = None,
) -> bool:
    """True iff ``attempt`` has a recent enough cart snapshot to serve as cache.

    An attempt is "fresh" when it carries a ``last_known_cart_at_monotonic``
    timestamp within ``CART_ITEMS_CACHE_TTL_S`` and a populated
    ``cart_items`` / ``cart_total`` pair (the snapshot proper).

    ``attempt`` is the record stored in ``backend.main._cart_add_attempts``
    (one per ``attempt_id``). Missing record / missing snapshot / stale
    timestamp all return ``False`` so the caller falls through to the normal
    ``basket_recalc.php`` path unchanged.
    """
    if not attempt or not isinstance(attempt, dict):
        return False
    captured = attempt.get("last_known_cart_at_monotonic")
    if captured is None:
        return False
    if attempt.get("cart_items") is None or attempt.get("cart_total") is None:
        return False
    if now_monotonic is None:
        now_monotonic = time.monotonic()
    return (now_monotonic - float(captured)) < CART_ITEMS_CACHE_TTL_S


__all__ = [
    "CART_ADD_IN_FLIGHT",
    "CART_ITEMS_CACHE_TTL_S",
    "SCRAPER_BRIDGE_TIMEOUT_S",
    "PROXY_EVENTS_PATH",
    "cart_add_slot",
    "scraper_slot",
    "is_pending_cache_fresh",
]
