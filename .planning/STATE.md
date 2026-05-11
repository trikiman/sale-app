---
gsd_state_version: 1.0
milestone: v1.22
milestone_name: UX Debt Cleanup + Tooling Polish
status: defining_requirements
last_updated: "2026-05-12T23:30:00.000Z"
last_activity: 2026-05-12
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
current_phase: 70
current_phase_status: not_started
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.22 UX Debt Cleanup + Tooling Polish — close 3 UI/API bugs documented in `.planning/todos/pending/` since April/May (history search catalog-wide, stale banner clarification, admin.html Bug Reports badge) plus `/gsd-check-todos` skill polish. 4 phases (70-73), 7 requirements (3 UX, 1 TOOL, 3 OPS).

## Current Position

Phase: not started (REQUIREMENTS.md + ROADMAP.md drafted 2026-05-12; awaiting `/gsd-plan-phase 70`).
Next step: `/gsd-discuss-phase 70` (History Search Catalog-Wide) to capture implementation decisions in 70-CONTEXT.md, then `/gsd-plan-phase 70` for 70-01/02-PLAN.md.
Status: v1.21 shipped 2026-05-12, archived to `.planning/milestones/v1.21-*`, tag `v1.21` pushed. 3 pending UX todos consumed into v1.22 scope (will move to `.planning/todos/completed/` as each phase ships). 1 tooling todo consumed into Phase 73.
Last activity: 2026-05-12 — v1.21 archived + tagged + v1.22 requirements/roadmap drafted.

## Milestone Goal (v1.22 — active)

- History search returns ALL products from `product_catalog` matching the query, not just `total_sale_count > 0` rows; `currentSaleType` field lets MiniApp render green/red/yellow badges inline with ghost cards (UX-BUG-01)
- Stale banner + updated-time header align semantically (option A header-switches or B banner-annotates, picked in discuss) so user no longer sees "Обновлено: 09:36 + stale warning" contradiction (UX-COPY-01)
- `backend/admin.html` renders `Bug Reports (N)` badge mirroring existing `proxy-badge` / `cart-pending-count` patterns — closes v1.16 Phase 61 Success Criterion 3 (~20 LOC) (UX-BADGE-01)
- `/gsd-check-todos` skill adds `priority: P1|P2|P3|P4` frontmatter, P1-first sort, fold-into-milestone action (TOOL-01)
- `scripts/verify_v1.22.sh` chains `verify_v1.21.sh all` (which chains v1.20 + v1.19); all four milestones' smoke gates stay green through v1.22 deploy (OPS-15/16/17)

## Previous Milestone (v1.21 — shipped 2026-05-12, tag `v1.21`)

- VLESS Pool Self-Healing & Reload Pipeline — all 8 requirements satisfied, 3 phases (67/68/69)
- 14 commits `fcc740f..44fba0f`, tag `v1.21` pushed to origin
- Live-verified on EC2: 13/13 smoke checks green, first systemctl xray reload in 299ms, drift injection proved OBS-06 detection + recovery
- Archive: `.planning/milestones/v1.21-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.21-phases/` (3 directories)

## Next Up

- `/gsd-discuss-phase 70` — capture 70-CONTEXT.md for History Search Catalog-Wide
- `/gsd-plan-phase 70` → execute → verify → ship
- Repeat for 71 (Stale Banner Clarification), 72 (admin.html Bug Reports Badge), 73 (gsd-check-todos Polish)
- After Phase 73 ships: invoke `gsd-audit-milestone` skill to produce `.planning/v1.22-MILESTONE-AUDIT.md`
- STOP before `/gsd-complete-milestone` per user's standing instruction — await manual review

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
| v1.13 Instant Cart & Reliability | 47-51 | 2026-04-16 |
| v1.14 Cart Truth & History Semantics | 52-55 | 2026-04-21 |
| v1.15 Proxy Infrastructure Migration | 56 | 2026-04-23 |
| v1.17 VLESS Timeout Hardening | 57 | 2026-04-25 |
| v1.18 Geo Resolver & Scraper Recovery | 58 | 2026-04-25 |
| v1.19 Production Reliability & 24/7 Uptime | 59-61 | 2026-05-05 |
| v1.20 Cart-Add Latency & User-Facing Responsiveness | 62-66 + 66.1/.2/.3 | 2026-05-12 |
| v1.21 VLESS Pool Self-Healing & Reload Pipeline | 67-69 | 2026-05-12 |

## Accumulated Context

- v1.21 shipped: admitted-node reprobe daemon every 10 min through bridge (REL-13), per-host success_rate tracking (REL-15), xray auto-reload via passwordless systemctl on admission-set diff (REL-14, 299ms live), `/api/health/deep` xray_drift block + `pool_refresh_complete` event schema (OBS-06/07), 13/13 smoke live-verified
- v1.20 shipped: 20-min keepalive daemon + on-open warmup nudge (PERF-03/04/05), per-user cart-items 12s cache + global scraper semaphore (PERF-06/07), USE_FAST_CART_ADD_ENDPOINT feature-flag scaffolding (PERF-08/09), frontend client_request_id idempotency + 5s AbortController + polling-on-abort (UX-01/02/03), /api/health/deep cart_add block + data/cart_events.jsonl 11-key ledger (OBS-04/05)
- v1.19 shipped: pre-flight VLESS probe + 3-state breaker + /api/health/deep + pool drift visibility
- 2026-05-10 outage manual fix automated by v1.21: self-healing loop now catches "pool healthy but xray stale" state in minutes, not days

### Pending Todos (see `.planning/todos/pending/`)

- **[P2]** `2026-04-02-history-search-shows-all-matching-products-from-catalog` — consumed into v1.22 UX-BUG-01 (Phase 70). Moves to completed/ when 70 ships.
- **[P3]** `2026-04-06-clarify-stale-banner-freshness-vs-updated-time` — consumed into v1.22 UX-COPY-01 (Phase 71). Moves to completed/ when 71 ships.
- **[P2]** `2026-05-10-v1-16-admin-html-bug-reports-badge-missing` — consumed into v1.22 UX-BADGE-01 (Phase 72). Moves to completed/ when 72 ships.
- **[P4]** `2026-05-12-update-gsd-check-todos-skill` — consumed into v1.22 TOOL-01 (Phase 73). Phase 73 executes the todo's scope directly.

## Known Bugs

- (none open — v1.21 closed the self-healing gap, v1.20 closed stale-color phantoms, cart stepper, and warmup endpoint choice)

## Timeline

| Event | Date |
|-------|------|
| v1.14 milestone closed and archived | 2026-04-22 |
| v1.15 shipped (VLESS proxy migration) | 2026-04-23 |
| v1.17 shipped (VLESS timeout hardening) | 2026-04-25 |
| v1.18 shipped (geo resolver + scraper recovery) | 2026-04-25 |
| v1.19 shipped + archived | 2026-05-05 |
| 4-day VLESS outage (pool.json healthy, xray routing to dead May 5 outbound) | 2026-05-06 → 05-10 |
| Manual fix: sudo systemctl restart saleapp-xray + pool whitelist rebuild | 2026-05-10 |
| v1.20 milestone STARTED | 2026-05-05 |
| v1.20 milestone SHIPPED + ARCHIVED + TAGGED | 2026-05-12 |
| v1.21 milestone STARTED (VLESS Pool Self-Healing & Reload Pipeline, 3 phases, 8 requirements) | 2026-05-12 |
| v1.21 all 3 phases shipped + live-verified on EC2 (299ms xray reload, 13/13 smoke green) | 2026-05-12 |
| v1.21 SHIPPED + ARCHIVED + TAGGED | 2026-05-12 |
| v1.22 milestone STARTED (UX Debt Cleanup + Tooling Polish, 4 phases, 7 requirements) | 2026-05-12 |

---
*Last updated: 2026-05-12 after v1.21 archived + tagged. v1.22 REQUIREMENTS.md + ROADMAP.md drafted with 4 phases (70-73) and 7 requirements (3 UX, 1 TOOL, 3 OPS). Three UX todos + one tooling todo consumed into scope (stay in pending/ until their phase ships). Next: `/gsd-discuss-phase 70` for History Search Catalog-Wide.*
