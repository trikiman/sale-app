"""Diagnose missing chicken from basket_recalc."""
import sys, json
sys.path.insert(0, '/home/ubuntu/saleapp')
from scrape_green import _fetch_basket_snapshot

basket = _fetch_basket_snapshot()
if not basket:
    print("ERROR: basket_recalc returned empty")
    sys.exit(1)

print(f"Total basket items: {len(basket)}")
print()

# Look for ALL items, especially chicken
for key, item in basket.items():
    if not isinstance(item, dict):
        continue
    name = item.get('NAME', '')
    is_green = item.get('IS_GREEN')
    can_buy = item.get('CAN_BUY')
    pid = item.get('PRODUCT_ID', '')
    price = item.get('PRICE', '')
    max_q = item.get('MAX_Q', '')
    
    # Print ALL items to see whats in the cart
    marker = ''
    if is_green in ('1', 1, True):
        marker = ' [GREEN]'
    if 'цыплен' in name.lower() or 'филе' in name.lower() or 'chicken' in name.lower():
        marker = ' *** CHICKEN ***'
    
    print(f"  {pid:>8} | {name[:40]:40} | green={str(is_green):5} | buy={str(can_buy):3} | price={str(price):6} | max_q={str(max_q):5}{marker}")
