"""
VkusVill Playwright Scraper with Saved Cookies
Uses cookies exported from undetected-chromedriver
For GitHub Actions
"""
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

COOKIES_FILE = "cookies.json"
DATA_FILE = "miniapp/public/data.json"
CART_URL = "https://vkusvill.ru/cart/"


def load_cookies():
    """Load cookies from file or environment variable"""
    # Try environment variable first (for GitHub Actions)
    if os.environ.get("VKUSVILL_COOKIES"):
        cookies = json.loads(os.environ["VKUSVILL_COOKIES"])
        print(f"✅ Loaded {len(cookies)} cookies from env")
        return cookies
    
    # Try file
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        print(f"✅ Loaded {len(cookies)} cookies from file")
        return cookies
    
    print("❌ No cookies found!")
    return None


def scrape_green_prices():
    """Scrape VkusVill green prices with Playwright using saved cookies"""
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Add saved cookies
        context.add_cookies(cookies)
        
        page = context.new_page()
        
        print("Opening cart page...")
        page.goto(CART_URL)
        
        # Wait for page to load
        page.wait_for_timeout(5000)
        
        # Check for blocks
        title = page.title()
        content = page.content()
        
        if "403" in title or "Forbidden" in content:
            print("❌ Blocked (403)!")
            browser.close()
            return None
        
        # Check for green prices
        if "Зелёные ценники" not in content:
            print("⚠️ Green prices not found - cookies may be expired")
            # Try to continue anyway
        else:
            print("✅ Green prices section found!")
        
        # Wait for products to load (JavaScript rendering)
        page.wait_for_timeout(3000)
        
        # Extract products
        products = page.evaluate("""
            () => {
                const products = [];
                
                document.querySelectorAll('a.HProductCard__Title, a[data-id]').forEach(titleEl => {
                    const productId = titleEl.getAttribute('data-id') || '';
                    const name = titleEl.innerText.trim();
                    const url = titleEl.href || '';
                    
                    // Get parent container
                    let row = titleEl.parentElement;
                    for (let i = 0; i < 5 && row; i++) {
                        if (row.querySelector('img') && row.querySelector('.HProductCard__Avail')) break;
                        row = row.parentElement;
                    }
                    if (!row) row = titleEl.parentElement.parentElement.parentElement;
                    
                    // Get image
                    const imgEl = row.querySelector('.HProductCard__ImgWrp img') || 
                                  row.querySelector('img[src*="vkusvill"]') ||
                                  row.querySelector('img');
                    
                    // Get stock
                    const stockEl = row.querySelector('.HProductCard__Avail');
                    const stockText = stockEl ? stockEl.innerText : '';
                    const stockMatch = stockText.match(/В наличии:?\\s*([\\d.,]+)\\s*(кг|шт)/i);
                    const outOfStock = stockText.toLowerCase().includes('не в наличии');
                    
                    // Get price
                    const rowText = row.innerText || '';
                    const priceMatch = rowText.match(/(\\d+)\\s*₽\\/(кг|шт)/);
                    
                    if (name && name.length > 2) {
                        products.push({
                            id: productId,
                            name: name,
                            url: url,
                            currentPrice: priceMatch ? priceMatch[1] : '0',
                            oldPrice: '0',
                            image: imgEl ? imgEl.src : null,
                            stock: stockMatch ? parseFloat(stockMatch[1].replace(',', '.')) : (outOfStock ? 0 : null),
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
            name_lower = p['name'].lower()
            if any(x in name_lower for x in ['морковь', 'капуста', 'лук', 'картофель', 'огурц', 'помидор']):
                p['category'] = 'Овощи'
            elif any(x in name_lower for x in ['яблок', 'груша', 'банан', 'манго', 'апельсин']):
                p['category'] = 'Фрукты'
            elif any(x in name_lower for x in ['молок', 'кефир', 'йогурт', 'сметан', 'творог', 'сыр']):
                p['category'] = 'Молочка'
            elif any(x in name_lower for x in ['мясо', 'курин', 'свинин', 'говядин']):
                p['category'] = 'Мясо'
            elif any(x in name_lower for x in ['икра', 'рыба', 'форель', 'лосось']):
                p['category'] = 'Морепродукты'
            else:
                p['category'] = 'Другое'
        
        # Save to file
        if products:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"✅ Saved to {DATA_FILE}")
        
        browser.close()
        return products


if __name__ == "__main__":
    products = scrape_green_prices()
    if products:
        print(f"\nSample products:")
        for p in products[:5]:
            print(f"  - {p['name'][:40]}... | {p['currentPrice']}₽")
    else:
        print("\n❌ Scraping failed")
