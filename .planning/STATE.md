---
gsd_state_version: 1.0
milestone: v1.23
milestone_name: Detail-Path Performance + UX Polish
status: ready_to_plan
last_updated: "2026-05-13T00:00:00.000Z"
last_activity: 2026-05-13
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
current_phase: 74
current_phase_status: not_started
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.23 Detail-Path Performance + UX Polish — close the three user-visible issues surfaced during v1.22 live MCP verification 2026-05-13 (cold-path card open 8-15s, card grid reflow on stepper morph, cart panel missing trash button). 3 phases (74-76), 7 requirements (2 PERF, 2 UX, 3 OPS).

## Current Position

Phase: v1.22 shipped + tagged + archived 2026-05-13. v1.23 REQUIREMENTS.md + ROADMAP.md drafted with 3 phases (74-76) and 7 requirements. Next: `/gsd-discuss-phase 74` for Product Details Cold-Path Latency, or direct plan if context is already clear.
Next step: Plan Phase 74 (PERF-10/11 — remove legacy per-proxy HEAD probe loop in `backend/main.py::product_details`, tighten httpx timeouts connect 4s→1s / read 6s→3s, add `data/detail_events.jsonl` ledger).
Status: v1.22 archived to `.planning/milestones/v1.22-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.22-phases/{70,71,72,73}-*/`. Tag `v1.22` pushed. 16 commits `5513ede..f56f285` (including Phase 72 `[hidden]` hotfix `825008c` and todo cleanup `f56f285`).
Last activity: 2026-05-13 — v1.22 closed, v1.23 scope defined, ready to plan Phase 74.

## Milestone Goal (v1.23 — active)

- Cold-path `GET /api/product/{id}/details` p95 ≤ 2s (PERF-10). Remove per-proxy HEAD probe loop (legacy pre-v1.15 SOCKS5-era artifact; xray `observatory`+`leastPing` already picks the fastest live outbound). Tighten httpx timeouts: connect 4s→1s, read 6s→3s. Keep 3 retries.
- `data/detail_events.jsonl` ledger emits one line per `/api/product/{id}/details` call with `{ts, product_id, duration_ms, cached, retry_count, outcome}` (PERF-11). Bounded file, tail-readable from admin, following v1.20 `cart_events.jsonl` pattern.
- Zero visible card-grid layout shift when product card's cart button morphs into quantity stepper (UX-SHIFT-01). Reserve stepper slot via fixed card min-height. Lighthouse CLS ≤ 0.1 on main page.
- Cart panel item rows gain a trash/remove button (UX-CART-01). Frontend wiring only — backend `cart.remove(product_id)` already exists. Optimistic UI with spinner, error toast on failure, panel refresh on success.
- `scripts/verify_v1.23.sh` grows phase-by-phase and chains `verify_v1.22.sh all` (which chains v1.21 + v1.20 + v1.19) so all five milestones' smoke gates stay green through v1.23 deploy (OPS-18/19/20).

## Previous Milestone (v1.22 — shipped 2026-05-13, tag `v1.22`)

- UX Debt Cleanup + Tooling Polish — 7/7 requirements + 1 late insert (UX-BADGE-02), 4 phases (70/71/72/73)
- 16 commits `5513ede..f56f285`, tag `v1.22` pushed to origin
- 3/4 phases live-verified on EC2 via Chrome DevTools MCP 2026-05-13 (Phase 73 is Kiro-side only, local 3/3 smoke green)
- Phase 72 shipped `[hidden]` hotfix `825008c` after live MCP caught a `.badge { display: inline-block }` override making badges show "(0)" when they should be invisible — v1.21 "push ≠ verified" lesson reinforced
- Archive: `.planning/milestones/v1.22-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.22-phases/{70,71,72,73}-*/`

## Next Up

- `/gsd-discuss-phase 74` or direct plan for Product Details Cold-Path Latency (PERF-10/11). Backend target: `backend/main.py::product_details` endpoint (lines ~525-625, two-phase probe loop) + pair with `backend/detail_service.py` existing cache.
- Phase 75 (UX-SHIFT-01) — CSS-only fix in `miniapp/src/App.jsx` + `miniapp/src/index.css` for card min-height slot reservation.
- Phase 76 (UX-CART-01) — trash button in `miniapp/src/CartPanel.jsx`, calls existing `POST /api/cart/remove`.
- After each phase: live MCP verification (v1.21 "push ≠ verified" lesson — code-review-only is insufficient for UI changes).
- Move consumed todos from `.planning/todos/pending/` to `.planning/todos/completed/` as each phase ships.
- After Phase 76: `.planning/v1.23-MILESTONE-AUDIT.md` + tag `v1.23` + archive. **STOP before `/gsd-complete-milestone`** per user's standing instruction.

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

## Accumulated Context

- v1.22 shipped: history search catalog-wide with `currentSaleType` field (Phase 70 UX-BUG-01), stale banner rescoped to `Источники устарели` with per-source age (Phase 71 UX-COPY-01), admin.html `Bug Reports (N)` + `Drift (N)` attention badges + `[hidden]` hotfix (Phase 72 UX-BADGE-01/02), `/gsd-check-todos` priority-aware triage with P1-first sort (Phase 73 TOOL-01)
- v1.21 shipped: admitted-node reprobe daemon every 10 min through bridge (REL-13), per-host success_rate tracking (REL-15), xray auto-reload via passwordless systemctl on admission-set diff (REL-14, 299ms live), `/api/health/deep` xray_drift block + `pool_refresh_complete` event schema (OBS-06/07)
- v1.20 shipped: 20-min keepalive daemon + on-open warmup nudge (PERF-03/04/05), per-user cart-items 12s cache + global scraper semaphore (PERF-06/07), USE_FAST_CART_ADD_ENDPOINT feature-flag scaffolding (PERF-08/09), frontend client_request_id idempotency + 5s AbortController + polling-on-abort (UX-01/02/03), `/api/health/deep` cart_add block + `data/cart_events.jsonl` 11-key ledger (OBS-04/05)
- v1.19 shipped: pre-flight VLESS probe + 3-state breaker + `/api/health/deep` + pool drift visibility
- User bug-report feature (modal with category/textarea/screenshot upload) discovered already shipped in production during v1.22 live verification — obsolete todo removed `f56f285`

### Pending Todos (see `.planning/todos/pending/`)

- **[P2]** `2026-05-13-product-details-cold-path-8-15s` — consumed into v1.23 PERF-10/11 (Phase 74). Moves to completed/ when 74 ships.
- **[P2]** `2026-05-13-card-ui-shift-on-details-load` — consumed into v1.23 UX-SHIFT-01 (Phase 75). Moves to completed/ when 75 ships.
- **[P3]** `2026-05-13-cart-panel-remove-trash-button` — consumed into v1.23 UX-CART-01 (Phase 76). Moves to completed/ when 76 ships.
- **[P4]** `2026-05-13-update-gsd-add-todo-skill` — deferred to a future `/gsd-quick`-able tooling task; not in v1.23 scope.

## Known Bugs

- (none open — v1.22 closed the UX debt list; v1.23 opens 3 fresh issues surfaced during the v1.22 live verification session, all scoped into phases 74/75/76)

## Timeline

| Event | Date |
|-------|------|
| v1.19 shipped + archived | 2026-05-05 |
| v1.20 milestone SHIPPED + ARCHIVED + TAGGED | 2026-05-12 |
| v1.21 milestone SHIPPED + ARCHIVED + TAGGED (299ms xray reload live) | 2026-05-12 |
| v1.22 milestone STARTED (UX Debt Cleanup + Tooling Polish, 4 phases, 7 reqs) | 2026-05-12 |
| v1.22 Phase 70 (History Search Catalog-Wide) shipped + live-verified | 2026-05-12 |
| v1.22 Phase 71 (Stale Banner Clarification) shipped + live-verified | 2026-05-12 |
| v1.22 Phase 72 (admin.html Bug Reports + Drift Badges + `[hidden]` hotfix) shipped + live-verified | 2026-05-12/13 |
| v1.22 Phase 73 (/gsd-check-todos Skill Polish) shipped locally | 2026-05-13 |
| v1.22 SHIPPED + ARCHIVED + TAGGED (16 commits `5513ede..f56f285`) | 2026-05-13 |
| v1.23 milestone STARTED (Detail-Path Performance + UX Polish, 3 phases 74-76, 7 reqs) | 2026-05-13 |

---
*Last updated: 2026-05-13 after v1.22 archived + tagged. v1.23 REQUIREMENTS.md + ROADMAP.md drafted. 3 new todos (card UI shift, trash button, cold-path latency) consumed into phases 74-76. Next: `/gsd-discuss-phase 74` or direct plan for Product Details Cold-Path Latency.*
