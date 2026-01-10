"""
VkusVill Scraper for VPS (Linux)
Uses undetected-chromedriver with xvfb for headless mode
"""
import json
import os
import time
from datetime import datetime

# Use pyvirtualdisplay for headless on Linux
try:
    from pyvirtualdisplay import Display
    HAS_DISPLAY = True
except ImportError:
    HAS_DISPLAY = False

import undetected_chromedriver as uc

# Config
PROFILE_DIR = os.path.join(os.path.dirname(__file__), "data", "chrome_profile")
DATA_FILE = os.path.join(os.path.dirname(__file__), "miniapp", "public", "data.json")
CART_URL = "https://vkusvill.ru/cart/"


def scrape_green_prices(auto_mode=False):
    """Scrape VkusVill green prices on Linux VPS"""
    print("=" * 50)
    print(f"VkusVill Scraper - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    display = None
    
    # Start virtual display on Linux
    if HAS_DISPLAY and auto_mode:
        display = Display(visible=False, size=(1920, 1080))
        display.start()
        print("Started virtual display")
    
    # Chrome options
    options = uc.ChromeOptions()
    options.add_argument("--lang=ru-RU")
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    if auto_mode:
        options.add_argument("--headless=new")
    
    driver = None
    
    try:
        driver = uc.Chrome(options=options)
        
        print("Opening cart page...")
        driver.get(CART_URL)
        time.sleep(5)
        
        # Check for green prices
        page_source = driver.page_source
        if "Зелёные ценники" not in page_source:
            print("⚠️ Green prices not found!")
            if not auto_mode:
                print("Please log in manually...")
                input("Press ENTER after logging in...")
                driver.get(CART_URL)
                time.sleep(5)
            else:
                print("Cookies may be expired. Run without auto_mode to login.")
                return None
        else:
            print("✅ Green prices found!")
        
        # Wait for JS to load
        time.sleep(3)
        
        # Extract products
        products = driver.execute_script("""
            const products = [];
            
            document.querySelectorAll('a.HProductCard__Title, a[data-id]').forEach(titleEl => {
                const productId = titleEl.getAttribute('data-id') || '';
                const name = titleEl.innerText.trim();
                const url = titleEl.href || '';
                
                let row = titleEl.parentElement;
                for (let i = 0; i < 5 && row; i++) {
                    if (row.querySelector('img') && row.querySelector('.HProductCard__Avail')) break;
                    row = row.parentElement;
                }
                if (!row) row = titleEl.parentElement.parentElement.parentElement;
                
                const imgEl = row.querySelector('.HProductCard__ImgWrp img') || 
                              row.querySelector('img[src*="vkusvill"]') ||
                              row.querySelector('img');
                
                const stockEl = row.querySelector('.HProductCard__Avail');
                const stockText = stockEl ? stockEl.innerText : '';
                const stockMatch = stockText.match(/В наличии:?\\s*([\\d.,]+)\\s*(кг|шт)/i);
                const outOfStock = stockText.toLowerCase().includes('не в наличии');
                
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
        """)
        
        print(f"✅ Found {len(products)} products")
        
        # Add categories
        for p in products:
            name_lower = p['name'].lower()
            if any(x in name_lower for x in ['морковь', 'капуста', 'лук', 'картофель']):
                p['category'] = 'Овощи'
            elif any(x in name_lower for x in ['яблок', 'груша', 'банан', 'манго']):
                p['category'] = 'Фрукты'
            elif any(x in name_lower for x in ['молок', 'кефир', 'йогурт', 'творог']):
                p['category'] = 'Молочка'
            elif any(x in name_lower for x in ['мясо', 'курин', 'свинин']):
                p['category'] = 'Мясо'
            elif any(x in name_lower for x in ['икра', 'рыба', 'форель']):
                p['category'] = 'Морепродукты'
            else:
                p['category'] = 'Другое'
        
        # Save
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
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        if display:
            display.stop()


if __name__ == "__main__":
    import sys
    auto = "--auto" in sys.argv
    products = scrape_green_prices(auto_mode=auto)
    
    if products:
        print(f"\nSample:")
        for p in products[:3]:
            print(f"  - {p['name'][:40]}...")
