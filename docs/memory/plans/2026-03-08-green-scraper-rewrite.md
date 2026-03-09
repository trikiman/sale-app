# Green Scraper Rewrite Plan

> Created: 2026-03-08

## Problem

The current green scraper produces mismatched data vs. the live VkusVill cart page.  
The existing flow is overly complex (~700 lines in `scrape_green_prices_async`) with multiple fallback paths that often conflict.

## New Logic (User-Defined)

```
1. Go to /cart/
2. Turn on "Больше товаров" switch
3. Search for the "Зелёные ценники" section
   3.1 If there's a button "X товаров" or "показать все" → click it
       3.1.1 In popup: scroll down, click "В корзину" on each item
             until item disappears OR button under no longer says "в корзину"
       3.1.2 Reload page
   3.2 If inline items (no popup): add all items one-by-one
        3.2.0 until item disappears OR button under no longer says "в корзину"
            3.2.1 Reload page
4. In reloaded cart: scroll down through cart items
   - Items with GREEN label → scrape (name, price, old price, stock, image, url)
   - Items with GRAY label → skip entirely
   - Stop scrolling when hitting "нет в наличии" or stock 0
5. If ALL items are "нет в наличии" → green price is gone (return empty)
6. Close Chrome
```

## What Exists Already

| Function | Status | Reuse? |
|----------|--------|--------|
| `_launch_browser()` | Works | ✅ Keep |
| `_load_cookies()` | Works | ✅ Keep |
| `_inspect_green_section()` | Works but complex | 🔄 Simplify |
| `_add_green_cards_to_cart()` | Works for inline cards | 🔄 Adapt for modal too |
| `_extract_green_cart_items()` | Works | 🔄 Add green/gray label filter |
| `_scrape_cart_stock_map()` | Works | ✅ Keep |
| `_merge_green_cart_data()` | Works | ✅ Keep |
| `_fetch_green_from_basket()` | Basket API fallback | ✅ Keep as fallback |
| Toggle "Больше товаров" | Already implemented (L1030-1113) | ✅ Keep |
| Modal scroll + load more | Already implemented (L1231-1279) | ✅ Keep |

## Proposed Changes

### [MODIFY] [scrape_green.py](file:///e:/Projects/saleapp/scrape_green.py)

#### 1. New simplified `_scrape_green_v2()` function (~200 lines)

Replace/rewrite `scrape_green_prices_async()` with a cleaner flow:

```python
async def scrape_green_prices_async():
    # 1. Launch browser, load cookies, navigate to /cart/
    # 2. Enable "Больше товаров" toggle (reuse existing code)
    # 3. Find green section
    # 4. Click "X товаров"/"показать все" if button exists
    #    4a. If modal opened: scroll + add all items via "В корзину"
    #    4b. If no modal: add inline items via "В корзину"
    # 5. Reload page
    # 6. Scrape cart items WITH GREEN LABEL ONLY
    #    - Scroll cart list down
    #    - Stop at "нет в наличии" items
    #    - Skip gray-labeled items
    # 7. Process & save
```

#### 2. New `_add_all_green_items_in_modal(page)` function

Combines existing modal scroll + add logic. Scrolls through popup, clicks "В корзину" on each card. Stops when:
- Card disappears after click
- Button text changes from "В корзину"  
- No more cards

#### 3. Update `_extract_green_cart_items(page)` 

Add green/gray label detection:
- Look for green price label (the green badge from user's screenshot)
- Skip items with gray labels
- Capture stock count ("В наличии X шт")
- Stop processing when hitting "нет в наличии"

#### 4. Remove dead code

Remove unreachable branches and overly complex fallback chains that cause data conflicts.

## Card Layout Fix (CSS)

### [MODIFY] [index.css](file:///e:/Projects/saleapp/miniapp/src/index.css)

Already applied: `.card-vertical` → `display: flex; flex-direction: column` and `.card-body` → `flex: 1` so price row + cart button always aligns at bottom regardless of title height (1 vs 2 lines).

## Verification Plan

### Automated
1. `python -c "from backend.main import app; print('OK')"` — backend loads
2. `npx vite build` — frontend builds without errors

### Manual (User)
1. Run green scraper from admin panel
2. Check logs for the new simplified flow steps
3. Compare green item count on our site vs VkusVill /cart/ page
4. Verify card buttons are aligned when titles vary in length
