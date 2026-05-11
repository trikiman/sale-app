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

Measured behavior:
- **Warm path (cached)**: instant return via `detail_service.read_cache`.
- **Cold path (first open)**: 8-15 s typical, up to 22 s worst case.

Latency breakdown in `backend/main.py::product_details`:
1. **Phase 1 HEAD probe loop** (lines ~557-582): for each entry in proxy pool, HEAD vkusvill.ru/ with 4 s connect + 4 s read timeout. Breaks on first success. If 2-3 proxies are slow or dead before a live one, this alone costs 8-12 s.
2. **Phase 2 full fetch** (lines ~590-615): actual `GET <product_url>` via the proxy that passed Phase 1. 4 s connect + 6 s read, up to 3 retries. Typical 4-10 s.

## Root cause

Phase 1 is a **legacy artifact from the pre-v1.15 SOCKS5 pool era**. Back then, proxies could be silently dead, and a per-call HEAD probe was the only way to avoid wasting a 15 s fetch on a dead node.

Starting v1.15 (VLESS+Reality via xray bridge) and hardened in v1.17/v1.19/v1.21, the pool is continuously self-healed:
- v1.17 REL: xray `observatory` + `leastPing` picks the fastest live outbound automatically.
- v1.19 REL-11: pre-flight probe already ensures the bridge is reachable.
- v1.21 REL-13: reprobe daemon every 10 min keeps admitted nodes alive.
- v1.21 REL-15: per-node `success_rate` tracks production-traffic health.
- v1.21 REL-14: xray auto-reload on admission diff keeps config fresh.

So by the time `product_details` runs Phase 1, xray's leastPing has already picked the fastest live outbound. The Python-side Phase 1 probe is doing work the bridge already did — at a 4-12 s cost.

## Solution

**Option A — Remove Phase 1 entirely (recommended):**
- Go straight to Phase 2 fetch via `127.0.0.1:10808` (the local xray bridge address). No per-proxy probe.
- Keep the retry loop (3 attempts) so a flaky fetch still recovers.
- Expected cold-path latency: 1-3 s (single healthy fetch).
- Risk: if xray IS broken, we waste one full retry cycle (~12 s) instead of the probe's 4 s. But v1.21 `/api/health/deep` already catches that state and the scheduler's reprobe daemon re-heals within 10 min. Acceptable tradeoff.

**Option B — Background pre-warm (additional, not alternative):**
- When the main page renders, kick a low-priority background task to pre-fetch the top N visible products' details into the cache.
- Similar to v1.20 Phase 62 warmup daemon pattern.
- User opens a product → cache hit → instant render.
- Cost: 2-5 concurrent bridge fetches per main-page render. Shouldn't overwhelm the pool.

**Ship Option A first**, then measure. If cold-path p95 stays above ~3 s even after removing Phase 1, add Option B.

## Acceptance

- [ ] `backend/main.py::product_details` no longer runs a per-proxy HEAD probe loop.
- [ ] Cold-path p95 ≤ 3 s measured over 20+ synthetic opens of never-before-seen products.
- [ ] Warm-path still instant (cache unchanged).
- [ ] No regression on `/api/product/{id}/details` error rate.
- [ ] `data/cart_events.jsonl` or a new `details_events.jsonl` ledger captures duration_ms for observability (optional but recommended for calibration).

## Candidate for

v1.23 — fits naturally alongside other v1.20/v1.21 reliability-polish items. Scope: ~40 LOC backend change + a simple latency ledger + live MCP measurement.
