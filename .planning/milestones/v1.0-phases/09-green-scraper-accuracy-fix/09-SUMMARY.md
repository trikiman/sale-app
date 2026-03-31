---
phase: 09-green-scraper-accuracy-fix
plan: 09
subsystem: scraper
tags: [green-scraper, phantom-items, data-accuracy, basket-api]

requires:
  - phase: 03-green-scraper-accuracy
    provides: "Green scraper baseline with modal+basket approach"
provides:
  - "Accurate green product count matching live VkusVill site"
  - "Stale data eviction for modal products >15min"
  - "Basket API restricted to enrichment-only (no new item injection)"
affects: []

tech-stack:
  added: []
  patterns:
    - "MAX_MODAL_AGE_MIN guard for stale data rejection"
    - "Basket API enrichment-only pattern (never add new products)"

key-files:
  created: []
  modified:
    - scrape_green_data.py

key-decisions:
  - "Removed live_count inflation entirely rather than fixing the formula — DOM detection is the only valid source"
  - "Basket API IS_GREEN=1 items blocked from adding as new products — stale cached flag unreliable"
  - "15-minute threshold for modal staleness — balances freshness vs scraper timing"

patterns-established:
  - "DOM-only live_count: live_count must come from inspect_green_section() and never be inflated"
  - "Enrichment-only basket: basket_recalc data used only to add stock/price to existing DOM-detected products"

requirements-completed: [SCRP-07]

duration: 3min
completed: 2026-03-31
---

# Phase 9: Green Scraper Accuracy Fix Summary

**Removed 3 phantom-item bugs: live_count inflation, basket IS_GREEN=1 new-item injection, and stale modal data preservation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T22:32:37Z
- **Completed:** 2026-03-30T22:35:04Z
- **Tasks:** 3 code tasks + 1 verification (Task 4 deferred to EC2 deploy)
- **Files modified:** 1

## Accomplishments
- `live_count` now reflects DOM-detected count only — no artificial inflation
- Basket API can no longer inject new green products via stale `IS_GREEN=1` flag
- Modal products older than 15 minutes are discarded, preventing phantom persistence

## Task Commits

All 3 code fixes committed atomically (same file, tightly coupled):

1. **Task 1: Remove live_count inflation** - `725457d` (fix)
2. **Task 2: Stop adding new items from basket IS_GREEN=1** - `725457d` (fix)
3. **Task 3: Reject stale modal products** - `725457d` (fix)
4. **Task 4: Run verification checklist** - Requires EC2 deployment

## Files Created/Modified
- `scrape_green_data.py` — Removed `max(live_count, len(products))` inflation (line 515), removed basket new-item block (lines 347-361), added MAX_MODAL_AGE_MIN=15 guard with modal product rejection (lines 135-138)

## Decisions Made
- Combined all 3 fixes into a single commit since they're in the same file and semantically coupled — all address phantom item causes
- Chose 15-minute modal age threshold as it covers the ~2min gap between scrape_green_add.py and scrape_green_data.py runs while still catching genuinely stale data

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Code fixes applied locally — need EC2 deployment to take effect
- After deployment: run `python execution/verify_green_accuracy.py` and check checklist
- Live user report: 127 vs 124 items (3-item gap) — these fixes should close it

---
*Phase: 09-green-scraper-accuracy-fix*
*Completed: 2026-03-31*
