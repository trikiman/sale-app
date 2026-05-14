# Phase 84-02 — App.jsx + ProductDetail.jsx inline-style refactor — SUMMARY

## Status

✅ **Shipped 2026-05-14** as commit `4f7969b`. 19 inline-style sites refactored to utility / domain classes. 70/70 vitest tests passing (Phase 83 snapshots = no visual regression). Lint warnings 48 → 29 (exact 19-warning drop). Vite build 889ms 0 errors. Visually verified on Vercel-deployed miniapp post-push.

## Goal

Continue Phase 84 (TOOL-05): refactor 46 inline-style violations to zero. Phase 84-01 closed 3 sites (ProductCard + CartPanel). Phase 84-02 closes the next 19 in App.jsx (10) + ProductDetail.jsx (9). Phase 83 snapshot tests are the safety net.

## Commit

| Commit | Purpose |
|---|---|
| `4f7969b` | App.jsx + ProductDetail.jsx + index.css updates |

## Sites refactored

### App.jsx (10 sites)

| Line | Description | Replacement |
|---|---|---|
| 1537 | Suspense fallback (HistoryDetail) | `.suspense-fallback` |
| 1554 | Suspense fallback (HistoryPage, duplicate) | `.suspense-fallback` |
| 1590 | Browser-link banner outer flex | `.link-banner.link-banner--browser` |
| 1603 | "Открыть сайт в браузере" underline span | `.u-underline-2` |
| 1611 | Telegram-link banner outer flex | `.link-banner` |
| 1630 | Telegram-link clickable action | `.link-banner__action` |
| 1639 | "для уведомлений" hint span | `.link-banner__hint-soft` |
| 1645 | Banner dismiss button reset | `.link-banner__dismiss` |
| 2085 | Infinite-scroll sentinel | `.products-grid__load-more` |
| 2093 | Empty-state grid copy | `.u-grid-row-full` |

### ProductDetail.jsx (9 sites)

| Line | Description | Replacement |
|---|---|---|
| 152 | `.detail-loading` vertical-padding override | `.detail-loading--vertical` modifier |
| 153 | Cart spinner sized for detail | `.cart-btn-spinner--detail` |
| 157 | Error-state container | `.detail-error-state` |
| 158 | Error message paragraph | `.detail-error-msg` |
| 166 | VkusVill CTA in error state (was unnamed) | `.detail-vkusvill-link` (folded inline → existing class) |
| 211 | Section: unavailable variant | `.detail-section--unavailable` modifier |
| 212 | Inline "временно недоступна" message | `.detail-section-msg` |
| 219 | Section: center variant for footer link | `.detail-section--center` modifier |
| 225 | VkusVill CTA in success state (had partial class) | `.detail-vkusvill-link` (folded inline → existing class) |

## CSS additions (`miniapp/src/index.css`)

### General utilities (in the existing Phase 84 `.u-*` block)

- `.u-underline-2` — text-decoration underline + 2px offset
- `.u-grid-row-full` — `grid-column: 1 / -1`
- `.suspense-fallback` — full-viewport centered loader
- `.link-banner` (+ `--browser` modifier) — header-region link banner shared by Telegram + browser variants
- `.link-banner__action` / `__hint-soft` / `__dismiss` — element subclasses
- `.products-grid__load-more` — full-row sentinel with padding/opacity

### ProductDetail rules (extending the existing `.detail-*` block)

- `.detail-loading--vertical` — `padding: 24px 0` override of base (which uses 24px all sides)
- `.cart-btn-spinner--detail` — 24×24 with `margin: 0 auto 8px`
- `.detail-error-state` / `.detail-error-msg`
- `.detail-section--center` / `.detail-section--unavailable`
- `.detail-section-msg` — short inline message (distinct from `.detail-section-body` paragraph)
- `.detail-vkusvill-link` — full styling folded into existing class so both call sites use the same rule

Style guide v2 invariant respected: all new utility classes are documented inline; domain-specific classes live near the existing component blocks they extend.

## Verification

- `npm test -- --run`: **70/70 passing** (incl. all Phase 83 snapshot tests covering ProductCard, CartPanel, StaleBanner, EmptyVsStaleAll). Snapshot tests are the safety net for visual regressions.
- `npm run lint`: 48 → **29 warnings** (exact 19-drop matches plan; remaining 29 are HistoryPage + HistoryDetail sites for Phase 84-03 + a few non-style React-hooks warnings).
- `npm run build`: vite 7.3.1 production build succeeds in 889ms, 0 errors.
- Live miniapp on Vercel post-deploy: Telegram-link banner renders correctly (`🔔 Привязать Telegram для уведомлений ✕`), product cards render, infinite-scroll sentinel ("Загружаем ещё 24 из 124…") renders. No visual breakage.

## Phase 84 progress

| Sub-phase | Sites | Status |
|---|---|---|
| 84-01 | ProductCard + CartPanel (3) | ✅ shipped (`b8d4d30`) |
| 84-02 | App.jsx + ProductDetail.jsx (19) | ✅ shipped (`4f7969b`, this) |
| 84-03 | HistoryPage + HistoryDetail (24) + bump `react/forbid-dom-props` WARN→ERROR | ⏳ pending |

**22 of 46 sites done.** Phase 84 main goal still in progress.

## Sidequests landed during Phase 84

These were necessary infrastructure work surfaced by EC2 production verification:

- **Phase 84.1** (`7ad9b8f`) — VLESS pool recovery hardening (pre-probe dedup, graduated quarantine TTL, soft-tier release).
- **Phase 84.2** (`863a093`) — Multi-source aggregation (igareck + kort0881 + SoliSpirit).
- **Phase 84.3** (`a2db9f3`) — Consensus voting in `verify_egress` (3-provider majority).
- **Phase 84.4** (`d469080`) — TCP pre-filter + RU-only label gate. Closed pool-starvation regression.
- **Phase 84.5** (`2cf4f1c` + `76ed258`) — Robust scheduler: green-only overshoot tolerance + stall recovery + 5-min freshness threshold + systemd `Wants=` cascade fix.

## Discovery during Phase 84-02 verification

EC2 verification at 23:39 MSK showed green file 31m old, stale banner active. Root cause is **NOT** Phase 84-02 — the inline-style refactor itself is fine and visually verified. The staleness is caused by a **pre-existing bug in `scrape_green.py`**:

- Phase 84.5 stall recovery is firing exactly as designed (every 5 min when file > 4 min old).
- Each forced retry runs `_close_delivery_modal()`, which fails with `TypeError: btn.click is not a function` and exits the scraper with code 1.
- The underlying issue: `[class*="close"]` selectors can match SVG elements where `.click()` is not a function in the same way as on `HTMLElement`.

Filed as Phase 84.6 — a tiny safe-click helper makes the scrape robust against any element type. Will ship next as a separate atomic commit.

## Files modified

- `miniapp/src/App.jsx`
- `miniapp/src/ProductDetail.jsx`
- `miniapp/src/index.css`
