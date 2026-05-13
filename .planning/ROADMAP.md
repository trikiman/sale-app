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
- ✅ **v1.23** Detail-Path Performance + UX Polish — Phases 74-76 (shipped 2026-05-13, tag `v1.23`)
- ✅ **v1.24** Pool Self-Heal Hardening + Outage UX — Phases 77-79 (shipped 2026-05-13, tag `v1.24`)
- ✅ **v1.25** Operator Visibility + Test Coverage — Phases 80-82 (shipped 2026-05-13, tag `v1.25`)
- ⏳ **v1.26** Miniapp Test Harness + Style Guide Debt Cleanup — Phases 83-85 (active, started 2026-05-13)

## v1.26 Miniapp Test Harness + Style Guide Debt Cleanup (ACTIVE — started 2026-05-13)

Close the long-standing Vitest/RTL gap (tech debt since v1.22) and use that safety net to refactor the 46 inline-style violations + 135 spacing-scale CSS entries baselined in v1.24 Phase 79 + v1.25 Phase 82. After refactor, promote both lint rules from WARN → ERROR so future regressions can't land. v1.25 Phase 82 explicitly deferred the inline-style refactor because "rushing risks UX regressions — v1.23 Phase 75 layout-shift fix could regress if inline styles get moved wrong." v1.26 builds the safety net first, then does the refactor.

Driving evidence:

| Area | Issue | v1.26 Phase |
|---|---|---|
| No component-level tests | Vitest/RTL never wired; v1.24 verifier carry-forward | Phase 83 (TEST-01/02/03) |
| 46 inline-style violations baselined | v1.25 Phase 82 deferred refactor pending safety net | Phase 84 (TOOL-05) |
| 135 spacing-scale CSS violations baselined | v1.25 Phase 82 added rule at WARN with `--max-warnings=150` cap | Phase 85 (TOOL-07/08) |
| Fresh-deploy empty-state misleading UX | v1.25 QA-08 pinned the edge case; copy still wrong | Phase 85 (UX-EMPTY-01) |

**Goal:** Vitest/RTL safety net + 46 inline-style and 135 spacing-scale CSS violations refactored to zero + lint rules promoted to ERROR + fresh-deploy empty-state copy fixed.
**Granularity:** Small
**Phases:** 3 (83-85)
**Requirements:** 8 (3 TEST, 3 TOOL, 1 UX, 3 OPS-continuity)

### Phases

- [ ] **Phase 83: Vitest/RTL Foundation + Critical Invariant Snapshots** — Install vitest + @testing-library/react + @testing-library/jest-dom + jsdom (TEST-01). CI `test-miniapp` job in `.github/workflows/lint-and-test.yml`. 4 snapshot tests pinning UX invariants: ProductCard 36px-min-height lock (v1.23 UX-SHIFT-01), CartPanel trash-button row (v1.23 UX-CART-01), stale-banner variants (dataStale vs staleAll), empty-vs-staleAll rendering (TEST-02). 3 unit tests — `normalizeUnit`, `getCartStep`, `isTelegramRuntime` — pinning v1.23 Phase 76 helpers shipped without coverage (TEST-03).

- [ ] **Phase 84: Inline-Style Refactor (TOOL-05)** — Refactor 46 inline-style violations using Phase 83 snapshots as safety net. Three treatments: extract-to-utility-class (cursor, opacity, grid-col-full, dim-text), convert-to-explicit-class-prop (priceColor → priceClass), keep-inline-with-justified-disable for genuinely dynamic values. Add 3-5 new utility classes to `miniapp/src/index.css`. After refactor, promote `react/forbid-dom-props` WARN → ERROR.

- [ ] **Phase 85: CSS Spacing-Scale Refactor + Lint Bump + Empty-State UX (TOOL-07/08 + UX-EMPTY-01)** — Migrate 135 raw pixel values in `miniapp/src/*.css` to CSS custom properties from style guide v2 Spacing Scale (add `--space-xxs` token for 2px). `rem` values → px equivalents → tokens. After refactor, promote `declaration-property-value-allowed-list` WARN → ERROR and drop both `--max-warnings=N` caps to `--max-warnings=0`. Bundle UX-EMPTY-01 fresh-deploy empty-state copy fix — backend `/api/products` emits `emptyReason: "scheduler_not_yet_produced_data"` when products=[] AND mtime<60s AND files-present-but-empty; frontend renders "Данные ещё не подгружены..." copy.

### Phase Details

### Phase 83: Vitest/RTL Foundation + Critical Invariant Snapshots
**Goal:** Vitest + RTL installed, CI runs snapshot + unit tests on every PR, 4 snapshot tests pin critical UX invariants, 3 unit tests cover v1.23 helpers.
**Depends on:** v1.25 Phase 82 CI workflow (adds new job to same file).
**Requirements:** TEST-01/02/03 + continued OPS-29/30/31.
**Success Criteria:**
  1. [ ] `miniapp/package.json` has `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` in `devDependencies`. `npm run test` and `npm run test -- --run` both work.
  2. [ ] `vitest.config.js` or `vite.config.js` configures `test.environment = 'jsdom'`, `globals = true`, setupFiles for `@testing-library/jest-dom`.
  3. [ ] `.github/workflows/lint-and-test.yml` gains `test-miniapp` job running `npm run test -- --run`.
  4. [ ] `miniapp/src/__tests__/ProductCard.test.jsx` — snapshot of ProductCard in `cart-button` state + `stepper` state, both with `min-height: 36px` preserved in rendered DOM.
  5. [ ] `miniapp/src/__tests__/CartPanel.test.jsx` — snapshot of CartPanel row with trash button visible.
  6. [ ] `miniapp/src/__tests__/StaleBanner.test.jsx` — snapshots for `dataStale && !staleAll`, `staleAll`, and empty-vs-staleAll rendering.
  7. [ ] `miniapp/src/__tests__/productMeta.test.js` — `normalizeUnit`, `getCartStep` unit tests.
  8. [ ] `miniapp/src/__tests__/isTelegramRuntime.test.js` — extracts + tests `isTelegramRuntime` logic from `CartPanel.jsx::handleClearAll`. Extract to `miniapp/src/isTelegramRuntime.js`.
  9. [ ] All tests green locally + in CI.
  10. [ ] v1.25 + earlier regression green.
**Plans:** TBD via `/gsd-plan-phase 83`

### Phase 84: Inline-Style Refactor (TOOL-05)
**Goal:** Refactor 46 inline-style violations from baseline to zero using Phase 83 snapshots as safety net. Promote `react/forbid-dom-props` WARN → ERROR.
**Depends on:** Phase 83 (snapshots must be green before touching inline styles).
**Requirements:** TOOL-05 + continued OPS-29/30/31.
**Success Criteria:**
  1. [ ] All 46 baselined inline-style violations from `docs/style-guide-debt.md` refactored to one of: utility class, explicit class prop, or justified-disable.
  2. [ ] 3-5 new utility classes added to `miniapp/src/index.css` (e.g. `.u-clickable`, `.u-dim-50`, `.u-grid-row-full`).
  3. [ ] Every `// eslint-disable-next-line react/forbid-dom-props` carries `-- JUSTIFIED(v1.26): <reason>` comment.
  4. [ ] `react/forbid-dom-props` bumped from WARN → ERROR in `miniapp/eslint.config.js`.
  5. [ ] `npm run lint -- --max-warnings=0` passes.
  6. [ ] All Phase 83 snapshots still green (no UX regression).
  7. [ ] `docs/style-guide-debt.md` updated to reflect zero inline-style debt.
  8. [ ] v1.25 + earlier regression green.
**Plans:** TBD via `/gsd-plan-phase 84`

### Phase 85: CSS Spacing-Scale Refactor + Lint Bump + Empty-State UX
**Goal:** Refactor 135 spacing-scale CSS violations to zero. Promote both lint rules to ERROR with `--max-warnings=0`. Fix fresh-deploy empty-state UI copy.
**Depends on:** Phase 84 (eslint rules at ERROR first, then stylelint).
**Requirements:** TOOL-07/08 + UX-EMPTY-01 + continued OPS-29/30/31.
**Success Criteria:**
  1. [ ] All 135 baselined `declaration-property-value-allowed-list` violations refactored to CSS custom properties.
  2. [ ] `miniapp/src/index.css` adds `--space-xxs: 2px` token (extends existing scale).
  3. [ ] `rem` values converted to px → tokens (0.5rem=`--space-sm`, 0.75rem=`--space-md`, 1rem=`--space-lg`, 2rem=`--space-2xl`).
  4. [ ] Non-scale values (6/10/14/20px) either migrated to nearest scale token or retained with `/* spacing-scale-deviation: <reason> */` comment.
  5. [ ] `declaration-property-value-allowed-list` bumped WARN → ERROR in `miniapp/.stylelintrc.json`.
  6. [ ] Both lint jobs in CI drop their `--max-warnings=N` caps to `--max-warnings=0`.
  7. [ ] Backend `/api/products` emits `emptyReason: "scheduler_not_yet_produced_data"` when products=[] AND all source mtimes<60s AND files present but empty.
  8. [ ] Frontend renders "Данные ещё не подгружены. Первый сбор начнётся через ~N минут." when `emptyReason === "scheduler_not_yet_produced_data"`.
  9. [ ] All Phase 83 snapshots still green.
  10. [ ] v1.25 + earlier regression green. `pytest backend/ + tests/` 412+ passing.
**Plans:** TBD via `/gsd-plan-phase 85`

## v1.25 Operator Visibility + Test Coverage (SHIPPED 2026-05-13, tag `v1.25`)

Full scope shipped, 10/13 requirements + REL-19 production hotfix, 3 phases (80-82). Archive: `.planning/milestones/v1.25-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.25-phases/` (3 directories). 16 commits `e76a78e..9d3d185`.

**Goal:** Close the "time-to-notice" gap — operator notified of pool outage via Telegram within 10 min. Escape hatches. Integration tests replay 2026-05-13 pattern. CI blocks regressions.
**Shipped:** Phase 80 (`backend/admin_alerts.py` raw Telegram Bot API alerts for pool-dead/breaker-transitions/xray-restart-failed + `/admin/vless/quarantine/clear` + `/admin/force-stale-all` endpoints, 19 unit tests), Phase 81 (`tests/test_collapse_replay.py` 2026-05-13 pattern replay + pool IO race test + staleAll-empty edge), Phase 82 (`.github/workflows/lint-and-test.yml` lint-miniapp + test-backend jobs, eslint baseline cleared 23 errors → 0, stylelint spacing-scale rule baselined 135 violations). **REL-19 hotfix** (`b65cde7`): production outage 00:04→01:13 — `_run_scraper_set` now always calls `ensure_pool()` before skip-vs-run decision; pinned by 2 regression tests. **UAT audit** (`.planning/UAT-AUDIT-2026-05-13.md`): 6 items surfaced, 1 P1 (Telegram config on EC2), 3 P2 observable, 2 P3 defer-safe. TOOL-05 deferred to v1.26.

## v1.24 Pool Self-Heal Hardening + Outage UX (SHIPPED 2026-05-13, tag `v1.24`)

Full scope shipped, 9/9 requirements + OBS-08 deferred to v1.25, 3 phases (77-79). Archive: `.planning/milestones/v1.24-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT,MILESTONE-VERIFICATION}.md` + `.planning/milestones/v1.24-phases/` (3 directories).

**Goal:** Pool recovery from ~1h to ≤10 min + zero empty grid during rebuild + style guide v2 enforcement tooling.
**Shipped:** Phase 77 (persistent quarantine + refresh throttle + rate-of-decline + scheduler graceful degrade), Phase 78 (`staleAll` API + per-card badge + prominent banner), Phase 79 (stylelint + eslint forbid-dom-props + 46-entry debt baseline). Verifier audit resolved 4 MUST-CONFIRM-IN-CODE items; final verdict PASS with honest scope framing ("time-to-recover reduced, time-to-notice deferred to v1.25").

## v1.23 Detail-Path Performance + UX Polish (SHIPPED 2026-05-13, tag `v1.23`)

Full scope shipped, 7/7 requirements + 1 late insert (UX-CART-02), 3 phases (74-76). Archive: `.planning/milestones/v1.23-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.23-phases/` (3 directories).

**Goal:** Close the three user-visible issues surfaced during v1.22 live MCP verification.
**Shipped:** Phase 74 (Cold-Path Product Details Latency — 25× improvement, p95 0.678s), Phase 75 (Card Grid Layout Shift Fix — `min-height: 36px` lock), Phase 76 (Cart Panel Trash Button + Clear-Cart Telegram Fallback). Plus style guide v2 upgrade (docs/miniapp-ui-style-guide.md `91a6e30`) capturing the rules that should have prevented the header visual-weight violation.

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
