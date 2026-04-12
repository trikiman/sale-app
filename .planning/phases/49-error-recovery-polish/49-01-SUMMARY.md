---
phase: 49
plan: 1
status: complete
started: 2026-04-12
completed: 2026-04-12
---

# Summary: Plan 49-01 — Error Type Mapping, Distinct Messages & Retry

## What Was Built

Replaced generic cart-add error handling with `error_type`-based routing. Frontend now parses the structured `error_type` field from backend responses and maps each to a distinct Russian message. Retryable errors (transient, timeout, network, AbortError) show a 🔄 replay icon on the cart button for 4 seconds, allowing users to retry with a single tap. Non-retryable errors (sold-out, generic) show ❌ and reset after 2 seconds. `auth_expired` triggers the login prompt directly.

## Key Changes

| File | Change |
|------|--------|
| `miniapp/src/App.jsx` | Parse `error_type` from backend response in `handleAddToCart`; message mapping object (`product_gone`, `transient`, `timeout`); new `'retry'` cart state for retryable errors; 4s timers for retryable, 2s for non-retryable; auth_expired → login prompt; replay SVG icon in ProductCard |
| `miniapp/src/ProductDetail.jsx` | Added `'retry'` to `showQuantityControl` exclusion, error className, and button text ("🔄 Повторить"); mirrors retry behavior from App.jsx |

## Commits

1. `23be8b9` — feat(49): parse error_type, distinct messages, retry state in cart-add
2. `b607b24` — feat(49): retry icon on cart button for retryable errors
3. `61ecf86` — feat(49): mirror retry state in ProductDetail cart button

## Verification

- `error_type` parsed: 2 locations (handleAddToCart + poll handler)
- `auth_expired` handled: 1 match
- `product_gone` handled: 3 matches
- `transient` handled: 3 matches
- `'retry'` cart state: 7 assignments in App.jsx, 3 in ProductDetail.jsx
- VkusVill-down message: 1 match
- 4000ms retryable timers: 13 occurrences
- Retry SVG icon: 1 match
- "Повторить" text: 1 match in ProductDetail

## Deviations

None — all tasks implemented as planned.
