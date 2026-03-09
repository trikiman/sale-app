# Live Data Mismatch Tests

Checklist to verify what our scraped data shows vs. what VkusVill actually shows live.
Run these checks whenever green prices = 0 or data looks wrong.

---

## Layer 1: Cookie Health

### Test 1.1 — Technical PHPSESSID validity
**Check:** Is `__Host-PHPSESSID` in `data/cookies.json` expired?
```python
import json, time
cookies = json.load(open('data/cookies.json'))
phpsessid = next((c for c in cookies if c['name'] == '__Host-PHPSESSID'), None)
print(phpsessid)
# PASS: expiry > time.time() OR expiry field absent (session cookie)
# FAIL: expiry == 0 or expiry < time.time()
```
**Current state (2026-03-06):** `expiry = 0` → EXPIRED → FAIL
**Root cause of green = 0.**

### Test 1.2 — Cookie load via CDP
**Check:** Does the scraper silently skip expired cookies?
- In `scrape_green.py` `_load_cookies()`: if `expiry = 0`, CDP `network.TimeSinceEpoch(0)` = Jan 1 1970 → Chrome drops cookie
- Fix: skip setting `expires` when `expiry == 0` (session cookies)

### Test 1.3 — Auth cookie validity
**Check:** Does navigating to `https://vkusvill.ru/personal/` with loaded cookies return 200 (logged in) or 302 (anonymous redirect)?
```bash
# Manually test with curl using the cookie string
curl -s -o /dev/null -w "%{http_code}" -L \
  -H "Cookie: __Host-PHPSESSID=<value>; BXVV_SALE_UID=<value>" \
  https://vkusvill.ru/personal/
# PASS: 200
# FAIL: 302 (redirect to login)
```

---

## Layer 2: Green Scraper Page Content

### Test 2.1 — "Зелёные ценники" section presence
**Check:** Does `https://vkusvill.ru/cart/` show green section when logged in?
```javascript
// Run in browser console on cart page while logged in:
document.querySelector('[data-action="GreenLabels"]')
// PASS: returns element
// FAIL: null (anonymous user sees no green section)
```

### Test 2.2 — Live count from page vs scraped count
**Check:** Is the count shown in the green button == what we scraped?
```javascript
// In browser console:
document.querySelector('[data-action="GreenLabels"] .js-vv-tizers-section__link-text')?.innerText
// Compare to green_products.json -> live_count
// PASS: numbers match (or scraper count <= live count due to OOS items)
// FAIL: live_count = 0 but button shows N items (= not authenticated)
```

### Test 2.3 — Green scraper section detection guard
**Check:** Does the scraper return early with 0 when it shouldn't?
- `scrape_green.py` line ~305: checks for "Зелёные ценники" OR "Зеленые ценники" in `document.body.innerHTML`
- If neither found → `scrape_success = True`, returns `[]`
- This is a correct exit, but only triggers because auth failed (Layer 1)

---

## Layer 3: File Format Consistency

### Test 3.1 — Output format: green vs red/yellow
| File | Format | Has `products` key? | Has `live_count`? |
|---|---|---|---|
| `green_products.json` | dict | Yes | Yes |
| `red_products.json` | list | No (is the list) | No |
| `yellow_products.json` | list (expected) | No (is the list) | No |

**Check:** `scrape_merge.py` handles both — confirmed OK (line 44-53 checks `isinstance(data, list)`)
**Status:** No bug, but inconsistent formats make debugging confusing.

### Test 3.2 — Merge counts
**Check:** After merge, do green/red/yellow counts in proposals.json match source files?
```python
import json
p = json.load(open('data/proposals.json'))
g = json.load(open('data/green_products.json'))
r = json.load(open('data/red_products.json'))
y = json.load(open('data/yellow_products.json'))

scraped_green = len(g.get('products', g if isinstance(g, list) else []))
scraped_red = len(r) if isinstance(r, list) else len(r.get('products', []))
scraped_yellow = len(y) if isinstance(y, list) else len(y.get('products', []))

merged_green = len([x for x in p['products'] if x.get('type') == 'green'])
merged_red = len([x for x in p['products'] if x.get('type') == 'red'])
merged_yellow = len([x for x in p['products'] if x.get('type') == 'yellow'])

print(f"green: scraped={scraped_green}, merged={merged_green}")
print(f"red:   scraped={scraped_red}, merged={merged_red}")
print(f"yellow: scraped={scraped_yellow}, merged={merged_yellow}")
# PASS: merged counts <= scraped counts (dedup may reduce)
# FAIL: merged > scraped (impossible) or scraped > 0 but merged == 0
```

---

## Layer 4: Site vs Our Data

### Test 4.1 — Red prices: our price vs VkusVill live price
Manual spot check for items in `red_products.json`:
1. Pick 3 items from `red_products.json`
2. Open their URLs on vkusvill.ru
3. Compare our `price` and `old_price` to what the site shows

| Product | Our price | Site price | Our old_price | Site old_price | Match? |
|---|---|---|---|---|---|
| (fill in) | | | | | |

### Test 4.2 — Yellow prices: our quantity threshold vs site
Manual spot check for items in `yellow_products.json`:
1. Pick 2 items from `yellow_products.json`
2. Check vkusvill.ru for "купи 6 и больше" label
3. Verify our `min_qty` and `price` match

### Test 4.3 — Green prices: requires logged-in technical account
When tech cookies are valid:
1. Run green scraper
2. Pick 3 items from `green_products.json`
3. Open vkusvill.ru/cart/ while logged in as the technical account
4. Verify our `price` matches the green price shown in cart

### Test 4.4 — Stock status (can_buy / max_q)
**Check:** Do our `can_buy` and `max_q` fields match what VkusVill shows?
1. Find items where `can_buy = false` in proposals.json
2. Visit their product pages — are they actually out of stock?

---

## Layer 5: MiniApp Display

### Test 5.1 — greenMissing flag
**Check:** Is `proposals.json` correctly setting `greenMissing`?
```python
import json
d = json.load(open('data/proposals.json'))
print('greenMissing:', d.get('greenMissing'))
print('greenLiveCount:', d.get('greenLiveCount'))
# If both are False/0 but we know green is broken → flag logic wrong
# Current: greenMissing=false even though green_products has 0 items
# BUG: greenMissing only checks file existence, not content
```

### Test 5.2 — Stale data detection threshold
**Check:** Are source files fresh?
```python
import os, time
for f in ['green_products.json', 'red_products.json', 'yellow_products.json']:
    age = (time.time() - os.path.getmtime(f'data/{f}')) / 60
    print(f"{f}: {age:.1f} min old")
# PASS: all < 10 min (STALE_MINUTES in scrape_merge.py)
# FAIL: any > 10 min when scraper should be running every 5 min
```

### Test 5.3 — MiniApp filter shows 0 green
1. Open miniapp at http://localhost:5173
2. Click the green filter chip
3. If count = 0 but step 4.3 shows products on site → auth broken (confirmed)

---

## Verified via Browser (2026-03-06)

**Tech account (9958993023) green section check:**
- Page `/cart/` loads with tech account logged in ✓
- "Зелёных ценников сейчас нет" shown initially — BUT this was because green items were already IN the cart
- After user removed 1 cart item → "Зелёные ценники" section appeared with items (Апельсины, Виноград)
- **Real root cause: VkusVill hides green items from the recommendation section if they're already in the cart. Cart had all green items → section showed 0 → scraper reported 0.**

**Fix applied:** Green scraper now reads green items directly from `basket_recalc.php` (IS_GREEN flag) as a fallback when the recommendation section returns 0. This catches all green-priced items already in the cart without clearing it.

---

## Confirmed Bugs Found (2026-03-06)

| ID | Layer | Bug | Root Cause | Status |
|---|---|---|---|---|
| BUG-065 | Cookie load | `__Host-PHPSESSID` expiry=0 loaded via CDP → Chrome drops it → anonymous session → 0 green items | Session cookies saved with `expiry: 0` in JSON; CDP `TimeSinceEpoch(0)` = 1970 | NEEDS FIX |
| BUG-066 | greenMissing flag | `greenMissing` only checks if file exists, not if it has 0 products | `scrape_merge.py` line 91: `not os.path.exists(...)` — file exists but empty | NEEDS FIX |

## Fix for BUG-065: Skip expiry=0 when loading cookies via CDP

In `scrape_green.py` `_load_cookies()`:
```python
# BEFORE (broken — sets expired timestamp):
if 'expiry' in c:
    cp.expires = network.TimeSinceEpoch(c['expiry'])

# AFTER (fix — skip session cookies with expiry=0):
if c.get('expiry', 0) > 0:
    cp.expires = network.TimeSinceEpoch(c['expiry'])
```

## Fix for BUG-066: greenMissing should also check for 0 products

In `scrape_merge.py` line 91:
```python
# BEFORE:
green_missing = not os.path.exists(os.path.join(DATA_DIR, "green_products.json"))

# AFTER:
green_path = os.path.join(DATA_DIR, "green_products.json")
if not os.path.exists(green_path):
    green_missing = True
else:
    gdata = json.load(open(green_path))
    gproducts = gdata.get('products', gdata) if isinstance(gdata, dict) else gdata
    green_missing = len(gproducts) == 0
```
