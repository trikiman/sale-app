# Requirements — v1.12 Add-to-Cart 5s Hard Cap

## Milestone Goal

Enforce a hard 5-second wall-clock budget from tap to final UI state for add-to-cart.

## Diagnosed Problems (2026-04-07)

| Issue | Measured | Expected |
|-------|----------|----------|
| Initial `/api/cart/add` fetch | 3748ms | <2s |
| Each poll `/api/cart/add-status/` | ~5000ms | N/A (shouldn't poll this long) |
| Pending attempt TTL | 30s (pruned mid-poll → 404) | Aligned with frontend budget |
| Total tap-to-error | 41s | ≤5s |
| Poll count | 20 × 900ms + VkusVill read | Budget-capped |

## Requirements

### Cart UX Budget

- [ ] **CART-10**: Add-to-cart tap-to-result completes within 5 seconds total (success, error, or timeout)
- [ ] **CART-11**: Frontend enforces 5s hard cap via AbortController on `/api/cart/add` fetch
- [ ] **CART-12**: Poll loop uses remaining time budget (5s minus initial add duration) instead of fixed 20-poll loop
- [ ] **CART-13**: Polling stops immediately on 404/non-recoverable error instead of retrying
- [ ] **CART-14**: Backend pending attempt TTL aligned with frontend 5s budget (no premature pruning causing 404s)

### Non-Goals

- No changes to VkusVill API interaction or cart session management
- No changes to cart UI appearance (buttons, toasts, states stay the same)
- No background reconciliation changes — that path stays as-is for late success detection

## Traceability

| REQ | Phase |
|-----|-------|
| CART-10 | 46 |
| CART-11 | 46 |
| CART-12 | 46 |
| CART-13 | 46 |
| CART-14 | 46 |
