---
gsd_state_version: 1.0
milestone: v1.26
milestone_name: Miniapp Test Harness + Style Guide Debt Cleanup
status: in_progress
last_updated: "2026-05-15T00:35:00.000Z"
last_activity: 2026-05-15
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 7
  completed_plans: 7
  percent: 100
current_phase: 85
current_phase_status: complete
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.26 milestone scope **CLOSED**. All 3 phases shipped: 83 (Vitest/RTL foundation), 84 (inline-style refactor 46/46 + 7 robustness sidequests), 85 (spacing-scale tokens + UX-EMPTY-01 + lint promotion). All 8 v1.26 requirements landed and live-verified. **Pending manual approval before `/gsd-complete-milestone`** per standing instruction.

## Current Position

Phase 85 closed v1.26 scope. End-to-end verification at 03:34 MSK 2026-05-15:

- **Spacing-scale**: 7 `--space-*` tokens loaded (xs=4, sm=8, md=12, lg=16, xl=24, 2xl=32, 3xl=48), `.product-grid` gap resolved to 16px from `var(--space-lg)`, 357 cards rendering, no layout breakage. Stylelint 0 warnings (was 135 baseline), rule promoted WARN→ERROR.
- **UX-EMPTY-01**: backend `_compute_empty_reason()` classifies into fresh_deploy / all_stale / genuinely_empty; ProductsResponse model adds `emptyReason: Optional[str]`; frontend renders 3 differentiated copy variants. /api/products returns 200 with `emptyReason="fresh_deploy"` when proposals.json missing (was HTTPException 404).
- **Tests**: 4 new pytest cases for `_compute_empty_reason`. Full suite 314 passed (was 310, +4), 3 Windows-baseline failures, no regressions.
- **Build/lint**: vitest 70/70, lint 5 warnings (pre-existing react-hooks advisories), lint:css 0, vite build 676ms.

Pending: operator UAT, then explicit `/gsd-complete-milestone` invocation. **Do NOT auto-tag v1.26.**

Next session: Phase 84-03 (HistoryPage.jsx 10 sites + HistoryDetail.jsx 14 sites + bump `react/forbid-dom-props` WARN→ERROR + drop CI `--max-warnings=60`). Closes Phase 84 main goal at 46/46 sites.

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

1. **Operator UAT** — verify miniapp end-to-end (history pages, cart, freshness banner, fresh-deploy empty-state copy if you wipe data dir).
2. **`/gsd-complete-milestone`** — manual invocation required. Tags v1.26, archives ROADMAP/REQUIREMENTS/phase summaries, prepares for next milestone cycle.

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
| Phase 84.5 robust-freshness scheduler (`2cf4f1c`) — overshoot tolerance + stall recovery + 5-min threshold + Wants= systemd fix; live-verified gaps 3:12/4:43/4:26 across 5 cycles | 2026-05-14 |
| Phase 84-02 inline-style refactor (`4f7969b`) — App.jsx 10 sites + ProductDetail.jsx 9 sites (22 of 46 total); lint 48 → 29 warnings; visually verified on Vercel | 2026-05-14 |
| Phase 84.6 robust scraper (`2fc0048` + `4fb8af1`) — safe-click for modal-close TypeError + mtime touch on suspicious-result safety guard; EC2-verified green age 0.9m, miniapp Обновлено: 00:07 at 00:08:31 (1m fresh), banner cleared | 2026-05-15 |
| Phase 84.7 per-color staleness thresholds (`5919ef8`) — green=5, red=5, yellow=10 (was uniform 5); resolves cycle-cadence-vs-threshold edge flicker on red and yellow; staleThresholdMinutes surfaced per color in API; live-verified red age 4.6m fresh under 5m, yellow with 10m headroom | 2026-05-15 |
| Phase 84-03 final inline-style refactor (`bc537cf`) — HistoryPage 10 + HistoryDetail 14 sites; lint 48 → 5 warnings; react/forbid-dom-props WARN→ERROR; CI --max-warnings 60 → 10; visually verified on Vercel (1866 products, hero+chart+log all rendering). Phase 84 main goal CLOSED at 46/46. | 2026-05-15 |
| Phase 85 (`3faaac5`) — spacing-scale tokens (135 → 0 violations) + UX-EMPTY-01 (emptyReason field + differentiated copy) + stylelint WARN→ERROR + dropped CI --max-warnings=150. **v1.26 milestone scope CLOSED.** Pending manual approval for `/gsd-complete-milestone`. | 2026-05-15 |

---
*Session checkpoint 2026-05-15 ~03:35 MSK. **v1.26 milestone scope COMPLETE.** All 3 phases (83/84/85) shipped + live-verified. 7 robustness sidequests (84.1-84.7) shipped during Phase 84. STOP before `/gsd-complete-milestone` per standing instruction — operator UAT required first.*
