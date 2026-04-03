# Phase 33 Summary: Group/Subgroup Notifications

**Status:** ✅ Complete
**Completed:** 2026-04-03

## What was built

### Notification matching
- Extended `backend/notifier.py` to evaluate product favorites, group favorites, and subgroup favorites in one pass
- Added exact parsing for existing favorite keys:
  - `group:X`
  - `subgroup:X/Y`
- Merged all matches per user by `product_id` so one product sends one alert even if multiple favorites match it

### Category metadata fallback
- Added `Database.get_product_catalog_metadata()` in `database/db.py`
- The notifier now fills missing `group` / `subgroup` from `product_catalog` when the current `proposals.json` sale snapshot does not carry hierarchy fields yet

### Telegram message behavior
- Notification messages now include the most specific visible reason:
  - subgroup match first
  - then group match
  - then direct product-favorite fallback
- Existing inline buttons and per-user batching behavior were preserved

## Verification

- ✅ `python -m pytest backend/test_notifier_category_alerts.py -q`
- ✅ Local temporary-db dry run verified:
  - product/group/subgroup dedupe
  - subgroup-over-group precedence
  - `product_catalog` fallback when merged JSON lacks hierarchy
- ✅ EC2 `python3 backend/notifier.py --dry-run` executed cleanly after deploy

## Requirements covered

- **BOT-06** ✅ Telegram notifier checks group/subgroup favorites, avoids duplicates, and shows which group/subgroup matched
