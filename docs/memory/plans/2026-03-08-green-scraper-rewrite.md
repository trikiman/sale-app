# Green Scraper Rewrite Plan

> Created: 2026-03-08  
> Last updated: 2026-03-19

## Problem

The current green scraper produces mismatched data vs. the live VkusVill cart page.  
The existing flow is overly complex (~700 lines in `scrape_green_prices_async`) with multiple fallback paths that often conflict.

## New Logic (User-Defined, updated 2026-03-19)

```
1. Go to /cart/
2. Turn on "Больше товаров" switch
2.5. SEED ITEM: If cart is empty, add one item from "Добавьте в заказ" section
     - Without this, first add-to-cart triggers page force-reload, killing modal
     - Wait for reload, navigate back to /cart/
2.9. CLEAR ALPHA ITEMS: Click button.js-delivery__basket_unavailable--clear
     - Removes only alpha/faded items taking up cart slots (~300 limit)
     - ⚠️ Do NOT use button.js-delivery__basket--clear — that clears ENTIRE cart!
     - After click: wait 2s → reload page
3. Close delivery modal if it pops up
 from #js-Delivery__Order-green-state-not-empty section
   - All items in this section are green by definition
   - Extract: id (data-id attr), name (URL slug), price, oldPrice, image, url
   - This MUST happen BEFORE add-to-cart (items disappear after add+reload)
5. Check button #js-Delivery__Order-green-show-all:
   5.1 Button VISIBLE → click → modal opens
       5.1.1 Scroll modal + load more to get ALL items
       5.1.2 Scrape products FROM MODAL (modal has all items, section Swiper only ~12)
       5.1.3 Add all to cart
       5.1.4 Close modal
   5.2 Button HIDDEN (_hidden class, <5 items) → add inline items
   5.3 Button NOT IN DOM → no new green items to add
6. Reload page
7. Cart scraping step uses pre-scraped data from step 4 + modal (ALWAYS runs)
   - Green section is EMPTY after reload (items moved to regular cart)
   - Items from this run OR from previous runs are counted
8. If ALL items are "нет в наличии" → green price is gone (return empty)
9. Close Chrome

📸 Screenshots saved at each step to logs/screenshots/green/
```

> **Key insight**: After adding green items to cart + page reload, the `#js-Delivery__Order-green-state-not-empty` section becomes empty because items move to the regular cart. Therefore, scraping MUST happen before any cart modifications.

> Note: basket API (`basket_recalc.php`) is unreliable (times out).
> DOM cart scraping from the green section is the primary source of green items.

## What Exists Already

| Function | Status | Reuse? |
|----------|--------|--------|
| `_launch_browser()` | Works | ✅ Keep |
| `_load_cookies()` | Works | ✅ Keep |
| `_inspect_green_section()` | Works, now called from main flow (BUG 7 fix) | ✅ Keep |
| `_add_green_cards_to_cart()` | Works for inline + modal (BUG 4 fix) | ✅ Keep |
| `_scrape_cart_stock_map()` | Works | ✅ Keep |
| `_merge_green_cart_data()` | Works | ✅ Keep |
| `_fetch_green_from_basket()` | Single definition (BUG 1: removed dead duplicate) | ✅ Keep |
| Toggle "Больше товаров" | Already implemented | ✅ Keep |
| Modal scroll + load more | Already implemented | ✅ Keep |

## Bug Fixes Applied

### Round 1 (2026-03-10)

| Bug | Description | Status |
|-----|-------------|--------|
| BUG 1 | Dead duplicate `_fetch_green_from_basket()` removed | ✅ Fixed |
| BUG 2 | `raw_products` NameError on empty green | ✅ Fixed |
| BUG 3 | Hardcoded `True` in suspicious check | ✅ Fixed |
| BUG 4 | Modal cart-add unscoped → uses `_add_green_cards_to_cart` | ✅ Fixed |
| BUG 5 | Unicode escapes → Cyrillic in raw string | ✅ Fixed |
| BUG 7 | `live_count` always 0 → calls `_inspect_green_section` | ✅ Fixed |
| BUG 8 | Empty-state detection (green-state-empty ID, "сейчас нет") | ✅ Fixed + Verified |
| BUG 11 | Chrome zombie: `proc.wait()` + `proc.kill()` | ✅ Fixed + Verified |
| BUG 14 | Redundant `_fetch_basket_snapshot()` removed (18 lines) | ✅ Fixed |
| BUG 15 | Atomic write via `save_products_safe` | ✅ Fixed |
| BUG 17 | Basket API retry 3x with backoff (3s/6s) | ✅ Fixed + Verified |
| BUG 18 | Full Chrome User-Agent in API requests | ✅ Fixed |
| BUG 20 | `check_vkusvill_available()` in async func | ✅ Fixed |
| — | Scroll 1400→2000px | ✅ Fixed |
| — | Cart-add delay 0.3/0.4→1.0s | ✅ Fixed |
| — | "Добавьте в заказ" section confusion guard | ✅ Fixed |
| — | Chrome startup wait 3→5s | ✅ Fixed |
| — | Page reload after cart modifications | ✅ Fixed |
| — | Mojibake 'шт' on L772 | ✅ Fixed |

### Round 2 — Green Section Scraping (2026-03-11 → 2026-03-13)

| Issue | Description | Status |
|-------|-------------|--------|
| Modal close | Delivery modal blocks green section — added multi-selector close + Escape key fallback | ✅ Fixed |
| Button detection | `offsetParent` unreliable behind modal → `classList.contains('_hidden')` | ✅ Fixed |
| 3-state button | VISIBLE/HIDDEN/NOT_IN_DOM detection | ✅ Fixed + Verified |
| Wrong scraping order | Scraped green section AFTER reload (empty!) → moved to BEFORE add-to-cart | ✅ Fixed |
| Name extraction | Greedy span/div fallback picked up prices → URL-based parsing | ✅ Fixed |
| Missing product ID | No `id` field in scraped data → 500 API error → extract from `data-id` attr/URL | ✅ Fixed |
| Diagnostic cleanup | Removed all temp DIAG/DEBUG blocks | ✅ Done |

### Round 3 — Cart Detection & Parsing (2026-03-19)

| Issue | Description | Status |
|-------|-------------|--------|
| Wrong cart selector | `.VV23_CartProduct` class doesn't exist → changed to `.js-delivery-basket-item` | ✅ Fixed |
| Nodriver parsing | JS objects returned as `[['key', {type, value}]]` → fixed Python parsing to dict | ✅ Fixed |
| `save_products_safe()` | Was printing `len(dict)` (= key count) instead of product list length | ✅ Fixed |
| Seed item detection | Cart-empty check now uses 3 signals: empty text, cart item count, clear button | ✅ Fixed |

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
5. Compare scraped items with manual research on VkusVill
