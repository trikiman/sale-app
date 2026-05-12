---
gsd_state_version: 1.0
milestone: v1.25
milestone_name: Operator Visibility + Test Coverage
status: ready_to_plan
last_updated: "2026-05-13T00:00:00.000Z"
last_activity: 2026-05-13
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
current_phase: 80
current_phase_status: not_started
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.25 Operator Visibility + Test Coverage — close the "time-to-notice" gap from v1.24 (Telegram alerts on pool-dead / breaker / xray-fail), add ops escape hatches (force-clear quarantine, force-stale for testing), add the integration tests the v1.24 verifier flagged, wire CI for lint enforcement. 3 phases (80-82), 13 requirements (3 OBS, 2 OPS-escape, 3 QA, 3 TOOL, 3 OPS-continuity).

## Current Position

v1.24 shipped + tagged + archived + verified 2026-05-13 (11 commits `4eb637e..3ae45bd`). v1.25 REQUIREMENTS.md + ROADMAP.md drafted. Next: `/gsd-plan-phase 80` for Telegram Alerts + Admin Escape Hatches.

## Milestone Goal (v1.25 — active)

- Telegram admin DM on pool size 0 for 10+ min (OBS-08), breaker state transitions (OBS-09), xray_restart_failed (OBS-10). Cooldowns prevent thrash.
- `POST /admin/vless/quarantine/clear` (OPS-24) and `POST /admin/force-stale-all` (OPS-25) for ops + deterministic testing.
- Integration test replaying 2026-05-13 collapse pattern (QA-06), scheduler-manager race (QA-07), staleAll+empty edge case (QA-08).
- CI wiring (`.github/workflows/lint.yml`) + refactor of 46 baselined inline-style violations + bump `react/forbid-dom-props` to ERROR (TOOL-04/05/06).
- `scripts/verify_v1.25.sh` chains v1.24→v1.23→v1.22→v1.21→v1.20→v1.19 (OPS-26/27/28).

## Previous Milestone (v1.24 — shipped 2026-05-13, tag `v1.24`)

- Pool Self-Heal Hardening + Outage UX — 9/9 requirements + OBS-08 deferred to v1.25, 3 phases (77/78/79)
- 11 commits `4eb637e..3ae45bd`, tag `v1.24` pushed to origin
- Verifier audit resolved 4 MUST-CONFIRM-IN-CODE items; final verdict PASS
- Persistent quarantine + refresh throttle + rate-of-decline + scheduler graceful degrade (Phase 77)
- `/api/products` staleAll + per-card badge + prominent banner (Phase 78)
- Stylelint + eslint forbid-dom-props + 46-entry inline-style debt baseline (Phase 79)
- Live EC2 confirms MIN_HEALTHY=10 active
- Archive: `.planning/milestones/v1.24-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT,MILESTONE-VERIFICATION}.md` + `.planning/milestones/v1.24-phases/{77,78,79}-*/`

## Next Up

- `/gsd-plan-phase 80` or direct plan for Telegram Alerts + Admin Escape Hatches (OBS-08/09/10 + OPS-24/25). Target files: `bot/notifier.py` (send_admin_alert helper + cooldown ledger), `backend/main.py` (admin endpoints), `scheduler_service.py` + `vless/manager.py` (hook points for state transitions).
- Phase 81 integration tests — consume Phase 80 force-stale endpoint for deterministic QA-06/07/08.
- Phase 82 CI wiring — after inline-style refactor (Phase 82 also includes the refactor as TOOL-05).
- After each phase: live MCP or EC2 smoke verification.
- Move consumed todos as each phase ships.
- After Phase 82: `.planning/v1.25-MILESTONE-AUDIT.md` + tag `v1.25` + archive. **STOP before `/gsd-complete-milestone`**.

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
| v1.22 UX Debt Cleanup + Tooling Polish | 70-73 | 2026-05-13 |
| v1.23 Detail-Path Performance + UX Polish | 74-76 | 2026-05-13 |
| v1.24 Pool Self-Heal Hardening + Outage UX | 77-79 | 2026-05-13 |

## Accumulated Context

- v1.24 shipped: pool recovery hardening (REL-16/17/18/19) + stale-state UX (UX-STALE-01/02) + style guide v2 enforcement tooling (TOOL-02/03). Verifier audit confirms all 4 MUST-CONFIRM items resolved in code. OBS-08 Telegram alert deferred to v1.25 by design.
- Style guide v2 (`docs/miniapp-ui-style-guide.md` `91a6e30`) — design tokens, spacing scale, state patterns, accessibility rules, 12-point review checklist.
- **Known outage precedent:** 2026-05-13 ~60 min VLESS pool outage drove v1.24 scope. Operator learned via MiniApp; v1.25 Phase 80 closes this "time-to-notice" gap with Telegram alerts.

### Pending Todos (see `.planning/todos/pending/`)

- **[P4]** `2026-05-13-update-gsd-add-todo-skill.md` — tooling skill polish, deferred. No phase consumes this in v1.25.

## Known Bugs

- (none open — v1.24 closed the pool-recovery + stale-grid issues; verifier flagged a few edge cases like empty-source-files + newly-created-file but none are regressions)

## Timeline

| Event | Date |
|-------|------|
| v1.23 SHIPPED + ARCHIVED + TAGGED (25× cold-path improvement, layout shift fix, cart trash + clear-cart fallback) | 2026-05-13 |
| ~60-min VLESS pool outage observed during v1.23 verification — drove v1.24 scope | 2026-05-13 |
| v1.24 STARTED — Pool Self-Heal Hardening + Outage UX, 3 phases 77-79, 9 reqs | 2026-05-13 |
| v1.24 Phase 77 (Pool Self-Heal) shipped + live-verified on EC2 (MIN_HEALTHY=10 active) | 2026-05-13 |
| v1.24 Phase 78 (Stale-State UX) shipped | 2026-05-13 |
| v1.24 Phase 79 (Style Guide v2 Enforcement) shipped | 2026-05-13 |
| v1.24 SHIPPED + ARCHIVED + TAGGED (9 commits, verifier audit PASS) | 2026-05-13 |
| v1.25 STARTED — Operator Visibility + Test Coverage, 3 phases 80-82, 13 reqs | 2026-05-13 |

---
*Last updated: 2026-05-13 after v1.24 archived + tagged + verified. v1.25 scope driven by v1.24 verifier carry-forwards (OBS-08 Telegram alert, 2026-05-13 collapse replay test, CI wiring). Next: `/gsd-plan-phase 80` for Telegram Alerts + Admin Escape Hatches.*
