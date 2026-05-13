# Phase 84 — Inline-Style Refactor (TOOL-05) — PLAN

## Goal

Refactor 46 inline-style violations from baseline to zero. Add 3–5 utility classes to `miniapp/src/index.css`. Promote `react/forbid-dom-props` from WARN → ERROR. Every Phase 83 snapshot stays green.

## Plans

### 84-01 — Utility classes + ProductCard + CartPanel

**Files touched:**
- `miniapp/src/index.css` — add utility classes
- `miniapp/src/ProductCard.jsx` — 2 sites (lines 38, 104)
- `miniapp/src/CartPanel.jsx` — 1 site (line 171)

**Specific refactors:**
- ProductCard.jsx:38 `<div className="card-image-wrap" onClick={...} style={{ cursor: 'pointer' }}>` → add `.u-clickable` class, apply it alongside existing className
- ProductCard.jsx:104 `<div className="absolute inset-0 skeleton" />` — examine site; this may be Tailwind-style utility already. Investigate whether the warning is from a different line.
- CartPanel.jsx:171 `<span className="cart-btn-spinner" style={{ width: 24, height: 24 }} />` → add `.cart-btn-spinner--lg` modifier class

**Verification:**
- `npm run test -- --run` → 70 tests green (ProductCard + CartPanel snapshots MUST still match)
- `npm run lint -- --max-warnings=60` → count drops by 3 (should be 48 warnings)
- `npm run build` → succeeds

**Commit:** `refactor(miniapp): inline-style -> utility classes in ProductCard + CartPanel (Phase 84-01)`

### 84-02 — App.jsx + ProductDetail.jsx

**Files touched:**
- `miniapp/src/App.jsx` — 10 sites (lines 1537, 1554, 1590, 1603, 1611, 1630, 1639, 1645, 2085, 2093)
- `miniapp/src/ProductDetail.jsx` — 9 sites (lines 152, 153, 157, 158, 166, 211, 212, 219, 225)
- `miniapp/src/index.css` — any additional utility classes the refactor surfaces

**Strategy:**
- Read each site; classify A/B/C per the taxonomy
- Most App.jsx sites are probably layout (grid, padding, margin) — extract to utility classes
- ProductDetail.jsx 152,153 and 211,212,219 are grouped — likely table/nutrition layout. Convert to one `.nutrition-row` / `.nutrition-cell` class.

**Verification:**
- `npm run test -- --run` → 70 tests green
- `npm run lint` → count drops by 19
- `npm run build` → succeeds
- Manual MCP check against production: open a product detail drawer + scroll main list — no visual regression

**Commit:** `refactor(miniapp): inline-style -> utility classes in App + ProductDetail (Phase 84-02)`

### 84-03 — HistoryPage + HistoryDetail + rule bump WARN → ERROR

**Files touched:**
- `miniapp/src/HistoryPage.jsx` — 10 sites (lines 47, 64, 90, 108, 124, 144, 173, 441, 512, 524)
- `miniapp/src/HistoryDetail.jsx` — 14 sites (lines 36, 64, 132, 133, 134, 135, 158, 179, 184, 229, 242, 274, 282, 290)
- `miniapp/eslint.config.js` — promote `react/forbid-dom-props` from `'warn'` to `'error'`
- `.github/workflows/lint-and-test.yml` — reduce `--max-warnings=60` to `--max-warnings=5` (retain headroom for react-hooks advisories; Phase 85 sets to 0)
- `docs/style-guide-debt.md` — update baseline count

**Strategy:**
- HistoryDetail chart bars (lines 132, 133, 134, 135 are clustered) likely represent chart bar widths with runtime values — justified-disable with `JUSTIFIED(v1.26): chart bar width driven by data value`
- HistoryPage sparkline widths at 441, 512, 524 — similar, justified-disable
- Other sites are static → utility classes

**Verification:**
- `npm run test -- --run` → 70 tests green
- `npm run lint -- --max-warnings=5` → passes (only react-hooks advisories remain)
- `npm run build` → succeeds
- Manual MCP check against production history page → chart rendering unchanged
- CI must go green on push

**Commit:** `refactor(miniapp): finalize inline-style refactor, promote forbid-dom-props to ERROR (Phase 84-03 + TOOL-05)`

## Definition of Done

- [ ] 46 → 0 unjustified inline-style violations
- [ ] 3–5 utility classes added to `index.css`, each tagged with `/* v1.26 Phase 84 */`
- [ ] Any justified-disable carries `-- JUSTIFIED(v1.26): <reason>` explanation
- [ ] `react/forbid-dom-props` at `'error'` in `eslint.config.js`
- [ ] All 70 Phase 83 tests green (no snapshot regressions)
- [ ] CI green after push
- [ ] `docs/style-guide-debt.md` updated
- [ ] Phase 84 SUMMARY.md written
- [ ] `.planning/STATE.md` advanced to `current_phase: 85`

---
*Plan written: 2026-05-14. Ready for execution.*
