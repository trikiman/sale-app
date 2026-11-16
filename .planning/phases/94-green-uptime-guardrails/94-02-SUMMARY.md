---
phase: 94
plan: 94-02
title: greenSuppressed in payload and admin status
status: complete
---

# 94-02 — Summary

`/api/products` now always emits `greenSuppressed`: `null` when green cards are
in the payload, a reason string when they are withheld (`source_empty`,
`missing`, `no_snapshot_products`), and the loud
`payload_missing_but_snapshot_has_products` when the snapshot claims products
but the payload carries none — that case is also printed, so it cannot pass as a
normal empty state.

`/admin/status` mirrors `greenSuppressed` and adds `greenAgeMinutes` (snapshot
mtime age) plus `greenAlerts`.

Verified live after deploy (`dee21b4`):

```
GET /api/products  → green=77 live=77 stale=False greenSuppressed=null
GET /admin/status  → green=77 greenSuppressed=None greenAgeMinutes=41.8 greenAlerts=None
```

`greenAgeMinutes=41.8` is the proof: the old 15-minute threshold would have
stripped all 77 cards at that age.
