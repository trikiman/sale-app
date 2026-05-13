# Phase 83 — Vitest/RTL Foundation + Critical Invariant Snapshots — SUMMARY

## Status

✅ **Shipped 2026-05-13**. 5 atomic commits, 70 tests passing, CI job added, lint + build green, live MCP-verified.

## Commits

| Commit | Plan | Purpose |
|---|---|---|
| `85f1105` | 83-01 | vitest + RTL + jsdom install, vite.config.js `test` block, test-setup.js, CI `test-miniapp` job |
| `a46f0b6` | 83-02 | extract `getCartStep` + `isTelegramRuntime` + 50 unit tests |
| `be38ec1` | 83-03 step 1 | extract ProductCard + cardConstants to own files |
| `ef96dda` | 83-03 step 2 | extract StaleBanner to own file |
| `9bbd5e7` | 83-03 step 3 | 4 snapshot-test files + __snapshots__/ directory, smoke test removed |

## Files added

**Tooling + config:**
- `miniapp/vite.config.js` — `test` block extended (jsdom env, globals, setupFiles, include paths)
- `miniapp/src/test-setup.js` — jest-dom matchers + per-test cleanup
- `miniapp/package.json` — devDeps: vitest@4.1.6, @testing-library/react@16.3.2, @testing-library/jest-dom@6.9.1, jsdom@29.1.1
- `.github/workflows/lint-and-test.yml` — `test-miniapp` job

**Extracted modules (unblocks Phase 84):**
- `miniapp/src/cartStep.js` — `getCartStep` from App.jsx
- `miniapp/src/isTelegramRuntime.js` — from CartPanel.jsx inline
- `miniapp/src/cardConstants.js` — `CATEGORY_EMOJIS`, `getCategoryEmoji`, `proxyImg`, `TYPE_CONFIG`
- `miniapp/src/ProductCard.jsx` — extracted from App.jsx (inline styles preserved for Phase 84)
- `miniapp/src/StaleBanner.jsx` — extracted from App.jsx

**Test files (7 total, 70 tests):**
- `miniapp/src/__tests__/productMeta.test.js` — 28 tests
- `miniapp/src/__tests__/cartStep.test.js` — 15 tests
- `miniapp/src/__tests__/isTelegramRuntime.test.js` — 7 tests
- `miniapp/src/__tests__/ProductCard.test.jsx` — 7 tests, 2 snapshots
- `miniapp/src/__tests__/StaleBanner.test.jsx` — 6 tests, 2 snapshots
- `miniapp/src/__tests__/CartPanel.test.jsx` — 6 tests, 1 snapshot
- `miniapp/src/__tests__/EmptyVsStaleAll.test.jsx` — 4 tests

**Snapshots:**
- `miniapp/src/__tests__/__snapshots__/ProductCard.test.jsx.snap`
- `miniapp/src/__tests__/__snapshots__/StaleBanner.test.jsx.snap`
- `miniapp/src/__tests__/__snapshots__/CartPanel.test.jsx.snap`

## Requirements coverage

- ✅ **TEST-01**: vitest + RTL + jsdom installed; `npm run test` runs locally; CI `test-miniapp` job added
- ✅ **TEST-02**: 4 snapshot test files pinning UX invariants (ProductCard min-height, CartPanel trash button, StaleBanner variants, empty-vs-staleAll composition)
- ✅ **TEST-03**: 3 unit-test files (productMeta, cartStep, isTelegramRuntime)
- ✅ **OPS-29/30/31**: build + lint + regression all green, continuity maintained

## Verification

**Local (Windows):**
- `npm run test -- --run`: 7 files, 70 tests green in 1.78s
- `npm run lint`: 0 errors, 51 warnings (exactly baseline — extractions split inline-style sites between App.jsx and ProductCard.jsx, total unchanged)
- `npm run lint:css`: 135 warnings (baseline, Phase 85 target)
- `npm run build`: 663ms, 43 modules, no bundle regression

**Live (MCP DevTools against production https://vkusvillsale.vercel.app/):**
- StaleBanner DOM matches snapshot contract exactly — `role="status"` + `aria-live="polite"` + `stale-banner-prominent` class + "Данные устарели" title + per-source age labels + "~N мин." recovery hint. Production was live-stale during verification (43 min) so the prominent variant rendered.
- ProductCard DOM structure intact — type badge, stale badge (⏳), discount badge, category-tint class, cart button with aria-label. 20+ cards rendered, grid layout stable.
- No React errors; no component crashes. 500s on local /api are backend-not-running (expected in Windows dev without EC2 tunnel).

**CI (will verify on next push):**
- `test-miniapp` job added alongside `lint-miniapp` + `test-backend`, running `npm run test -- --run`. Expected green on first push — smoke already confirmed locally on same Node 20 toolchain CI uses.

## Known deferrals / follow-ups

- None. Phase 83 scope shipped clean.
- Phase 84 starts from here: inline-style refactor with snapshot safety net in place. Target: 46 violations → 0, `react/forbid-dom-props` WARN → ERROR. Snapshots tolerate inline-style refactor as long as rendered DOM class names + structure stay identical — which is the whole point of the Phase 83 pin.

## Next

- Commit + push this SUMMARY.md + update STATE.md `current_phase_status: completed_pending_ci` + `last_activity: 2026-05-13`
- `/gsd-plan-phase 84` to begin inline-style refactor

---
*Phase 83 completed: 2026-05-13. 5 commits `85f1105..9bbd5e7` + docs commit to follow.*
