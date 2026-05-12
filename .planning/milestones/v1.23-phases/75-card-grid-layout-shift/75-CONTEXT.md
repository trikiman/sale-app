# Phase 75 — Card Grid Layout Shift Fix
**Milestone:** v1.23 Detail-Path Performance + UX Polish
**Requirement:** UX-SHIFT-01
**Started:** 2026-05-13

## Goal

Zero visible card-grid reflow when a product card's cart button morphs into the quantity stepper (on add-to-cart success) and back (on remove-to-zero). Cards in rows below the changed card must not shift vertically.

## Problem

Live MCP 2026-05-13 on https://vkusvillsale.vercel.app/: user adds product → card updates from "cart button" UI to "stepper" UI → **neighbor cards in other rows visibly shift**. Same on remove-to-zero.

## Root Cause

Measured in `miniapp/src/index.css`:

- `.cart-btn` (rendered when `cartItem.quantity == 0`): `width: 36px; height: 36px;` — rounded button
- `.cart-inline-qty.compact` (rendered when `cartItem.quantity > 0`): `min-width: 90px; padding: 2px;` — **no fixed height**; inner buttons are `24px × 24px`, so the control renders at roughly 28px tall

Swap direction height delta: **~8 px per card.** `.card-price-row` uses `display:flex; align-items:center;` with no explicit min-height, so it inherits the taller of the two children. When the row shrinks by ~8px, `.card-body` shrinks, `.card-vertical` shrinks, and every card below it in the CSS Grid (`grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`) flows up by 8px. Multiply by 3 cards toggled × 60 visible below = a jarring ripple.

## Decision

**Lock `.card-price-row` to a fixed `min-height` matching the taller state.** CSS-only, zero JSX changes, zero behavior changes, zero test churn.

### Specific Fix

```css
.card-price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  min-height: 36px;    /* match .cart-btn height so the stepper-swap */
                       /* never changes row height */
}
```

And belt-and-braces on the stepper itself so its internal rendering can't dip below 36px even if a future change tweaks button sizes:

```css
.cart-inline-qty.compact {
  min-width: 90px;
  padding: 2px;
  min-height: 36px;    /* NEW — lock compact stepper to cart-btn parity */
}
```

Dual lock: the row's floor + the stepper's floor. If either regresses in isolation, the other still prevents the shift. Defense-in-depth is cheap for CSS.

## Non-Goals

- **No refactor of CartQuantityControl.** Component stays; only its visual height floor is enforced externally.
- **No card-wide min-height change.** Image wrapper + title already lock the upper half; only the footer swap was shifting.
- **No visual restyle.** The cart button stays 36×36; the stepper stays ~90px wide. Only the *height floor* is added to the row container.
- **No Vitest wiring.** Vitest for miniapp is v1.22 tech debt deferred to a future milestone (per v1.23 REQUIREMENTS.md "Out of Scope"). Live MCP validation is the gate.

## Files Touched

| File | Change |
|---|---|
| `miniapp/src/index.css` | Add `min-height: 36px` to `.card-price-row` and `.cart-inline-qty.compact` |

One file, two rules. ~2 lines added.

## Plan Order

Single atomic commit under Plan 75-01. Phase 75 is small enough that multi-plan split would be ceremony without benefit.

1. **75-01**: CSS min-height fix + live MCP verification.

## Success Criteria

1. [ ] `.card-price-row` has `min-height: 36px` in `miniapp/src/index.css`.
2. [ ] `.cart-inline-qty.compact` has `min-height: 36px`.
3. [ ] Live MCP: screenshot main page → add 3 products to cart → screenshot again. Diff shows no vertical shift of neighboring cards.
4. [ ] Lighthouse Cumulative Layout Shift (CLS) ≤ 0.1 on main page via DevTools Performance trace around the cart-add interaction.
5. [ ] No regression: v1.22 cross-version smoke stays green on EC2.
6. [ ] No regression: existing 110 backend tests stay green (CSS change doesn't touch backend but full suite is cheap to run).
