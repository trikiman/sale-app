---
gsd_state_version: 1.0
milestone: v1.20
milestone_name: Cart-Add Latency & User-Facing Responsiveness
status: ready_for_audit
last_updated: "2026-05-12T03:30:00.000Z"
last_activity: 2026-05-12
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 18
  completed_plans: 18
  percent: 100
current_phase: 66.1
current_phase_status: shipped_local
current_phase_resume_file: .planning/phases/66.1-stale-color-phantom-strip/66.1-VERIFICATION.md
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.20 Cart-Add Latency & User-Facing Responsiveness — cut p95 from 10.8 s → ≤ 4 s and eliminate the false-fail-then-double-add UX pattern observed in 2026-05-05 live UAT. 5 phases (62-66), 15 requirements (7 PERF, 3 UX, 2 OBS, 3 OPS). Carries the v1.19 robust-over-fast cultural commitment: per-phase smoke + VERIFICATION.md + rollback rehearsal mandatory.

## Current Position

Phase: 66.1 Stale-Color Phantom Strip (🟢 SHIPPED LOCAL — late UX insert; awaiting EC2 deploy + milestone audit refresh).
Next step: Present v1.20 + 66.1 summary to user for manual review. User instructed to STOP before `/gsd-complete-milestone`.
Status: All 5 planned v1.20 phases (62-66) plus the late 66.1 insert landed as local commits. 66.1 commits: `f821d45` (backend filter + 3 tests) and `c00d644` (smoke gate 66.1-A + planning docs + audit catch-up). Live MCP evidence captured: pre-fix HEAD~1 server on :18067 vs post-fix HEAD on :18066, same stale-green fixture → pre=4 products (2 phantom greens), post=2 products (no greens). Banner fields (`dataStale`, `staleInfo`, `sourceFreshness.green.isStale`) preserved in both. Screenshots in `.planning/phases/66.1-stale-color-phantom-strip/`. Full suite 323 passed + 3 pre-existing Windows-only baseline failures. `bash -n scripts/verify_v1.20.sh` green. NEEDS_OPERATOR for 66.1: EC2 deploy, synthetic stale-green check, rollback rehearsal, v1.19 regression 24/24.
Last activity: 2026-05-12 — Phase 66.1 live MCP evidence captured; full v1.20 + 66.1 ready for user review.

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

- **User-blocked**: Per explicit instruction, STOP before milestone close. User will review and run `/gsd-complete-milestone` manually after verifying.
- Milestone audit `.planning/v1.20-MILESTONE-AUDIT.md` is already generated (verdict `passed`, 15/15 requirements, 0 gaps). Refresh needed to reflect the 66.1 late insert (18 local tests instead of 27 original; 7 phase VERIFICATION.md files instead of 5 — tracking amended in audit YAML frontmatter).
- NEEDS_OPERATOR gates (captured in each phase's VERIFICATION.md): EC2 deploy of all v1.20 phases + 66.1, 50-sample p95 ≤ 4.0 s measurement on EC2, external `/api/health/deep` probe for `cart_add` block, synthetic stale-green check for 66.1, rollback rehearsal per phase, `bash scripts/verify_v1.20.sh all` green on EC2, `bash scripts/verify_v1.19.sh all` still 24/24.
- v1.19 commit `9ccd72b` is the v1.19 audit-pass mark. v1.19 archive remains read-only at `.planning/milestones/v1.19-*` and `.planning/milestones/v1.19-phases/`.
- v1.20 commit range: `51888f7` (62-01) through `c00d644` (66-03 planning + 66.1 smoke + v1.20 audit), 18 commits ahead of origin/main (not pushed — local only).
- 66.1 commits: `f821d45` (backend filter + 3 tests, `backend/main.py` lines 1230-1250 + `backend/test_products_stale_filter.py`), `c00d644` (smoke gate 66.1-A in `scripts/verify_v1.20.sh`, planning docs under `.planning/phases/66.1-stale-color-phantom-strip/`, live MCP evidence screenshots).

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
| v1.20 Phase 62 SHIPPED LOCAL — keepalive/warmup.py + scheduler daemon + 7 tests + NUDGE_QUEUE | 2026-05-08 |
| v1.20 Phase 63 SHIPPED LOCAL — cart/bridge_semaphore.py + cart-items 12s cache + scraper semaphore + 7 tests | 2026-05-09 |
| v1.20 Phase 64 SHIPPED LOCAL — USE_FAST_CART_ADD_ENDPOINT flag + ablation harness + research skeleton | 2026-05-10 |
| v1.20 Phase 65 SHIPPED LOCAL — client_request_id idempotency + 8s->5s AbortController + pending polling | 2026-05-11 |
| v1.20 Phase 66 SHIPPED LOCAL — /api/health/deep cart_add block + data/cart_events.jsonl 11-key ledger + 7 tests | 2026-05-12 |
| v1.20 milestone READY FOR AUDIT — 16 commits local (51888f7..f74b008), 320 tests green, NEEDS_OPERATOR items captured in VERIFICATION.md per phase | 2026-05-12 |
| v1.20 milestone AUDIT PASSED — 15/15 requirements, 0 gaps, verdict `passed` in `.planning/v1.20-MILESTONE-AUDIT.md` | 2026-05-12 |
| v1.20 Phase 66.1 late insert: stale-color phantom strip — pre-existing bug caught during audit (stale green source + banner + phantom cards) | 2026-05-12 |
| v1.20 Phase 66.1 SHIPPED LOCAL — backend filter + 3 tests + smoke gate 66.1-A + live MCP evidence (pre/post fixture comparison) | 2026-05-12 |

---
*Last updated: 2026-05-12 after Phase 66.1 shipped local (late UX insert). All 5 planned v1.20 phases (62/63/64/65/66) plus the 66.1 phantom-strip fix landed as 18 local commits `51888f7..c00d644`. 323 tests green + 3 pre-existing Windows-only baseline failures unchanged. `scripts/verify_v1.20.sh` has 19 smoke checks across Phase 62-66.1 plus v1.19 cross-version regression gate. NEEDS_OPERATOR sections captured per phase in `VERIFICATION.md`: EC2 deploy, 50-sample p95 ≤ 4.0 s measurement, external `/api/health/deep` cart_add block probe, synthetic stale-green check for 66.1, rollback rehearsal, `bash scripts/verify_v1.19.sh all` 24/24. Milestone audit at `.planning/v1.20-MILESTONE-AUDIT.md` passed before 66.1 landed (15/15 requirements). Per explicit user instruction, STOP before `/gsd-complete-milestone` — user will review and close manually after reviewing the 66.1 evidence.*
