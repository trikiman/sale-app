---
phase: 43-backend-cart-response-contract
plan: 01
subsystem: cart-client
completed: 2026-04-06
---

# Phase 43 Plan 01: Session Metadata And Bounded Cart Client Summary

**The cart hot path now reuses saved session metadata and returns an ambiguous timeout result instead of doing an inline cart read before responding**

## Accomplishments

- Login cookie saves now persist `cookies`, `sessid`, `user_id`, and `saved_at` metadata in `backend/main.py`
- `VkusVillCart` now prefers metadata-first bootstrap and only falls back to a warmup page fetch when metadata is missing
- `VkusVillCart.add()` now uses a bounded 1.5-second add deadline and no longer calls `get_cart()` from its timeout path

## Verification Notes

- `python -m py_compile backend/main.py cart/vkusvill_api.py` passed
- `pytest backend/test_cart_items_fallback.py -q` passed

---
*Phase: 43-backend-cart-response-contract*
*Completed: 2026-04-06*
