---
phase: 39-sale-continuity-guardrails
plan: 03
subsystem: reentry-alerts
completed: 2026-04-05
---

# Phase 39 Plan 03: Confirmed Reentry Alerts And Newness APIs Summary

**Notifier and backend “new products” surfaces now follow confirmed session reentry instead of first-ever-seen product IDs**

## Accomplishments

- Added `new_entry_pending` support to active `sale_sessions`
- Replaced `get_new_products(...)` usage in notifier and API newness paths with pending active-session entry logic
- Kept the legacy `seen_products` table for compatibility while removing it as the source of truth for sale-entry alerts

## Verification Notes

- `pytest backend/test_sale_continuity.py backend/test_notifier.py -q` passed within the broader milestone suite

---
*Phase: 39-sale-continuity-guardrails*
*Completed: 2026-04-05*
