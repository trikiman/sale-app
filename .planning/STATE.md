---
gsd_state_version: 1.0
milestone: v1.20
milestone_name: Cart-Add Latency & User-Facing Responsiveness
status: planning
last_updated: "2026-05-05T19:13:00.000Z"
last_activity: 2026-05-05
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
current_phase: 62
current_phase_status: context_gathered
current_phase_resume_file: .planning/phases/62-sessid-keepalive-warmup/62-CONTEXT.md
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.20 Cart-Add Latency & User-Facing Responsiveness — cut p95 from 10.8 s → ≤ 4 s and eliminate the false-fail-then-double-add UX pattern observed in 2026-05-05 live UAT. 5 phases (62-66), 15 requirements (7 PERF, 3 UX, 2 OBS, 3 OPS). Carries the v1.19 robust-over-fast cultural commitment: per-phase smoke + VERIFICATION.md + rollback rehearsal mandatory.

## Current Position

Phase: 62 Sessid Keep-Alive + On-App-Open Warmup (🔵 CONTEXT GATHERED — ready for plan-phase).
Next step: `/gsd-plan-phase 62` to produce per-deliverable PLAN.md files (estimated 4-5 plans: warmup module, scheduler thread spawn, backend nudge wiring, race-cancellation flag, smoke script skeleton).
Status: 62-CONTEXT.md captured (201 lines) with 4 implementation decisions locked: warm-all linked users (D1), silent-log + JSONL retry on failure (D2), daemon thread in scheduler_service.py (D3), cart-add cancels in-flight warmup (D4). User direction: "fastest way and on the same side robust but robust in prioritize if it didn't cost too much delays" — interpreted as ship simplest, escalate robustness only when free. v1.19 archived (18/18 requirements, 24/24 smoke green). v1.20 ROADMAP.md and REQUIREMENTS.md drafted with 5 phases / 15 requirements.
Last activity: 2026-05-05 — Phase 62 context discussion complete.

## Milestone Goal (v1.20 — active)

- Eliminate the ~1.5 s cold-sessid revalidation cost via 20-min background keep-alive + on-MiniApp-open opportunistic warmup (PERF-03/04/05)
- Stop fighting ourselves on the bridge — skip parallel `basket_recalc.php` while a `basket_add.php` is in flight (per-user mutex), pause detail scrapers during active cart-add (global semaphore) (PERF-06/07)
- HAR-driven spike of VkusVill's cart-add API surface for lighter endpoints; ablation-trim the 16-field `basket_add.php` payload to minimum (PERF-08/09)
- Fix the false-fail UX: frontend `AbortController` 8 s → 5 s + on-AbortError pending-polling at `/api/cart/add-status/{attempt_id}` for up to 15 s; backend `client_request_id` idempotency (UX-01/02/03)
- `/api/health/deep` `cart_add` block (`p50/p95/p99_ms`, `success_rate`, `double_add_rate`); structured `data/cart_events.jsonl` ledger (OBS-04/05)
- Per-phase smoke gate `scripts/verify_v1.20.sh` carrying p95 baseline; rollback rehearsal mandatory (OPS-09/10/11)
- No regression on v1.19 reliability gains (pool drift visibility, breaker, deep health endpoint must still pass)

## Previous Milestone Goal (v1.19 — last shipped 2026-05-05)

- Detected silently-degraded VLESS exits before Chrome launch (corrected pre-flight probe, 12 s timeout, capped rotations, balancer-preferred fallback) — 30-45 s wasted-Chrome cycles stopped
- Aligned xray observatory probeURL with VkusVill (not Google) so `leastPing` ranks by real-target reachability
- Replaced the cycle-counter circuit breaker with a 3-state machine + exponential backoff capped at 30 min, persisted in `data/scheduler_state.json`
- Exposed stack health truthfully via unauth `GET /api/health/deep` returning 200/503 + 8-key OBS-02 schema with `reasons[]`
- Pool drift like the silent 25 → 13 over 8 days is now visible in real time via enriched `proxy_events.jsonl`
- Per-phase EC2 smoke verification non-optional (24/24 green via `scripts/verify_v1.19.sh`, retained as cross-version regression guard alongside v1.20's smoke script)

## Next Up

- `/gsd-plan-phase 62` — produce per-deliverable PLAN.md files for Phase 62 grounded in `62-CONTEXT.md`. Expected plans: 62-01 keepalive/warmup.py module, 62-02 scheduler thread spawn + backend nudge wiring, 62-03 race-cancellation flag in cart hot path, 62-04 tests + smoke script skeleton, 62-05 EC2 deploy + p95 baseline measurement.
- After plans drafted: `/gsd-execute-phase 62` to build, then `/gsd-verify-work 62` for smoke + p95 baseline + rollback rehearsal.
- After Phase 62 ships: `/gsd-discuss-phase 63` for Bridge Contention Elimination (PERF-06/07).
- v1.19 commit `9ccd72b` is the audit-pass mark. v1.19 archive remains read-only at `.planning/milestones/v1.19-*` and `.planning/milestones/v1.19-phases/`.

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Bug Fix & Stability | 1-9 | 2026-03-31 |
| v1.1 Testing & QA | 10-12 | 2026-03-31 |
| v1.2 Price History | 13-18 | 2026-04-01 |
| v1.3 Performance & Optimization | 19-20 | 2026-04-01 |
| v1.4 Proxy Centralization | 21-23 | 2026-04-01 |
| v1.5 History Search & Polish | 24-26 | 2026-04-01 |
| v1.6 Green Scraper Robustness | 27-28 | 2026-04-02 |
| v1.7 Categories & Subgroups | 29-33 | 2026-04-03 |
| v1.8 History Search Completeness | 34-35 | 2026-04-04 |
| v1.9 Catalog Coverage Expansion | 36-38 | 2026-04-04 |
| v1.10 Scraper Freshness & Reliability | 39-42 | 2026-04-05 |
| v1.11 Cart Responsiveness & Truth Recovery | 43-45 | 2026-04-06 |
| v1.12 Add-to-Cart 5s Hard Cap | 46 | 2026-04-08 |
| v1.13 Instant Cart & Reliability | 47-51 | 2026-04-16 (closed 2026-04-22) |
| v1.14 Cart Truth & History Semantics | 52-55 | 2026-04-21 (closed 2026-04-22) |
| v1.15 Proxy Infrastructure Migration | 56 | 2026-04-23 |
| v1.17 VLESS Timeout Hardening | 57 | 2026-04-25 |
| v1.18 Geo Resolver & Scraper Recovery | 58 | 2026-04-25 |
| v1.19 Production Reliability & 24/7 Uptime | 59-61 | 2026-05-05 |

## Accumulated Context

- v1.2 shipped: Price History with 16K+ products, predictions, and detail analytics
- v1.4 shipped: ProxyManager centralization across backend/cart/login flows
- v1.5 shipped: search normalization, fuzzy Cyrillic search, lazy image enrichment
- v1.6 shipped: green scraper robustness with CDP modal loading + validation gates
- v1.7 shipped: group/subgroup hierarchy scraped, drill-down filters on main/history, category favorites, and Telegram category alerts
- v1.8 shipped: History search now covers the full local catalog during active queries and clearly labels mixed result states
- v1.9 shipped: supplemental catalog discovery/backfill now expands local search coverage with parity reporting and regression gates
- Auto-deploy is active via GitHub webhook → EC2 and Vercel frontend deploys
- Scheduler now runs full cycles on a 5-minute target with extra green-only refresh opportunities on a 1-minute target between them
- Sale sessions now stay continuous across transient misses and only close after 60 healthy minutes of absence
- New-item alerts now follow confirmed session reentry instead of first-ever-seen product IDs
- `/api/products` and `/admin/status` now expose per-source freshness and cycle-state visibility
- MiniApp now hydrates from the last good product payload and uses a lower-pressure enrichment queue for missing card metadata
- The milestone verification set now includes continuity, scheduler freshness, notifier, admin-status, history-search, catalog-merge, and API coverage together
- v1.10 archived to `.planning/milestones/` with roadmap, requirements, and audit snapshots
- v1.15 shipped: SOCKS5 proxy pool replaced with xray-core VLESS+Reality bridge (`socks5://127.0.0.1:10808`); legacy code archived under `legacy/proxy-socks5/`; live cart-add of 76 items confirmed via scheduler on EC2
- v1.17 shipped: xray `policy` (`connIdle=30s`, `handshake=8s`) + `observatory` + `leastPing` balancer; egress geo-verification restored; `remove_proxy` now rotates instead of no-op; Vercel miniapp `/api/cart/add` HTTP 200 ×2
- v1.18 shipped: 3-provider geo resolver chain (ipinfo.io → ipapi.co → ip-api.com) lifts pool 15 → 25 nodes (+67%); `scrape_green.py` survives Chromium CDP-WebSocket HTTP 500 via 4 new helpers (`_is_dead_ws_error`, `_refresh_page_handle`, `_safe_js`, `_navigate_and_settle`); +15 new tests

### Pending Todos

- Clarify stale banner freshness vs updated time — the stale warning is driven by per-color source age, while the header shows the latest merged payload time, so the UI currently looks contradictory even when backend freshness logic is correct. (Deferred to v1.20 — part of UI degraded mode UI-FUT-01.)
- ~~Consider an observability milestone to add pool-size monitoring + alerting on top of the v1.18 multi-provider geo chain~~ — **resolved as v1.19 itself**: REL-11, REL-12, OBS-01, OBS-02, OBS-03 plus deferred follow-ups OBS-FUT-01/02/03 cover this concern.

## Known Bugs

- (none open — the three bugs previously listed here were fixed and verified by v1.14: cart add now works live, history no longer fakes reentries, and persisted data was repaired)

## Timeline

| Event | Date |
|-------|------|
| v1.7 milestone archived | 2026-04-03 |
| v1.8 milestone started | 2026-04-03 |
| v1.8 milestone completed | 2026-04-04 |
| v1.8 milestone archived | 2026-04-04 |
| v1.9 milestone started | 2026-04-04 |
| v1.9 phase 36 context gathered | 2026-04-04 |
| v1.9 phase 36 planned | 2026-04-04 |
| v1.9 phase 36 completed | 2026-04-04 |
| v1.9 phase 37 completed | 2026-04-04 |
| v1.9 phase 38 completed | 2026-04-04 |
| v1.10 milestone started | 2026-04-05 |
| v1.10 phase 39 context gathered | 2026-04-05 |
| v1.10 phase 39 planned | 2026-04-05 |
| v1.10 phase 40 context gathered | 2026-04-05 |
| v1.10 phases 39-42 implemented | 2026-04-05 |
| v1.10 verification artifacts written | 2026-04-05 |
| v1.10 milestone archived | 2026-04-05 |
| v1.11 milestone started | 2026-04-06 |
| v1.11 roadmap created | 2026-04-06 |
| v1.11 phase 43 executed | 2026-04-06 |
| v1.11 phase 44 context gathered | 2026-04-06 |
| v1.11 phase 44 executed | 2026-04-06 |
| v1.11 phase 45 context gathered | 2026-04-06 |
| v1.11 phase 45 executed | 2026-04-06 |
| v1.11 milestone archived | 2026-04-06 |
| v1.12 milestone closed (retroactive audit) | 2026-04-22 |
| v1.13 milestone closed (retroactive audit, supersedes gaps_found) | 2026-04-22 |
| v1.14 milestone closed and archived | 2026-04-22 |
| Scheduler SOCKS5 deadlock hotfix (commit 4c7f271) | 2026-04-22 |
| v1.15 phase 56 shipped (VLESS proxy migration) | 2026-04-23 |
| v1.17 phase 57 shipped (VLESS timeout hardening) | 2026-04-25 |
| v1.18 phase 58 shipped (geo resolver + scraper recovery) | 2026-04-25 |
| Planning state realigned for v1.15/v1.17/v1.18 | 2026-05-03 |
| v1.19 milestone started (Production Reliability & 24/7 Uptime) | 2026-05-03 |
| v1.19 research files written (STACK / FEATURES / ARCHITECTURE / PITFALLS / SUMMARY) | 2026-05-03 |
| v1.19 REQUIREMENTS.md defined (18 items: 12 REL, 3 OBS, 3 OPS) | 2026-05-03 |
| v1.19 ROADMAP.md drafted (3 phases: 59, 60, 61) | 2026-05-03 |
| v1.19 Phase 59 plans written (README + CONTEXT + 59-01/02/03-PLAN) | 2026-05-03 |
| v1.19 Phase 59 SHIPPED — vless/preflight.py + scheduler integration + 23 tests + smoke script + rehearsed rollback | 2026-05-04 |
| v1.19 Phase 60 SHIPPED — xray probeURL alignment + 3-state circuit breaker + 21 tests + smoke-script extension | 2026-05-05 |
| v1.19 Phase 61 SHIPPED — pool_snapshot() + /api/health/deep + /admin/status reliability block + 29 tests + smoke 8/8 + rollback rehearsed | 2026-05-05 |
| v1.19 milestone READY FOR AUDIT — all 18 requirements satisfied, 24/24 smoke green | 2026-05-05 |
| v1.19 milestone AUDIT PASSED — 18/18 requirements, 0 gaps, commit `9ccd72b` | 2026-05-05 |
| v1.19 milestone ARCHIVED to `.planning/milestones/v1.19-*` (ROADMAP, REQUIREMENTS, AUDIT, phases) | 2026-05-05 |
| v1.20 milestone STARTED — Cart-Add Latency & User-Facing Responsiveness, 5 phases (62-66), 15 requirements | 2026-05-05 |
| v1.20 Phase 62 context gathered — 4 implementation decisions locked (warm-all, silent-retry, daemon thread, cart-add-cancels-warmup) | 2026-05-05 |

---
*Last updated: 2026-05-05 after Phase 62 context discussion. 62-CONTEXT.md captures 4 implementation decisions plus locked defaults from REQUIREMENTS.md / ROADMAP.md. User explicitly delegated decision-making with the rule "fastest way + robust if it doesn't cost delays" — applied to choose warm-all-users (D1), silent-retry (D2), in-process daemon thread (D3), and cart-add-cancels-warmup (D4). Run `/gsd-plan-phase 62` next to produce per-deliverable PLAN.md files.*
