"""
VkusVill Scraper 2.0 (Green/Red/Yellow Prices)
Uses persistent Chrome profile and unified JSON output.
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json
import os
import sys
from datetime import datetime
from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount, ChromeLock

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chrome_profile_shared")
RED_BOOK_URL = "https://vkusvill.ru/offers/?F%5B212%5D%5B%5D=284"
YELLOW_PRICE_URL = "https://vkusvill.ru/offers/?F%5B212%5D%5B%5D=278"

def init_driver(headless=False):
    """Initialize Chrome with persistent profile"""
    print("=" * 60)
    print("Initializing Chrome Driver...")
    print(f"Profile: {PROFILE_DIR}")
    print("=" * 60)
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={PROFILE_DIR}')

    with ChromeLock():
        try:
            return uc.Chrome(options=options, headless=headless)
        except OSError as e:
            if "WinError 183" in str(e):
                print(f"⚠️ WinError 183 despite lock, retrying in 2s...")
                time.sleep(2)
                return uc.Chrome(options=options, headless=headless)
            raise e


def scrape_catalog_page(driver, url, product_type):
    """Scrape standard catalog pages (Red Book, Yellow Prices)"""
    print(f"\nScanning {product_type.upper()} page: {url}")
    products = []
    
    try:
        driver.get(url)
        time.sleep(5)
        
        # Scroll to load more
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        products = driver.execute_script(f"""
            const products = [];
            const type = "{product_type}";
            
            document.querySelectorAll('.ProductCard').forEach(card => {{
                // Stock check: must have 'Add to cart' button 
                // and NOT have 'Notify' class/text
                const btn = card.querySelector('.js-delivery__basket--add');
                const notify = card.querySelector('.ProductCard__notify');
                
                // If button exists and text is 'В корзину' (or similar positive action), it's good.
                // If button missing or 'Узнать о поступлении', skip.
                if (!btn || (btn.innerText && btn.innerText.includes('Узнать'))) {{
                     return;
                }}
                if (notify && notify.offsetParent !== null) {{
                     return; 
                }}
                
                const titleEl = card.querySelector('.ProductCard__link');
                const priceEl = card.querySelector('.Price.subtitle');
                const oldPriceEl = card.querySelector('.Price._last');
                const imgEl = card.querySelector('.ProductCard__imageImg');

                // Extract real category from data layer element
                const catEl = card.querySelector('.js-datalayer-catalog-list-category');
                const category = catEl ? catEl.innerText.trim() : '';

                if (titleEl && priceEl) {{
                    const url = titleEl.href || '';
                    const idMatch = url.match(/-(\\d+)\\.html/);

                    products.push({{
                        id: idMatch ? idMatch[1] : '',
                        name: titleEl.innerText.trim(),
                        url: url,
                        currentPrice: priceEl.innerText.replace(/[^0-9.,]/g, ''),
                        oldPrice: oldPriceEl ? oldPriceEl.innerText.replace(/[^0-9.,]/g, '') : '',
                        image: imgEl ? imgEl.src : '',
                        stock: 99, // Catalog doesn't show exact stock, assume available
                        unit: 'шт',
                        category: category,
                        type: type
                    }});
                }}
            }});
            return products;
        """)
        
        # Clean categories and prices using utils
        for p in products:
            p['currentPrice'] = clean_price(p.get('currentPrice'))
            p['oldPrice'] = clean_price(p.get('oldPrice'))
            raw_cat = p.get('category', '').split('//')[0].strip()
            p['category'] = normalize_category(raw_cat, p['name'], p.get('id'))

            # Ensure discount is synthesized if missing
            p = synthesize_discount(p)

        print(f"✅ Found {len(products)} {product_type} items")
        return products
        
    except Exception as e:
        print(f"⚠️ Error scraping {product_type}: {e}")
        return []

def scrape_green_prices(driver, auto_mode=False):
    """Scrape Green Prices from Cart (preserving original logic)"""
    print("\n--- Phase 1: Green Prices (Cart) ---")
    products = []
    
    try:
        # Navigate to cart
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        if "403" in driver.title or "Forbidden" in driver.page_source:
            print("❌ Blocked by VkusVill!")
            return []
            
        page_source = driver.page_source
        if "Зелёные ценники" not in page_source:
            print("⚠️ Green prices not found in cart (Not logged in or none available)")
            return []
            
        print("✅ Green prices section found!")
        
        # Try to find and click the show all button
        use_modal = False
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)
            
            clicked = driver.execute_script("""
                // Try the specific button ID first
                const showAllBtn = document.getElementById('js-Delivery__Order-green-show-all');
                if (showAllBtn) {
                    showAllBtn.scrollIntoView();
                    showAllBtn.click();
                    return 'clicked_by_id';
                }

                // Fallback: find by class in green section
                const sections = document.querySelectorAll('.VV_TizersSection, .js-vv-tizers-section');
                for (const section of sections) {
                    if (section.innerText.includes('Зелёные ценники')) {
                        const btn = section.querySelector('button.js-prods-modal, .VV_TizersSection__Link, a[href*="green"]');
                        if (btn) {
                            btn.click();
                            return 'clicked_fallback';
                        }
                    }
                }
                return null;
            """)
            
            if clicked:
                print(f"✅ Opened modal: {clicked}")
                time.sleep(3)
                use_modal = True
            else:
                print("ℹ️ No 'show all' button - scraping from cart page directly")
                
        except Exception:
            pass
        
        # Extract logic
        if use_modal:
            print("Loading all products from modal...")
            for i in range(20):
                loaded = driver.execute_script("""
                    const modal = document.getElementById('js-modal-cart-prods-scroll');
                    if (modal) modal.scrollTop = modal.scrollHeight;
                    const btn = document.querySelector('.js-prods-modal-load-more');
                    if (btn && btn.offsetParent !== null) { btn.click(); return true; }
                    return false;
                """)
                if loaded: time.sleep(1)
                else: break
                
            products = driver.execute_script("""
                const modal = document.getElementById('js-modal-cart-prods-scroll');
                if (!modal) return [];
                return Array.from(modal.querySelectorAll('.ProductCard')).map(card => {
                    const nameEl = card.querySelector('.ProductCard__link');
                    // Try new selectors first (same as catalog), then fallback
                    const priceEl = card.querySelector('.Price.subtitle') || card.querySelector('.Price__value');
                    const oldPriceEl = card.querySelector('.Price._last') || card.querySelector('.ProductCard__priceStrike');
                    const imgEl = card.querySelector('.ProductCard__imageImg') || card.querySelector('img');
                    const catEl = card.querySelector('.js-datalayer-catalog-list-category');
                    const url = nameEl?.href || '';
                    const idMatch = url.match(/-(\\d+)\\.html/);

                    return {
                        id: idMatch ? idMatch[1] : '',
                        name: nameEl?.innerText?.trim() || '',
                        url: url,
                        currentPrice: priceEl?.innerText?.replace(/[^0-9.,]/g, '') || '0',
                        oldPrice: oldPriceEl?.innerText?.replace(/[^0-9.,]/g, '') || '0',
                        image: imgEl?.src || null,
                        stock: 99, unit: 'шт', type: 'green',
                        category: catEl?.innerText?.trim() || ''
                    };
                }).filter(p => p.name);
            """)
        else:
            print("Extracting products from cart page directly...")
            time.sleep(2)
            products = driver.execute_script("""
                const products = [];
                document.querySelectorAll('a.HProductCard__Title').forEach(titleEl => {
                    let parent = titleEl.parentElement;
                    let isUnavailable = false;
                    for (let i=0; i<10 && parent; i++) {
                        if (parent.innerText && parent.innerText.includes('не в наличии')) {
                            const header = parent.querySelector('h2, h3, .Delivery__Title');
                            if (header && header.innerText.includes('не в наличии')) { isUnavailable=true; break; }
                        }
                        parent = parent.parentElement;
                    }
                    if (isUnavailable) return;

                    const name = titleEl.innerText.trim();
                    const url = titleEl.href || '';
                    const productId = titleEl.getAttribute('data-id') || '';
                    
                    let row = titleEl.parentElement;
                    for(let i=0; i<5 && row; i++){
                        if(row.querySelector('img') && row.querySelector('.HProductCard__Avail')) break;
                        row=row.parentElement;
                    }
                    if (!row) row=titleEl.parentElement.parentElement.parentElement;
                    
                    const imgEl = row.querySelector('img');
                    const stockEl = row.querySelector('.HProductCard__Avail');
                    const stockText = stockEl ? stockEl.innerText : '';
                    const stockMatch = stockText.match(/В наличии:?\\s*([\\d.,]+)\\s*(кг|шт)/i);

                    // Try to get category from data layer
                    const catEl = row.querySelector('.js-datalayer-catalog-list-category');
                    const category = catEl ? catEl.innerText.trim() : '';

                    const priceEl = row.querySelector('.Price__value, .HProductCard__Price');
                    let currentPrice = priceEl ? priceEl.innerText.replace(/[^0-9]/g, '') : '0';
                    const oldPriceEl = row.querySelector('[style*="line-through"]');
                    let oldPrice = oldPriceEl ? oldPriceEl.innerText.replace(/[^0-9]/g, '') : '0';

                    if (name && name.length > 2) {
                        products.push({
                            id: productId,
                            name: name, url: url,
                            currentPrice: currentPrice,
                            oldPrice: oldPrice,
                            image: imgEl ? imgEl.src : null,
                            stock: stockMatch ? parseFloat(stockMatch[1].replace(',', '.')) : 0,
                            unit: stockMatch ? stockMatch[2] : 'шт',
                            type: 'green',
                            category: category
                        });
                    }
                });
                return products;
            """)

        # Filter out stock <= 0 logic is handled in JS (returning 0) and post-filter
        products = [p for p in products if p.get('stock') is not None and p['stock'] > 0]

        # Clean categories and prices using utils
        for p in products:
            p['currentPrice'] = clean_price(p.get('currentPrice'))
            p['oldPrice'] = clean_price(p.get('oldPrice'))

            # Use helper to synthesize discount for green items
            p = synthesize_discount(p)

            # Use 'Зелёные ценники' as raw category context for green items if missing
            raw_cat = p.get('category', '')
            if not raw_cat:
                raw_cat = 'Зелёные ценники'
            else:
                raw_cat = raw_cat.split('//')[0].strip()

            p['category'] = normalize_category(raw_cat, p['name'], p.get('id'))

        print(f"✅ Found {len(products)} GREEN products")
        return products
        
    except Exception as e:
        print(f"⚠️ Error scraping Green Prices: {e}")
        return []

def main():
    driver = init_driver(headless=False) # Keep headless=False for now to handle login/bot checks
    all_products = []
    
    try:
        # 1. Green Prices
        green_items = scrape_green_prices(driver)
        all_products.extend(green_items)
        
        # 2. Red Book
        red_items = scrape_catalog_page(driver, RED_BOOK_URL, 'red')
        all_products.extend(red_items)
        
        # 3. Yellow Prices
        yellow_items = scrape_catalog_page(driver, YELLOW_PRICE_URL, 'yellow')
        all_products.extend(yellow_items)

        # Deduplicate products
        all_products = deduplicate_products(all_products)

        # Save unified data
        output_data = {
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "products": all_products
        }
        
        os.makedirs("data", exist_ok=True)
        with open("data/proposals.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        # Also save to miniapp
        miniapp_data_path = os.path.join(os.path.dirname(__file__), "miniapp", "public", "data.json")
        if os.path.exists(os.path.dirname(miniapp_data_path)):
            with open(miniapp_data_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print("\n" + "="*60)
        print(f"✅ SAVED TOTAL: {len(all_products)} products")
        print(f"  💚 Green: {len(green_items)}")
        print(f"  🔴 Red: {len(red_items)}")
        print(f"  🟡 Yellow: {len(yellow_items)}")
        print("="*60)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
