"""
Yellow prices scraper - standalone script for subagent
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
YELLOW_URL = "https://vkusvill.ru/offers/?F%5B212%5D%5B%5D=278&F%5BDEF_3%5D=1&sf4=Y&statepop"

def clean_category(cat):
    if not cat:
        return 'Другое'
    return cat.split('//')[0].strip() or 'Другое'


def init_driver():
    # Use shared profile with VkusVill login (same as green)
    profile = os.path.join(BASE_DIR, "data", "chrome_profile_shared")
    os.makedirs(profile, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={profile}')
    
    driver = uc.Chrome(options=options, headless=False)
    return driver


def scrape_yellow_prices():
    print("🔄 [YELLOW] Starting...")
    driver = None
    products = []
    
    try:
        driver = init_driver()
        driver.get(YELLOW_URL)
        time.sleep(10)  # Wait for initial load
        
        # Validate that YELLOW filter "Скидка по вашей карте" is active
        is_active = driver.execute_script("""
            const buttons = document.querySelectorAll('.VV_Teaser__link, .js-filter-link, [class*="filter"]');
            for (const btn of buttons) {
                if (btn.textContent.includes('Скидка по вашей карте') && 
                    (btn.classList.contains('active') || btn.classList.contains('is-active') ||
                     getComputedStyle(btn).borderColor.includes('rgb(76, 175, 80)') ||
                     btn.closest('.active'))) {
                    return true;
                }
            }
            // Also check if URL filter applied correctly
            return document.querySelectorAll('.ProductCard').length > 0;
        """)
        print(f"  [YELLOW] Filter active: {is_active}")
        
        # Smart pagination: click once, scroll 500px, count in-stock products
        # Stop when in-stock count stops increasing
        prev_in_stock = 0
        no_increase_count = 0
        
        for batch in range(20):  # Max 20 iterations (safety limit)
            # Click "Показать ещё" ONCE if visible
            driver.execute_script("""
                const btn = Array.from(document.querySelectorAll('button, a')).find(
                    b => b.innerText.toLowerCase().includes('показать ещ') && b.offsetParent
                );
                if (btn) btn.click();
            """)
            time.sleep(2)
            
            # Scroll 500px ONCE
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
            
            # Count IN-STOCK products (with "В наличии X шт", not "Не осталось")
            in_stock_count = driver.execute_script("""
                let count = 0;
                document.querySelectorAll('.ProductCard').forEach(card => {
                    const text = card.innerText;
                    // In-stock has "В наличии X шт", out-of-stock has "Не осталось"
                    if (text.includes('В наличии') && !text.includes('Не осталось')) {
                        count++;
                    }
                });
                return count;
            """)
            
            print(f"  [YELLOW] In-stock count: {in_stock_count}")
            
            # Stop if in-stock count didn't increase
            if in_stock_count <= prev_in_stock:
                no_increase_count += 1
                if no_increase_count >= 2:
                    print(f"  [YELLOW] In-stock count stopped growing - done")
                    break
            else:
                no_increase_count = 0
            
            prev_in_stock = in_stock_count
        
        products = driver.execute_script("""
            const products = [];
            document.querySelectorAll('.ProductCard').forEach(card => {
                // ONLY include products with "В наличии X шт" (in-stock)
                const cardText = card.innerText;
                
                // Skip if out-of-stock (has "Не осталось")
                if (cardText.includes('Не осталось')) return;
                
                // Must have "В наличии" text to be in-stock
                if (!cardText.includes('В наличии')) return;
                
                const titleEl = card.querySelector('.ProductCard__link');
                // Use data-layer prices (hidden spans with clean numeric values)
                const priceEl = card.querySelector('.js-datalayer-catalog-list-price');
                const oldPriceEl = card.querySelector('.js-datalayer-catalog-list-price-old');
                const imgEl = card.querySelector('.ProductCard__imageLink img') || card.querySelector('img');
                const catEl = card.querySelector('.js-datalayer-catalog-list-category');
                
                if (titleEl) {
                    const url = titleEl.href || '';
                    const idMatch = url.match(/-(\\d+)\\.html/);
                    const currentPrice = priceEl ? priceEl.innerText.trim() : '0';
                    const oldPrice = oldPriceEl ? oldPriceEl.innerText.trim() : '0';
                    
                    products.push({
                        id: idMatch ? idMatch[1] : '',
                        name: titleEl.innerText.trim(),
                        url: url,
                        currentPrice: currentPrice.replace(/[^0-9]/g, ''),
                        oldPrice: oldPrice.replace(/[^0-9]/g, ''),
                        image: imgEl ? imgEl.src : '',
                        stock: 99,
                        unit: 'шт',
                        category: catEl ? catEl.innerText.trim() : '',
                        type: 'yellow'
                    });
                }
            });
            return products;
        """)
        
        for p in products:
            p['category'] = clean_category(p.get('category', ''))
        
        print(f"✅ [YELLOW] Found {len(products)} products")
        
    except Exception as e:
        print(f"❌ [YELLOW] Error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # Save to temp file
    output_path = os.path.join(DATA_DIR, "yellow_products.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Saved {len(products)} yellow products to {output_path}")
    return products


if __name__ == "__main__":
    scrape_yellow_prices()
