# Phase 83 — Vitest/RTL Foundation + Critical Invariant Snapshots — CONTEXT

## Why

Close the long-standing Vitest/RTL gap (tech debt flagged by v1.22, v1.24 verifier, v1.25 Phase 82 scope decision). The 46 inline-style violations baselined in v1.24 Phase 79 + the 135 spacing-scale CSS violations baselined in v1.25 Phase 82 both need a safety net before refactor. v1.25 Phase 82 explicitly deferred TOOL-05 because "rushing the 46-site refactor without snapshot infrastructure risks UX regressions — v1.23 Phase 75 layout-shift fix could regress if inline styles get moved wrong." Phase 83 builds that safety net.

## Scope (in)

- `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` installed as `devDependencies` in `miniapp/`
- `vitest.config.js` (or vite.config merger) with `test.environment = 'jsdom'`, `globals: true`, setupFiles
- `miniapp/src/test-setup.js` importing `@testing-library/jest-dom/vitest`
- `npm run test` script — runs in watch mode locally; CI uses `npm run test -- --run`
- `test-miniapp` job added to `.github/workflows/lint-and-test.yml`
- **Extracted modules** (to make helpers testable):
  - `miniapp/src/cartStep.js` — extract `getCartStep` from `App.jsx` (App.jsx imports from new module)
  - `miniapp/src/isTelegramRuntime.js` — extract `isTelegramRuntime` logic from `CartPanel.jsx::handleClearAll`
- **Unit tests**:
  - `miniapp/src/__tests__/productMeta.test.js` — covers `normalizeUnit`, `isWeightedUnit`, `formatQuantity`, `parseQuantityInput`, `getCardMetaBadges`
  - `miniapp/src/__tests__/cartStep.test.js` — covers `getCartStep` (pulls from cartItem.step || cartItem.koef, falls back to 0.01 for weighted units, 1 for piece units)
  - `miniapp/src/__tests__/isTelegramRuntime.test.js` — covers runtime detection via `initData.length > 0`
- **Snapshot tests** (4 critical UX invariants):
  - `miniapp/src/__tests__/ProductCard.test.jsx` — "cart-button" state + "stepper" state; asserts rendered DOM contains `card-price-row` with `min-height` rule active (v1.23 UX-SHIFT-01 regression guard)
  - `miniapp/src/__tests__/CartPanel.test.jsx` — CartPanel rendered with 1+ items; asserts trash-button row is visible (v1.23 UX-CART-01 regression guard) + `🗑 Очистить` header button
  - `miniapp/src/__tests__/StaleBanner.test.jsx` — three renderings: `dataStale && !staleAll` (thin line), `staleAll` (prominent bordered card), and "fresh" (no banner)
  - `miniapp/src/__tests__/EmptyVsStaleAll.test.jsx` — four renderings: products list (normal), empty+fresh, empty+staleAll, preserved-products+staleAll

## Scope (out)

- **Playwright E2E tests** — separate concern (component-unit vs browser-integration); v1.27+ candidate
- **Full snapshot coverage of every component** — Phase 83 targets the 4 critical UX invariants, not exhaustive pinning. Additional snapshot coverage lands incrementally as v1.26 Phase 84/85 touch more components.
- **Refactor of the 46 inline-style sites** — that's Phase 84's work
- **Refactor of the 135 spacing-scale CSS entries** — that's Phase 85's work
- **Bumping lint rules to ERROR** — Phase 85 after all refactor lands

## Key Decisions

- **Snapshot strategy: Vitest inline snapshots via `toMatchInlineSnapshot()`** — keeps snapshots next to the assertion, easier code review, no `__snapshots__/` pollution. Alternative considered: external `.snap` files via `toMatchSnapshot()` — rejected for review friction.
- **ProductCard test: pass minimal mock props** — `product` + `cartItem` fixtures; mock `onAddToCart`, `onOpenDetail`, etc. as no-op vitest `vi.fn()`. Do not render full App context.
- **CartPanel test: render with mocked `fetch`** — use `vi.stubGlobal('fetch', vi.fn(...))` to return canned cart rows. Test both empty and populated states.
- **StaleBanner tests: extract from App.jsx** — the banner logic is inline in `App.jsx` return block. Phase 83 either (a) extracts a `StaleBanner` component OR (b) renders App with forced props. **Go with (a)** — extraction aligns with v1.26's "make testable" theme. Move banner markup to `miniapp/src/StaleBanner.jsx`, export `StaleBanner({ dataStale, staleAll, sourceFreshness })`.
- **CI job shape: matches lint-miniapp** — same `setup-node@v4` + `npm ci` + working-directory: `miniapp`. Add as third job alongside `lint-miniapp` and `test-backend`.
- **Skip the `App.test.jsx` megatest** — App.jsx is 1300+ LOC with global state, network, DOM effects. Full App rendering would be fragile and slow. Phase 83 tests target the components Phase 84/85 will actually touch.

## Inputs / dependencies

- **Existing miniapp build**: Vite 7 + React 19; no jest or vitest currently installed
- **Existing CI workflow**: `.github/workflows/lint-and-test.yml` from v1.25 Phase 82 — has `lint-miniapp` + `test-backend` jobs
- **Source files to test**:
  - `miniapp/src/App.jsx` — `ProductCard` at line 112, `getCartStep` at line 103, stale-banner logic at the `/api/products` response rendering site
  - `miniapp/src/CartPanel.jsx` — `handleClearAll` at line 114 with inline `isTelegramRuntime`
  - `miniapp/src/productMeta.js` — pure helpers, no extraction needed
- **Reference for CSS min-height invariant**: `miniapp/src/index.css` `.card-price-row` + `.cart-inline-qty.compact` rules from v1.23 Phase 75

## Risks

| Risk | Mitigation |
|---|---|
| Vitest picks up unintended files (conflicts with existing linter/build) | Scope `test.include` to `src/**/__tests__/**/*.{js,jsx}` + `src/**/*.test.{js,jsx}` |
| jsdom missing Telegram globals leaks window.Telegram from one test to the next | `beforeEach(() => { delete window.Telegram })` + document in test-setup.js |
| Extracting `getCartStep` / `isTelegramRuntime` from inline call-sites breaks existing behavior | Single commit per extraction, rebuild + manual smoke before moving on. Snapshot tests pin final behavior as regression guard. |
| Adding `StaleBanner.jsx` changes DOM subtly and breaks existing live UI | Extraction must produce byte-identical JSX to what App.jsx rendered. Validate via visual diff of pre/post HTML in jsdom + manual miniapp load. |
| CI node_modules caching across lint-miniapp and test-miniapp duplicates install | Both jobs use `actions/setup-node@v4` with `cache: npm` — GitHub handles cross-job cache reuse automatically |
| react-hooks `set-state-in-effect` warning threshold breaks when new test components are added | Tests render in jsdom, don't count toward production hooks; should not trip the 60-warning baseline |

## Success gate

- `cd miniapp && npm run test -- --run` prints `7 passed` (or more) and exits 0
- `cd miniapp && npm run lint -- --max-warnings=60` still passes (no regression from extractions)
- `cd miniapp && npm run build` still produces a working bundle
- CI `test-miniapp` job green on the PR commit
- Manual smoke: `npm run dev` locally → load miniapp → confirm ProductCard renders, CartPanel opens, stale-banner renders when data is stale, empty-state renders on filtered-to-zero

## Plans

- 83-01 Vitest install + config + CI job
- 83-02 Testable-helper extractions (getCartStep, isTelegramRuntime, StaleBanner) + unit tests
- 83-03 Snapshot tests for 4 critical UX invariants + smoke verification

---
*Context captured: 2026-05-13. Next: write 83-PLAN.md with these 3 plans, then execute.*
