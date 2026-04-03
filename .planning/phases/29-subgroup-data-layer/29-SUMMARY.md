# Phase 29 Summary: Subgroup Data Layer

**Status:** ✅ Complete
**Completed:** 2026-04-02

## What was built

### Scraper and data model
- Extended the category scraper to discover VkusVill subgroup structure and persist it into `category_db.json`
- Recorded 16,426 products with group/subgroup hierarchy, including 524 discovered subgroups across 46 groups
- Preserved multi-subgroup data in `category_db.json` while keeping a single subgroup field in `product_catalog`

### Database and backend
- Added `group_name` and `subgroup` columns plus indices to `product_catalog`
- Seeded catalog rows with the new hierarchy data
- Added `/api/groups` and history-query support for group/subgroup filters in `backend/main.py`

### Pipeline integration
- Updated `scrape_merge.py` so merged sale products can include `group` / `subgroup` when category data is present
- Fixed follow-on backend issues discovered during integration:
  - proper `group` / `subgroup` query parameters in history API
  - correct use of the global DB handle in history/groups code
  - missing SQLite import for the groups endpoint

## Verification

- ✅ Category scraper run on EC2 produced valid subgroup data
- ✅ `category_db.json` contains 16K+ products with hierarchy data
- ✅ `product_catalog` stores `group_name` / `subgroup`
- ✅ `/api/groups` and `/api/history/products` group/subgroup filters returned expected results

## Requirements covered

- **DATA-01** ✅ Category scraper stores `{group, subgroup}` data
- **DATA-02** ✅ Existing catalog was re-scraped with subgroup information
- **DATA-03** ✅ `product_catalog` populated with group/subgroup fields
