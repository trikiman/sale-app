# Phase 9 Research: Green Scraper Accuracy Fix

## Summary

The green scraper pipeline produces phantom items (8 in API vs 4 on site) due to 4 bugs across 2 scripts. This research traces the exact code paths and root causes.

## VkusVill Cart Page DOM Structure

Two distinct sections on `/cart/`:

### Green Section (SOURCE OF TRUTH)
```css
#js-Delivery__Order-green-state-not-empty
  > div.VV_TizersSection__Content.js-order-form-green-labels-slider-wrp
  > div
```
Shows items with green price tags. Currently **4 items**: Морковь, Тунец копч., Клубника, Яблоко Богатырь.

### Cart List (what the user will buy)
```css
#js-delivery__basket--notempty
  > div.js-log-place.js-datalayer-catalog-list.js-datalayer-basket
```
Shows items in shopping cart. Currently **4 items**: Бри (non-green!), Морковь, Тунец копч., Клубника.

**KEY**: Green section ≠ Cart list. Our API should match GREEN SECTION count.

## Current Data State (2026-03-30)

| Source | Count | Notes |
|--------|-------|-------|
| VkusVill green section | **4** | Морковь, Тунец копч., Клубника, Яблоко |
| VkusVill cart list | **4** | Бри (non-green), Морковь, Тунец копч., Клубника |
| basket_recalc IS_GREEN=1 | **3** | Морковь, Тунец копч., Клубника |
| Our API | **8** | 3 real + 5 phantoms |

## Standard Stack

No external libraries needed. All fixes are in existing Python scripts using existing dependencies (nodriver, httpx, json).

## Architecture Patterns

### Scraper Pipeline Flow
```
scrape_green_add.py (Script 1)
  ├── Opens green modal → scrolls to load all items
  ├── Scrapes product data from modal DOM → saves green_modal_products.json
  └── Clicks "В корзину" on each item → adds to cart

scrape_green_data.py (Script 2)  
  ├── Reads green_modal_products.json (primary source)
  ├── Reads green section DOM inline cards
  ├── Merges modal + inline products
  ├── Calls basket_recalc API → enriches with stock/price
  ├── Adds IS_GREEN=1 basket items not already in list  ← BUG: leaks old items
  ├── live_count = max(live_count, len(products))       ← BUG: inflates count
  └── Saves green_products.json

scrape_merge.py
  └── Reads green_products.json → merges into proposals.json → served by API
```

## Root Cause Analysis — 4 Bugs

### Bug 1: live_count inflation (Critical severity)
**File:** `scrape_green_data.py`, line 515
```python
live_count = max(live_count, len(products))
```
**Problem:** After all processing, this line forces `live_count` to always be ≥ the number of scraped products. If the scraper finds 8 products (including phantoms), `live_count` becomes 8, making the self-reported accuracy ratio meaningless (always shows 100%).

**Impact:** The staleness detection and accuracy logging are completely broken — the scraper thinks it's perfect when it's collecting phantoms.

**Fix:** Remove this line entirely. `live_count` should only come from `inspect_green_section()` DOM detection.

### Bug 2: basket_recalc leaks old green items (Critical severity)
**File:** `scrape_green_data.py`, lines 347-361
```python
# Add basket items not in raw_products — ONLY if IS_GREEN=1
for pid, bp in basket_by_id.items():
    if pid not in existing_ids:
        if bp.get('is_green_api'):
            raw_products.append(bp)
```
**Problem:** `basket_recalc` returns ALL cart items. Items that WERE green-tagged in the past but are no longer in the green section still have `IS_GREEN=1` cached by VkusVill's server. The tech account's cart is a graveyard of former green items.

**Current state proof:** Cart has 4 items (Бри + 3 green), but basket_recalc reports IS_GREEN=1 on only 3 items. The green section shows 4 items. Яблоко is in the green section but wasn't added to cart by the scraper.

**Why phantom items appear:** Items like Вода Псыж, Лук, Масло Гхи, Тунец зам. were once green-tagged and added to cart. They lost green status but remain in `green_modal_products.json` from that older run. `IS_GREEN=1` flag in basket API is stale.

**Fix:** Only include basket items that are ALSO found in the current green section DOM scrape (cross-validate). Basket should enrich existing products with stock/price data, but NEVER add new items to the green list based solely on `IS_GREEN=1`.

### Bug 3: Stale modal products used as primary source (High severity)
**File:** `scrape_green_data.py`, lines 126-141
```python
if os.path.exists(modal_path):
    modal_products = modal_data.get('products', [])
    if age_min > 10:
        print(f"⚠️ Modal products are stale ({age_min:.0f}min old), using as fallback only")
        # Don't discard, still use as base — better stale data than missing data
```
**Problem:** `green_modal_products.json` from `scrape_green_add.py` is the primary data source. But when the file is stale (>10 min), the code warns but STILL uses it as the primary merge base. Items from previous green sections persist across runs.

**Current scraper cycle:** Scheduler runs both scripts sequentially. If Script 1 fails or doesn't run, Script 2 uses the OLD modal products file — which may contain items from days ago.

**Fix:** 
- If modal products file is >15 min old, refuse to use it (don't merge stale data)
- Only use inline green section DOM as source when modal is stale
- This is more conservative but prevents phantom accumulation

### Bug 4: Яблоко not added to cart (Medium severity)
**File:** `scrape_green_add.py`, `_add_green_cards_to_cart()`, lines 91-176

**Problem:** Яблоко Богатырь appears in the green section but wasn't added to the cart. The `_add_green_cards_to_cart()` function identifies "В корзину" buttons by text matching and CSS selectors, then clicks them. For Яблоко, the click either:
1. Didn't execute (button not matched due to selector mismatch)
2. Executed but VkusVill didn't register it (network lag, debounce)
3. A popup (delivery modal, "unavailable" dialog) blocked the click

**Evidence from screenshot:** Яблоко shows "В корзину" text in the green section, meaning it hasn't been added. The other 3 items show quantity controls (already in cart).

**Fix:** This is likely a timing/scroll issue in the modal. The batch click runs synchronously — items at the end of the modal may not be fully visible. Need to verify after adding: re-check which items are missing, then retry individually.

## Don't Hand-Roll

- **Don't create a new scraper** — fix the existing pipeline
- **Don't try to parse VkusVill's API for green status** — their IS_GREEN flag is unreliable (cached)
- **Don't implement browser-level caching** — just fix the data flow

## Common Pitfalls

1. **Testing with wrong account/address** — green items vary by delivery address. Always test with the tech account at the registered address.
2. **Trusting IS_GREEN=1 from basket_recalc** — this flag is cached server-side and doesn't reflect current green section.
3. **Assuming cart = green section** — cart has non-green items too (seed item, regular purchases).
4. **live_count inflation hiding bugs** — the max() trick makes the scraper look healthy when it's not.

## Code Examples

### Fix 1: Remove live_count inflation
```python
# scrape_green_data.py, line 515
# BEFORE:
live_count = max(live_count, len(products))

# AFTER: (just remove the line entirely)
# live_count stays as detected by inspect_green_section()
```

### Fix 2: Cross-validate basket items
```python
# scrape_green_data.py, lines 347-361
# BEFORE: trust IS_GREEN=1 from basket
# AFTER: only enrich existing items, never add new from basket
existing_ids = {str(p.get('id', '')) for p in raw_products}
# Remove the loop that adds new basket items entirely
# Only use basket for enriching stock/price of items already found in DOM
```

### Fix 3: Reject stale modal products
```python
# scrape_green_data.py, lines 126-141
MAX_MODAL_AGE_MIN = 15  # one scraper cycle
if age_min > MAX_MODAL_AGE_MIN:
    print(f"[{TAG}] ❌ Modal products too stale ({age_min:.0f}min) — ignoring")
    modal_products = []  # force use of inline-only
```

### Fix 4: Retry failed cart additions
```python
# After batch add, check which items still show "В корзину" and retry
# This is secondary priority — Bug 1-3 are more impactful
```

## Verification Plan

After all fixes, run:
```bash
python execution/verify_green_accuracy.py
```

Expected output:
- Green section count = Our API count (±1 tolerance)
- 0 phantom items
- greenLiveCount matches DOM-detected count, not scraped count
- All checks ✅
