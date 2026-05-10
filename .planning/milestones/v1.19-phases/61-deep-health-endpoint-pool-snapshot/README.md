# Phase 61 — Deep Health Endpoint + Pool Snapshot

**Milestone:** v1.19 Production Reliability & 24/7 Uptime
**Status:** Planned — executing autonomously after Phases 59 + 60 shipped
**Depends on:** Phase 60 (breaker state file is part of the health response)
**Requirements:** REL-11, REL-12, OBS-01, OBS-02, OBS-03 + continued OPS-06/07/08

## User intent (verbatim)

> "robust solution" — applied to the "is the stack actually working right now?" question. Current `/admin/status` is authed, so external uptime monitors (UptimeRobot, BetterStack, etc.) can't see when the stack is "active but broken." Phase 61 fixes that.

## What Phase 61 delivers

1. **`VlessProxyManager.pool_snapshot()`** — typed dict with `{size, min_healthy, quarantined_count, active_outbounds, last_refresh_at}`. Single accessor used by both the new health endpoint and the extended admin view. (REL-12, OBS-03)

2. **`proxy_events.jsonl` enrichment** — every event auto-includes `pool_size`, `quarantined_count`, `active_outbounds_count` so multi-day pool drift (e.g. v1.18's 25 → 13 drift) is visible by querying the file alone, without cross-referencing state. (OBS-02)

3. **`GET /api/health/deep`** — unauthed, rate-limited 1 req/s/IP, returns:
   - HTTP **200** + JSON when healthy
   - HTTP **503** + JSON when degraded (reasons[] explains why)
   - Shape:
     ```json
     {
       "status": "healthy" | "degraded" | "down",
       "reasons": ["pool_below_min", "breaker_open", ...],
       "pool": {size, min_healthy, quarantined_count, active_outbounds, last_refresh_at},
       "breaker": {state, cooldown_s, fails},
       "xray": {listening: bool, port: int},
       "last_cycle_age_s": int
     }
     ```
   - Degraded criteria (any): pool < `MIN_HEALTHY`, breaker not `closed`, xray not listening, last cycle > 15 min old. (REL-11, OBS-01)

4. **`/admin/status` extension** — add a `reliability` block with the same shape as `/api/health/deep` (minus rate limiting, which is unnecessary for authenticated ops view). (OBS-03)

5. **Smoke script Phase 61 block** — external curl from local machine (non-EC2 origin) to `https://vkusvillsale.vercel.app/api/health/deep`. Expect HTTP 200 when healthy. (OPS-07)

## Scope boundary

- No change to scheduler loop (Phase 60 owns that).
- No change to xray config (Phase 60 owns probeURL).
- No change to `vless/preflight.py` (Phase 59 owns pre-flight probe).
- No new metrics pipeline (Prometheus / Grafana) — out of scope for v1.19.
- Rate limit is 1 req/s/IP — basic DDoS mitigation; not bulletproof.

## Files touched

| File | Change |
|---|---|
| `@/Users/ProsalovP/Desktop/projects/sale-app/vless/manager.py` | Add `pool_snapshot()` method + inject pool counts into `_track_event` |
| `@/Users/ProsalovP/Desktop/projects/sale-app/backend/main.py` | New route `/api/health/deep` + extend `/admin/status` with `reliability` block + rate-limit state dict |
| `@/Users/ProsalovP/Desktop/projects/sale-app/tests/test_pool_snapshot.py` | NEW (≈6 tests) |
| `@/Users/ProsalovP/Desktop/projects/sale-app/tests/test_health_deep_endpoint.py` | NEW (≈8 tests via FastAPI TestClient; may skip locally if fastapi missing) |
| `@/Users/ProsalovP/Desktop/projects/sale-app/scripts/verify_v1.19.sh` | Append Phase 61 block (61-A..61-E) |
| `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/61-deep-health-endpoint-pool-snapshot/61-VERIFICATION.md` | NEW |
| `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/STATE.md` | Progress update to 3/3 phases shipped |

## Risk register

| Risk | Mitigation |
|---|---|
| Unauthed endpoint → resource abuse / info leak | 1 req/s/IP rate limit in-memory (matches existing `_client_log_counts` pattern); no secrets in response; only health info already visible to any authenticated admin |
| Pool snapshot racing with mid-refresh writes | `pool_snapshot()` takes the same `self._lock` as mutations; atomic read of pool dict |
| Event-file enrichment breaks existing `get_event_stats` aggregation | New fields are additive; `get_event_stats` only reads specific fields via `.get(...)` so unknown new fields are harmless |
| Vercel edge caching the deep-health response | Response includes `Cache-Control: no-store`; endpoint explicitly marked `include_in_schema=True` but not cached |
| Backend restart loses rate-limit state (clients get temporary free pass) | Acceptable — 1 req/s/IP is ddos-mitigation, not authorization; backend restarts are infrequent enough this is negligible |

## Rollback

Same pattern as Phase 60: `git revert <feat-commit>` on EC2. Backend restart required because FastAPI routes are defined at module load. No xray or scheduler restart needed.

## Plans

- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/61-deep-health-endpoint-pool-snapshot/61-01-PLAN.md` — `pool_snapshot()` + event enrichment + `/api/health/deep` + `/admin/status` extension
- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/61-deep-health-endpoint-pool-snapshot/61-02-PLAN.md` — tests (pool_snapshot + health endpoint)
- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/61-deep-health-endpoint-pool-snapshot/61-03-PLAN.md` — smoke script extension + external curl + deploy + VERIFICATION.md + milestone prep

## Milestone closeout

After Phase 61 ships, the v1.19 milestone is **complete**. Next step: `/gsd-audit-milestone v1.19` to verify all 18 requirements are covered, then milestone archive + start v1.20.
