---
gsd_state_version: 1.0
milestone: v1.21
milestone_name: TBD
status: archived_previous
last_updated: "2026-05-12T15:30:00.000Z"
last_activity: 2026-05-12
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
current_phase: null
current_phase_status: idle
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** Between milestones — v1.20 archived 2026-05-12; next milestone (v1.21) not yet defined.

## Current Position

Phase: none (between milestones).
Next step: `/gsd-new-milestone` to define v1.21 scope, or `/gsd-check-todos` to review pending backlog first.
Status: v1.20 fully archived to `.planning/milestones/v1.20-*` — 15 requirements shipped, 6 phases delivered (62-66 + 66.1 + 66.2 + 66.3). 325 local tests pass + 3 pre-existing Windows-only baseline failures. Production deployed (origin/main at `e362507`, EC2 + Vercel auto-deployed). Live Phase 66.3 basket_recalc warmup confirmed working (2.2s vs 6s on /personal/). `/api/health/deep` returning 200 healthy.
Last activity: 2026-05-12 — v1.20 milestone complete + archive + tag.

## Previous Milestone (v1.20 — shipped 2026-05-12)

- Cart-Add Latency & User-Facing Responsiveness — all 15 requirements satisfied
- 6 phases: 62 (Sessid Keep-Alive), 63 (Bridge Contention), 64 (API Surface Spike scaffolding), 65 (Frontend Polling + Idempotency), 66 (Hot-Path Observability), 66.1 (Stale-Color Phantom Strip late insert), 66.2 (Cart Stepper Cache-Hit Fix late insert), 66.3 (Warmup Endpoint Retune late insert)
- Archive: `.planning/milestones/v1.20-ROADMAP.md`, `.planning/milestones/v1.20-REQUIREMENTS.md`, `.planning/milestones/v1.20-MILESTONE-AUDIT.md`, `.planning/milestones/v1.20-phases/` (8 dirs), `.planning/milestones/v1.20-SESSION-REPORT-2026-05-12.md`
- Git range: commits `51888f7..e362507` (20 commits) between v1.19 audit-pass mark `9ccd72b` and v1.20 tip

## Next Up

- `/gsd-check-todos` — review 5 pending todos (2 P1 VLESS infra gaps, 3 smaller UX/admin debts)
- `/gsd-new-milestone` — define v1.21 scope
- Open P1 todos worth folding into v1.21: VLESS pool dynamic rehealth + xray reload on admission (both caused the 4-day outage 2026-05-06..05-10, manual fix rehearsed but not permanent)

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
| v1.20 Cart-Add Latency & User-Facing Responsiveness | 62-66 + 66.1/.2/.3 | 2026-05-12 |

## Accumulated Context

- v1.20 shipped: 20-min keepalive daemon + on-open warmup nudge (PERF-03/04/05), per-user cart-items 12s cache + global scraper semaphore (PERF-06/07), USE_FAST_CART_ADD_ENDPOINT feature-flag scaffolding (PERF-08/09), frontend client_request_id idempotency + 5s AbortController + polling-on-abort (UX-01/02/03), /api/health/deep cart_add block + data/cart_events.jsonl 11-key ledger (OBS-04/05), scripts/verify_v1.20.sh with 19 smoke checks + v1.19 regression gate, 66.1 stale-color filter dropping phantom products, 66.2 cache-hit stepper UI fix, 66.3 warmup endpoint swap /personal/ → basket_recalc (3x speedup)
- v1.19 shipped: pre-flight VLESS probe + 3-state breaker + /api/health/deep + pool drift visibility
- v1.18 shipped: 3-provider geo resolver (ipinfo → ipapi → ip-api), scraper CDP-WS recovery helpers, +15 tests
- v1.17 shipped: xray policy + observatory + leastPing, remove_proxy rotation, egress geo verification
- v1.15 shipped: VLESS+Reality migration via xray-core bridge (socks5://127.0.0.1:10808)

### Pending Todos (see `.planning/todos/pending/`)

- **[P1]** `2026-05-10-vless-pool-admission-lacks-dynamic-rehealth` — nodes admitted once, never re-probed; VkusVill can block IP silently after admission. Root cause of 4-day outage 2026-05-06 to 05-10.
- **[P1]** `2026-05-10-xray-not-reloaded-after-pool-admission` — pool refresh rewrites config but systemd xray never reloads. Same outage cause. Manual `systemctl restart saleapp-xray` was the fix.
- **[P2]** `2026-05-10-v1-16-admin-html-bug-reports-badge-missing` — v1.16 gap: backend exposes counts, admin.html never wired.
- **[P3]** `2026-04-06-clarify-stale-banner-freshness-vs-updated-time` — partially resolved by 66.1; UX copy refinement remains.
- **[P3]** `2026-04-02-history-search-shows-all-matching-products-from-catalog` — v1.5 search filter too restrictive.

## Known Bugs

- (none open — v1.20 closed the stale-color phantom (66.1), cart stepper ⟲ flash (66.2), and warmup endpoint choice (66.3) bugs)

## Timeline

| Event | Date |
|-------|------|
| v1.14 milestone closed and archived | 2026-04-22 |
| v1.15 shipped (VLESS proxy migration) | 2026-04-23 |
| v1.17 shipped (VLESS timeout hardening) | 2026-04-25 |
| v1.18 shipped (geo resolver + scraper recovery) | 2026-04-25 |
| v1.19 shipped + archived | 2026-05-05 |
| v1.20 milestone STARTED | 2026-05-05 |
| v1.20 Phase 62 SHIPPED LOCAL (keepalive/warmup.py daemon) | 2026-05-08 |
| v1.20 Phase 63 SHIPPED LOCAL (bridge_semaphore + cache) | 2026-05-09 |
| v1.20 Phase 64 SHIPPED LOCAL (feature-flag scaffolding) | 2026-05-10 |
| v1.20 Phase 65 SHIPPED LOCAL (client_request_id + polling) | 2026-05-11 |
| v1.20 Phase 66 SHIPPED LOCAL (OBS-04 + OBS-05) | 2026-05-12 |
| v1.20 Phase 66.1 SHIPPED LOCAL (stale-color phantom strip) | 2026-05-12 |
| v1.20 Phase 66.2 SHIPPED LOCAL (cache-hit stepper fix) | 2026-05-12 |
| v1.20 Milestone AUDIT PASSED (15/15 requirements, 0 gaps) | 2026-05-12 |
| v1.20 PUSHED to origin/main + auto-deployed to EC2 + Vercel | 2026-05-12 |
| v1.20 Phase 66.3 SHIPPED + DEPLOYED (warmup endpoint retune, live-verified) | 2026-05-12 |
| v1.20 Milestone ARCHIVED to `.planning/milestones/v1.20-*` | 2026-05-12 |

---
*Last updated: 2026-05-12 after v1.20 milestone close + archive. All v1.20 artifacts under `.planning/milestones/v1.20-*`. Top-level REQUIREMENTS.md + ROADMAP.md deleted (will be recreated by `/gsd-new-milestone` for v1.21). Working tree clean; origin/main at commit `e362507` (pre-archive) — archive commit + tag coming next.*
