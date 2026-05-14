---
gsd_state_version: 1.0
milestone: v1.26
milestone_name: Miniapp Test Harness + Style Guide Debt Cleanup
status: in_progress
last_updated: "2026-05-14T16:05:00.000Z"
last_activity: 2026-05-14
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 7
  completed_plans: 5
  percent: 60
current_phase: 84
current_phase_status: in_progress
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.26 Phase 84 inline-style refactor — 3 of 46 sites done. Pool fix shipped (Phase 84.4 `d469080`); EC2 verified data freshness <5 min over 3 cycles, pool degraded but stable on a single Sberbank CDN node.

## Current Position

Phase 84.4 closed the pool-starvation regression. Live verification at 19:04 MSK:
- Backend `/admin/status` → green 2.3m, red 1.5m, yellow 0.7m, all `isStale: false`.
- Miniapp `/api/products` → `Обновлено: 19:01 at 19:04` — 3 min stale, no banner.
- Pool: 1/10 (degraded) on `yt-noads.sbrf-cdn342.ru:443` — single node sustains all 3 scrapers because TCP pre-filter saves ~150s/cycle of probe budget.

Next session: continue Phase 84-02 (App.jsx 10 sites + ProductDetail.jsx 9 sites). Pool will continue refreshing in background; if it drops to 0 again, the soft-tier (60s) recovery + TCP pre-filter should auto-recover within 1-2 cycles.

## Milestone Goal (v1.26 — active)

- Vitest + React Testing Library in `miniapp/`. CI `test-miniapp` job runs snapshot + unit tests on every PR. (TEST-01)
- Snapshot tests covering UX invariants: ProductCard 36px-min-height lock (v1.23 UX-SHIFT-01), CartPanel trash button (v1.23 UX-CART-01), stale-banner variants, empty-vs-staleAll rendering. (TEST-02)
- Unit tests for `normalizeUnit`, `getCartStep`, `isTelegramRuntime`. (TEST-03)
- Refactor 46 inline-style violations → utility classes + explicit class props + justified-disable markers. Bump `react/forbid-dom-props` WARN→ERROR. (TOOL-05)
- Refactor 135 spacing-scale CSS violations → CSS custom properties from style guide v2. Bump `declaration-property-value-allowed-list` WARN→ERROR. (TOOL-07/08)
- Fix fresh-deploy empty-state UI copy — add `emptyReason` diagnostic field + proper message. (UX-EMPTY-01)

## Previous Milestone (v1.25 — shipped 2026-05-13, tag `v1.25`)

- Operator Visibility + Test Coverage — 10/13 requirements + REL-19 hotfix, 3 phases (80/81/82)
- 16 commits `e76a78e..9d3d185`, tag `v1.25` pushed + archived
- Phase 80: Telegram admin alerts (OBS-08/09/10) + admin escape endpoints (OPS-24/25)
- Phase 81: 2026-05-13 collapse replay integration test + pool IO race + staleAll-empty edge
- Phase 82: GitHub Actions CI + eslint baseline cleared (23 errors → 0) + spacing-scale stylelint rule (135-violation baseline)
- REL-19 hotfix: production outage 00:04→01:13 fixed + pinned by regression tests
- UAT audit: 6 items surfaced, 1 P1 blocking (Telegram config), 3 P2 observable, 2 P3 defer-safe
- Archive: `.planning/milestones/v1.25-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.25-phases/{80,81,82}-*/`

## Next Up

1. **Phase 84-02** — App.jsx (10) + ProductDetail.jsx (9) inline-style refactor.
2. **Phase 84-03** — HistoryPage (10) + HistoryDetail (14), then bump `react/forbid-dom-props` WARN→ERROR.
3. **Phase 85** (TOOL-07/08 + UX-EMPTY-01) — CSS spacing-scale + final lint bump.
4. **STOP before `/gsd-complete-milestone`** — manual approval required.

**Pool watch:** if pool drops back to 0 mid-session and data goes stale, run
`scripts/debug_admission.py --limit 5` first to see which sources are dying.
Phase 84.4 ships the corrective filter but the upstream aggregators churn —
we may need to add another aggregator or revisit the "RU-only requirement"
question (see Open Questions).

## Outstanding UAT

From `.planning/UAT-AUDIT-2026-05-13.md`:
- **P1: UAT-001** — configure `ADMIN_TELEGRAM_CHAT_IDS` on EC2 (2-min operator task, blocks v1.25 Phase 80 runtime value)
- **P2: UAT-002/003/004** — observable or self-serve
- **P3: UAT-005/006** — defer-safe

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0-v1.15 | 1-56 | Mar-Apr 2026 |
| v1.17-v1.19 | 57-61 | Apr-May 2026 |
| v1.20 | 62-66 + 66.1/.2/.3 | 2026-05-12 |
| v1.21 | 67-69 | 2026-05-12 |
| v1.22 | 70-73 | 2026-05-13 |
| v1.23 | 74-76 | 2026-05-13 |
| v1.24 | 77-79 | 2026-05-13 |
| v1.25 | 80-82 | 2026-05-13 |

## Known Bugs

- None active. v1.25 REL-19 hotfix closed the 2026-05-13 pool-stuck outage. UAT audit found zero stale documentation.

## Timeline

| Event | Date |
|-------|------|
| v1.24 SHIPPED + ARCHIVED + TAGGED | 2026-05-13 |
| 00:04→01:13 production outage (REL-19 graceful-degrade bug) | 2026-05-13 |
| Hotfix `b65cde7` shipped + pool recovered 0→10 live | 2026-05-13 |
| v1.25 SHIPPED + ARCHIVED + TAGGED (Phase 80/81/82) | 2026-05-13 |
| UAT audit produced (6 items, 1 P1 blocking) | 2026-05-13 |
| v1.26 STARTED — Miniapp Test Harness + Style Guide Debt Cleanup, 3 phases 83-85, 8 reqs | 2026-05-13 |
| v1.26 Phase 83 SHIPPED — vitest + 70 tests + 5 snapshots + extracted ProductCard/StaleBanner | 2026-05-13 |
| Phase 84-01 inline-style refactor (3 of 46 sites) | 2026-05-14 |
| Phase 84.1 pool recovery hardening (dedup + graduated TTL + soft-tier release) | 2026-05-14 |
| Phase 84.2 multi-source aggregation (igareck + kort0881 + SoliSpirit) | 2026-05-14 |
| Phase 84.3 consensus voting in verify_egress (3-provider majority) | 2026-05-14 |
| Phase 84.4 TCP pre-filter + RU-only label gate (`d469080`) — pool fix shipped + EC2-verified data freshness <5 min | 2026-05-14 |

---
*Session checkpoint 2026-05-14 ~19:05 MSK. v1.26 Phase 84 in progress, blocker resolved. Pool degraded (1/10) but stable; data fresh <5 min. Next: Phase 84-02 inline-style refactor (App.jsx + ProductDetail.jsx, 19 sites).*
