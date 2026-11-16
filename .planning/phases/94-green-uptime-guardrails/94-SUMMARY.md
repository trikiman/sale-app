---
phase: 94
title: Green Uptime Guardrails
status: complete
---

# Phase 94 — Summary

**Why.** Green showed `0` while `green_products.json` held 6-77 real products
with real markdowns, because `/api/products` stripped every stale colour and
green was just another colour.

**What shipped**

- `backend/green_visibility.py` — `green_visibility(is_stale, has_snapshot_products, empty_reason)`
  returning `(visible, reason)`. Dependency-free by design: testable without
  FastAPI and impossible to fork into a second implementation inside the endpoint.
- `/api/products` consults it before the stale strip, and always emits
  `greenSuppressed` (null when shown, reason when not), including a loud
  `payload_missing_but_snapshot_has_products` case.
- `/admin/status` mirrors `greenSuppressed`, adds `greenAgeMinutes` and
  `greenAlerts` (`green_snapshot_stale:<Nm>`, `green_zero_with_live_count`).
- `tests/test_green_uptime_guardrails.py` — 9 tests, including a source-level
  test that fails if the unconditional strip returns.
- `tests/test_scheduler_freshness.py` updated for the 15 → 45 minute green
  threshold (the two assertions that pinned 15).

**Measured after deploy (live server)**

```
green=77  live=77  stale=False  greenSuppressed=None
/admin/status: green=77 greenSuppressed=None greenAgeMinutes=41.8 alerts=None
```

`greenAgeMinutes=41.8` is the proof this phase matters: under the old 15-minute
threshold those 77 cards would have been stripped and the UI would have shown 0.
