"""
VkusVill Scraper for Replit
Uses Playwright with saved cookies
"""
import json
import os
from datetime import datetime

# Install playwright on first run
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "playwright"])
    subprocess.run(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright

COOKIES_FILE = "cookies.json"
DATA_FILE = "data.json"
CART_URL = "https://vkusvill.ru/cart/"


def load_cookies():
    """Load cookies from file"""
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ {COOKIES_FILE} not found!")
        print("Upload your cookies.json file from your PC")
        return None
    
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    print(f"✅ Loaded {len(cookies)} cookies")
    return cookies


def scrape_green_prices():
    """Scrape VkusVill green prices"""
    print("=" * 50)
    print(f"VkusVill Scraper - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    cookies = load_cookies()
    if not cookies:
        return None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # Add cookies
        context.add_cookies(cookies)
        
        page = context.new_page()
        
        print("Opening cart page...")
        page.goto(CART_URL, timeout=60000)
        page.wait_for_timeout(5000)
        
        # Check status
        title = page.title()
        content = page.content()
        
        if "403" in title or "Forbidden" in content:
            print("❌ Blocked (403)!")
            browser.close()
            return None
        
        if "Зелёные ценники" not in content:
            print("⚠️ Green prices not found")
        else:
            print("✅ Green prices found!")
        
        # Wait for JS
        page.wait_for_timeout(3000)
        
        # Extract products
        products = page.evaluate("""
            () => {
                const products = [];
                document.querySelectorAll('a.HProductCard__Title, a[data-id]').forEach(el => {
                    const name = el.innerText.trim();
                    const url = el.href || '';
                    let row = el.parentElement;
                    for (let i = 0; i < 5 && row; i++) {
                        if (row.querySelector('img')) break;
                        row = row.parentElement;
                    }
                    const imgEl = row?.querySelector('img');
                    const stockEl = row?.querySelector('.HProductCard__Avail');
                    const stockText = stockEl ? stockEl.innerText : '';
                    const stockMatch = stockText.match(/([\\d.,]+)\\s*(кг|шт)/i);
                    const priceMatch = (row?.innerText || '').match(/(\\d+)\\s*₽/);
                    
                    if (name && name.length > 2) {
                        products.push({
                            name: name,
                            url: url,
                            currentPrice: priceMatch ? priceMatch[1] : '0',
                            image: imgEl ? imgEl.src : null,
                            stock: stockMatch ? parseFloat(stockMatch[1].replace(',', '.')) : null,
                            unit: stockMatch ? stockMatch[2] : 'шт'
                        });
                    }
                });
                return products;
            }
        """)
        
        print(f"✅ Found {len(products)} products")
        
        # Add categories
        for p in products:
            name = p['name'].lower()
            if any(x in name for x in ['морковь', 'капуста', 'лук', 'картофель']):
                p['category'] = 'Овощи'
            elif any(x in name for x in ['яблок', 'груша', 'банан']):
                p['category'] = 'Фрукты'
            elif any(x in name for x in ['молок', 'кефир', 'йогурт']):
                p['category'] = 'Молочка'
            else:
                p['category'] = 'Другое'
        
        # Save
        if products:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"✅ Saved to {DATA_FILE}")
        
        browser.close()
        return products


if __name__ == "__main__":
    products = scrape_green_prices()
    if products:
        for p in products[:3]:
            print(f"  - {p['name'][:40]}...")
    else:
        print("❌ Failed. Check cookies.json")
