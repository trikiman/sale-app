---
phase: 46-enforce-5s-cart-budget
plan: 01
subsystem: miniapp-cart
tags: [cart, timeout, abort-controller, polling, budget]
dependency_graph:
  requires: []
  provides: [5s-cart-cap, budget-aware-polling]
  affects: [miniapp/src/App.jsx]
tech_stack:
  added: []
  patterns: [AbortController-timeout, time-budget-loop]
key_files:
  modified:
    - miniapp/src/App.jsx
decisions:
  - "4s threshold for D3 budget gate — if 202 arrives after 4s, skip polling and show background message"
  - "800ms minimum remaining budget to enter poll iteration — ensures poll can complete before 5s cap"
  - "Per-poll AbortController capped at min(1500ms, remaining) — prevents single slow poll from exceeding budget"
metrics:
  tasks: 2
  completed: 2
  duration: ~4min
  completed_date: "2026-04-07"
---

# Phase 46 Plan 01: Enforce 5s Cart Budget Summary

AbortController 5s hard cap on add-to-cart fetch + time-budget polling loop replacing fixed 20-iteration loop

## Tasks Completed

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | AbortController 5s cap on handleAddToCart | e4f4a79 | AbortController+signal on fetch, D3 budget gate at 4s, AbortError catch, clearTimeout in 4 paths |
| 2 | Time-budget pollCartAttemptStatus | 1af78f9 | while(true)+remainingMs<800 exit, t0 param, per-poll AbortController, 404 immediate break |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- AbortController count in App.jsx: 2 (handleAddToCart + poll)
- `attempt < 20` count: 0 (fixed loop removed)
- `remainingMs < 800` present at line 773
- `res.status === 404` present at line 797
- Build passes cleanly

## Known Stubs

None.
