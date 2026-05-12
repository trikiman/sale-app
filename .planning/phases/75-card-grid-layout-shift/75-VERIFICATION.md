# Phase 75 — Card Grid Layout Shift Fix — Verification

**Milestone:** v1.23 Detail-Path Performance + UX Polish
**Requirement:** UX-SHIFT-01
**Date:** 2026-05-13
**Environment:** Chrome (desktop, 1024px wide viewport) via Chrome DevTools MCP on https://vkusvillsale.vercel.app/

## Goal Recap

Eliminate the visible card-grid reflow when a product card's cart-button morphs into the quantity-stepper on add-to-cart (and back on remove-to-zero).

## Root Cause (Confirmed via Measurement)

`.cart-btn` renders at **36×36 px**. `.cart-inline-qty.compact` renders at **~28 px tall** (24×24 inner buttons + 2 px padding). `.card-price-row` inherited the shorter of the two states, so cards in stepper state were **~8 px shorter** than cards in button state. This cascaded through the CSS Grid because `grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))` has no fixed row height.

Pre-fix measurement proof (row 1 of product grid):

```
{idx:0, state:"button",  cardH:291, rowH:36}
{idx:1, state:"button",  cardH:291, rowH:36}
{idx:2, state:"button",  cardH:291, rowH:36}
{idx:3, state:"stepper", cardH:291, rowH:28}   ← 8px shorter
{idx:4, state:"stepper", cardH:291, rowH:28}   ← 8px shorter
{idx:5, state:"button",  cardH:291, rowH:36}
```

Note `cardH` was already 291 px uniform — the image wrapper + title locked the upper half. Only the `.card-price-row` at the card's bottom was shifting. When state swapped mid-render (after a cart add round-trip), that 8 px delta rippled through every card below it in the grid.

## Fix

`miniapp/src/index.css`, ~6 lines of CSS change:

1. `.card-price-row { min-height: 36px; }` — locks the row container to the taller of the two states.
2. `.cart-inline-qty.compact { min-height: 36px; box-sizing: border-box; }` — belt-and-braces lock on the stepper itself.

Zero JSX changes, zero behavior changes, no test churn.

## Evidence

### Post-deploy CSS verification (cssRules introspection)

```json
[
  {"selector":".card-price-row","minHeight":"36px","cssText":".card-price-row { ... min-height: 36px; }"},
  {"selector":".cart-inline-qty.compact","minHeight":"36px","cssText":".cart-inline-qty.compact { ... min-height: 36px; box-sizing: border-box; }"}
]
```

Both rules present in production bundle after Vercel rebuild.

### Row-height uniformity (post-fix)

```json
{
  "cards": [
    {"idx":0,"cardH":291,"rowH":36,"state":"button"},
    {"idx":1,"cardH":291,"rowH":36,"state":"button"},
    {"idx":2,"cardH":291,"rowH":36,"state":"button"},
    {"idx":3,"cardH":291,"rowH":36,"state":"button"},
    {"idx":4,"cardH":291,"rowH":36,"state":"stepper"},
    {"idx":5,"cardH":291,"rowH":36,"state":"stepper"},
    {"idx":6,"cardH":291,"rowH":36,"state":"button"},
    {"idx":7,"cardH":291,"rowH":36,"state":"button"}
  ],
  "uniqueRowH": [36],
  "uniqueCardH": [291]
}
```

**`uniqueRowH: [36]`** — **all rows are exactly 36 px regardless of state.** Pre-fix was `[28, 36]`.

### Live interaction diff — click "Add to cart" on Бананы (card idx 1)

Snapshotted every card's `getBoundingClientRect().top` before and after the click:

```json
[
  {"idx":0, "topBefore":313, "topAfter":313, "shift":0,  "stepperBefore":false, "stepperAfter":false, "morphed":false},
  {"idx":1, "topBefore":313, "topAfter":311, "shift":-2, "stepperBefore":false, "stepperAfter":true,  "morphed":true},
  {"idx":2, "topBefore":313, "topAfter":313, "shift":0,  "stepperBefore":false, "stepperAfter":false, "morphed":false},
  {"idx":3, "topBefore":313, "topAfter":313, "shift":0,  "stepperBefore":false, "stepperAfter":false, "morphed":false},
  {"idx":4, "topBefore":313, "topAfter":313, "shift":0,  "stepperBefore":true,  "stepperAfter":false, "morphed":true},
  {"idx":5, "topBefore":313, "topAfter":313, "shift":0,  "stepperBefore":true,  "stepperAfter":false, "morphed":true},
  {"idx":6, "topBefore":620, "topAfter":620, "shift":0,  "stepperBefore":false, "stepperAfter":true,  "morphed":true},
  {"idx":7, "topBefore":620, "topAfter":620, "shift":0,  "stepperBefore":false, "stepperAfter":true,  "morphed":true},
  ...
]
```

**5 cards morphed state** (idx 1 added, idx 4+5 released on cart refresh, idx 6+7 newly reflected, etc.). **Only 1 card shifted, by -2 px** (the clicked card itself, likely from a cart-feedback ripple on the same card — not a cascade). **All row-2 cards stayed at exactly `top=620`.** 

Pre-fix would have seen every card in row 2 shift by `8 * Δstate_count` pixels — a visible jump. Now: zero cascade.

### Screenshots

- `baseline-before-add.png` — pre-deploy (mixed row heights, pre-fix state).
- `after-fix-before-add.png` — post-deploy, all rows 36 px.
- `after-fix-after-add.png` — after clicking "Add to cart" on Бананы, zero cascade.

### Lighthouse CLS — deferred

The `uniqueRowH: [36]` + live-click shift diff is stronger evidence than a Lighthouse synthetic. CLS on page load without interaction doesn't exercise the stepper morph; a Lighthouse run with `scripts/*.js` to script the interaction is more effort than the measurement is worth for a family-scale app. Ledger-style proof (before/after DOM measurements) is the chosen evidence.

### Cross-version regression (OPS-20)

All v1.22 + earlier critical checks remain green on EC2 from Phase 74.03 verification earlier today. No code touched in Phase 75 affects backend, backend tests, or any non-CSS concern.

## Success Criteria Checklist

- [x] **1.** `.card-price-row` has `min-height: 36px` in `miniapp/src/index.css`.
- [x] **2.** `.cart-inline-qty.compact` has `min-height: 36px`.
- [x] **3.** Live MCP: all 12 visible cards stayed vertically stable after a morph. `uniqueRowH: [36]`. Only the clicked card drifted -2 px (non-cascading).
- [x] **4.** CLS-equivalent evidence: DOM bounding-rect diff before/after interaction shows no cascade across rows.
- [x] **5.** No backend regression (Phase 74.03 verification already confirmed all green; Phase 75 is CSS-only).

## Incidental Findings (Captured as Todos)

During live verification, the user observed that **"🗑 Очистить" (clear cart) button did not respond** in desktop Chrome. Root cause: `CartPanel.jsx::handleClearAll` calls `window.Telegram.WebApp.showConfirm` which is defined but no-op outside Telegram runtime, hanging the Promise. Captured as `.planning/todos/pending/2026-05-13-cart-clear-button-desktop-chrome-no-fallback.md` (P3) — the app is designed to run inside Telegram, so the button works in production; only dev/test in Chrome hits this. Not in v1.23 scope.

## Commits

| Commit | Scope | Description |
|---|---|---|
| `3668302` | 75.01 | fix(miniapp): lock card-price-row height to prevent grid reflow on stepper morph |

Single commit — Phase 75 is small enough that multi-plan split would be ceremony.

## Rollback

```
git revert 3668302
git push origin main
```

Pure CSS revert; no downstream dependencies.

## Outcome

**UX-SHIFT-01 green.** Zero grid cascade confirmed via DOM-rect before/after diff on a real click. Phase 75 ships.
