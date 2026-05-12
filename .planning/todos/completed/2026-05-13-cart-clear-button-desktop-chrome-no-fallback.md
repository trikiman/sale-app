---
date: 2026-05-13
area: miniapp/cart
priority: P3
source: live MCP verification of v1.23 Phase 75
---

# Очистить button silently no-ops in desktop Chrome (outside Telegram)

## Problem

User reported during v1.23 Phase 75 live verification (2026-05-13): pressed **🗑 Очистить** in the cart panel while viewing `https://vkusvillsale.vercel.app/` in desktop Chrome → **nothing happened**. No confirmation dialog, no visual feedback, no error, no network call.

## Root Cause

`miniapp/src/CartPanel.jsx::handleClearAll` (line 113-132):

```js
if (window.Telegram?.WebApp?.showConfirm) {
    const ok = await new Promise(r => window.Telegram.WebApp.showConfirm('Очистить всю корзину?', r))
    if (!ok) return
}
```

When the MiniApp runs in desktop Chrome (not inside Telegram), `window.Telegram.WebApp.showConfirm` **exists** (the Telegram SDK script `https://telegram.org/js/telegram-web-app.js` is unconditionally loaded in `index.html`) but calling it outside the Telegram runtime does nothing — the callback `r` is never invoked, so the Promise never resolves and the button click is silently dropped.

Same gotcha likely exists for any other call to `window.Telegram.WebApp.show*` in CartPanel + App.jsx (showPopup, showAlert, etc.) but is less visible because they're used for non-blocking feedback, not gating actions.

## Fix (proposed)

Race the Telegram Promise against a timeout so the fallback path fires when the native dialog doesn't respond. Or detect Telegram environment properly via `window.Telegram.WebApp.isVersionAtLeast?.('6.2')` or `window.Telegram.WebApp.initData` non-empty check (the `initData` is empty when not launched from Telegram).

Minimal fix:

```js
const isTelegram = typeof window !== 'undefined'
    && window.Telegram?.WebApp?.initData
    && window.Telegram.WebApp.initData.length > 0

if (isTelegram && window.Telegram.WebApp.showConfirm) {
    const ok = await new Promise(r => window.Telegram.WebApp.showConfirm('Очистить всю корзину?', r))
    if (!ok) return
} else if (typeof window.confirm === 'function') {
    try { if (!window.confirm('Очистить всю корзину?')) return } catch { /* blocked */ }
}
```

## Scope

Single file, ~5 LOC. Quick-fix via `/gsd-quick`-style atomic commit, no new milestone needed. The app is designed to run inside Telegram so this is edge-case polish.

## Family impact

Near-zero — family members use the Telegram MiniApp, not desktop Chrome. But I (dev) routinely test in Chrome and this blocks the Clear-cart flow there. Worth 5 LOC.

## Similar surfaces to audit later

- `showPopup` calls in App.jsx (multiple — used for login prompts, error displays)
- `showAlert` calls
- Any `HapticFeedback` call (silent on desktop, which is fine)
- Telegram `BackButton` / `MainButton` events (likely no-op on desktop, already graceful)
