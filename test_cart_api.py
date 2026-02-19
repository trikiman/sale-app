"""
Test VkusVill add-to-cart API with requests.Session.
First visits the site to establish session, then adds to cart.
Also tests a product with higher MAX_Q.
"""
import requests
import json
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")
API_URL = "https://vkusvill.ru/ajax/delivery_order/basket_add.php"


def main():
    print("🧪 Testing with requests.Session")
    print("=" * 60)
    
    session = requests.Session()
    
    # Set User-Agent
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    })
    
    # Load saved cookies
    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        cookies_list = json.load(f)
    
    for c in cookies_list:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.vkusvill.ru'))
    
    print(f"✅ Loaded {len(cookies_list)} cookies")
    
    # Step 1: Visit the site to establish session
    print("\n📌 Step 1: Visiting vkusvill.ru to warm up session...")
    r = session.get('https://vkusvill.ru/', timeout=15)
    print(f"   Status: {r.status_code}, cookies after visit: {len(session.cookies)}")
    
    # Show important cookies
    for name in ['__Host-PHPSESSID', 'PHPSESSID', 'UF_USER_AUTH', 'domain_sid']:
        val = session.cookies.get(name, 'NOT SET')
        if val != 'NOT SET':
            print(f"   {name}: {val[:30]}...")
    
    # Step 2: Try adding a product with high MAX_Q (Борщ 42530 has MAX_Q=12)
    print("\n📌 Step 2: Adding product 42530 (Борщ, MAX_Q=12)...")
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Origin': 'https://vkusvill.ru',
        'Referer': 'https://vkusvill.ru/goods/borshch-s-govyadinoy-42530.html',
    }
    
    data = {
        'id': 42530,
        'xmlid': 42530,
        'max': 1,
        'delivery_no_set': 'N',
        'koef': 1,
        'step': 1,
        'coupon': '',
        'isExperiment': 'N',
        'isOnlyOnline': '',
        'isGreen': 0,
        'user_id': 6443332,
        'skip_analogs': '',
        'is_app': '',
        'is_default_button': 'Y',
        'cssInited': 'N',
        'price_type': 1,
    }
    
    r = session.post(API_URL, data=data, headers=headers, timeout=15)
    print(f"   Status: {r.status_code}")
    
    try:
        result = r.json()
        success = result.get('success')
        error = result.get('error', '')
        
        if success == 'Y':
            ba = result.get('basketAdded', {})
            print(f"   ✅ SUCCESS! {ba.get('NAME', '?')} (Q={ba.get('Q')}, Price={ba.get('PRICE')})")
            totals = result.get('totals', {})
            print(f"   Cart: {totals.get('Q_ITEMS')} items, {totals.get('PRICE_FINAL')} руб")
        else:
            print(f"   ❌ FAILED: success={success}, error='{error}'")
            # Show response keys for debugging
            print(f"   Keys: {list(result.keys())}")
            popup = result.get('POPUP_ANALOGS', '')
            if popup and popup != 'N':
                print(f"   POPUP_ANALOGS present (length: {len(popup)})")
    except:
        print(f"   Raw: {r.text[:300]}")
    
    # Step 3: Try minimal payload - just id + xmlid
    print("\n📌 Step 3: Minimal payload (id + xmlid only)...")
    data_min = {'id': 42530, 'xmlid': 42530}
    r = session.post(API_URL, data=data_min, headers=headers, timeout=15)
    try:
        result = r.json()
        print(f"   success={result.get('success')}, error='{result.get('error', '')}'")
        if result.get('success') == 'Y':
            print(f"   ✅ MINIMAL PAYLOAD WORKS!")
    except:
        print(f"   Raw: {r.text[:200]}")
    
    # Step 4: Check if we're logged in
    print("\n📌 Step 4: Checking login status...")
    r = session.get('https://vkusvill.ru/personal/', timeout=15, allow_redirects=False)
    print(f"   Personal page status: {r.status_code}")
    if r.status_code == 302:
        print(f"   ❌ Redirected (not logged in): {r.headers.get('Location', '')}")
    elif r.status_code == 200:
        if 'Выход' in r.text or 'Кабинет' in r.text:
            print(f"   ✅ Logged in!")
        else:
            print(f"   ⚠️ Page loaded but unclear if logged in")


if __name__ == "__main__":
    main()
