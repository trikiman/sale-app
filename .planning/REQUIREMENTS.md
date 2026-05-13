# Requirements — v1.26 Miniapp Test Harness + Style Guide Debt Cleanup

## Milestone Goal

Close the long-standing Vitest/RTL gap (tech debt since v1.22) and use that safety net to refactor the 46 inline-style violations + 135 spacing-scale CSS debt entries baselined in v1.24 Phase 79 + v1.25 Phase 82. After refactor, promote both lint rules from WARN → ERROR so future regressions can't land. The v1.24 verifier and v1.25 Phase 82 scope decision both explicitly flagged that refactoring inline-styles without snapshot test coverage risks UX regressions (e.g., v1.23 Phase 75 layout-shift fix could be broken by a wrong style migration). v1.26 builds the safety net first, then does the refactor.

Driving evidence:
- **v1.24 verifier audit** (`.planning/milestones/v1.24-MILESTONE-VERIFICATION.md`): "Vitest/RTL full wiring" flagged as carry-forward
- **v1.25 Phase 82 scope decision**: TOOL-05 deferred because "rushing risks UX regressions — v1.23 Phase 75 layout-shift fix could regress if inline styles get moved wrong"
- **Live production state:** 46 eslint WARN + 135 stylelint WARN entries baselined in CI (`--max-warnings=60` + `--max-warnings=150` caps in `.github/workflows/lint-and-test.yml`). New violations still block PRs; existing ones accumulate.
- **v1.23 Phase 75 precedent:** `min-height: 36px` lock on `.card-price-row` + `.cart-inline-qty.compact` prevented card-grid layout shift. A careless inline-style refactor that moves those values wrong would silently break the layout. Snapshot tests would catch this.

## Requirements

### Miniapp Test Harness — Foundation

- [ ] **TEST-01**: Vitest + React Testing Library installed in `miniapp/`. `npm run test` runs the suite. CI's `test-miniapp` job added to `.github/workflows/lint-and-test.yml`. Matches the existing backend pytest integration pattern.

- [ ] **TEST-02**: Snapshot tests for the critical UX invariants — **(a)** `ProductCard` in both "cart-button" and "stepper" states with `min-height: 36px` preserved (v1.23 UX-SHIFT-01 regression guard); **(b)** `CartPanel` row with trash button (v1.23 UX-CART-01); **(c)** stale-banner variants: `dataStale && !staleAll` (thin line), `staleAll` (prominent bordered card per style guide v2); **(d)** empty state vs. `staleAll` + preserved products. Each snapshot pins the rendered DOM structure so a bad inline-style refactor trips CI.

- [ ] **TEST-03**: Unit tests for 3 pure helpers — `normalizeUnit`, `getCartStep`, `isTelegramRuntime` (the v1.23 UX-CART-02 runtime detector). Pins the logic Phase 76 shipped without unit coverage.

### Style Guide v2 Debt Refactor

- [ ] **TOOL-05**: Refactor the 46 inline-style violations from `docs/style-guide-debt.md` baseline. Each site gets one of three treatments:
  - **Extract to utility class** when the pattern is reusable (cursor, opacity, grid-col-full, dim-text). Add 3-5 new classes to `miniapp/src/index.css` (e.g. `.u-clickable`, `.u-dim-50`, `.u-grid-row-full`).
  - **Convert to explicit prop-driven class** when the value is discrete (e.g. `style={{color: config.priceColor}}` → `className={config.priceClass}`).
  - **Keep inline but justify** when value is genuinely dynamic (chart widths, animation offsets). Add `// eslint-disable-next-line react/forbid-dom-props -- JUSTIFIED(v1.26): <reason>` comment.
  Target: 46 → 0 unjustified. After refactor, bump `react/forbid-dom-props` from WARN → ERROR in `eslint.config.js`.

- [ ] **TOOL-07**: Refactor the 135 spacing-scale CSS violations from `docs/style-guide-debt.md`. Migrate raw pixel values to CSS custom properties from style guide v2 Spacing Scale section:
  - Replace `2px` → `var(--space-xxs)` (add this token, it's not in scale but needed)
  - Replace `4/8/12/16/24/32/48px` → `var(--space-xs/sm/md/lg/xl/2xl/3xl)` (already defined)
  - Replace `6/10/14/20px` → pick nearest scale token, document deviation if non-scale is intentional
  - `rem` values → convert to `px` equivalents then to tokens (0.5rem=8px=`--space-sm`, 0.75rem=12px=`--space-md`, 1rem=16px=`--space-lg`, 2rem=32px=`--space-2xl`)
  Target: 135 → 0. After refactor, bump `declaration-property-value-allowed-list` WARN → ERROR.

- [ ] **TOOL-08**: Add `--max-warnings=0` enforcement to both lint jobs in CI. Replaces the current `--max-warnings=60` and `--max-warnings=150` baseline caps. Future warnings block PRs.

### UX Polish

- [ ] **UX-EMPTY-01**: Fresh-deploy `staleAll=false + products=[]` edge case (v1.25 QA-08 baselined). Backend `/api/products` gains `emptyReason: "scheduler_not_yet_produced_data"` field when products is empty AND sourceFreshness mtime < 60s AND all files present-but-empty. Frontend renders "Данные ещё не подгружены. Первый сбор начнётся через ~N минут." instead of misleading "В этой категории пока нет товаров".

### Operations — Continuity

- [ ] **OPS-29**: `scripts/verify_v1.26.sh` chains `verify_v1.24.sh all`. (Note: `verify_v1.25.sh` wasn't written in v1.25 — Phase 81/82 relied on CI workflow instead. Starting the chain from v1.24 matches current state.)

- [ ] **OPS-30**: CI green post-refactor. Both `npm run lint` and `npm run lint:css` must pass with `--max-warnings=0`.

- [ ] **OPS-31**: Cross-version regression — `pytest backend/ + tests/` 412+ passing after v1.26 changes. Since this milestone is miniapp-only, backend regression should be near-zero.

## v2 Requirements (Deferred)

### Carried from earlier milestones

- **REL-FUT-01..04, REL-FUT-06..08, OBS-FUT-01..03** — v1.19 unaddressed
- **Phase 64 HAR capture + `FAST_CART_ADD_URL` go/no-go** (v1.20)
- **Playwright slow-path test** (v1.20 NEEDS_OPERATOR-1) — defer again; v1.26 scope is already full with Vitest + 181 refactor sites. Playwright is a separate testing concern (browser-integration vs component-unit).
- **`XRAY_RESTART_THROTTLE_S` persistence** (v1.21 tech debt)
- **`_DRIFT_FIRST_SEEN` persistence** (v1.21 tech debt)
- **Background pre-warm of product details** (v1.23 deferred)
- **React 19 set-state-in-effect refactor** (v1.25 Phase 82 baseline — 5 warnings) — bundle with TOOL-05 if trivial, else defer

### Explicit v1.27+ candidates

- Telegram alert action buttons (inline keyboards on admin DMs)
- SSE `/api/stream` graceful-shutdown on SIGTERM
- Multi-region scheduler failover
- Custom stylelint plugin for shorthand-value spacing-scale enforcement (if `declaration-property-value-allowed-list` proves insufficient after TOOL-07 cleanup)

## Out of Scope

| Feature | Reason |
|---|---|
| Playwright E2E tests | Separate scope — v1.26 focuses on component-level Vitest/RTL |
| Full design system rewrite | Refactor-in-place with style guide v2 tokens, not a new system |
| Backend refactor | v1.26 is miniapp-only; backend tests must stay at 412+ |
| New features | Pure debt cleanup + safety net |
| Admin panel visual redesign | Style guide v2 applies to miniapp only for now |

## Traceability

| Requirement | Provisional Phase | Status |
|---|---|---|
| TEST-01 | Phase 83 (Vitest foundation) | Defined |
| TEST-02 | Phase 83 (paired with TEST-01) | Defined |
| TEST-03 | Phase 83 (paired with TEST-01/02) | Defined |
| TOOL-05 | Phase 84 (inline-style refactor — uses Phase 83 snapshots) | Defined |
| TOOL-07 | Phase 85 (spacing-scale CSS refactor) | Defined |
| TOOL-08 | Phase 85 (pairs with TOOL-07 — lint bump) | Defined |
| UX-EMPTY-01 | Phase 85 (small UX polish, bundle with lint bump) | Defined |
| OPS-29/30/31 | All phases (cross-cutting) | Defined |

**Coverage:**
- v1.26 requirements: 8 total (3 TEST, 3 TOOL, 1 UX, 3 OPS-continuity)
- Mapped to phases: 8 (3 phases 83/84/85)
- Unmapped: 0 ✓

## Prior Milestone — Archived

v1.25 Operator Visibility + Test Coverage shipped 2026-05-13 with 10/13 requirements + REL-19 hotfix, 3 phases (80/81/82). 16 commits `e76a78e..9d3d185`. Full archive:
- `.planning/milestones/v1.25-ROADMAP.md`
- `.planning/milestones/v1.25-REQUIREMENTS.md`
- `.planning/milestones/v1.25-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.25-phases/{80,81,82}-*/`
- Git tag `v1.25`
- UAT audit `.planning/UAT-AUDIT-2026-05-13.md` — 6 items, 1 P1 (Telegram config), 3 P2 (observable), 2 P3 (defer-safe)

---
*Requirements defined: 2026-05-13*
*Prior milestone v1.25 archived 2026-05-13*
