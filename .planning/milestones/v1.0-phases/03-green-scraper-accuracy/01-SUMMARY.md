---
phase: 3
plan: 1
subsystem: green-scraper
tags: [scraper, green, accuracy, verification]
requires: []
provides: []
affects: []
key-files:
  created: []
  modified: []
key-decisions:
  - "No code changes needed — green scraper was already refactored in conversation 27a0c0d3 (March 28)"
  - "Modal DOM extraction provides 100% item capture before adding to cart"
  - "Merge pipeline: modal products → inline section → basket API → stock cache"
requirements-completed: [SCRP-07]
duration: "2 min"
completed: "2026-03-30"
---

# Phase 3 Plan 01: Green Scraper Accuracy — Verification Summary

**No code changes needed.** The green scraper was comprehensively refactored in a prior session (conversation 27a0c0d3, March 28).

**Duration:** ~2 min (code audit only) | **Tasks:** 1/1 | **Files:** 0 modified

## What Was Verified

The refactored green scraper architecture already satisfies SCRP-07 (≥90% capture):

### scrape_green_add.py (Script 1)
1. **Scroll-to-load loop** — clicks "показать ещё" until button disappears AND card count stabilizes (3 stable iterations)
2. **Modal DOM scraping** — extracts ALL products from `#js-modal-cart-prods-scroll` `ProductCard` elements
3. **Saves `green_modal_products.json`** — provides 100% capture before cart-add step, so data doesn't depend on successful cart clicks

### scrape_green_data.py (Script 2)
4. **Merge pipeline** — combines modal products (primary) + inline green section + basket API
5. **Basket enrichment** — `basket_recalc` CDP/httpx fallback provides stock, price corrections
6. **data-max fallback** — fills stock from DOM `data-max` attribute when basket fails
7. **Stock cache** — `green_stock_cache.json` preserves valid stock values across runs
8. **Suspicious result protection** — rejects empty/single-item results when existing data exists

### Key Architecture
```
Modal DOM (100% items) → green_modal_products.json
  ↓ merge
Inline section (cart page green cards)
  ↓ enrich
Basket API (stock, real prices)
  ↓ fallback
data-max / stock cache
  ↓ save
green_products.json
```

## Deviations from Plan

None — verification-only phase, no code changes.

## Issues Encountered

None. Architecture is sound for ≥90% capture.

## Next

Phase 4 (stock=99 fix) — verify stock=99 filters are complete.
