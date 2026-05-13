# Phase 63 — Bridge Contention Elimination — Context

**Milestone:** v1.20 Cart-Add Latency & User-Facing Responsiveness
**Phase number:** 63
**Phase slug:** bridge-contention-elimination
**Date captured:** 2026-05-10
**Requirements covered:** PERF-06, PERF-07 + continuing OPS-09/10/11

---

## Domain

Remove the ~5 s of self-inflicted latency that cart-add pays when our own other traffic is fighting it on the VLESS bridge:

1. **PERF-06** — Stale-read cart-items cache during pending cart-add. When `/api/cart/add` is in flight for user X, a subsequent `/api/cart/items` call for the same user must NOT trigger a parallel `basket_recalc.php` (which fights the same VkusVill DB row lock). Return cached state from the pending attempt record instead.
2. **PERF-07** — Pause detail scrapers during cart-add. `scrape_green` / `scrape_red` / `scrape_yellow` detail-page fetches compete with the cart-add for the single VLESS SOCKS5 bridge on 127.0.0.1:10808. A global semaphore makes them yield until the cart-add finishes (or the 10 s timeout lapses).

Together these drop the 2-3 s bridge-contention + 2-3 s DB-lock-contention from the cart-add slow path. OPS-10 gate is p95 ≤ 4.5 s.

---

## SPEC Lock (from REQUIREMENTS.md PERF-06/07 and ROADMAP.md)

LOCKED — planner must NOT re-litigate:

- **PERF-06 freshness window:** 12 seconds. If the pending attempt record is older than 12 s, treat as stale and fall through to the normal `basket_recalc.php` path.
- **PERF-06 cache source:** `_cart_pending_attempts[user_id]` (existing dict managed by `/api/cart/add`). No new data structure.
- **PERF-07 semaphore:** single global `threading.BoundedSemaphore(1)` guarding "a cart-add is in flight anywhere in the process". Not per-user. The bridge is the contended resource.
- **PERF-07 semaphore timeout:** 10 seconds max wait in scrapers before proceeding anyway. Prevents scraper starvation.
- **PERF-07 module:** new `cart/bridge_semaphore.py` exporting `CART_ADD_IN_FLIGHT: threading.BoundedSemaphore(1)` + helpers. `cart/vkusvill_api.py::add()` acquires; scrapers acquire with timeout via `asyncio.to_thread`.
- **PERF-07 metric:** emit events to existing `data/proxy_events.jsonl`. New types: `cart_items_cache_hit`, `cart_items_cache_miss`, `scraper_paused_for_cart_add`.
- **OPS-09 smoke:** 4 new checks (63-A..63-D) in `scripts/verify_v1.20.sh`.
- **OPS-10 regression gate:** cart-add p95 ≤ 4.5 s on EC2 with Phase 62+63 active, 50 samples, during active scraper window.
- **OPS-11 rollback rehearsal:** mandatory before merge.

---

## Decisions

### D1. Cache hit criteria for PERF-06

- Cache hit if `_cart_pending_attempts[user_id]` exists AND was created within 12 s AND has a `last_known_cart` snapshot.
- Cache miss → fall through to existing `basket_recalc.php` path unchanged.
- Response includes `from_cache: true` flag (needed by Phase 66 OBS-05 later; added now to avoid re-touching response shape).

### D2. Pending attempt record lifecycle

`_cart_pending_attempts[user_id]` already exists. This phase adds ONE field: `last_known_cart: {items: list, total: float, captured_at_monotonic: float}` — populated on cart-add SUCCESS with the server-acknowledged post-add state. Backwards compatible.

### D3. Semaphore primitive

`threading.BoundedSemaphore(1)` (sync-friendly) rather than `asyncio.Semaphore`. Cart-add acquires in its existing sync context. Async scrapers use `await asyncio.to_thread(sem.acquire, timeout=10)` pattern — non-blocking from event loop perspective.

### D4. Scraper callsite integration

Semaphore acquire goes immediately BEFORE the batch of detail-page fetches (not around the full scrape cycle). On 10 s timeout, scraper proceeds anyway (graceful degradation). Waited/timeout metric emitted to `proxy_events.jsonl` regardless.

---

## Locked Defaults

- Cache key: string `user_id`.
- `CART_ITEMS_CACHE_TTL_S = 12.0` in `cart/bridge_semaphore.py`.
- `SCRAPER_BRIDGE_TIMEOUT_S = 10.0` same module.
- JSONL stream: reuse `data/proxy_events.jsonl`.
- Missing `last_known_cart` → no cache hit (pre-63 behavior).

---

## Files Modified

- `cart/bridge_semaphore.py` — NEW ~80 LOC (semaphore + TTL + context managers + JSONL helper)
- `cart/vkusvill_api.py::add()` — +8 lines (acquire around body + write `last_known_cart` on success)
- `backend/main.py::cart_items_endpoint` — +18 lines (cache check + JSONL emit)
- `scrape_green.py` — +3 lines (scraper_slot acquire before detail-fetch batch)
- `scrape_red.py` — +3 lines
- `scrape_yellow.py` — +3 lines
- `tests/test_bridge_semaphore.py` — NEW 5 tests
- `scripts/verify_v1.20.sh` — +40 lines (63-A..63-D checks)

---

## Verification

- Local: 5 new pytest cases pass, full suite green, smoke script syntax OK, imports clean.
- EC2 (operator, 63-03): 50 synthetic cart-adds during active scraper window → p95 ≤ 4.5 s AND ≤ Phase 62 baseline +500 ms. 63-A..63-D smoke 4/4. v1.19 regression 24/24. Rollback rehearsed.

---

## Phase Boundary

**Ships:** cart-items 12 s cache + bridge semaphore + 5 unit tests + 4 smoke checks + JSONL metrics.

**Does NOT ship:** `basket_add.php` payload changes (Phase 64), frontend polling (Phase 65), `/api/health/deep` new fields (Phase 66), warmup daemon changes (Phase 62 already live).

**Acceptance gate:** p95 ≤ 4.5 s during active scraper window + 4/4 Phase-63 smoke + 24/24 v1.19 + rollback rehearsed.
