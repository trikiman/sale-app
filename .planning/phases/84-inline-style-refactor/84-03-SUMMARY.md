# Phase 84-03 + Phase 84 wrap-up — SUMMARY

## Status

✅ **Shipped 2026-05-15 02:56 MSK** as commit `bc537cf`. Vercel-deployed,
visually verified on the production miniapp at 03:09 MSK. **Phase 84
main goal closed at 46/46 inline-style sites.** `react/forbid-dom-props`
now ERROR. CI `--max-warnings` dropped from 60 → 10.

## Goal

Close the inline-style refactor (TOOL-05). Phase 84-01 + 84-02 had
landed 22 of 46 sites. Phase 84-03 closes the remaining 24 in
HistoryPage.jsx (10) + HistoryDetail.jsx (14), promotes the lint rule
to ERROR so new violations fail CI rather than accumulate as silent
warnings, and tightens the CI warning budget.

## Sites refactored (24 final, 46 total)

### HistoryPage.jsx (10 sites)

3 extracted to utility / domain classes:

| Line | Replacement |
|---|---|
| 47 | `.u-opacity-50` (no-data hint copy) |
| 519 | `.history-empty__icon` (empty-state emoji) |
| 530 | `.u-mt-3` (reset-filters CTA spacing) |

7 justified-disable with TODO(v1.27) for runtime-dynamic theme/data:

| Line | Reason |
|---|---|
| 49 | timeline bar height/opacity from `prob` |
| 65 | sparkline dot color from per-instance array |
| 95 | card outer theme tint conditional on `hasSales` |
| 113 | type badge background from `tc.badge` |
| 150 | price text color from `tc.text` |
| 130 | live-dot offset shifts when favorite is set |
| 449 | filter chip theme tint from `f.color` when active |

### HistoryDetail.jsx (14 sites)

3 extracted:

| Line | Replacement |
|---|---|
| 36 | `.hd-stroke-anim` (SVG ring transition) |
| 233 | `.hcard-skeleton--md` (hero loader skeleton height) |
| 245 | `.history-empty__icon` (error-state emoji, reused from HistoryPage) |

11 justified-disable with TODO(v1.27):

| Element | Reason |
|---|---|
| day chart bar | height/color/transition-delay all data-driven |
| calendar legend dots × 4 | TYPE_COLORS values |
| hour chart bar | height/transition-delay |
| sale-log dot | per-session-type color |
| sale-log type pill | per-session-type bg/text |
| hero price | per-type color |
| hero discount pct | per-type bg/text |
| hero type pill | per-type bg/text |

Every justified-disable carries a `TODO(v1.27): ... refactor via CSS custom properties` comment with a concrete remediation path.

## CSS additions (`miniapp/src/index.css`)

```css
.u-opacity-50              { opacity: 0.5; }
.u-mt-3                    { margin-top: 12px; }    /* 3 × 4px scale */
.history-empty__icon       { font-size: 48px; margin-bottom: 12px; }
.hd-stroke-anim            { transition: stroke-dashoffset 0.8s ease; }
.hcard-skeleton--md        { height: 120px; }
```

## Lint hardening

`miniapp/eslint.config.js`:
- `react/forbid-dom-props` bumped `'warn'` → `'error'`. New violations fail CI; existing violations are zero or annotated.

`.github/workflows/lint-and-test.yml`:
- `--max-warnings` dropped from 60 → 10. The remaining 5 warnings are pre-existing `react-hooks/set-state-in-effect` + `react-hooks/exhaustive-deps` advisories — bigger refactor scoped to v1.27. The 10 budget gives safety margin.

## Verification

- `npm test -- --run`: **70/70 passing** (Phase 83 snapshot tests = no visual regression).
- `npm run lint`: 48 → **5 warnings**, 0 errors (43-warning drop, under 10-budget).
- `npm run build`: vite 7.3.1 production build, **777ms**, 0 errors.
- Live miniapp on Vercel post-deploy at 03:09 MSK:
  - HistoryPage: 1866 products, all filter chips render, type badges + timeline columns + prediction times all visible.
  - HistoryDetail (after clicking a card): `hd-hero-price` + `hd-hero-pct` + `hd-type-pill` render with theme colors (justified-disables work), `hd-stroke-anim` CSS class works, 7 day-bar-fill + 24 hour-bar-fill + 4 calendar legend dots + 5 log dots all rendering correctly.

## Phase 84 — final tally

| Sub-phase | Sites | Commit | Status |
|---|---|---|---|
| 84-01 | ProductCard + CartPanel | `b8d4d30` | ✅ |
| 84-02 | App + ProductDetail | `4f7969b` | ✅ |
| 84-03 | HistoryPage + HistoryDetail + lint promotion | `bc537cf` | ✅ |

**46 of 46 inline-style sites refactored. `react/forbid-dom-props` ERROR active. CI warning budget at 10 (5 pre-existing react-hooks). Phase 84 main goal CLOSED.**

## Sidequests landed during Phase 84

These were necessary infrastructure work surfaced by EC2 production verification — none of them part of the original Phase 84 plan, but all required to deliver the user-visible "Обновлено: never > 5 min" target:

| Phase | Layer | Commits |
|---|---|---|
| 84.1 | VLESS pool recovery hardening (pre-probe dedup, graduated quarantine TTL, soft-tier release) | `7ad9b8f` |
| 84.2 | Multi-source aggregation (igareck + kort0881 + SoliSpirit) | `863a093` |
| 84.3 | Consensus voting in `verify_egress` | `a2db9f3` |
| 84.4 | TCP pre-filter + RU-only label gate | `d469080` |
| 84.5 | Robust scheduler (overshoot tolerance + stall recovery + 5-min threshold + Wants= systemd fix) | `2cf4f1c` + `76ed258` |
| 84.6 | Robust scrape_green.py (safe-click for SVG targets + mtime touch on suspicious-result safety guard) | `2fc0048` + `4fb8af1` |
| 84.7 | Per-color staleness thresholds (green=5, red=5, yellow=10) | `5919ef8` |

## v1.26 progress after Phase 84

| Phase | Status |
|---|---|
| 83 — Vitest/RTL Foundation + Critical Invariant Snapshots | ✅ shipped |
| 84 — Inline-Style Refactor (TOOL-05) + 7 sidequest fixes | ✅ shipped |
| 85 — CSS Spacing-Scale Refactor (TOOL-07/08) + UX-EMPTY-01 | ⏳ pending |

Phase 85 is the last phase of v1.26 (135 spacing-scale CSS violations → CSS custom properties from style guide v2, bump `declaration-property-value-allowed-list` WARN→ERROR, fix fresh-deploy empty-state UI copy).

## Files modified

- `miniapp/src/HistoryPage.jsx`
- `miniapp/src/HistoryDetail.jsx`
- `miniapp/src/index.css`
- `miniapp/eslint.config.js`
- `.github/workflows/lint-and-test.yml`
