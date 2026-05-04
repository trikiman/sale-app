---
gsd_state_version: 1.0
milestone: v1.19
milestone_name: Production Reliability & 24/7 Uptime
status: planning
last_updated: "2026-05-03T18:28:03.477Z"
last_activity: 2026-05-03
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 3
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.19 Production Reliability & 24/7 Uptime — robust-over-fast hardening of the EC2 data pipeline (corrected pre-flight VLESS probe, observatory probeURL alignment, graduated circuit breaker, unauthed deep health endpoint, per-phase EC2 smoke verification gate). 3 phases (59-61), 18 requirements (12 REL, 3 OBS, 3 OPS).

## Current Position

Phase: 59 Corrected Pre-flight VLESS Probe (planned, ready to execute)
Plan: 59-01-PLAN.md (vless/preflight.py + scheduler integration) -> 59-02-PLAN.md (tests) -> 59-03-PLAN.md (verify + deploy + rollback rehearsal)
Status: Plans written (README + CONTEXT + 3 PLANs, 1473 lines total); ready for `/gsd-execute-phase 59` or manual execution one plan at a time.
Last activity: 2026-05-03 — Phase 59 plans committed (3 atomic plans mapping to REL-01..05 + OPS-06/07/08)

## Milestone Goal (v1.19 — active)

- Detect a silently-degraded VLESS exit before launching Chrome (corrected pre-flight probe with 12 s timeout, capped rotations, balancer-preferred fallback) so 30-45 s wasted-Chrome cycles stop
- Align xray observatory probeURL with the real traffic target (VkusVill, not Google) so the `leastPing` balancer ranks outbounds by real-target reachability
- Replace the cycle-counter circuit breaker with a 3-state machine (closed → open → half_open) + exponential backoff capped at 30 min so 162 useless re-trips can't happen again
- Expose stack health truthfully via unauth `GET /api/health/deep` returning 200/503 + `reasons[]` so external uptime pings catch "active but broken" states
- Make per-phase EC2 smoke verification non-optional (`scripts/verify_v1.19.sh`, `VERIFICATION.md`, rehearsed rollback) so PR #25-style 8-minute-revert regressions cannot reach `main`
- No regression on v1.18 (Vercel miniapp `/api/cart/add` HTTP 200 with `success=true` must still pass)

## Previous Milestone Goal (v1.18 — last shipped 2026-04-25)

- Lifted the VLESS pool ceiling by removing the single-provider `ipinfo.io` rate-limit bottleneck during admission (3-provider geo chain; pool 15 → 25 nodes, +67%)
- Made `scrape_green.py` survive Chromium CDP-WebSocket HTTP 500 errors mid-cycle (4 new helpers; tests grew 96 → 111)
- Preserved v1.17 cart-add reliability (Vercel miniapp `/api/cart/add` returned HTTP 200 with `success=true, cart_items=3, cart_total=971.6`)

## Next Up

- `/gsd-discuss-phase 59` (or `/gsd-plan-phase 59`) — begin Phase 59 (Corrected Pre-flight VLESS Probe). Phases run serially per the no-hotfix discipline; Phase 60 starts only after Phase 59's smoke test passes on EC2 + Vercel miniapp `/api/cart/add` regression check.
- See `.planning/research/v1.19-SUMMARY.md` for the grounded findings (probe/target mismatch, both rotation paths restart xray, breaker has no half-open state) before planning Phase 59 details.
- Note: the 2026-04-22 scheduler SOCKS5 recv() deadlock hotfix (commit `4c7f271`) was superseded by the v1.15 → v1.18 VLESS migration chain, which replaced SOCKS5 entirely with xray-core VLESS+Reality through a local SOCKS5 bridge.

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

---
*Last updated: 2026-05-03 after Phase 59 planning completed (1473 lines across 5 files: README, 59-CONTEXT, 59-01-PLAN Impl, 59-02-PLAN Tests, 59-03-PLAN Verify+Deploy+Rollback)*
