---
phase: 43-backend-cart-response-contract
plan: 02
subsystem: api
completed: 2026-04-06
---

# Phase 43 Plan 02: Pending Add Contract And Attempt Registry Summary

**The backend now has an opt-in pending add contract with short-lived dedupe and a status route for later reconciliation**

## Accomplishments

- Extended `/api/cart/add` with `allow_pending` and `client_request_id` so pending-aware callers can opt in without breaking legacy timeout behavior
- Added an in-memory cart-add attempt registry keyed by attempt ID and `user_id + product_id` for short dedupe protection
- Added `GET /api/cart/add-status/{attempt_id}` so later callers can reconcile a pending add into success, failure, or expiry outside the original request path

## Verification Notes

- `python -m py_compile backend/main.py` passed
- `pytest backend/test_cart_items_fallback.py backend/test_cart_pending_contract.py -q` passed

---
*Phase: 43-backend-cart-response-contract*
*Completed: 2026-04-06*
