# Phase 74 — Product Details Cold-Path Latency
**Milestone:** v1.23 Detail-Path Performance + UX Polish
**Requirements:** PERF-10, PERF-11
**Started:** 2026-05-13

## Goal

Drop `GET /api/product/{id}/details` cold-path p95 from ~16 s to ≤ 2 s by removing the legacy two-phase probe in `backend/main.py::product_details` and tightening httpx timeouts to match a healthy VLESS bridge profile.

## Problem

Live MCP on https://vkusvillsale.vercel.app/ 2026-05-13:
- First tap on any product card → cache miss → **~16 s before drawer fills**.
- Second tap on the same card → cache hit → **~2 s**.
- User's reaction (verbatim): "one ping it's 30-40 ms what problem why 4 sec I don't get".

The 4s HEAD-probe timeout is the visible delay. Post-v1.15 the whole SOCKS5 pool collapsed into a single xray bridge at `127.0.0.1:10808` (see `vless/manager.py` docstring and `tests/test_vless_manager.py::test_cache_property_exposes_bridge_when_pool_non_empty`). The two-phase probe loop in `product_details`:

```python
# Phase 1: HEAD check to find a live proxy.
for entry in pool:  # pool is a 1-element list: [{addr: "127.0.0.1:10808"}]
    ...
    await client.head("https://vkusvill.ru/", timeout=4s)  # always this exact entry
    ...
# Phase 2: fetch only if Phase 1 succeeded
fetch_attempts = 3 if working_proxy else 0
for attempt in range(fetch_attempts):
    ...
```

…burns 4s up front for a probe against the same bridge that v1.19 pre-flight probe (12s timeout, every 30s via `vless/preflight.py`) and v1.21 reprobe daemon (10-min cadence via `keepalive/reprobe.py`, using `_probe_vkusvill(proxy=REPROBE_BRIDGE_ADDR)`) already guard. If the HEAD hiccups for any reason (TLS flap, momentary xray state change, balancer re-pick on a fresh connection — which xray does per-connection via `observatory`+`leastPing`), `fetch_attempts = 0` and the request short-circuits to fallback with no actual fetch ever attempted.

## Root Cause (Confirmed)

Legacy pre-v1.15 SOCKS5 pool-era artifact. The two-phase probe made sense when `pm._cache["proxies"]` held 8-25 raw residential SOCKS5 endpoints with varying liveness. Post-v1.15 migration (Phase 56) collapsed that behind a single xray bridge — the code survived the migration but the rationale didn't.

Confirmed not a probe-succeeds-but-fetch-fails pattern: logs show `[DETAIL-PROXY] Product X: proxy 127.0.0.1:10808 passed health check` followed by fetch success in 1-3s for the cache-miss case. The 4s is pure HEAD overhead.

## Decision

**Remove Phase 1 entirely.** Go straight to fetch via `127.0.0.1:10808`. Tighten Phase 2 timeouts to match healthy bridge profile. Keep 3 retries so flaky tail fetches recover.

**Timeouts (decision + rationale):**

| Parameter | Before | After | Rationale |
|---|---|---|---|
| `connect` | 4.0s | **1.0s** | Local loopback + healthy bridge: 30-40ms. 1s = 25-33x margin |
| `read` | 6.0s | **3.0s** | VkusVill TTFB healthy: 0.3-1.2s. 3s = 2.5-10x margin |
| `write` | 3.0s | **1.0s** | GET request is tiny; write is instant |
| `pool` | 3.0s | **1.0s** | Fresh client per call, no pool reuse |

Retries stay at **3**. Worst-case if every retry burns the full timeout: `3 × (1+3) = 12s`, still better than the current 4s probe + up-to-3×10s fetch = 34s worst case.

**Ledger design (`data/detail_events.jsonl`):**

One line per `/api/product/{id}/details` call:
```json
{"ts": 1747123456.789, "product_id": "33215", "duration_ms": 1823, "cached": false, "retry_count": 1, "outcome": "ok"}
```

Fields:
- `ts` — `time.time()` at request start
- `product_id` — URL param
- `duration_ms` — total wall-clock for the endpoint (incl. cache check, HTML parse, cache write)
- `cached` — `true` if cache hit, `false` if fetched
- `retry_count` — fetch attempts taken (0 on cache hit, 1-3 on fetch)
- `outcome` — `"ok" | "failed" | "fallback"` (`failed` = exception after all retries; `fallback` = HTML too short / unreadable → `_fallback_product_details`)

Bounded file, same prune pattern as `data/cart_events.jsonl` (v1.20). Tail-readable from admin if needed.

## Non-Goals (Explicit)

- **No change to detail_service.py cache TTL or layout.** Cache behavior unchanged.
- **No background prewarm of top-visible products.** Out of scope per REQUIREMENTS.md — measure PERF-10 alone first.
- **No API surface change.** Endpoint signature + response schema identical.
- **No frontend change.** Phase 75/76 cover that.

## Files Touched

| File | Change |
|---|---|
| `backend/main.py` | Remove Phase 1 probe loop in `product_details`. Tighten Phase 2 timeouts. Add ledger write call. |
| `backend/detail_events.py` (new) | `append_event()` + `prune()` matching `cart_events` pattern. |
| `backend/test_product_details_latency.py` (new, force-add) | Mocks httpx, asserts ledger records happy/cached/failed correctly. |
| `scripts/verify_v1.23.sh` (new) | Smoke script with PERF-10/11 checks. Chains `verify_v1.22.sh all`. |
| `.planning/phases/74-*/74-VERIFICATION.md` | Live MCP + curl measurements, before/after numbers. |

## Plan Order

1. **74-01**: Core fix in `backend/main.py::product_details` — remove probe, tighten timeouts.
2. **74-02**: `backend/detail_events.py` ledger + wire into `product_details` + unit test.
3. **74-03**: `scripts/verify_v1.23.sh` + live MCP verification + 74-VERIFICATION.md.

## Success Criteria (from ROADMAP)

1. [ ] `backend/main.py::product_details` no longer executes the per-proxy HEAD probe loop. Single code path: check cache → fetch via xray bridge → retry up to 3 times.
2. [ ] httpx.Timeout tightened: connect 4.0 → 1.0, read 6.0 → 3.0. Retry loop preserves at 3.
3. [ ] New `data/detail_events.jsonl` ledger: one line per request with `ts, product_id, duration_ms, cached, retry_count, outcome`. Bounded file.
4. [ ] Unit test: `backend/test_product_details_latency.py` mocks httpx and asserts the ledger records the happy path + cached path + failed path correctly.
5. [ ] Live MCP: 5 synthetic cold-path fetches via `curl -w "%{time_total}"` against never-cached product_ids, p95 ≤ 2 s.
6. [ ] v1.22 + v1.21 + v1.20 + v1.19 regression green.
