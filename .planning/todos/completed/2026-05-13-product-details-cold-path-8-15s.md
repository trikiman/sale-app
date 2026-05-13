---
created: 2026-05-13T01:00:00Z
title: Product details cold-path open takes 8-15 seconds
area: api
priority: P2
files:
  - backend/main.py:525 (product_details endpoint)
  - backend/detail_service.py:229 (read_cache — works, but only on warm path)
---

## Problem

Opening a product card in the MiniApp takes 8-15 seconds on the first open (cold path). Subsequent opens of the same product are instant (24h cache in `detail_service`). User reported latency observed 2026-05-13 on production Vercel build against live backend.

**Measured live 2026-05-13:**
- **Cold path (first card open)**: ~16 s.
- **Warm path (same card reopened)**: ~2 s.

User question: "one ping is 30-40 ms, what problem, why 4 sec, i don't get it." Correct observation. Healthy VLESS bridge through xray is ~330 ms overhead + ~40 ms ping = fetch should be ~500 ms, not 4 s.

## Root cause + over-conservative timeouts

Latency breakdown in `backend/main.py::product_details`:
1. **Phase 1 HEAD probe loop** (~557-582): for each entry in proxy pool, HEAD vkusvill.ru/ with **4 s connect + 4 s read timeout**. Breaks on first success. If 2-3 proxies are slow or dead before a live one, this alone costs 8-12 s.
2. **Phase 2 full fetch** (~590-615): actual `GET <product_url>` via the proxy that passed Phase 1. **4 s connect + 6 s read**, up to 3 retries. Typical 4-10 s.

The 4 s timeout is a **legacy artifact from pre-v1.15 SOCKS5 pool era**. Back then, proxies could be silently dead and 4 s was the floor for a TCP handshake over flaky Russian residential SOCKS5 paths. With v1.21 VLESS+Reality via xray bridge:
- Healthy ping through bridge: 30-50 ms.
- Full HTTP round-trip to vkusvill.ru: 300-600 ms p50, 1-2 s p95.
- A 4 s budget is 10x what a healthy request needs.

Meanwhile, Phase 1 is **redundant** entirely because:
- v1.17 xray `observatory` + `leastPing` already picks the fastest live outbound.
- v1.19 pre-flight probe already catches broken bridge state.
- v1.21 reprobe daemon + success_rate tracking keeps admitted pool alive.
- v1.21 auto-reload ensures xray config matches admitted set.

By the time `product_details` runs Phase 1, xray's leastPing has already picked the fastest live outbound. The Python-side probe is doing work the bridge already did — at a 4-12 s cost per cold open.

## Solution

**Option A — Remove Phase 1 entirely + tighten Phase 2 timeouts (recommended):**
- Delete the per-proxy HEAD probe loop.
- Go straight to the local xray bridge (`127.0.0.1:10808`) for the fetch.
- Tighten connect timeout: 4 s → **1 s** (10x safety margin over healthy 30-50 ms ping).
- Tighten read timeout: 6 s → **3 s** (5x safety margin over healthy 500-1000 ms full round-trip).
- Keep 3 retries so a flaky tail fetch still recovers.
- Expected cold-path latency: **500 ms - 1.5 s** (single healthy fetch).
- Risk: if xray IS broken, we waste 3 × 3 s = 9 s on retries instead of the probe's 4 s. But v1.21 `/api/health/deep` already catches that state. Acceptable tradeoff.

**Option B — Background pre-warm (additional, not alternative):**
- When main page renders, kick a low-priority background task to pre-fetch the top N visible products' details into the cache.
- Similar to v1.20 Phase 62 warmup daemon pattern.
- User taps product → cache hit → instant render.
- Cost: 2-5 concurrent bridge fetches per main-page render. Shouldn't overwhelm the pool.

**Ship Option A first** — ~30 LOC change, immediate impact. Then measure. If cold-path p95 stays above ~2 s, add Option B.

## Acceptance

- [ ] `backend/main.py::product_details` no longer runs the per-proxy HEAD probe loop.
- [ ] `httpx.Timeout` for the detail fetch: connect 1 s, read 3 s (retained 3 retries).
- [ ] Cold-path p95 ≤ 2 s measured over 20+ synthetic opens of never-before-seen products.
- [ ] Warm-path still instant (cache unchanged).
- [ ] No regression on `/api/product/{id}/details` error rate.
- [ ] `data/cart_events.jsonl` or a new `details_events.jsonl` ledger captures duration_ms for observability (optional but recommended for calibration).

## Candidate for

v1.23 — fits naturally alongside other v1.20/v1.21 reliability-polish items. Scope: ~30 LOC backend change + a simple latency ledger + live MCP measurement before/after.
