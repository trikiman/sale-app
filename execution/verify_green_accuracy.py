"""
GREEN SCRAPER ACCURACY VERIFICATION CHECKLIST
==============================================
Automated 3-way comparison:
  1. VkusVill GREEN SECTION (what's actually green-tagged)
  2. VkusVill CART LIST (what's in the tech account cart)
  3. OUR API (what our site shows as green)

Run: python execution/verify_green_accuracy.py
  --local   : compare against local green_products.json instead of live API
  --api-url : override API URL (default: https://vkusvillsale.vercel.app/api/products)

Exit codes:
  0 = all checks pass
  1 = mismatches found

VkusVill Cart Page DOM Structure (https://vkusvill.ru/cart/):
=============================================================
GREEN SECTION (items with green price tags — the source of truth):
  Selector: #js-Delivery__Order-green-state-not-empty
            > div.VV_TizersSection__Content.js-order-form-green-labels-slider-wrp
            > div
  Contains: ProductCard elements with green-tagged items (swiper slides)

CART LIST (items currently in the shopping cart):
  Selector: #js-delivery__basket--notempty
            > div.js-log-place.js-datalayer-catalog-list.js-datalayer-basket
  Contains: BasketItem/CartItem elements (items user will actually buy)

KEY INSIGHT: Green section ≠ Cart list!
  - Green section shows available green-tagged discounts
  - Cart list shows items the scraper successfully added to cart
  - If scrape_green_add.py fails to click "В корзину" for an item,
    it will be in green section but NOT in cart list
  - Our API should match GREEN SECTION count, not cart count
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIES_PATH = os.path.join(DATA_DIR, "cookies.json")

MSK = timezone(timedelta(hours=3))


# ═══════════════════════════════════════════════════════
# STEP 1: Fetch OUR API green items
# ═══════════════════════════════════════════════════════

def fetch_our_api(api_url="https://vkusvillsale.vercel.app/api/products", local=False):
    """Fetch green items from our API or local file."""
    if local:
        path = os.path.join(DATA_DIR, "green_products.json")
        if not os.path.exists(path):
            print("  ❌ No local green_products.json found")
            return [], 0, None
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        products = data.get('products', data) if isinstance(data, dict) else data
        live_count = data.get('live_count', 0) if isinstance(data, dict) else 0
        mtime = os.path.getmtime(path)
        updated = datetime.fromtimestamp(mtime, tz=MSK).strftime("%Y-%m-%d %H:%M:%S")
        return products, live_count, updated

    import urllib.request
    with urllib.request.urlopen(api_url, timeout=10) as r:
        data = json.loads(r.read())
    all_products = data.get('products', [])
    greens = [p for p in all_products if isinstance(p, dict) and p.get('type') == 'green']
    return greens, data.get('greenLiveCount', 0), data.get('updatedAt')


# ═══════════════════════════════════════════════════════
# STEP 2: Fetch VkusVill basket_recalc (cart items)
# ═══════════════════════════════════════════════════════

def fetch_vkusvill_cart():
    """Fetch cart items from VkusVill basket_recalc API using tech account cookies."""
    if not os.path.exists(COOKIES_PATH):
        print("  ❌ No cookies.json — can't fetch VkusVill cart")
        return None

    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        raw_cookies = json.load(f)

    cookies = {c['name']: c['value'] for c in raw_cookies}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://vkusvill.ru',
        'Referer': 'https://vkusvill.ru/cart/',
    }

    try:
        import httpx
    except ImportError:
        print("  ⚠️ httpx not installed — skipping VkusVill cart check")
        return None

    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                'https://vkusvill.ru/ajax/delivery_order/basket_recalc.php',
                data={'COUPON': '', 'BONUS': ''},
                headers=headers,
                cookies=cookies,
            )
        data = r.json()
        basket = data.get('basket', {})
        if not isinstance(basket, dict):
            return {}

        cart_items = {}
        for item in basket.values():
            if not isinstance(item, dict):
                continue
            pid = str(item.get('PRODUCT_ID', ''))
            if not pid:
                continue
            cart_items[pid] = {
                'id': pid,
                'name': item.get('NAME', ''),
                'price': str(item.get('PRICE', '')),
                'is_green': item.get('IS_GREEN') in ('1', 1, True),
                'can_buy': item.get('CAN_BUY') == 'Y',
                'quantity': item.get('QUANTITY', 0),
            }
        return cart_items
    except Exception as e:
        print(f"  ❌ basket_recalc failed: {e}")
        return None


# ═══════════════════════════════════════════════════════
# STEP 3: Build report
# ═══════════════════════════════════════════════════════

def run_checklist(api_url="https://vkusvillsale.vercel.app/api/products", local=False):
    all_pass = True
    now = datetime.now(tz=MSK).strftime("%Y-%m-%d %H:%M:%S MSK")

    print(f"\n{'━' * 65}")
    print(f" GREEN SCRAPER VERIFICATION CHECKLIST")
    print(f" Run: {now}")
    print(f"{'━' * 65}")

    # ── CHECK 1: Fetch our API ──
    print(f"\n{'─' * 65}")
    print(f" CHECK 1: Our API / green_products.json")
    print(f"{'─' * 65}")

    source = "local file" if local else api_url
    print(f"  Source: {source}")

    our_greens, our_live_count, our_updated = fetch_our_api(api_url, local)
    our_by_id = {str(p.get('id', '')): p for p in our_greens}
    print(f"  Green items:     {len(our_greens)}")
    print(f"  greenLiveCount:  {our_live_count}")
    print(f"  updatedAt:       {our_updated}")
    for p in our_greens:
        print(f"    {str(p.get('id','')):>6} | {p.get('name','')[:42]:42s} | {str(p.get('currentPrice','')):>5}₽ | stock={p.get('stock')}")

    # ── CHECK 2: Fetch VkusVill cart ──
    print(f"\n{'─' * 65}")
    print(f" CHECK 2: VkusVill cart (basket_recalc API)")
    print(f"{'─' * 65}")

    cart = fetch_vkusvill_cart()
    if cart is None:
        print("  ⚠️ SKIPPED — could not fetch cart")
        cart_green_ids = set()
        cart_all_ids = set()
    else:
        cart_green_items = {pid: item for pid, item in cart.items() if item['is_green']}
        cart_non_green = {pid: item for pid, item in cart.items() if not item['is_green']}

        print(f"  Total cart items:   {len(cart)}")
        print(f"  IS_GREEN=1 items:   {len(cart_green_items)}")
        print(f"  Non-green items:    {len(cart_non_green)}")

        print(f"\n  Cart items (IS_GREEN=1):")
        for pid, item in sorted(cart_green_items.items(), key=lambda x: x[1]['name']):
            in_our = "✓" if pid in our_by_id else "✗"
            print(f"    {in_our} {pid:>6} | {item['name'][:42]:42s} | {item['price']:>5}₽")

        if cart_non_green:
            print(f"\n  Cart items (NOT green):")
            for pid, item in sorted(cart_non_green.items(), key=lambda x: x[1]['name']):
                leaked = "⚠ LEAKED" if pid in our_by_id else "  ok"
                print(f"    {leaked} {pid:>6} | {item['name'][:42]:42s} | {item['price']:>5}₽")

        cart_green_ids = set(cart_green_items.keys())
        cart_all_ids = set(cart.keys())

    # ── CHECK 3: Cross-comparison ──
    print(f"\n{'─' * 65}")
    print(f" CHECK 3: Cross-comparison")
    print(f"{'─' * 65}")

    our_ids = set(our_by_id.keys())

    # 3a: Items in our API but NOT in cart (any status)
    our_not_in_cart = our_ids - cart_all_ids
    if our_not_in_cart:
        print(f"\n  ⚠ In OUR API but NOT in VkusVill cart at all ({len(our_not_in_cart)}):")
        for pid in sorted(our_not_in_cart):
            p = our_by_id[pid]
            print(f"    👻 {pid:>6} | {p.get('name','')[:42]}")
        all_pass = False
    else:
        print(f"\n  ✓ All our API items exist in VkusVill cart")

    # 3b: Items in cart with IS_GREEN=1 but NOT in our API
    if cart is not None:
        cart_green_not_in_ours = cart_green_ids - our_ids
        if cart_green_not_in_ours:
            print(f"\n  ⚠ IS_GREEN=1 in cart but MISSING from our API ({len(cart_green_not_in_ours)}):")
            for pid in sorted(cart_green_not_in_ours):
                item = cart[pid]
                print(f"    ❌ {pid:>6} | {item['name'][:42]}")
            all_pass = False
        else:
            print(f"  ✓ All IS_GREEN=1 cart items are in our API")

    # 3c: Non-green cart items leaking into our API
    if cart is not None:
        non_green_leaked = (our_ids & cart_all_ids) - cart_green_ids
        if non_green_leaked:
            print(f"\n  ❌ NON-GREEN cart items LEAKED into our API ({len(non_green_leaked)}):")
            for pid in sorted(non_green_leaked):
                item = cart.get(pid, {})
                print(f"    🔴 {pid:>6} | {item.get('name','')[:42]} | IS_GREEN={item.get('is_green')}")
            all_pass = False
        else:
            print(f"  ✓ No non-green cart items leaked into our API")

    # ── CHECK 4: greenLiveCount accuracy ──
    print(f"\n{'─' * 65}")
    print(f" CHECK 4: greenLiveCount accuracy")
    print(f"{'─' * 65}")

    if cart is not None:
        cart_green_count = len(cart_green_ids)
        print(f"  greenLiveCount (scraper claims): {our_live_count}")
        print(f"  IS_GREEN=1 in cart:              {cart_green_count}")
        print(f"  Items in our API:                {len(our_greens)}")

        if our_live_count == len(our_greens) and our_live_count != cart_green_count:
            print(f"  ❌ INFLATED — live_count matches scraped count but not cart IS_GREEN count")
            print(f"     This means live_count = max(live_count, len(products)) is hiding the real count")
            all_pass = False
        elif our_live_count == cart_green_count:
            print(f"  ✓ greenLiveCount matches cart IS_GREEN count")
        else:
            print(f"  ⚠ greenLiveCount ({our_live_count}) ≠ cart IS_GREEN ({cart_green_count})")

    # ── CHECK 5: Green section vs green items on site ──
    # Note: This check requires the green section count from VkusVill DOM
    # The scraper should report this. For now we compare cart IS_GREEN vs our output.
    print(f"\n{'─' * 65}")
    print(f" CHECK 5: Summary — what to verify on VkusVill site")
    print(f"{'─' * 65}")

    if cart is not None:
        print(f"\n  Manual verification needed:")
        print(f"  Open https://vkusvill.ru/cart/ in browser and compare:")
        print(f"")
        print(f"  ┌─────────────────────────────────────────────────────────────┐")
        print(f"  │ Source                  │ Count │ Match?                    │")
        print(f"  ├─────────────────────────┼───────┼───────────────────────────┤")
        print(f"  │ Green section on site   │  ???  │ Count items in section    │")
        print(f"  │ Cart list on site       │ {len(cart):>4}  │ Items in cart             │")
        print(f"  │ Cart IS_GREEN=1 (API)   │ {len(cart_green_ids):>4}  │ Should match green sect.  │")
        print(f"  │ Our API green items     │ {len(our_greens):>4}  │ Should match green sect.  │")
        print(f"  │ greenLiveCount          │ {our_live_count:>4}  │ Should match green sect.  │")
        print(f"  └─────────────────────────┴───────┴───────────────────────────┘")
        print(f"")
        print(f"  Items to check on site:")
        all_relevant = {}
        for pid in our_ids | cart_green_ids:
            item = our_by_id.get(pid) or cart.get(pid, {})
            name = item.get('name', '') if isinstance(item, dict) else ''
            in_our = pid in our_ids
            in_cart_green = pid in cart_green_ids
            in_cart = pid in cart_all_ids
            all_relevant[pid] = {
                'name': name,
                'in_our_api': in_our,
                'in_cart_green': in_cart_green,
                'in_cart': in_cart,
            }

        for pid, info in sorted(all_relevant.items(), key=lambda x: x[1]['name']):
            flags = []
            if info['in_our_api']:
                flags.append("OUR_API")
            if info['in_cart_green']:
                flags.append("CART_GREEN")
            if info['in_cart'] and not info['in_cart_green']:
                flags.append("CART_NONGR")
            status = "✓" if info['in_our_api'] and info['in_cart_green'] else "⚠"
            print(f"    {status} {pid:>6} | {info['name'][:40]:40s} | {', '.join(flags)}")

    # ── VERDICT ──
    print(f"\n{'━' * 65}")
    if all_pass:
        print(f" ✅ ALL CHECKS PASSED")
    else:
        print(f" ❌ MISMATCHES FOUND — see details above")
    print(f"{'━' * 65}\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    local = "--local" in sys.argv
    api_url = "https://vkusvillsale.vercel.app/api/products"
    for arg in sys.argv[1:]:
        if arg.startswith("--api-url="):
            api_url = arg.split("=", 1)[1]

    sys.exit(run_checklist(api_url=api_url, local=local))
