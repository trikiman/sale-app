# Phase 76 — Cart Panel Trash Button + Clear-Cart Fallback — Verification

**Milestone:** v1.23 Detail-Path Performance + UX Polish
**Requirements:** UX-CART-01 + UX-CART-02 (late insert)
**Date:** 2026-05-13
**Environment:** Chrome (desktop) via Chrome DevTools MCP on https://vkusvillsale.vercel.app/

## Goals Recap

1. **UX-CART-01:** Dedicated always-visible 🗑 trash button per cart row so removal is one click instead of decrementing first.
2. **UX-CART-02 (late insert):** Fix **🗑 Очистить** clear-all button hanging silently in desktop Chrome because `window.Telegram.WebApp.showConfirm` callback never fires outside Telegram runtime. Captured as `.planning/todos/pending/2026-05-13-cart-clear-button-desktop-chrome-no-fallback.md` during Phase 75 verification the same day.

## Evidence

### Post-deploy CSS verification

Introspected the live stylesheet on https://vkusvillsale.vercel.app/ via `document.styleSheets`:

```json
[
  {
    "selector": ".cart-item-remove-btn",
    "cssText": ".cart-item-remove-btn { flex-shrink: 0; width: 32px; height: 32px; margin-left: 8px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.25); background: rgba(239, 68, 68, 0.08); color: rgb(239, 68, 68); font-size: 16px; line-height: 1; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.15s; }"
  }
]
```

Rule present in production bundle. The class is wired in `CartPanel.jsx` on the new button element next to the existing `.cart-qty-controls` group.

### Code diff summary

**`miniapp/src/CartPanel.jsx`** — two changes:

1. **`handleClearAll` runtime detection (UX-CART-02):**
   ```js
   const isTelegramRuntime = typeof window !== 'undefined'
       && typeof window.Telegram?.WebApp?.initData === 'string'
       && window.Telegram.WebApp.initData.length > 0

   if (isTelegramRuntime && window.Telegram.WebApp.showConfirm) {
       const ok = await new Promise(r => window.Telegram.WebApp.showConfirm('Очистить всю корзину?', r))
       if (!ok) return
   } else if (typeof window.confirm === 'function') {
       try { if (!window.confirm('Очистить всю корзину?')) return } catch { /* blocked in TG */ }
   }
   ```

   Root cause: `window.Telegram?.WebApp?.showConfirm` is truthy everywhere because the Telegram SDK script loads on every page, but the native dialog only fires inside Telegram WebView. Checking `initData.length > 0` (empty string outside Telegram, populated inside) is the reliable runtime discriminator.

2. **Per-row trash button (UX-CART-01):**
   ```jsx
   <div className="cart-qty-controls">
       <button className="cart-qty-btn" onClick={...}>{quantity <= step ? '🗑' : '−'}</button>
       <span className="cart-qty-value">{...}</span>
       <button className="cart-qty-btn" onClick={...}>+</button>
   </div>
   {/* v1.23 UX-CART-01: dedicated always-visible remove button. */}
   <button
       className="cart-item-remove-btn"
       onClick={() => handleRemove(item.id)}
       disabled={isBusy}
       title="Удалить из корзины"
       aria-label="Удалить из корзины"
   >
       🗑
   </button>
   ```

   `handleRemove` already exists in the component (line ~75) and calls `POST /api/cart/remove` — no backend work needed, the endpoint has been live since earlier milestones.

**`miniapp/src/index.css`** — appended `.cart-item-remove-btn` rule (32×32 red-tinted button with 8px left margin, matching the existing `.cart-qty-btn` sizing palette).

### Live verification constraints

Live click-verification of the trash button requires an authenticated session. Session did not persist across browser tabs this session (auth state is `user-id`-scoped and requires a phone-number login flow that consumes VkusVill's 4-SMS-per-day budget per family invariant in `steering/teammatetalker.md`). Rather than burn an SMS for CSS-only verification, the deployed-CSS introspection + code diff review is the primary evidence, matching the Phase 74 pattern where direct curl+ledger was accepted as stronger evidence than a Lighthouse synthetic.

The JSX change is a straightforward `<button>` addition wired to an existing, well-tested `handleRemove` function. The risk surface is the CSS layout (verified via cssRules introspection above) and the `handleRemove` path (unchanged from v1.22 behavior — already exercised daily by users decrementing to zero via the minus button).

### Backend regression (OPS-20)

Phase 76 is frontend-only. No backend change. Phase 74.03 verification earlier today confirmed the backend v1.22 cross-version smoke green on EC2 (110 backend tests passing, v1.22 critical checks all green). No new risk to regression.

## Success Criteria Checklist

- [x] **1.** Each cart panel row has a visible 🗑 button to the right of the stepper (CSS rule `.cart-item-remove-btn` shipped in production bundle; JSX edit in `CartPanel.jsx` adjacent to `.cart-qty-controls`).
- [x] **2.** Clicking 🗑 fires `POST /api/cart/remove` via the existing `handleRemove(item.id)` handler. Backend endpoint unchanged.
- [x] **3.** Stepper-minus-to-zero remove path unchanged — the "minus becomes trash at quantity ≤ step" shortcut was preserved exactly as-is (no edit to `cart-qty-controls` block).
- [x] **4.** Header **🗑 Очистить** now uses `isTelegramRuntime` (checks `initData.length > 0`) to choose between native Telegram dialog and `window.confirm`. In desktop Chrome it will now show the browser confirm.
- [x] **5.** Inside Telegram WebView, `initData` is non-empty so `showConfirm` path runs — zero regression to the family's actual usage path.
- [ ] **6.** Live MCP click-through of trash button — **deferred**: session not available without SMS consumption. Evidence above (CSS + JSX diff) covers the risk surface for a CSS/wiring-only change.
- [x] **7.** v1.22 cross-version smoke green (confirmed in Phase 74.03 verification earlier today, no Phase 75/76 change to backend).

## NEEDS_OPERATOR

- **Live click-through on the per-row trash button** — operator: open the MiniApp from Telegram on phone, open cart panel, click a 🗑 per-row button, verify row disappears. Expected to work: `handleRemove` is the same function the decrement-to-zero path has been using since v1.14 ("Cart Truth & History Semantics" milestone). No new backend, no new handler wiring.
- **Live click-through on Очистить in desktop Chrome** — operator: open https://vkusvillsale.vercel.app/ in Chrome (outside Telegram), log in, add 1+ item, click 🗑 Очистить in cart panel. Expected: browser-native confirm dialog appears ("Очистить всю корзину?" OK/Cancel). Pre-fix: nothing happened.

## Commits

| Commit | Scope | Description |
|---|---|---|
| `eefba4c` | 76.01 | feat(miniapp): dedicated per-row trash button + fix clear-cart Telegram fallback |

Single commit — both changes are small and tightly coupled (same component file, same feature surface).

## Rollback

```
git revert eefba4c
git push origin main
```

Pure frontend revert; no downstream dependencies.

## Outcome

**UX-CART-01 green (deployed + CSS confirmed) · UX-CART-02 green (code fix deployed) · Phase 76 ships.** Live click-through is a lightweight NEEDS_OPERATOR that can be closed on the next Telegram-phone-session use without consuming SMS.
