"""
VkusVill Scraper using Requests (no browser!)
Uses saved cookies from export_cookies.py
Scrapes the cart HTML page directly
"""
import json
import os
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

COOKIES_FILE = "cookies.json"
DATA_FILE = "miniapp/public/data.json"
CART_URL = "https://vkusvill.ru/cart/"


def load_cookies():
    """Load cookies from file and convert to requests format"""
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ {COOKIES_FILE} not found! Run export_cookies.py first.")
        return None
    
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        selenium_cookies = json.load(f)
    
    # Convert to requests format (simple dict)
    cookies = {}
    for c in selenium_cookies:
        cookies[c["name"]] = c["value"]
    
    print(f"✅ Loaded {len(cookies)} cookies")
    return cookies


def parse_stock(text):
    """Parse stock from text like 'В наличии: 0.1 кг'"""
    if not text:
        return None, "шт"
    
    text = text.strip().lower()
    if "не в наличии" in text or "нет в наличии" in text:
        return 0, "шт"
    
    match = re.search(r'([\d.,]+)\s*(кг|шт)', text)
    if match:
        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2)
        return value, unit
    
    return None, "шт"


def scrape_green_prices():
    """Scrape VkusVill green prices using requests + saved cookies"""
    print("=" * 50)
    print(f"VkusVill Scraper - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    cookies = load_cookies()
    if not cookies:
        return None
    
    # Headers from real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
    }
    
    print("Fetching cart page...")
    
    try:
        response = requests.get(
            CART_URL,
            cookies=cookies,
            headers=headers,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return None
        
        # Check if logged in
        html = response.text
        if "Зелёные ценники" not in html:
            print("⚠️ Green prices not found - may need to re-login")
            if "Вход" in html and "Зарегистрироваться" in html:
                print("❌ Not logged in! Run export_cookies.py again.")
                return None
        else:
            print("✅ Green prices section found!")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        products = []
        
        # Find all product cards
        product_cards = soup.select('.HProductCard, .ProductCard, [class*="Product"]')
        print(f"Found {len(product_cards)} product elements")
        
        # Alternative: look for product links with data-id
        product_links = soup.select('a.HProductCard__Title, a[data-id]')
        print(f"Found {len(product_links)} product links")
        
        for link in product_links:
            product_id = link.get('data-id', '')
            name = link.get_text(strip=True)
            url = link.get('href', '')
            
            if not url.startswith('http'):
                url = f"https://vkusvill.ru{url}"
            
            # Extract ID from URL if not in data-id
            if not product_id and '/goods/' in url:
                match = re.search(r'-(\d+)\.html', url)
                if match:
                    product_id = match.group(1)
            
            # Find parent container for more info
            parent = link.find_parent(class_=lambda x: x and 'Product' in str(x))
            
            # Get price (look for price elements near link)
            price = "0"
            if parent:
                price_el = parent.select_one('[class*="Price"], [class*="price"]')
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    price_match = re.search(r'(\d+)', price_text)
                    if price_match:
                        price = price_match.group(1)
            
            # Get stock
            stock_val = None
            unit = "шт"
            if parent:
                stock_el = parent.select_one('.HProductCard__Avail, [class*="Avail"]')
                if stock_el:
                    stock_val, unit = parse_stock(stock_el.get_text())
            
            # Get image
            image = None
            if parent:
                img_el = parent.select_one('img')
                if img_el:
                    image = img_el.get('src') or img_el.get('data-src')
            
            if name and len(name) > 2:
                product = {
                    "id": product_id,
                    "name": name,
                    "currentPrice": price,
                    "oldPrice": "0",
                    "image": image,
                    "stock": stock_val,
                    "unit": unit,
                    "url": url
                }
                
                # Add category
                name_lower = name.lower()
                if any(x in name_lower for x in ['морковь', 'капуста', 'лук', 'картофель', 'огурц', 'помидор']):
                    product['category'] = 'Овощи'
                elif any(x in name_lower for x in ['яблок', 'груша', 'банан', 'манго', 'апельсин']):
                    product['category'] = 'Фрукты'
                elif any(x in name_lower for x in ['молок', 'кефир', 'йогурт', 'сметан', 'творог', 'сыр']):
                    product['category'] = 'Молочка'
                elif any(x in name_lower for x in ['мясо', 'курин', 'свинин', 'говядин']):
                    product['category'] = 'Мясо'
                elif any(x in name_lower for x in ['икра', 'рыба', 'форель', 'лосось']):
                    product['category'] = 'Морепродукты'
                else:
                    product['category'] = 'Другое'
                
                products.append(product)
        
        print(f"✅ Parsed {len(products)} products")
        
        # Save to data.json
        if products:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"✅ Saved to {DATA_FILE}")
        
        return products
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    products = scrape_green_prices()
    if products:
        print(f"\nSample products:")
        for p in products[:5]:
            print(f"  - {p['name'][:40]}... | {p['currentPrice']}₽ | Stock: {p['stock']}")
    else:
        print("\n⚠️ No products found. Try running export_cookies.py again.")
