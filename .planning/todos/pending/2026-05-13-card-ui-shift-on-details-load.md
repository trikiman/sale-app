---
created: 2026-05-13T01:10:00Z
title: Product card UI shifts/expands when details finish loading
area: ui
priority: P2
files:
  - miniapp/src/App.jsx
  - miniapp/src/index.css (likely — card grid layout)
---

## Problem

When a user opens a product card on the main page, the layout shifts visibly as the details finish loading. Observed 2026-05-13 on live Vercel:

- **Before tap**: card shows compact layout — image, name, price, weight chip, bottom-right cart icon.
- **During load**: clicked card shows hourglass/loading spinner in bottom-right.
- **After details loaded**: the SAME card expands and its neighbors shift to accommodate the "-1 шт +" quantity stepper control (now green, full-width). Adjacent cards jump left/right as the grid rebalances.

User-reported: "ui is bad why all shifted?"

## Root cause (hypothesis)

Two likely contributors:
1. **Card height is not fixed** — the card container's min-height grows when the stepper control replaces the simple cart button. This shifts every card below it in the grid.
2. **Grid uses auto-rows (not fixed row height)** — so one card growing pushes neighbors down.

CSS audit needed in `miniapp/src/index.css` or whatever the card grid class is. The React render is likely correct; the issue is the stylesheet rule that lets cards be variable-height.

## Solution

**Reserve the space up front.** Two approaches, either works:

**Option A — Fixed card min-height:**
- Give every card a `min-height` large enough to accommodate the stepper + weight chip + price + name + image.
- When the card is in "not-in-cart" state, there's a bit of blank space at the bottom. Acceptable.
- When the card flips to "in-cart" state, no layout shift because the height didn't change.

**Option B — Reserve stepper slot as invisible:**
- Always render the stepper slot in the DOM but visually hide it (`visibility: hidden`) when count is 0.
- Replace the current bottom-right cart icon with the stepper's size/shape.
- When count goes 0→1, toggle `visibility: visible`. No layout shift.

Option A is simpler (pure CSS). Option B is more precise (exact same DOM on both states).

**Recommended: Option A**, then measure CLS in Lighthouse/DevTools to confirm the shift score drops to near zero.

## Acceptance

- [ ] Tapping a product card and adding it to cart causes no visible shift of ANY other card in the grid.
- [ ] Lighthouse Cumulative Layout Shift (CLS) score for the main page ≤ 0.1 (good threshold).
- [ ] Card min-height doesn't introduce excessive empty space on short-text cards (visual check).
- [ ] Works on mobile + desktop viewports.

## Candidate for

v1.23 — pairs naturally with the product-details cold-path fix since both touch the same user interaction (tap card → open details → add to cart). Pure CSS change, ~10-20 LOC.
