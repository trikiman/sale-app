"""
Test VkusVill API directly (no browser!)
If this works, it can run on Replit without any browser automation
"""
import json
import requests

COOKIES_FILE = "cookies.json"

# Possible VkusVill API endpoints to try
API_ENDPOINTS = [
    "https://vkusvill.ru/api/cart/",
    "https://vkusvill.ru/api/v1/cart/",
    "https://vkusvill.ru/api/cart/get/",
    "https://vkusvill.ru/ajax/cart/",
    "https://vkusvill.ru/api/goods/",
    "https://vkusvill.ru/api/catalog/green-price/",
    "https://vkusvill.ru/api/v1/goods/green-price/",
]


def load_cookies():
    with open(COOKIES_FILE) as f:
        selenium_cookies = json.load(f)
    
    # Convert to requests format
    cookies = {}
    for c in selenium_cookies:
        cookies[c["name"]] = c["value"]
    return cookies


def test_api():
    print("=" * 50)
    print("Testing VkusVill API (no browser)")
    print("=" * 50)
    
    cookies = load_cookies()
    print(f"Loaded {len(cookies)} cookies")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Referer": "https://vkusvill.ru/cart/",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    # Test each endpoint
    for url in API_ENDPOINTS:
        print(f"\nTrying: {url}")
        try:
            response = requests.get(url, cookies=cookies, headers=headers, timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                try:
                    data = response.json()
                    print(f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                    print(f"  Preview: {str(data)[:200]}...")
                except:
                    print(f"  Not JSON: {response.text[:200]}...")
            elif response.status_code == 403:
                print(f"  ❌ Blocked (403)")
            else:
                print(f"  Response: {response.text[:100]}...")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    # Also try the main cart page
    print(f"\nTrying main cart page...")
    try:
        response = requests.get("https://vkusvill.ru/cart/", cookies=cookies, headers=headers, timeout=10)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            if "Зелёные ценники" in response.text:
                print("  ✅ Green prices found in HTML!")
            else:
                print("  ⚠️ Page loaded but no green prices")
        else:
            print(f"  ❌ Status: {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    test_api()
