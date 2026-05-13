# Phase 84 — Inline-Style Refactor (TOOL-05) — CONTEXT

## Why

v1.24 Phase 79 baselined 46 inline-style eslint warnings via `react/forbid-dom-props`. v1.25 Phase 82 CI pinned the count at `--max-warnings=60` but deferred the refactor itself, because "rushing the 46-site refactor without snapshot infrastructure risks UX regressions — v1.23 Phase 75 layout-shift fix could regress if inline styles get moved wrong." Phase 83 built that safety net (Vitest + RTL + 4 critical-invariant snapshots + ProductCard + StaleBanner extractions). Phase 84 does the actual refactor, then promotes `react/forbid-dom-props` from WARN → ERROR.

## Violations map (46 sites, 6 files)

| File | Sites | Notes |
|---|---|---|
| `src/HistoryDetail.jsx` | 14 | Chart axis labels, tick marks, bar widths — lots of dynamic values |
| `src/App.jsx` | 10 | Category chips + assorted layout stragglers |
| `src/HistoryPage.jsx` | 10 | List-item meta spans, sparkline widths |
| `src/ProductDetail.jsx` | 9 | Image gallery sizing + nutrition layout |
| `src/ProductCard.jsx` | 2 | Card-image-wrap cursor + skeleton positioning |
| `src/CartPanel.jsx` | 1 | Loading spinner size |
| **Total** | **46** | — |

## Refactor taxonomy

Three treatments per the v1.26 scope decision:

### A. Extract to utility class (static, reusable patterns)
Candidates (Phase 83 scope note mentioned 3–5 new classes):
- `.u-clickable` — `cursor: pointer` (ProductCard:38, HistoryDetail:36)
- `.u-dim-50` — `opacity: 0.5` (if found)
- `.u-grid-col-full` — `grid-column: 1 / -1` (if found)
- `.u-spinner-lg` — `width: 24px; height: 24px` for CartPanel:171 loading spinner
- `.u-absolute-fill` — `position: absolute; inset: 0` (skeleton overlays)

These land in `miniapp/src/index.css` with `/* v1.26 Phase 84 */` comments so future cleanup is traceable.

### B. Convert to explicit prop-driven class (discrete value sets)
- Chart axis tick colors / type-specific colors → add CSS classes keyed by type, drop inline `style={{color: ...}}`
- `style={{width: "${pct}%"}}` on progress bars → consider CSS custom property (`--progress: 42%`) still needs inline style in the React tree but can use `style={{'--progress': '42%'}}` which is allowed under `forbid-dom-props` since it's a CSS variable

### C. Keep inline but justify (genuinely dynamic)
`// eslint-disable-next-line react/forbid-dom-props -- JUSTIFIED(v1.26): <reason>`

Expected candidates:
- Chart bar widths driven by data (`width: ${value*pixelsPerUnit}px`)
- Animation keyframe offsets based on list index (`animationDelay: ${index*30}ms`)
- Any computed gradient angle / color mix from runtime data

## Invariants to preserve

Every Phase 83 snapshot MUST stay green:
- `ProductCard.test.jsx.snap` — min-height 36px lock (v1.23 UX-SHIFT-01), 2 states
- `CartPanel.test.jsx.snap` — trash button row
- `StaleBanner.test.jsx.snap` — dataStale + staleAll variants

If refactor breaks a snapshot, fix the refactor — don't regenerate the snapshot unless the DOM change is intentional (e.g., a class rename) AND manually verified in the browser.

## Scope (in)

- 46 → 0 unjustified inline-style sites
- 3–5 new utility classes in `index.css` with comments
- Any `// eslint-disable ... -- JUSTIFIED(v1.26): ...` comments where inline is unavoidable
- Promote `react/forbid-dom-props` from `warn` → `error` in `miniapp/eslint.config.js`
- Drop `--max-warnings=60` cap for eslint in `.github/workflows/lint-and-test.yml` (at least down to ~5, the react-hooks advisory count; TOOL-08 in Phase 85 sets it to 0)
- Update `docs/style-guide-debt.md` to reflect zero inline-style debt

## Scope (out)

- Stylelint 135 spacing-scale violations — that's Phase 85 (TOOL-07)
- `--max-warnings=0` final lock — Phase 85 (TOOL-08)
- Fresh-deploy empty-state UX — Phase 85 (UX-EMPTY-01)
- React 19 `set-state-in-effect` refactor — v1.27+ (these 2 hooks warnings stay)
- Backend refactor — v1.26 is miniapp-only

## Plans

- **84-01**: Add utility classes to `index.css` + refactor ProductCard.jsx (2 sites) + CartPanel.jsx (1 site) — easiest sites, validates the pattern. Snapshot safety net lives directly on these two files, so any regression trips CI immediately.
- **84-02**: Refactor App.jsx (10 sites) + ProductDetail.jsx (9 sites) — medium complexity, uses prop-driven classes for type-specific chart colors.
- **84-03**: Refactor HistoryPage.jsx (10 sites) + HistoryDetail.jsx (14 sites) — chart-heavy; some will need justified-disable for genuinely dynamic widths. After refactor, bump rule WARN → ERROR + update style-guide-debt doc.

## Risks

| Risk | Mitigation |
|---|---|
| Snapshot tests break because class move subtly alters rendered DOM | Run `npm run test -- --run` after every file; if snapshot diffs, visually diff in browser before `-u`-ing |
| `--max-warnings=0` breaks CI before Phase 85 lands | Drop the cap only at the end of 84-03; current plan keeps eslint at `--max-warnings=5` (the react-hooks advisories) until Phase 85 |
| `style={{'--custom-prop': ...}}` still trips `forbid-dom-props` | Verified: `react/forbid-dom-props` flags *any* `style=` prop unless configured otherwise; use `setProperty` on a ref OR add `-- JUSTIFIED(v1.26): CSS-variable-only` comment |
| Visual regression in chart components | Phase 83 does NOT cover HistoryDetail charts — manual MCP verification against production after Phase 84-03 lands |

---
*Context captured: 2026-05-14. Next: write 84-PLAN.md, execute 84-01/02/03 atomically.*
