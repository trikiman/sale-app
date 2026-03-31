# Phase 9 Context: Green Scraper Accuracy Fix

## VkusVill Cart Page DOM Structure

### Green Section (SOURCE OF TRUTH for green items)
```css
#js-Delivery__Order-green-state-not-empty
  > div.VV_TizersSection__Content.js-order-form-green-labels-slider-wrp
  > div
```
Contains `ProductCard` elements inside swiper slides. This is the definitive list of green-tagged items.

### Cart List (items actually in shopping cart)
```css
#js-delivery__basket--notempty
  > div.js-log-place.js-datalayer-catalog-list.js-datalayer-basket
```
Contains `BasketItem`/`CartItem` elements. Only has items that were successfully added by scrape_green_add.py.

## Key Insight: Green Section ≠ Cart List
- Green section = what discounts are available (source of truth)
- Cart list = what the scraper managed to add (subset, may be incomplete)
- Our API should match GREEN SECTION, not cart list

## Current State (2026-03-30 22:25 MSK)

| Source | Count | Items |
|--------|-------|-------|
| Green section (user verified) | **4** | Морковь, Тунец копч., Клубника, Яблоко Богатырь |
| Cart list (user verified) | **4** | Бри (non-green!), Морковь, Тунец копч., Клубника |
| Cart IS_GREEN=1 (basket API) | **3** | Морковь, Тунец копч., Клубника |
| Our API | **8** | 3 real + 5 phantoms |

## Bugs to Fix

### Bug 1: live_count inflation
**File:** `scrape_green_data.py:515`
```python
live_count = max(live_count, len(products))  # REMOVE THIS
```
Forces live_count to always ≥ scraped count → fake 100% accuracy.

### Bug 2: Stale modal products used as primary source
**File:** `scrape_green_data.py:126-141`
- `green_modal_products.json` used even when age > 10 min
- Old items from previous green sections persist across runs
- Fix: reject modal products older than one scraper cycle (~15 min)

### Bug 3: basket_recalc leaks non-current green items
**File:** `scrape_green_data.py:347-361`
- basket_recalc returns ALL cart items
- Items with `IS_GREEN=1` that are no longer in the green section get included
- Fix: cross-validate basket items against current green section DOM scrape

### Bug 4: Яблоко not added to cart
**File:** `scrape_green_add.py`
- Яблоко Богатырь appears in green section but wasn't added to cart
- scrape_green_add.py failed to click "В корзину" for this item
- Likely a click/scroll issue in the modal interaction

## Verification Script
```
python execution/verify_green_accuracy.py
```
Automated 5-check comparison. Run after any scraper change to verify.
