# Requirements — v1.20 Cart-Add Latency & User-Facing Responsiveness

## Milestone Goal

Cut end-to-end cart-add latency from the current 3–12 s envelope to a 2–4 s envelope through backend-side optimization, and prevent the false-fail-then-double-add UX pattern that appears whenever VkusVill's server takes >8 s. Ship with the same robust-over-fast discipline that v1.19 established (per-phase EC2 smoke + VERIFICATION.md + rehearsed rollback).

Driving evidence (2026-05-05, live user UAT):
- First cart-add attempt took 10.8 s, returned HTTP 200 success, but frontend aborted at 8 s and showed "fail" toast
- User retried → second attempt succeeded in 3.6 s
- **Net effect: double-added product (0.7 kg onion instead of 0.35 kg)**
- Log forensics revealed ~5 s of the 10.8 s is self-inflicted:
  - ~2–3 s: xray bridge multiplexing contention (6+ concurrent detail-scrapes + HEADs + recalc sharing one VLESS tunnel during the add)
  - ~2–3 s: VkusVill cart-row DB lock contention vs. parallel `basket_recalc.php` triggered by our own cart-items poll
  - ~1.5 s: stale sessid cold-path revalidation on VkusVill's side (14-day-old sessid)
- Bridge probe confirms network is healthy: authenticated `HEAD vkusvill.ru/` TTFB ≈ 600 ms, `GET /personal/` ≈ 400 ms

The milestone is **optimization + UX robustness**, continuing the v1.19 robust-over-fast cultural commitment: no quick patches, every behavior change lands behind a phase VERIFICATION.md + smoke script extension + rollback rehearsal.

## Requirements

### Latency — Session Warmth

- [ ] **PERF-03**: A background task fires a lightweight authenticated warmup request to VkusVill (e.g. `GET /personal/`) every ≤ 20 min for each linked Telegram user whose session has shown recent activity within the last 24 h, so VkusVill's session cache never goes cold — eliminating the ~1.5 s cold-path revalidation tax from the cart-add hot path.
- [ ] **PERF-04**: When a user opens the MiniApp, the backend opportunistically fires a warmup request for that user within 500 ms of their first `/api/link/status` or `/api/cart/items` call, so even users whose 20-min keep-alive window has elapsed still get a warm session before their first tap.
- [ ] **PERF-05**: A regression test asserts warmup traffic never exceeds 1 request per user per 15 min to VkusVill (anti-spam floor), and that warmup requests through the bridge complete in ≤ 3 s p95 (measured on EC2, excluded from the cart-add hot path).

### Latency — Bridge Contention

- [ ] **PERF-06**: When a `/api/cart/add` is in flight for user X, any subsequent `/api/cart/items` call for the same user X skips its VkusVill round-trip and returns the last-known cart state (cached in-memory from the pending attempt record), preventing the parallel `basket_recalc.php` that today fights the same DB row lock on VkusVill's side.
- [ ] **PERF-07**: `scrape_green` / `scrape_red` / `scrape_yellow` detail-fetch scrapers pause for up to 10 s when a `/api/cart/add` is in flight anywhere in the process (global semaphore), so the cart hot path doesn't compete with 2–3 concurrent detail scrapes through the shared VLESS tunnel.

### Latency — VkusVill API Surface Review

- [ ] **PERF-08**: Capture one full HAR of an authenticated add-to-cart flow on `vkusvill.ru` in a real browser and document any lighter endpoints (e.g. `/ajax/quick_add`, `basket_add_short`, GraphQL, Telegram-integration endpoints) that could replace or augment `basket_add.php`; if a faster endpoint exists, a new phase spike-tests it through the bridge with the same 16-field payload and measures p50/p95/p99.
- [ ] **PERF-09**: The 16-field `basket_add.php` payload is trimmed to the minimum server-accepted set (measured: which fields can be omitted without degrading success rate); a regression test pins the final field list.

### UX — False-Fail Prevention

- [ ] **UX-01**: On frontend `AbortController` timeout during `/api/cart/add`, the client does NOT show a "fail" toast or reset cart state. Instead it begins polling `/api/cart/add-status/{attempt_id}` using the `client_request_id` already sent with the original request, for up to 15 s total (from original request start). Toast/fail state only shows after both channels time out.
- [ ] **UX-02**: The frontend `AbortController` cutoff is reduced from 8 s → 5 s (tighter; fast-path p95 after PERF-03/04/06/07 is expected < 4 s) without any user-visible regression on slow paths (guarded by UX-01 polling).
- [ ] **UX-03**: A `client_request_id` collision test confirms that submitting the same `client_request_id` twice is idempotent — the second call returns the same `attempt_id` and never triggers a duplicate VkusVill `basket_add.php` POST.

### Observability — Cart Hot-Path Metrics

- [ ] **OBS-04**: `/api/health/deep` response gains an optional `cart_add` block (fields: `p50_ms`, `p95_ms`, `p99_ms`, `success_rate_1h`, `success_rate_24h`, `double_add_rate_1h`) computed from the existing `_cart_pending_attempts` ledger, so cart-latency regressions are visible to the same uptime monitor that already watches pool + breaker.
- [ ] **OBS-05**: Every `/api/cart/add` attempt logs a single structured JSONL line to `data/cart_events.jsonl` capturing: `user_id` (hashed), `attempt_id`, `product_id`, `duration_ms`, `success`, `error_type`, `client_request_id`, `sessid_age_s`, `warmup_hit` (bool), `concurrent_recalc` (bool). Enables offline post-mortem of every anomaly.

### Operations — Continuity with v1.19 Discipline

- [ ] **OPS-09**: `scripts/verify_v1.20.sh` is created (separate from v1.19's version-pinned script) and grows phase-by-phase, mirroring the per-phase smoke + cross-phase guard pattern from v1.19.
- [ ] **OPS-10**: Every v1.20 phase includes a p50/p95/p99 cart-add latency check against an EC2-measured baseline (captured during Phase 62 spike), failing the smoke gate if p95 regresses > 500 ms from baseline.
- [ ] **OPS-11**: Rollback rehearsal for every phase (carried forward from v1.19 OPS-08).

## v2 Requirements

### Carried forward from v1.19 (deferred items, remain open)

#### Reliability (pre-flight, breaker, pool)

- **REL-FUT-01** — Probe failure-reason classification (DNS / TLS / HTTP-4xx / timeout)
- **REL-FUT-02** — Multi-target probe (VkusVill + ipinfo.io)
- **REL-FUT-03** — Per-node VkusVill failure counter + auto-quarantine
- **REL-FUT-04** — Auto-trigger pool refresh on entering `half_open`
- **REL-FUT-05** — Telegram alert on breaker state changes (dedup'd)
- **REL-FUT-06** — Replenish to `MAX_CACHED` instead of `MIN_HEALTHY + 1`
- **REL-FUT-07** — Shorter cooldown for non-block failures (TLS = 15 min)
- **REL-FUT-08** — Predictive refresh when quarantine > replenish rate

#### Observability

- **OBS-FUT-01** — Light `/api/health` alias for systemd watchdog
- **OBS-FUT-02** — Reliability tab in `/admin` panel
- **OBS-FUT-03** — Telegram heartbeat (6 h still-healthy pings)

#### Operations

- **OPS-FUT-01** — Pre-merge live-deploy PR gate with smoke script
- **OPS-FUT-02** — Post-deploy 24 h hourly observation window

#### User-facing degraded mode (Category G)

- **UI-FUT-01** — Stale banner reflects `/api/health/deep` status
- **UI-FUT-02** — Detail drawer "live detail unavailable, showing cached info"
- **UI-FUT-03** — Cart-add button disabled with tooltip when deep health unhealthy
- **UI-FUT-04** — Reliability tab in admin panel (overlaps OBS-FUT-02)

## Out of Scope

| Feature | Reason |
|---|---|
| Replace xray with WireGuard / different bridge | v1.15 decision; bridge is healthy (~330 ms, confirmed by probe) |
| Move cart-add to a background job queue (fire-and-forget UX) | Family-scale doesn't justify the infra; users expect synchronous confirmation |
| Cache cart-add success client-side permanently | The product must actually land in VkusVill; optimistic UI only valid until VkusVill acknowledges |
| Rewrite the frontend in a different framework | React+Vite is correct |
| Aggressively parallelize cart-add on our side (fire multiple exits) | Creates duplicate-add risk; serialization is correct, latency optimization is elsewhere |
| Contact VkusVill for a private "fast cart add" API | Not a commercial relationship; reverse-engineering their public AJAX is the only valid path |

## Traceability

(Provisional phase mapping; finalized by `/gsd-roadmapper`.)

| Requirement | Provisional Phase | Status |
|---|---|---|
| PERF-03 | Phase 62 (Sessid keep-alive + on-open warmup) | Defined |
| PERF-04 | Phase 62 | Defined |
| PERF-05 | Phase 62 | Defined |
| PERF-06 | Phase 63 (Bridge contention elimination) | Defined |
| PERF-07 | Phase 63 | Defined |
| PERF-08 | Phase 64 (VkusVill API surface spike) | Defined |
| PERF-09 | Phase 64 | Defined |
| UX-01 | Phase 65 (Frontend pending-polling + idempotency) | Defined |
| UX-02 | Phase 65 | Defined |
| UX-03 | Phase 65 | Defined |
| OBS-04 | Phase 66 (Cart-add observability) | Defined |
| OBS-05 | Phase 66 | Defined |
| OPS-09 | All phases (cross-cutting) | Defined |
| OPS-10 | All phases (cross-cutting) | Defined |
| OPS-11 | All phases (cross-cutting) | Defined |

**Coverage:**
- v1.20 requirements: 15 total (7 PERF, 3 UX, 2 OBS, 3 OPS)
- Mapped to phases: 15 (provisional, 5 phases)
- Unmapped: 0 ✓

## Prior Milestone — Archived

v1.19 Production Reliability & 24/7 Uptime shipped 2026-05-05 with 18/18 requirements satisfied. Full archive:
- `.planning/milestones/v1.19-ROADMAP.md`
- `.planning/milestones/v1.19-REQUIREMENTS.md`
- `.planning/milestones/v1.19-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.19-phases/{59,60,61}-*/`

The v1.19 smoke script `scripts/verify_v1.19.sh` is retained in the repo as a cross-version reliability regression guard; v1.20 adds `scripts/verify_v1.20.sh` alongside.

---
*Requirements defined: 2026-05-05*
*Prior milestone v1.19 archived to `.planning/milestones/v1.19-REQUIREMENTS.md`: 2026-05-05*
