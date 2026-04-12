# Phase 49: Error Recovery & Polish — Research

**Researched:** 2026-04-12
**Status:** Complete

## Current Error Handling Analysis

### Backend Error Types (fully classified)

`cart/vkusvill_api.py` returns structured `error_type` in every failure path:

| error_type | HTTP status | Trigger |
|---|---|---|
| `auth_expired` | 401 | No sessid/user_id, or VkusVill returns success=N with no basket |
| `product_gone` | 410 | POPUP_ANALOGS present (sold out) |
| `transient` | 502 | ConnectError, "temporarily unreachable" |
| `timeout` | 504 | Deadline exceeded, "timed out" |
| `pending_timeout` | 202 | Allow_pending + deadline expired → goes to poll path |
| `http` | 400 | Generic httpx.HTTPError |
| `invalid_response` | 400 | Non-JSON response |
| `api` | 400 | Fallback for unclassified VkusVill errors |
| `unknown` | 500 | Unhandled exception |

`backend/main.py:3338-3379` maps these to HTTP status codes and always returns `{ success, error, error_type }`.

### Frontend Error Handling (current state)

`App.jsx:892-1025` `handleAddToCart`:

1. **401 response** → `setIsAuthenticated(false); setShowLogin(true)` — already triggers login screen
2. **Sold-out detection** → string-matching on `detail` ("распрод", "недоступ", "out of stock", "popup_analogs") → toast "Этот продукт уже раскупили"
3. **All other errors** → generic toast "Корзина временно недоступна"
4. **AbortError (5s timeout)** → toast "Корзина не ответила вовремя"
5. **Network error** → toast "Ошибка сети"

All error states reset cart button to `null` after 2000ms via `setTimeout`.

### What's Missing (Phase 49 scope)

1. **No `error_type` parsing** — Frontend ignores the `error_type` field from backend responses; only checks HTTP status (401) and string-matches on `detail`/`error` for sold-out
2. **No VkusVill-down message** — 502/transient errors show generic "Корзина временно недоступна" instead of specific "ВкусВилл временно недоступен"
3. **No retry mechanism** — Error state shows ❌ icon for 2s then resets; no way to retry without re-tapping the product
4. **No auth_expired handling for non-401** — Backend can return `error_type: auth_expired` with 400 status in edge cases (vkusvill_api.py line 316), frontend only handles 401
5. **Error display too brief** — 2s timeout for all errors; CONTEXT.md specifies 4s for retryable, 2s for non-retryable

### Existing Login Flow

- `showLogin` state → full-page Login component (line 1452-1468)
- `showLoginPrompt` → overlay card with "Войти" / "Не сейчас" buttons (line 1472-1495)
- 401 in `handleAddToCart` already sets `showLogin(true)` directly — bypasses the prompt overlay
- Login success callback: `setIsAuthenticated(true); setShowLogin(false)`

### Cart Button States

`cartStates[pid]` values: `loading` | `pending` | `success` | `error` | `null`

ProductCard (`App.jsx:208-231`):
- `error` → red ❌ SVG icon, disabled=false (clickable but no retry handler)
- Button renders based on `cartState` with ternary chain

ProductDetail (`ProductDetail.jsx:136-144`):
- `error` → red background, text "❌ Ошибка"
- Same state-driven rendering

### Implementation Approach

**Core change:** Parse `error_type` from response JSON and use it to:
1. Select the correct Russian message
2. Determine if error is retryable
3. Set appropriate timeout (4s retryable / 2s non-retryable)
4. Show retry icon on cart button for retryable errors

**Error type → message mapping:**

| error_type | Message | Retryable | Timer |
|---|---|---|---|
| `auth_expired` | → trigger login prompt | No | — |
| `product_gone` | "Этот продукт уже раскупили" | No | 2s |
| `transient` | "ВкусВилл временно недоступен, попробуйте позже" | Yes | 4s |
| `timeout` | "Корзина не ответила вовремя" (keep existing) | Yes | 4s |
| `pending_timeout` | — (handled by polling path) | — | — |
| network error | "Ошибка сети" (keep existing) | Yes | 4s |
| AbortError | "Корзина не ответила вовремя" (keep existing) | Yes | 4s |
| fallback | "Корзина временно недоступна" | No | 2s |

**Retry mechanism:**
- New cart state `'retry'` (or reuse `'error'` with sub-state) to show 🔄 icon
- On retry tap → call `onAddToCart(product)` again (same handler)
- Cart button needs to be clickable during error state for retryable errors
- Already clickable when `cartState === 'error'` (not disabled), just needs onClick wired

**Key insight:** The cart button is NOT disabled during error state (only during `loading`/`pending`). So retry is just a matter of:
1. Keeping `onClick` active during error (already true)
2. Showing 🔄 instead of ❌ for retryable errors
3. Extending the error display to 4s

**Files to modify:**
- `miniapp/src/App.jsx` — `handleAddToCart`: parse `error_type`, map to messages, set retryable state
- `miniapp/src/App.jsx` — ProductCard render: show 🔄 for retryable errors
- `miniapp/src/ProductDetail.jsx` — mirror retry icon/text for detail view
- `miniapp/src/index.css` — optional: `.cart-btn-retry` style (or reuse `.cart-btn-error`)

**No backend changes needed** — error classification already complete from Phase 47.

## Validation Architecture

### Testable Properties
1. Each backend `error_type` maps to a distinct frontend message
2. `auth_expired` triggers login prompt (not just a toast)
3. Retryable errors show retry icon and remain clickable for 4s
4. Non-retryable errors show ❌ and reset after 2s
5. Retry tap re-invokes `handleAddToCart` with the same product

### Verification Commands
- `grep "error_type" miniapp/src/App.jsx` — confirms error_type parsing exists
- `grep "retry\|Повторить\|🔄" miniapp/src/App.jsx` — confirms retry UI
- `grep "auth_expired" miniapp/src/App.jsx` — confirms auth_expired handling
- `grep "transient\|502" miniapp/src/App.jsx` — confirms VkusVill-down handling

## RESEARCH COMPLETE
