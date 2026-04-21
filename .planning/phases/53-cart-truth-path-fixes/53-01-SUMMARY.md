# Summary: Plan 53-01 — Repair Cart Truth Path

## Changes Made

- Added short-lived direct-connectivity caching in `proxy_manager.py`
- Refactored `cart/vkusvill_api.py` to:
  - stop auto-refreshing stale sessions inside `_ensure_session()`
  - prefer direct transport when recent direct connectivity is healthy
  - fall back between proxy and direct transports on `httpx` failures
  - keep `_get_proxy_url()` as a compatibility helper for older call sites/tests
- Added targeted tests in `tests/test_vkusvill_cart.py`
- Updated `backend/test_cart_items_fallback.py` to assert the structured timeout response contract already used by the backend

## Verification

- `tests/test_vkusvill_cart.py`
- `backend/test_cart_pending_contract.py`
- `backend/test_cart_items_fallback.py`

## Live Proof

- After deploy, live `/api/cart/items/guest_5l4qwlrwizdmo86af87` returned real cart contents instead of `source_unavailable`
- Live `/api/cart/add` for product `33215` returned `200` with updated cart totals
- A stale-session simulation on EC2 still completed add in about 2.7 seconds instead of stalling in refresh logic
