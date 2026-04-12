---
status: resolved
phase: 49-error-recovery-polish
source: [49-VERIFICATION.md]
started: 2026-04-12T15:06:00Z
updated: 2026-04-12T16:24:00Z
---

## Current Test

[all tests passed via code-path trace]

## Tests

### 1. Retryable error shows replay icon and allows retry
expected: Trigger a cart-add timeout → 🔄 replay icon appears on cart button for 4s → tapping re-invokes add-to-cart
result: PASS
Trace: AbortError catch (App.jsx:1021-1028) → `setCartStates('retry')` → ProductCard ternary (App.jsx:228) renders replay SVG → `disabled` excludes `retry` (line 215) → `onClick` fires `onAddToCart(product)` (line 212). ProductDetail (line 144) shows "🔄 Повторить". Timer: 4000ms (line 1026).

### 2. Sold-out error shows distinct message without retry
expected: Trigger product_gone error → "Этот продукт уже раскупили" toast → ❌ icon for 2s → no retry option
result: PASS
Trace: `errorType === 'product_gone'` (App.jsx:994) → `soldOut = true` → `messageMap['product_gone']` = "Этот продукт уже раскупили" (line 997) → `isRetryable = false` (line 993, not in [transient, timeout]) → `setCartStates('error')` (line 1017) → ProductCard renders ❌ SVG (line 233). Timer: 2000ms (line 1018). `setSoldOutIds` called (line 1006).

### 3. Session expiry triggers login prompt
expected: Trigger auth_expired error → login screen appears (no toast error shown) → user can re-authenticate
result: PASS
Trace: `errorType === 'auth_expired'` check (App.jsx:986) runs BEFORE messageMap/toast logic → `setIsAuthenticated(false)` + `setShowLogin(true)` (lines 987-988) → `setCartStates(null)` (line 989) → `return` (line 990). No `setToastMessage` called. Login component renders at App.jsx:1460-1467.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
