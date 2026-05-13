---
gsd_state_version: 1.0
milestone: v1.26
milestone_name: Miniapp Test Harness + Style Guide Debt Cleanup
status: in_progress
last_updated: "2026-05-13T22:20:00.000Z"
last_activity: 2026-05-13
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 33
current_phase: 84
current_phase_status: not_started
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.26 Miniapp Test Harness + Style Guide Debt Cleanup — Vitest/RTL as safety net, refactor 46 inline-style violations + 135 spacing-scale CSS debt, promote lint rules to ERROR. 3 phases (83-85), 8 requirements.

## Current Position

v1.26 Phase 83 **shipped** 2026-05-13 — Vitest + RTL + jsdom installed, `test-miniapp` CI job added, 5 extracted modules (`cartStep`, `isTelegramRuntime`, `cardConstants`, `ProductCard`, `StaleBanner`), 70 passing tests (3 unit + 4 snapshot files), 5 locked inline snapshots. Live MCP-verified against production. 5 commits `85f1105..9bbd5e7`. Safety net in place for Phase 84 inline-style refactor. Next: `/gsd-plan-phase 84` for TOOL-05 (46 inline-style sites → 0 + promote `react/forbid-dom-props` WARN → ERROR).

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

- **`/gsd-plan-phase 84`** — inline-style refactor (TOOL-05). Target: 46 violations → 0 using Phase 83 snapshots as safety net. Promote `react/forbid-dom-props` WARN → ERROR.
- Phase 85 (TOOL-07/08 + UX-EMPTY-01) — CSS spacing-scale refactor + promote rules to ERROR + empty-state copy fix.
- After each phase: live MCP + CI green before advancing.
- After Phase 85: `.planning/v1.26-MILESTONE-AUDIT.md` + tag `v1.26` + archive. **STOP before `/gsd-complete-milestone`**.

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

---
*Last updated: 2026-05-13 after Phase 83 shipped (5 commits `85f1105..9bbd5e7`, 70 tests, 5 inline snapshots, live MCP-verified against production). ProductCard + StaleBanner extracted for Phase 84 refactor target. Next: `/gsd-plan-phase 84` inline-style refactor.*
