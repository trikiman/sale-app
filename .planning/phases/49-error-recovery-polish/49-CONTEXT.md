# Phase 49: Error Recovery & Polish - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver distinct, actionable error messages for all cart-add failure modes and enable retry without page refresh. The frontend must distinguish sold-out, session-expired, VkusVill-down, network-error, and timeout states with appropriate user-facing messages and recovery paths.

</domain>

<decisions>
## Implementation Decisions

### Error Message Taxonomy
- VkusVill-down (502/transient) shows "ВкусВилл временно недоступен, попробуйте позже" — distinct from generic error
- Session-expired shows login prompt (extend existing 401 behavior to cover auth_expired error_type consistently)
- Keep current timeout message "Корзина не ответила вовремя" — clear and actionable
- Add inline retry button on cart button for retryable errors — user doesn't need to re-tap product

### Retry Mechanism
- Require explicit user tap to retry (no auto-retry) — avoids hammering a struggling API
- Show retry on the cart button itself — "🔄 Повторить" replaces ❌ for retryable errors
- Retryable errors: timeout, transient (502), network-error — NOT sold-out or auth-expired

### Error State UI
- 4s display for errors with retry option, 2s for non-retryable — gives time to read message and tap retry
- Single red error style (existing) — distinguish via message text only, not color
- Toast message is sufficient — no per-product errors in cart panel

### Claude's Discretion
No items deferred to Claude's discretion — all decisions captured above.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `miniapp/src/App.jsx` lines 900-1025: `handleAddToCart` — existing cart-add handler with error routing
- Backend `main.py` lines 3286-3379: `cart_add_endpoint` — already returns structured error_type (auth_expired, product_gone, transient, timeout, pending_timeout)
- Existing toast system via `setToastMessage({ text, type })` — supports success/error/info types
- Cart button states: loading, pending, success, error, null — via `cartStates` state

### Established Patterns
- Error state resets via `setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)`
- Toast messages auto-dismiss via setTimeout
- 401 response triggers `setIsAuthenticated(false); setShowLogin(true)`
- Sold-out detection via string matching on response detail

### Integration Points
- `App.jsx` handleAddToCart callback — where error routing happens
- `ProductDetail.jsx` mirrors cart button states from App.jsx
- `index.css` has `.cart-btn-error`, `.cart-panel-error`, `.detail-cart-btn.error` styles
- Backend returns `{ success: false, error: string, error_type: string }` for all failures

</code_context>

<specifics>
## Specific Ideas

- Error messages must be in Russian (existing pattern)
- Backend already classifies errors — frontend just needs to read error_type field and map to distinct messages
- Retry button replaces the error icon on the cart button for retryable errors

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
