# Phase 62 Discussion Log

**Date:** 2026-05-05
**Phase:** 62 — Sessid Keep-Alive + On-App-Open Warmup
**Workflow:** `/gsd-discuss-phase 62`

## Pre-decided (locked by REQUIREMENTS.md / ROADMAP.md, not discussed)

- Warmup endpoint = `GET /personal/`
- 20-min cycle; ≤ 1/user/15 min anti-spam ceiling
- Warmup p95 budget ≤ 3 s; cart-add p95 target ≤ 6 s after Phase 62
- `data/warmup_events.jsonl` for metrics
- Pool gating via `pool_snapshot()` from Phase 61
- No regression on v1.19 (24/24 smoke must stay green)

## Gray areas surveyed

Cascade presented 4 implementation choices with tradeoff analysis:

1. **Activity signal** (who gets warmed): warm-all vs activity-tracked vs file-mtime
2. **Failure handling** (silent retry vs mark stale vs Telegram alert)
3. **Concurrency model** (daemon thread vs separate systemd unit vs FastAPI async)
4. **On-app-open vs in-flight cart-add race** (independent vs wait vs cancel)

## User direction

> "idk i need fastest way and on the same side robust but robust in prioritize if it didnt cost too much delays"

Interpretation: ship simplest implementation; choose robustness only when it adds negligible code/runtime cost. User explicitly delegated decisions back to Cascade.

## Decisions captured

| # | Topic | Choice | Rationale |
|---|---|---|---|
| D1 | Activity signal | Warm ALL linked users every 20 min | 5 users × 3/h = 15 pings/h to VkusVill — trivial load. Zero new tracking infra. Every user always warm = robust by construction. |
| D2 | Failure handling | Silent log + JSONL + retry next cycle. NO inline-stale-mark, NO Telegram alerts. | Avoids cascade where one transient blip forces inline refresh on EVERY cart-add. Alerting deferred to v1.21 OPS-FUT. |
| D3 | Concurrency | Daemon thread in `scheduler_service.py`, new module `keepalive/warmup.py`. | Matches existing `_watchdog_loop` pattern. Same process, same logs, same systemd unit. Direct `pool_snapshot()` access. |
| D4 | Race vs cart-add | Cart-add cancels in-flight warmup for that user (best-effort). | Cart-add IS a session validation; double-firing wastes a VkusVill round-trip. Implementation: per-user `cart_add_active` flag, warmup checks before sending. |

## Locked defaults (no discussion needed)

- HTTP client: same `httpx.Client` and proxy config as `cart/vkusvill_api.py` today
- User discovery: union of `data/user_cookies/*.json` filenames + `data/auth/user_phone_map.json` values
- JSONL rotation: 10 MB → `.1` (matches `proxy_events.jsonl` pattern)
- User_id privacy: `sha256(user_id)[:12]` (same as Phase 66 will use)
- Skip-unhealthy threshold: `quarantined_count ≥ pool_size/2` OR `xray_listening = false` OR `breaker.state = "open"`
- Boot delay: 60 s grace before first cycle (lets breaker + watchdog stabilize)
- Shutdown: thread checks `stop_event.is_set()` between user iterations, exits ≤ 5 s after SIGTERM

## Deferred ideas (preserved for later)

- **Telegram alert on N consecutive warmup failures per user** → v1.21 OPS-FUT
- **Per-user warmup interval tuning** (some users 10-min, others 30-min) → v1.21 PERF-FUT
- **Warmup endpoint A/B comparison** (`/personal/` vs `HEAD /` vs custom) → revisit only if Phase 62 verification shows `/personal/` is insufficient

## Scope boundary

Phase 62 ships ONLY the keep-alive daemon thread + on-app-open nudge mechanism + JSONL metrics + smoke gate. It does NOT ship:
- `basket_recalc.php` skipping (Phase 63)
- Scraper semaphore freeing the bridge (Phase 63)
- Lighter VkusVill cart endpoint exploration (Phase 64)
- Frontend AbortController + pending-polling (Phase 65)
- `/api/health/deep` `cart_add` block (Phase 66)

## Acceptance gate

5 smoke checks green, EC2 cart-add p95 ≤ 6 s on warm sessid path, zero v1.19 regressions, rollback rehearsed.
