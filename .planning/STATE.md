---
gsd_state_version: 1.0
milestone: v1.24
milestone_name: Pool Self-Heal Hardening + Outage UX
status: ready_to_plan
last_updated: "2026-05-13T00:00:00.000Z"
last_activity: 2026-05-13
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
current_phase: 77
current_phase_status: not_started
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.24 Pool Self-Heal Hardening + Outage UX — eliminate the ~1h family-facing outage observed 2026-05-13 when VLESS pool collapsed. Recovery must take minutes not an hour. During rebuild, users see cached data with stale badges. Plus automated enforcement of style guide v2 rules. 3 phases (77-79), 9 requirements (4 REL, 2 UX, 2 TOOL, 1 optional OBS).

## Current Position

Phase: v1.23 shipped + tagged + archived 2026-05-13 (10 commits `e5574f3..91a6e30`). v1.24 REQUIREMENTS.md + ROADMAP.md drafted with 3 phases (77-79) and 9 requirements. Next: `/gsd-plan-phase 77` for Pool Self-Heal Hardening (the P1 priority — 1h outage observation drove this milestone).
Next step: Plan Phase 77 (REL-16/17/18/19 — persistent quarantine deadlist, refresh throttle, lower water mark, scheduler graceful degrade).
Status: v1.23 archived to `.planning/milestones/v1.23-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.23-phases/{74,75,76}-*/`. Tag `v1.23` pushed. 10 commits.
Last activity: 2026-05-13 — v1.23 closed, v1.24 scope defined driven by real outage observation.

## Milestone Goal (v1.24 — active)

- Pool recovery p95 ≤ 10 min after full collapse (REL-16 quarantine deadlist with 20-min TTL, REL-17 refresh throttle ≥60s, REL-18 lower water mark at 10 with rate-of-decline check, REL-19 scheduler graceful degrade when pool 0 for >2 min)
- Zero "empty grid" when cached data exists — `/api/products` returns last-good snapshot with `stale_all: true` flag instead of stripping products (UX-STALE-01). Stale banner upgraded to prominent card per style guide v2 (UX-STALE-02).
- Style guide v2 rules enforced automatically — stylelint rejects off-scale spacing (TOOL-02), eslint rejects inline `style=` (TOOL-03). Pre-commit + `npm run lint` integrated.
- `scripts/verify_v1.24.sh` chains v1.23→v1.22→v1.21→v1.20→v1.19 smoke scripts (OPS-21/22/23).
- Optional: Telegram admin alert when pool 0 > 10 min (OBS-08, conditional on Phase 77 trivially absorbing it)

## Previous Milestone (v1.23 — shipped 2026-05-13, tag `v1.23`)

- Detail-Path Performance + UX Polish — 7/7 requirements + 1 late insert (UX-CART-02), 3 phases (74/75/76)
- 10 commits `e5574f3..91a6e30`, tag `v1.23` pushed to origin
- Phase 74: Cold-path `/api/product/{id}/details` p95 dropped from ~16s → 0.678s (25× improvement), live-verified on EC2
- Phase 75: Card grid layout shift eliminated via `min-height: 36px` lock, DOM-diff verified on production
- Phase 76: Cart panel trash button per row + Очистить desktop Chrome fallback fix (late insert UX-CART-02)
- Style guide v2 upgrade (`docs/miniapp-ui-style-guide.md`) — codified spacing/shadow/motion tokens, state patterns, accessibility rules, 12-point review checklist
- Archive: `.planning/milestones/v1.23-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.23-phases/{74,75,76}-*/`

## Next Up

- `/gsd-plan-phase 77` or direct plan for Pool Self-Heal Hardening (REL-16/17/18/19, optional OBS-08). Target files: `vless/manager.py` (quarantine + throttle), `scheduler_service.py` (graceful degrade), new `tests/test_vless_quarantine.py`.
- Phase 78 (UX-STALE-01/02) — backend `/api/products` + frontend stale badge + prominent banner.
- Phase 79 (TOOL-02/03) — stylelint + eslint configs, pre-commit wiring, baseline `TODO(v1.25)` debt list.
- After each phase: live MCP or EC2 smoke verification — v1.21 "push ≠ verified" lesson still applies.
- Move consumed todos from `.planning/todos/pending/` to `.planning/todos/completed/` as each phase ships.
- After Phase 79: `.planning/v1.24-MILESTONE-AUDIT.md` + tag `v1.24` + archive. **STOP before `/gsd-complete-milestone`** per user's standing instruction (manual archive via Move-Item is the established pattern).

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

## Accumulated Context

- v1.23 shipped: cold-path product_details 25× faster (Phase 74 PERF-10/11), card grid layout shift eliminated (Phase 75 UX-SHIFT-01), cart panel trash button + clear-cart Telegram fallback (Phase 76 UX-CART-01 + UX-CART-02 late insert), style guide v2 upgrade
- v1.22 shipped: history search catalog-wide, stale banner clarification, admin.html attention badges, `/gsd-check-todos` priority triage
- v1.21 shipped: VLESS pool self-heal (admitted-node reprobe + xray auto-reload via passwordless systemctl), pool drift visibility
- v1.20 shipped: cart-add latency work, 11-key JSONL ledger, `/api/health/deep` cart_add block
- **2026-05-13 ~60-min outage** observed directly during v1.23 verification session — pool 20/20 quarantined, 0 healthy for ~1h. Drove v1.24 scope. v1.21 self-heal works for partial drift but not full collapse.

### Pending Todos (see `.planning/todos/pending/`)

- **[P1]** `2026-05-13-vless-pool-slow-recovery-1h-outage.md` — consumed into v1.24 Phase 77 (REL-16/17/18/19). Moves to completed/ when 77 ships.
- **[P2]** `2026-05-13-empty-grid-when-all-sources-stale-during-pool-recovery.md` — consumed into v1.24 Phase 78 (UX-STALE-01/02). Moves to completed/ when 78 ships.
- **[P4]** `2026-05-13-update-gsd-add-todo-skill.md` — still deferred.

## Known Bugs

- Pool recovery slow after full collapse (captured as P1 todo, scoped into Phase 77). Currently manifests as ~1h outage when pool fully dies. v1.21 self-heal handles partial drift; v1.24 Phase 77 handles full collapse.
- Empty grid when all 3 sources stale (captured as P2 todo, scoped into Phase 78). Pairs with pool-recovery fix.

## Timeline

| Event | Date |
|-------|------|
| v1.19 shipped + archived | 2026-05-05 |
| v1.20 SHIPPED + ARCHIVED + TAGGED | 2026-05-12 |
| v1.21 SHIPPED + ARCHIVED + TAGGED (299ms xray reload live) | 2026-05-12 |
| v1.22 SHIPPED + ARCHIVED + TAGGED | 2026-05-13 |
| v1.23 STARTED — Detail-Path Performance + UX Polish | 2026-05-13 |
| v1.23 Phase 74 shipped + live-verified (25× cold-path improvement) | 2026-05-13 |
| v1.23 Phase 75 shipped + live-verified (zero layout shift) | 2026-05-13 |
| v1.23 Phase 76 shipped (cart trash button + clear-cart fallback, late insert UX-CART-02) | 2026-05-13 |
| v1.23 SHIPPED + ARCHIVED + TAGGED (10 commits) | 2026-05-13 |
| ~60-min VLESS pool outage observed during v1.23 verification (drove v1.24 scope) | 2026-05-13 |
| Style guide v2 upgrade committed | 2026-05-13 |
| v1.24 STARTED — Pool Self-Heal Hardening + Outage UX, 3 phases 77-79, 9 reqs | 2026-05-13 |

---
*Last updated: 2026-05-13 after v1.23 archived + tagged. v1.24 REQUIREMENTS.md + ROADMAP.md drafted directly from observed ~1h pool outage + style guide v2 enforcement gap. Next: `/gsd-plan-phase 77` for Pool Self-Heal Hardening.*
