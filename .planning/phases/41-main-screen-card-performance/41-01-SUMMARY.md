---
phase: 41-main-screen-card-performance
plan: 01
subsystem: first-useful-content
completed: 2026-04-05
---

# Phase 41 Plan 01: Faster First Useful Content Summary

**The main sale screen now hydrates from the last good payload so users see useful content before the fresh network fetch completes**

## Accomplishments

- Added local caching for the main `/api/products` payload
- Switched the initial loading path to stale-while-revalidate behavior when cached data exists
- Kept stale warnings visible so cached data is not mistaken for fresh data

## Verification Notes

- `npm run build` passed

---
*Phase: 41-main-screen-card-performance*
*Completed: 2026-04-05*
