---
phase: 49
status: passed
verified: 2026-04-12
verifier: inline
---

# Phase 49 Verification: Error Recovery & Polish

## Goal

Users see actionable error messages and can recover from failures without confusion.

## Must-Haves

### 1. Distinct messages per error state
**Status:** PASS

| Error State | Expected | Actual |
|---|---|---|
| sold-out (product_gone) | Distinct sold-out message | "Этот продукт уже раскупили" ✓ |
| session-expired (auth_expired) | Login prompt | `setShowLogin(true)` ✓ |
| VkusVill-down (transient) | Distinct VkusVill message | "ВкусВилл временно недоступен" ✓ |
| network-error | Network message | "Ошибка сети" ✓ |
| timeout | Timeout message | "Корзина не ответила вовремя" ✓ |
| generic fallback | Fallback message | "Корзина временно недоступна" ✓ |

**Evidence:** `grep "messageMap" miniapp/src/App.jsx` — mapping object with 3 distinct entries + fallback. `grep "auth_expired" miniapp/src/App.jsx` — routed before messageMap.

### 2. Session-expired shows re-login prompt
**Status:** PASS

`auth_expired` check at line 986 runs before any toast/error logic. Sets `isAuthenticated(false)` and `showLogin(true)`, then returns immediately. No generic error message shown.

**Evidence:** `App.jsx:986-990` — `if (errorType === 'auth_expired' || res.status === 401) { setIsAuthenticated(false); setShowLogin(true); ... return }`

### 3. Retry without page refresh
**Status:** PASS

Retryable errors (transient, timeout, network, AbortError) set cart state to `'retry'` instead of `'error'`. The cart button:
- Shows 🔄 replay icon (ProductCard) or "🔄 Повторить" text (ProductDetail)
- Stays clickable (not in disabled list)
- Clicking invokes `onAddToCart(product)` — same handler, re-initiates full add flow
- 4-second window before auto-reset to null

**Evidence:** `grep "'retry'" miniapp/src/App.jsx` — 7 matches. `grep "'retry'" miniapp/src/ProductDetail.jsx` — 3 matches. Button `disabled` only for `loading`/`pending`.

## Requirements Coverage

| REQ-ID | Description | Status |
|--------|-------------|--------|
| ERR-01 | Distinct error messages per failure mode | ✓ Covered by must-have 1 |
| ERR-02 | Recovery from transient errors | ✓ Covered by must-have 3 |

## Human Verification

1. Trigger a cart-add timeout (slow network or backend down) → verify 🔄 icon appears and tap retries
2. Trigger a sold-out error → verify "Этот продукт уже раскупили" message and ❌ icon (no retry)
3. Trigger session expiry → verify login prompt appears (not a toast error)
