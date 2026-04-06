# Phase 43 Verification: Backend Cart Response Contract

**Verified:** 2026-04-06
**Status:** ✅ Passed

## Automated Checks

- `python -m py_compile backend/main.py cart/vkusvill_api.py`
  Result: passed

- `pytest backend/test_cart_items_fallback.py backend/test_cart_pending_contract.py -q`
  Result: `9 passed`

## Verification Highlights

- The cart hot path now returns a bounded ambiguous timeout result instead of doing an inline `get_cart()` recovery call.
- Cookie saves can now persist `sessid` and `user_id` metadata so cart bootstrap can skip a warmup fetch when those values are already known.
- `/api/cart/add` supports an opt-in pending response path without breaking legacy callers that still expect timeout-as-error behavior.
- Repeated unresolved adds for the same user and product reuse the same attempt ID during the short dedupe window.
- The backend now exposes a status route that can reconcile pending attempts into final success or failure outside the original add request path.

## Residual Risk

- The new pending contract is intentionally opt-in, so the current frontend still follows the legacy timeout path until Phase 44 switches to `allow_pending`.
- Attempt tracking is currently in-memory only; it protects short request races within one backend process, not cross-process durability.
