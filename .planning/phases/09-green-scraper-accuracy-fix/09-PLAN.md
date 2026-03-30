---
phase: 9
plan: 1
title: "Fix green scraper phantom items and accuracy reporting"
wave: 1
depends_on: []
files_modified:
  - scrape_green_data.py
  - execution/verify_green_accuracy.py
requirements_addressed: [SCRP-07]
autonomous: true
must_haves:
  - "greenLiveCount reflects DOM-detected count, not inflated"
  - "Basket IS_GREEN=1 items NEVER added as new green products"
  - "Stale modal products (>15min) rejected"
  - "Verification checklist passes with 0 phantom items"
---

# Plan 01: Fix Green Scraper Phantom Items

## Objective

Fix 3 bugs in `scrape_green_data.py` that cause the green scraper to report 8 items when VkusVill shows 4 green items. After this fix, our API green count must match the VkusVill green section count.

## Reference

- Checklist: `directives/green-scraper-checklist.md`
- Verification: `python execution/verify_green_accuracy.py`

## Tasks

<task id="1">
<title>Remove live_count inflation</title>
<read_first>
- scrape_green_data.py (line 515)
- green_common.py (function inspect_green_section, lines 599-688)
</read_first>
<action>
In `scrape_green_data.py`, line 515, DELETE the line:
```python
live_count = max(live_count, len(products))
```

This line forces `live_count` to always be >= the number of scraped products, making the accuracy ratio meaningless. After removal, `live_count` will only come from `inspect_green_section()` which reads the DOM count from VkusVill's green section header (e.g. "4 товара").
</action>
<acceptance_criteria>
- `scrape_green_data.py` does NOT contain `live_count = max(live_count`
- `live_count` in `green_products.json` output comes only from `inspect_green_section()`
- greenLiveCount in API can be different from scraped product count (this is now expected when phantoms existed)
</acceptance_criteria>
</task>

<task id="2">
<title>Stop adding new items from basket IS_GREEN=1</title>
<read_first>
- scrape_green_data.py (lines 347-361 — the loop that adds basket items)
- scrape_green_data.py (lines 306-345 — basket enrichment of existing items)
</read_first>
<action>
In `scrape_green_data.py`, lines 347-361, REMOVE the entire block that adds new basket items:

```python
# DELETE THIS BLOCK (lines ~350-361):
existing_ids = {str(p.get('id', '')) for p in raw_products}
new_from_basket = 0
skipped_non_green = 0
for pid, bp in basket_by_id.items():
    if pid not in existing_ids:
        if bp.get('is_green_api'):
            raw_products.append(bp)
            new_from_basket += 1
        else:
            skipped_non_green += 1
            print(f"  [{TAG}] ⏭️ Skipped non-green basket item: ...")
print(f"  [{TAG}] Enriched .../... with basket stock, {new_from_basket} new green from basket, ...")
```

REPLACE the print line with:
```python
print(f"  [{TAG}] Enriched {enriched}/{len(raw_products)} with basket stock data")
```

The basket API should ONLY be used to enrich existing products (stock, price, image) found via DOM scraping. It must NEVER add new products to the green list because `IS_GREEN=1` from basket_recalc is a stale cached flag that doesn't reflect current green section state.
</action>
<acceptance_criteria>
- `scrape_green_data.py` does NOT contain `new_from_basket` variable
- `scrape_green_data.py` does NOT contain `is_green_api` check that appends to `raw_products`
- Basket API is still used for enriching stock/price on existing items (lines 317-345 preserved)
- No new products are ever added from basket_recalc response
</acceptance_criteria>
</task>

<task id="3">
<title>Reject stale modal products</title>
<read_first>
- scrape_green_data.py (lines 122-141 — modal product loading)
- scrape_green_add.py (lines 660-673 — where modal products are saved with timestamp)
</read_first>
<action>
In `scrape_green_data.py`, around lines 134-137, REPLACE the stale handling:

BEFORE:
```python
if age_min > 10:
    print(f"  [{TAG}] ⚠️ Modal products are stale ({age_min:.0f}min old), using as fallback only")
    # Don't discard, still use as base — better stale data than missing data
```

AFTER:
```python
MAX_MODAL_AGE_MIN = 15
if age_min > MAX_MODAL_AGE_MIN:
    print(f"  [{TAG}] ❌ Modal products too stale ({age_min:.0f}min old, max={MAX_MODAL_AGE_MIN}min) — ignoring")
    modal_products = []
```

When modal products are stale (>15 min), the scraper should use ONLY the inline green section DOM as its source. Using stale modal data preserves phantom items from previous green sections.
</action>
<acceptance_criteria>
- `scrape_green_data.py` contains `MAX_MODAL_AGE_MIN = 15`
- When `age_min > MAX_MODAL_AGE_MIN`, `modal_products` is set to `[]` (empty list)
- The old comment "Don't discard, still use as base" is REMOVED
</acceptance_criteria>
</task>

<task id="4">
<title>Run verification checklist</title>
<read_first>
- execution/verify_green_accuracy.py
- directives/green-scraper-checklist.md
</read_first>
<action>
After deploying fixes to EC2, run the automated verification:
```bash
python execution/verify_green_accuracy.py
```

Expected result:
- 0 phantom items (in API but not in green section)
- greenLiveCount matches DOM-detected count
- All checks ✅

Also manually verify using the checklist:
1. Open https://vkusvill.ru/cart/ — count green section items
2. Open https://vkusvillsale.vercel.app/api/products — count green items
3. Open https://vkusvillsale.vercel.app/ — check badge count
4. All three must match (±1 for timing)
</action>
<acceptance_criteria>
- `python execution/verify_green_accuracy.py` exits with code 0
- Our API green count matches VkusVill green section count (±1)
- Frontend badge matches API green count
- 0 phantom items in cross-comparison
</acceptance_criteria>
</task>

## Verification

After all tasks complete:
1. Deploy `scrape_green_data.py` to EC2
2. Trigger a green scraper run (via admin panel "Run All" or manual)
3. Wait for scraper cycle to complete (~2 min)
4. Run `python execution/verify_green_accuracy.py`
5. Verify checklist per `directives/green-scraper-checklist.md`
