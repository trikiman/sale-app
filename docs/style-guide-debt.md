# Style Guide v2 Debt — Baselined 2026-05-13 (v1.24 Phase 79)

This doc tracks existing violations of `docs/miniapp-ui-style-guide.md` v2 rules. Phase 79 added the enforcement tooling (stylelint + eslint `react/forbid-dom-props`) at WARN level so these surface in `npm run lint` without blocking CI. Target: v1.25 refactor milestone bumps rule severity to ERROR after this debt list is empty.

## Totals (baseline 2026-05-13, v1.25 Phase 82)

| Rule | Severity | Count (v1.24 baseline) | Count (v1.25 baseline) |
|---|---|---|---|
| `react/forbid-dom-props` (inline `style={}`) | `warn` | 46 | ~46 (App.jsx refactor deferred to v1.26) |
| `react-hooks/exhaustive-deps` | `warn` | 3 | 3 |
| `react-hooks/set-state-in-effect` | `warn` | 1 | 2 (one more surfaced) |
| `declaration-property-value-allowed-list` (CSS spacing scale) | `warn` | — | **135 (v1.25 Phase 82 TOOL-06 baseline)** |
| `no-unused-vars` errors | `error` | 23 | **0** (v1.25 Phase 82 fixed) |
| `no-empty` errors | `error` | 3 | **0** (v1.25 Phase 82 fixed via `allowEmptyCatch`) |

## Inline `style={}` Violations (46)

Run `npm run lint 2>&1 | grep "react/forbid-dom-props"` for current list.

### By file (from 2026-05-13 baseline)

- `src/App.jsx` — bulk of violations. Common patterns:
  - `style={{ gridColumn: '1/-1', ... }}` on full-width grid row placeholders → add `.grid-row-full` class
  - `style={{ opacity: 0.5 }}` for dimmed text → add `.text-dimmed` utility class
  - `style={{ cursor: 'pointer' }}` on clickable divs → use `<button>` or add `.clickable` class
  - `style={{ color: '<hex>' }}` — should reference `var(--sale-green|red|yellow)` per style guide v2 Color Tokens section
- `src/HistoryPage.jsx` — similar patterns
- `src/HistoryDetail.jsx` — chart-related inline styles (some legitimately dynamic; keep with `eslint-disable` + reason)
- `src/ProductDetail.jsx` — image gallery dynamic styles (legitimate — add disable with `TODO(v1.25): review if these can become classes`)
- `src/CartPanel.jsx` — already uses classes; minimal violations
- `src/main.jsx` — early-boot placeholder with 2 inline styles for the loading spinner (legitimate — runs before CSS loads; keep with disable)

### Refactor strategy (v1.25)

1. Extract common patterns to utility classes (e.g. `.grid-row-full`, `.text-dimmed`, `.clickable`)
2. Replace raw hex colors with `var(--sale-*)` references
3. For truly-dynamic styles (computed per-item), add `eslint-disable-next-line` with a `TODO(v1.25)` reason comment
4. After refactor, bump rule in `eslint.config.js` from `warn` → `error`

## Spacing Scale Violations (CSS)

`npm run lint:css` currently passes with the scale-enforcement rule **disabled** because the `declaration-property-value-allowed-list` with a single regex can't cleanly handle multi-value shorthand (`padding: 0 16px 32px`) without producing false positives.

**Options for v1.25:**
- Write a custom stylelint plugin that tokenizes shorthand values and checks each token against the scale
- Or manually audit + refactor existing CSS to use CSS variables (`var(--space-md)`) exclusively, then enable a stricter rule

**Current baseline:** `src/index.css` contains ~80 raw-pixel spacing values that predate style guide v2. Full audit deferred to v1.25.

## React Hooks Warnings (4)

- `ProductDetail.jsx:22` — `setLoading(true)` inside useEffect (cascading render risk)
- `ProductDetail.jsx:33` — missing dep `product`
- 2 more in App.jsx — review case-by-case in v1.25

These are React 19 + `react-hooks` plugin defaults; fixes are mechanical.

## How to resolve a single violation

1. Identify the line in `npm run lint` output
2. Refactor to use a CSS class (preferred) or `eslint-disable-next-line` with TODO:
   ```jsx
   // eslint-disable-next-line react/forbid-dom-props -- TODO(v1.25): chart needs dynamic width per sample
   <div style={{ width: `${percent}%` }} />
   ```
3. Remove from debt count; goal is zero warnings in v1.25

## When to bump rule severity

v1.25 Phase 82 progress:
- ✓ Cleared all 23 `no-unused-vars` errors (pragmatic: leading-underscore rename for props genuinely-unused)
- ✓ Cleared all 3 `no-empty` errors (via `allowEmptyCatch: true` — these were best-effort try/catch)
- ✓ CI wired via `.github/workflows/lint-and-test.yml` — blocks PRs on new errors
- ✓ Stylelint spacing-scale rule added at WARN (135-violation baseline)

v1.26 scope (proposed) — single milestone:
- Clear inline `style={}` debt (46 → 0 or all explicitly opted-out with TODO markers)
- Bump `react/forbid-dom-props` rule from `warn` → `error`
- Clear 135-violation spacing-scale CSS debt (refactor raw pixel values to CSS custom properties from style guide v2 Spacing Scale section)
- Bump `declaration-property-value-allowed-list` from WARN → ERROR
- Enable `--max-warnings 0` in CI once debt is clear
