# Phase 83 — Vitest/RTL Foundation + Critical Invariant Snapshots — PLAN

## Goal

Install and configure Vitest + React Testing Library in `miniapp/`. Add a CI `test-miniapp` job. Extract 2 helpers (`getCartStep`, `isTelegramRuntime`) + 1 component (`StaleBanner`) to make them testable. Write 3 unit tests + 4 snapshot tests pinning the UX invariants v1.23 shipped. Exit with a green CI PR and manual smoke proving nothing regressed.

## Requirements mapping

| Requirement | Plan |
|---|---|
| TEST-01 (Vitest + RTL + CI) | 83-01 |
| TEST-02 (4 snapshot tests) | 83-03 |
| TEST-03 (3 unit tests) | 83-02 |
| OPS-29/30/31 (continuity) | All plans — each commit green on lint + build, CI green at end |

## Plans

### 83-01 — Vitest install + config + CI job

**Files**:
- `miniapp/package.json` — add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` to `devDependencies`; add `"test": "vitest"` script
- `miniapp/vitest.config.js` (new) — `test.environment = 'jsdom'`, `globals: true`, `setupFiles: ['./src/test-setup.js']`, `include: ['src/**/__tests__/**/*.{js,jsx}', 'src/**/*.test.{js,jsx}']`
- `miniapp/src/test-setup.js` (new) — `import '@testing-library/jest-dom/vitest'` + `beforeEach(() => { delete window.Telegram })`
- `miniapp/src/__tests__/smoke.test.js` (new, temporary) — one `it('1+1 equals 2', () => expect(1+1).toBe(2))` to prove the harness runs
- `.github/workflows/lint-and-test.yml` — add `test-miniapp` job (setup-node@v4, npm ci in miniapp/, run `npm run test -- --run`)

**Steps**:
1. `cd miniapp && npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom`
2. Write `vitest.config.js` + `src/test-setup.js`
3. Add `"test": "vitest"` script to `package.json`
4. Write the smoke test
5. Run `npm run test -- --run` locally, assert `1 passed`
6. Add `test-miniapp` job to CI workflow
7. Commit as single atomic unit: `feat(miniapp): add Vitest + RTL foundation (TEST-01)`

**Verification**:
- `npm run test -- --run` → exit 0, smoke test passes
- `npm run lint -- --max-warnings=60` → exit 0 (test files included in eslint scan)
- `npm run build` → succeeds
- Push → CI test-miniapp job green

---

### 83-02 — Testable-helper extractions + unit tests (TEST-03)

**Files**:
- `miniapp/src/cartStep.js` (new) — export `getCartStep(unit, cartItem)` (identical logic from `App.jsx::getCartStep` at line 103)
- `miniapp/src/App.jsx` — replace inline `getCartStep` definition with `import { getCartStep } from './cartStep'`
- `miniapp/src/isTelegramRuntime.js` (new) — export `isTelegramRuntime()` (encapsulates `window.Telegram?.WebApp?.initData.length > 0`)
- `miniapp/src/CartPanel.jsx::handleClearAll` — replace inline `const isTelegramRuntime = ...` with `import { isTelegramRuntime } from './isTelegramRuntime'` + `if (isTelegramRuntime() && ...)`
- `miniapp/src/__tests__/productMeta.test.js` (new) — covers `normalizeUnit`, `isWeightedUnit`, `formatQuantity`, `parseQuantityInput`, `getCardMetaBadges`
- `miniapp/src/__tests__/cartStep.test.js` (new) — covers `getCartStep` across piece-unit, weighted-unit, cartItem-with-step, cartItem-with-koef, falsy-cartItem
- `miniapp/src/__tests__/isTelegramRuntime.test.js` (new) — covers `window.Telegram` undefined, `initData: ''` (empty), `initData: 'abc'` (non-empty)

**Test cases** (from productMeta):
- `normalizeUnit('kg')` → `'кг'`, `normalizeUnit('gr')` → `'гр'` (not in mapping — stays `'гр'`), `normalizeUnit('')` → `'шт'`, `normalizeUnit(null)` → `'шт'`, `normalizeUnit('шт')` → `'шт'`
- `isWeightedUnit('кг')` → true, `isWeightedUnit('шт')` → false
- `formatQuantity(0.5)` → `'0.5'`, `formatQuantity(1)` → `'1'`, `formatQuantity(0)` → `''`, `formatQuantity(NaN)` → `''`
- `parseQuantityInput('0.5', 'кг')` → `0.5`, `parseQuantityInput('0.5', 'шт')` → `null` (not integer for piece units), `parseQuantityInput('', ...)` → `null`, `parseQuantityInput('-1', 'кг')` → `null`
- `getCardMetaBadges({stock:0.5, unit:'кг'})` → `[{kind:'stock', text:'📦 0.5 кг'}]`

**Test cases** (cartStep):
- `getCartStep('кг', null)` → `0.01`
- `getCartStep('шт', null)` → `1`
- `getCartStep('шт', {step: 2})` → `2`
- `getCartStep('кг', {koef: 0.05})` → `0.05`
- `getCartStep('кг', {step: 0})` → `0.01` (falls back because step<=0)

**Test cases** (isTelegramRuntime):
- No `window.Telegram` → `false`
- `window.Telegram.WebApp.initData = ''` → `false` (this is the real-browser case)
- `window.Telegram.WebApp.initData = 'tgWebAppData=abc...'` → `true`

**Steps**:
1. Create `cartStep.js` + `isTelegramRuntime.js`
2. Update `App.jsx` import + remove inline definition
3. Update `CartPanel.jsx` import + rename local var to avoid shadowing
4. Write 3 test files
5. `npm run test -- --run` → 3 test files pass (and smoke still passes, 4 files total)
6. `npm run lint -- --max-warnings=60` → passes
7. `npm run build` → succeeds
8. **Manual smoke**: `npm run dev`, load miniapp at localhost, click "Очистить" in CartPanel + quantity stepper on a weighted product
9. Commit as atomic unit: `feat(miniapp): extract cartStep + isTelegramRuntime + unit tests (TEST-03)`

**Verification**:
- All tests green
- CartPanel "Очистить" still triggers confirm dialog in desktop Chrome
- ProductCard stepper still uses 0.01 step for `кг` products
- No bundle-size regression (Vite build reports no surprise)

---

### 83-03 — Snapshot tests for 4 critical UX invariants (TEST-02) + smoke verification

**Files**:
- `miniapp/src/StaleBanner.jsx` (new) — extract stale-banner JSX from App.jsx into `StaleBanner({ dataStale, staleAll, sourceFreshness })`; App.jsx replaces inline banner with `<StaleBanner ... />`
- `miniapp/src/__tests__/ProductCard.test.jsx` (new) — imports ProductCard (need to export it from App.jsx first, OR duplicate via targeted test harness)
  - *Problem*: ProductCard is defined inside App.jsx and not exported. **Resolution**: extract ProductCard to `miniapp/src/ProductCard.jsx` (new file), App.jsx imports it. This also unlocks Phase 84 — it's exactly the inline-style-heavy component that needs refactor with snapshot safety net.
- `miniapp/src/ProductCard.jsx` (new) — extracted from App.jsx lines 112-280; exports `ProductCard` memo; imports `getCartStep`, `normalizeUnit`, etc.
- `miniapp/src/App.jsx` — replace inline ProductCard with `import ProductCard from './ProductCard'`
- `miniapp/src/__tests__/ProductCard.test.jsx` (new) — render ProductCard in 2 states (cart-button, stepper); assert `.card-price-row` exists (CSS min-height rule stays live at runtime)
- `miniapp/src/__tests__/CartPanel.test.jsx` (new) — mock fetch to return 1 item; assert trash-button visible + "🗑 Очистить" header button exists
- `miniapp/src/__tests__/StaleBanner.test.jsx` (new) — 3 renderings: fresh (null), `dataStale && !staleAll`, `staleAll` with sources
- `miniapp/src/__tests__/EmptyVsStaleAll.test.jsx` (new) — renders App-like list with various combinations; uses `StaleBanner` + a small wrapper component
- `miniapp/src/__tests__/smoke.test.js` — **delete** now that real tests exist

**Snapshot strategy**: prefer `toMatchInlineSnapshot()` for stable readable diffs. For large ProductCard DOM, accept external `__snapshots__/*.snap` for ProductCard only; inline for the rest.

**Steps**:
1. Extract ProductCard to its own file (atomic commit 1): `refactor(miniapp): extract ProductCard to its own file`
   - Verify with `npm run build` + `npm run dev` manual load
2. Extract StaleBanner (atomic commit 2): `refactor(miniapp): extract StaleBanner to its own file`
   - Verify dev-mode banner still renders when data is stale
3. Write 4 snapshot test files (atomic commit 3): `feat(miniapp): snapshot tests for ProductCard/CartPanel/StaleBanner/empty-vs-staleAll (TEST-02)`
4. Run `npm run test -- --run` → 4+ test files pass
5. Delete `smoke.test.js`
6. Run full verification chain:
   - `npm run test -- --run`
   - `npm run lint -- --max-warnings=60`
   - `npm run lint:css -- --max-warnings=150`
   - `npm run build`
7. **Manual smoke**: `npm run dev` → load miniapp → confirm ProductCard renders identically to before extraction, stepper still works, stale-banner still renders, empty state still renders
8. Push → CI test-miniapp job green
9. Mark phase complete

**Verification**:
- 7+ test files green (3 unit + 4 snapshot)
- `ProductCard.jsx` extraction is behaviorally identical (manual compare in dev mode)
- `StaleBanner.jsx` renders same markup as old inline version
- CI test-miniapp job green
- Final commit on the Phase 83 feature branch merged to main

---

## Commit shape

Per-plan atomic commits as specified above. Phase 83 lands ≥4 commits:

1. `feat(miniapp): add Vitest + RTL foundation (TEST-01)` — 83-01
2. `feat(miniapp): extract cartStep + isTelegramRuntime + unit tests (TEST-03)` — 83-02
3. `refactor(miniapp): extract ProductCard to its own file` — 83-03 step 1
4. `refactor(miniapp): extract StaleBanner to its own file` — 83-03 step 2
5. `feat(miniapp): snapshot tests for 4 critical UX invariants (TEST-02)` — 83-03 step 3

Each commit ships green on `npm run build` + `npm run lint` + (after 83-01) `npm run test -- --run`.

## Definition of Done

- [ ] vitest + RTL installed, `npm run test` works locally + CI
- [ ] `getCartStep`, `isTelegramRuntime`, `ProductCard`, `StaleBanner` all in own files
- [ ] 3 unit tests + 4 snapshot tests, all passing
- [ ] CI `test-miniapp` job green on latest main
- [ ] `npm run build` succeeds (no bundle regression)
- [ ] `npm run lint -- --max-warnings=60` + `npm run lint:css -- --max-warnings=150` both pass
- [ ] Manual smoke: miniapp loads + ProductCard/CartPanel/StaleBanner behave identically to pre-Phase-83
- [ ] Phase 83 SUMMARY.md written capturing what landed
- [ ] `.planning/STATE.md` advanced to `current_phase: 84` once phase complete

---
*Plan written: 2026-05-13. Ready for execution.*
