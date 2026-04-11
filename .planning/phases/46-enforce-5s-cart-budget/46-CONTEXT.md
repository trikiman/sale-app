# Phase 46 Context: Enforce 5s Add-to-Cart Budget

## Diagnosed Problem (2026-04-07, live MCP DevTools capture)

Product 107823 (Брецель), full timeline:
- `[CART-ADD] START` → `[CART-ADD] RESPONSE status=202 pending=true` = **3748ms** (loading spinner)
- `[CART-POLL] START` → 5 polls at ~5s each, then 404 errors (attempt pruned)
- `[CART-POLL] EXHAUSTED` at **40747ms** (error cross)

### Root causes

1. **No frontend timeout** — `fetch('/api/cart/add')` has no AbortController, waits indefinitely
2. **Cart init is slow** — each `VkusVillCart(cookies_path=...)` does `_ensure_session()` which may call `_extract_session_params()` (GET vkusvill.ru through proxy) = ~2-3s
3. **Backend hot path = 1.5s** but total endpoint = 3.7s because cart init happens before the deadline starts
4. **Poll loop = 20 × (900ms wait + ~5s VkusVill cart read)** = up to 118s theoretical max
5. **TTL = 30s** — `_CART_PENDING_ATTEMPT_TTL_SECONDS = 30.0` prunes attempt while polling → 404
6. **404 not treated as terminal** — poll loop catches error and continues retrying

## Decisions

### D1: 5s hard cap is frontend-only
The frontend owns the clock. Backend stays best-effort with 1.5s hot path. If backend is slow, frontend aborts at 5s and shows error.

### D2: AbortController on initial fetch
```js
const controller = new AbortController()
const timer = setTimeout(() => controller.abort(), 5000)
fetch('/api/cart/add', { signal: controller.signal, ... })
```
On abort → show error toast, set `cartState = 'error'`, done.

### D3: No polling after abort
If the initial fetch takes >4s and returns 202 pending, there's <1s left — not worth polling. Show "Добавляем в фоне" (adding in background) and move on. The item may appear in cart on next refresh.

### D4: Budget-aware polling (when time remains)
If initial fetch returns 202 in <3s, poll with remaining budget:
- `remainingMs = 5000 - (performance.now() - t0)`
- Poll only while `remainingMs > 800` (enough for one round-trip)
- Each poll has its own 1.5s fetch timeout
- Stop on 404 or any non-pending response immediately

### D5: Backend TTL stays 30s
Don't reduce — the TTL serves background reconciliation too. The fix is frontend: stop polling at 5s regardless.

### D6: Success after timeout is OK
If user sees error at 5s but VkusVill actually added the item, the next cart refresh (on panel open) will show it. No user confusion — they already see the item appear.

### D7: Keep all diagnostic logs
The `[CART-ADD]`, `[CART-POLL]`, `[CART-STATUS]` logs added today stay. They're essential for monitoring.

## Files to Change

| File | Change |
|------|--------|
| `miniapp/src/App.jsx` | `handleAddToCart`: add AbortController 5s; `pollCartAttemptStatus`: budget-aware loop; stop on 404 |
| `backend/main.py` | No changes needed (1.5s hot path already works) |
| `cart/vkusvill_api.py` | No changes needed |

## Out of Scope

- Speeding up `_ensure_session()` / cart init (separate optimization, not needed for 5s cap)
- Changing VkusVill API interaction patterns
- Background reconciliation improvements
