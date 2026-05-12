# Phase 76 — Cart Panel Trash Button + Clear-Cart Fallback
**Milestone:** v1.23 Detail-Path Performance + UX Polish
**Requirements:** UX-CART-01 + UX-CART-02 (late insert)
**Started:** 2026-05-13

## Goal

1. **UX-CART-01:** Every cart panel row gets a **dedicated, always-visible trash button** that removes the item in one click, instead of the current "hold down minus until it magically becomes a trash emoji" UX.
2. **UX-CART-02 (late insert from 2026-05-13 live MCP):** The header **🗑 Очистить** (clear-all-cart) button responds when the user presses it in desktop Chrome. Currently silently hangs because the Telegram `showConfirm` Promise never resolves outside the Telegram runtime.

## Current State

### Cart row layout (CartPanel.jsx line ~218-225)

```jsx
<div className="cart-qty-controls">
    <button className="cart-qty-btn" onClick={() => quantity <= step ? handleRemove(item.id) : handleQuantity(item.id, -1)} disabled={isBusy}>
        {quantity <= step ? <span className="cart-qty-trash">🗑</span> : '−'}
    </button>
    <span className="cart-qty-value">{isBusy ? '…' : formatQuantity(item.quantity)}</span>
    <button className="cart-qty-btn" onClick={() => handleQuantity(item.id, 1)} disabled={isBusy || !item.can_buy || atMax}>+</button>
</div>
```

**Problem:** the minus button silently becomes a trash when quantity equals step. User has no visible "delete" affordance when quantity > step — they must decrement first, then notice the button changed emoji, then tap again. That's two taps minimum to remove an item with step=1, and more taps for step>1.

### handleClearAll (CartPanel.jsx line 113-132)

```js
if (window.Telegram?.WebApp?.showConfirm) {
    const ok = await new Promise(r => window.Telegram.WebApp.showConfirm('Очистить всю корзину?', r))
    if (!ok) return
} else if (typeof window.confirm === 'function') {
    try { if (!window.confirm('Очистить всю корзину?')) return } catch { /* blocked in TG */ }
}
```

**Problem:** detection of `window.Telegram.WebApp.showConfirm` is truthy even outside Telegram (the SDK script loads on every page). The `showConfirm` callback only fires inside Telegram WebView, so the Promise hangs forever in desktop Chrome. Native `window.confirm` fallback never runs.

## Decision

### UX-CART-01 — always-visible trash button

Add a dedicated 🗑 trash button to the right of the `[− qty +]` stepper. Layout:

```
[− qty +]  [🗑]
```

Clicking 🗑 always fires `handleRemove(item.id)` regardless of quantity. Existing "minus becomes trash at quantity ≤ step" shortcut stays — it still works — but users now have a clear always-visible remove affordance.

CSS: add `.cart-item-remove-btn` styled like `.cart-qty-btn` but with explicit trash styling (red hover).

### UX-CART-02 — clear-cart fallback

Replace the truthy-check with a proper Telegram-runtime detection via `window.Telegram?.WebApp?.initData`. When running outside Telegram, `initData` is `""` (empty string) even though the SDK mock exists. Detecting a non-empty `initData` tells us we're really inside Telegram WebView.

```js
const isTelegramRuntime = typeof window !== 'undefined'
    && typeof window.Telegram?.WebApp?.initData === 'string'
    && window.Telegram.WebApp.initData.length > 0

if (isTelegramRuntime && window.Telegram.WebApp.showConfirm) {
    const ok = await new Promise(r => window.Telegram.WebApp.showConfirm('Очистить всю корзину?', r))
    if (!ok) return
} else if (typeof window.confirm === 'function') {
    try { if (!window.confirm('Очистить всю корзину?')) return } catch { /* blocked */ }
}
```

Same detection pattern can be extracted into a small helper (`isTelegramRuntime()`) if we want to apply it to other `showPopup`/`showAlert` call sites later — but for v1.23 keep the change minimal and inline.

## Non-Goals

- **No refactor of existing `minus-becomes-trash` logic.** Keep it — it's an extra convenience on top of the new button.
- **No change to `/api/cart/remove` backend.** Endpoint is already live since earlier milestones.
- **No redesign of the cart row.** Same width, trash button slots in at the right edge.
- **No toast/confirmation dialog for per-row delete.** Instant action. User can decrement back up from zero if they mis-tap (the panel refresh will show the item gone, they'd have to navigate to the main grid to re-add — accepted friction for family-scale app).

## Files Touched

| File | Change |
|---|---|
| `miniapp/src/CartPanel.jsx` | Add 🗑 button per row + fix `handleClearAll` runtime detection |
| `miniapp/src/index.css` | Add `.cart-item-remove-btn` style |

Two files, ~15 LOC combined.

## Plan Order

1. **76-01**: Implement per-row trash + clear-cart fallback fix (both in one commit; CSS + JSX edit in two files, tightly coupled).
2. **76-02**: Live MCP verification + 76-VERIFICATION.md + move consumed todos (UX-CART-01 + UX-CART-02 fallback todo).

## Success Criteria

1. [ ] Each cart panel row has a visible 🗑 button to the right of the stepper.
2. [ ] Clicking 🗑 fires `POST /api/cart/remove` and the row disappears on refresh.
3. [ ] Stepper-minus-to-zero remove path still works (regression pin).
4. [ ] Header **🗑 Очистить** button in desktop Chrome now shows `window.confirm` dialog and clears cart on OK (UX-CART-02).
5. [ ] Inside Telegram WebView, clear-cart still uses native `showConfirm` (no UX regression).
6. [ ] Live MCP: click per-row trash, assert the row disappears + cart count decrements on the main page badge.
7. [ ] v1.22 + v1.23 Phase 74/75 cross-version smoke green.
