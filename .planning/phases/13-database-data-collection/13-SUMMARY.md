# Phase 13 Summary: Database & Data Collection

**Status:** ✅ Complete
**Completed:** 2026-03-31

## What was built

### New file: `database/sale_history.py`
- `init_sale_history_tables()` — creates 3 new tables
- `record_sale_appearances()` — records every sale sighting + manages sessions
- `update_product_stats()` — recalculates per-product statistics
- `seed_product_catalog()` — seeds catalog from category_db.json
- `calc_discount()` — helper for discount % calculation

### Modified: `database/db.py`
- Added `_init_sale_history_tables()` method to Database class
- Tables are created on first DB access (CREATE IF NOT EXISTS)

### Modified: `scrape_merge.py`
- Added `record_sale_appearances()` call after proposals.json save
- Wrapped in try/except so sale history never breaks the merge pipeline

## Tables created

| Table | Purpose | Rows after seed |
|-------|---------|-----------------|
| `sale_appearances` | Every product sighting per scrape | 197 |
| `sale_sessions` | Continuous availability windows | 197 |
| `product_catalog` | All 16K VkusVill products + stats | 16,406 |

## Verification

- ✅ Tables created successfully on EC2
- ✅ 16,373 products seeded from category_db.json
- ✅ Merge test: 197 appearances recorded, 197 sessions opened
- ✅ Scheduler restarted — recording happens every 5 min automatically
- ✅ Sale history recording is fire-and-forget (never breaks merge)

## Requirements covered

- **HIST-01** ✅ Sale appearance tracking (DB + scraper integration)
- **HIST-02** ✅ Sale session aggregation
- **HIST-03** ✅ Product catalog seeding (16K products)
