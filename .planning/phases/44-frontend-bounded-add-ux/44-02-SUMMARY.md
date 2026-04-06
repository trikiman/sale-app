---
phase: 44-frontend-bounded-add-ux
plan: 02
subsystem: api
completed: 2026-04-06
---

# Phase 44 Plan 02: Quantity Support Contract Summary

**The cart contract now preserves decimal quantities and exposes a set-quantity route, so real `шт/кг` controls no longer depend on fake frontend-only state**

## Accomplishments

- `/api/cart/items` now preserves decimal `quantity` and `max_q` values and exposes basket-key/step metadata
- Added `VkusVillCart.set_quantity(...)` plus `POST /api/cart/set-quantity`
- Updated `miniapp/src/CartPanel.jsx` to stop faking decrement via `/api/cart/remove` and use the new quantity contract instead

## Verification Notes

- `python -m py_compile backend/main.py cart/vkusvill_api.py` passed
- `npm run build` passed

---
*Phase: 44-frontend-bounded-add-ux*
*Completed: 2026-04-06*
