# Roadmap — VkusVill Sale Monitor

## Milestones

- ✅ **v1.0** Bug Fix & Stability — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1** Testing & QA — Phases 10-12 (shipped 2026-03-31)
- ✅ **v1.2** Price History — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3** Performance & Optimization — Phases 19-20 (shipped 2026-04-01)
- ✅ **v1.4** Proxy Centralization — Phases 21-23 (shipped 2026-04-01)
- ✅ **v1.5** History Search & Polish — Phases 24-26 (shipped 2026-04-01)
- ✅ **v1.6** Green Scraper Robustness — Phases 27-28 (shipped 2026-04-02)
- ✅ **v1.7** Categories & Subgroups — Phases 29-33 (shipped 2026-04-03)
- ✅ **v1.8** History Search Completeness — Phases 34-35 (shipped 2026-04-04)
- ✅ **v1.9** Catalog Coverage Expansion — Phases 36-38 (shipped 2026-04-04)
- ✅ **v1.10** Scraper Freshness & Reliability — Phases 39-42 (shipped 2026-04-05)
- ✅ **v1.11** Cart Responsiveness & Truth Recovery — Phases 43-45 (shipped 2026-04-06)
- ✅ **v1.12** Add-to-Cart 5s Hard Cap — Phase 46 (shipped 2026-04-08)
- ✅ **v1.13** Instant Cart & Reliability — Phases 47-51 (shipped 2026-04-16)
- ✅ **v1.14** Cart Truth & History Semantics — Phases 52-55 (shipped 2026-04-21)
- ✅ **v1.15** Proxy Infrastructure Migration — Phase 56 (shipped 2026-04-23)
- ✅ **v1.17** VLESS Timeout Hardening — Phase 57 (shipped 2026-04-25)
- ✅ **v1.18** Geo Resolver & Scraper Recovery — Phase 58 (shipped 2026-04-25)
- ✅ **v1.19** Production Reliability & 24/7 Uptime — Phases 59-61 (shipped 2026-05-05)
- ✅ **v1.20** Cart-Add Latency & User-Facing Responsiveness — Phases 62-66 + 66.1/.2/.3 (shipped 2026-05-12, tag `v1.20`)
- ✅ **v1.21** VLESS Pool Self-Healing & Reload Pipeline — Phases 67-69 (shipped 2026-05-12, tag `v1.21`)
- ✅ **v1.22** UX Debt Cleanup + Tooling Polish — Phases 70-73 (shipped 2026-05-13, tag `v1.22`)
- ⏳ **v1.23** Detail-Path Performance + UX Polish — Phases 74-76 (active, started 2026-05-13)

## v1.23 Detail-Path Performance + UX Polish (ACTIVE — started 2026-05-13)

Close the three user-visible issues surfaced during v1.22 live MCP verification 2026-05-13: cold-path card open taking 8-15 seconds, card grid reflow when details finish loading, cart panel missing a trash button. Two of three are UI polish; the cold-path fix is surgical backend work removing a legacy pre-v1.15 SOCKS5-era probe that duplicates what xray's leastPing already does.

Driving evidence from live MCP verification 2026-05-13:

| Area | Issue | Measured | v1.23 Phase |
|---|---|---|---|
| Detail fetch latency | First product card open takes 8-15s (cache-miss path) | ~16s first open, ~2s reopen | Phase 74 (PERF-10/11) |
| Card grid reflow | Card grows when stepper replaces cart-button, neighbors jump | Visible layout shift | Phase 75 (UX-SHIFT-01) |
| Cart panel removal | No trash button per row; user must navigate back to main page | UX friction observed | Phase 76 (UX-CART-01) |

**Goal:** Cold-path card open p95 ≤ 2 s. Zero card grid layout shift. Trash button on every cart row.
**Granularity:** Small
**Phases:** 3 (74-76)
**Requirements:** 7 (2 PERF, 2 UX, 3 OPS)

### Phases

- [ ] **Phase 74: Product Details Cold-Path Latency** — Remove the per-proxy HEAD probe loop in `backend/main.py::product_details`. Go straight to `127.0.0.1:10808` (xray bridge). Tighten httpx timeouts: connect 4s → 1s, read 6s → 3s. Keep 3 retries so flaky tail fetches recover. Rationale: xray `observatory` + `leastPing` (v1.17) already picks the fastest live outbound, v1.19 pre-flight probe already catches broken bridges, v1.21 reprobe daemon keeps admitted pool alive, and v1.21 REL-15 tracks per-node success_rate. The Python-side probe is legacy work at 4-12s cost. Pair with PERF-11 latency ledger so before+after is measurable. Smoke gate: live MCP + curl of 5 never-cached product_ids, assert p95 ≤ 2s. (PERF-10, PERF-11)

- [ ] **Phase 75: Card Grid Layout Shift Fix** — Reserve the quantity-stepper slot in the product card's fixed min-height so the "not-in-cart" state (just a cart button) and "in-cart" state (full stepper) occupy the same vertical space. Neighbors no longer reflow. CSS-only change to `miniapp/src/App.jsx` + `miniapp/src/index.css`. Smoke gate: Lighthouse CLS ≤ 0.1 on main page before vs after. (UX-SHIFT-01)

- [ ] **Phase 76: Cart Panel Trash Button** — Add a trash icon button to every row in `CartPanel.jsx`. Click fires `POST /api/cart/remove` (existing endpoint). Optimistic UI: disable + spinner during request, error toast + re-enable on failure, panel refresh on success. Frontend-only. Smoke gate: live MCP click on trash button removes item + cart count decrements correctly. (UX-CART-01)

### Phase Details

### Phase 74: Product Details Cold-Path Latency
**Goal:** Drop `GET /api/product/{id}/details` cold-path p95 from ~16 s to ≤ 2 s by removing redundant pre-v1.15 probe logic and matching httpx timeouts to healthy VLESS bridge profile.
**Depends on:** v1.22 closed (no direct infrastructure dependency, but cross-version regression gate must stay green).
**Requirements:** PERF-10, PERF-11 — plus continued OPS-18/19/20.
**Success Criteria:**
  1. [ ] `backend/main.py::product_details` no longer executes the per-proxy HEAD probe loop. Single code path: check cache → fetch via xray bridge → retry up to 3 times.
  2. [ ] httpx.Timeout tightened: connect 4.0 → 1.0, read 6.0 → 3.0. Retry loop preserves at 3.
  3. [ ] New `data/detail_events.jsonl` ledger: one line per request with `ts, product_id, duration_ms, cached (bool), retry_count, outcome`. Bounded file (pruned via same mechanism as `cart_events.jsonl`).
  4. [ ] Unit test: `backend/test_product_details_latency.py` mocks httpx and asserts the ledger records the happy path + cached path + failed path correctly.
  5. [ ] Live MCP: 5 synthetic cold-path fetches via `curl -w "%{time_total}"` against never-cached product_ids, p95 ≤ 2 s.
  6. [ ] v1.22 + v1.21 + v1.20 + v1.19 regression green.
**Plans:** TBD via `/gsd-plan-phase 74`

### Phase 75: Card Grid Layout Shift Fix
**Goal:** Eliminate the visible reflow when a product card morphs from "not-in-cart" (cart button) to "in-cart" (full stepper) state.
**Depends on:** Phase 74 not required; independent CSS work.
**Requirements:** UX-SHIFT-01 — plus continued OPS-18/19/20.
**Success Criteria:**
  1. [ ] Product card has a fixed min-height that accommodates the tallest of the two states (stepper). "Not-in-cart" state has small reserved space at the bottom.
  2. [ ] Grid row height no longer varies per-card, so adding an item to cart doesn't reflow neighbors.
  3. [ ] Lighthouse CLS score on main page ≤ 0.1 (measured before + after via DevTools MCP Performance trace).
  4. [ ] Regression pin: `miniapp/src/__tests__/card-layout.test.jsx` if Vitest is wired (else deferred to future Vitest phase and documented in VERIFICATION.md NEEDS_OPERATOR).
  5. [ ] Live MCP: add 3 products to cart, screenshot main page before/after, diff shows no shift.
**Plans:** TBD via `/gsd-plan-phase 75`

### Phase 76: Cart Panel Trash Button
**Goal:** Let users remove items directly from the cart panel without navigating back to the main page.
**Depends on:** nothing (backend `cart.remove(product_id)` already exists).
**Requirements:** UX-CART-01 — plus continued OPS-18/19/20.
**Success Criteria:**
  1. [ ] Every row in `CartPanel.jsx` has a trash icon button (🗑️ or SVG) on the right side.
  2. [ ] Click fires `POST /api/cart/remove` with `{user_id, product_id}`. Button disables + shows spinner during request.
  3. [ ] On success: row animates out, panel count decrements, toast confirms.
  4. [ ] On error: button re-enables, row stays visible, toast shows reason.
  5. [ ] Live MCP: click trash button, assert row disappears and main-page cart count decrements.
  6. [ ] No regression on main-page stepper-to-zero remove path.
**Plans:** TBD via `/gsd-plan-phase 76`

## v1.22 UX Debt Cleanup + Tooling Polish (SHIPPED 2026-05-13, tag `v1.22`)

Full scope shipped, 7/7 requirements + 1 late insert (UX-BADGE-02), 4 phases (70-73). Archive: `.planning/milestones/v1.22-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.22-phases/` (4 directories).

**Goal:** Close accumulated UX debt from v1.5/v1.10/v1.16 plus `/gsd-check-todos` skill polish.
**Shipped:** History search catalog-wide with `currentSaleType` live badges (Phase 70 UX-BUG-01), stale banner rescoped to `Источники устарели` with per-source age (Phase 71 UX-COPY-01), admin.html `Bug Reports (N)` + `Drift (N)` attention badges + `[hidden]` hotfix (Phase 72 UX-BADGE-01/02), `/gsd-check-todos` priority-aware triage (Phase 73 TOOL-01).

## v1.21 VLESS Pool Self-Healing & Reload Pipeline (SHIPPED 2026-05-12, tag `v1.21`)

Full scope shipped, 8/8 requirements, 3 phases (67-69). Archive: `.planning/milestones/v1.21-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.21-phases/` (3 directories).

**Goal:** Convert the 2026-05-10 manual fix into a deterministic self-healing loop with visible drift signal.
**Shipped:** Phase 67 (Admitted-Node Self-Healing Loop with reprobe daemon + REL-15 success_rate tracking), Phase 68 (xray Auto-Reload on Admission Change — live-verified with 299ms systemctl reload-or-restart), Phase 69 (Drift Visibility via `/api/health/deep` xray_drift block + `pool_refresh_complete` JSONL event schema completion).

## v1.20 Cart-Add Latency & User-Facing Responsiveness (SHIPPED 2026-05-12, tag `v1.20`)

Full scope shipped, 15/15 requirements, 6 phases + 3 late inserts. Archive: `.planning/milestones/v1.20-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT,SESSION-REPORT}.md` + `.planning/milestones/v1.20-phases/` (8 directories: 62-66, 66.1, 66.2, 66.3).

**Goal:** Cut cart-add p95 from 10.8s → ≤4s envelope, eliminate false-fail-then-double-add UX pattern.
**Shipped:** 20-min keepalive daemon + on-open warmup nudge (PERF-03/04/05), per-user cart-items cache + scraper semaphore (PERF-06/07), API surface spike scaffolding (PERF-08/09), frontend 5s-abort + polling + idempotency (UX-01/02/03), `/api/health/deep` cart_add block + `data/cart_events.jsonl` ledger (OBS-04/05), per-phase smoke gate + rollback rehearsal (OPS-09/10/11), late UX fixes (66.1 stale-color phantom strip, 66.2 cart stepper cache-hit fix, 66.3 warmup endpoint retune with 3× speedup live-verified).

## v1.19 Production Reliability & 24/7 Uptime (SHIPPED 2026-05-05)

18/18 requirements, 3 phases (59-61). Archive: `.planning/milestones/v1.19-*`. Goal: 24/7 uptime via pre-flight probe, 3-state breaker, pool drift visibility, `/api/health/deep` external endpoint.

## v1.18 Geo Resolver & Scraper Recovery (SHIPPED 2026-04-25)

Multi-provider geo chain (ipinfo.io → ipapi.co → ip-api.com) + scraper CDP-WS recovery helpers.

## v1.17 VLESS Timeout Hardening (SHIPPED 2026-04-25)

xray `policy` + `observatory` + `leastPing` + timeout alignment + `remove_proxy` rotation.

## v1.15 Proxy Infrastructure Migration (SHIPPED 2026-04-23)

VLESS+Reality via xray-core bridge replaces SOCKS5 pool.

## v1.14 Cart Truth & History Semantics (SHIPPED 2026-04-21)

Real cart-add, truthful states, history semantics fixed.

## v1.13 Instant Cart & Reliability (SHIPPED 2026-04-16)

Classified error_type, session metadata pre-cache, retry without refresh, optimistic state preserved.

## v1.12 Add-to-Cart 5s Hard Cap (SHIPPED 2026-04-08)

AbortController cap, time-budget polling, D3 background gate.

## v1.11 Cart Responsiveness & Truth Recovery (SHIPPED 2026-04-06)

5s add-to-cart budget, background reconciliation, cart diagnostics.

## v1.10 Scraper Freshness & Reliability (SHIPPED 2026-04-05)

Sale-session continuity, green-only cadence, per-source freshness, cached MiniApp hydration.

## v1.9 Catalog Coverage Expansion (SHIPPED 2026-04-04)

Catalog discovery, merge/backfill, parity reporting.

## v1.8 History Search Completeness (SHIPPED 2026-04-04)

Full local-catalog search, result-state labels, regression coverage.

## v1.7 Categories & Subgroups (SHIPPED 2026-04-03)

Group/subgroup hierarchy + drill-down + favorites + Telegram notifier.

## v1.6 Green Scraper Robustness (SHIPPED 2026-04-02)

Green scraper CDP modal loading + validation gates.

## v1.5 History Search & Polish (SHIPPED 2026-04-01)

Search normalization, fuzzy Cyrillic search, lazy image enrichment.

## v1.4 Proxy Centralization (SHIPPED 2026-04-01)

ProxyManager singleton across backend/cart/login flows.

## v1.3 Performance & Optimization (SHIPPED 2026-04-01)

Rendering + load speed improvements.

## v1.2 Price History (SHIPPED 2026-04-01)

16K+ products, predictions, detail analytics.

## v1.1 Testing & QA (SHIPPED 2026-03-31)

Test coverage groundwork.

## v1.0 Bug Fix & Stability (SHIPPED 2026-03-31)

Foundation bug fixes.
