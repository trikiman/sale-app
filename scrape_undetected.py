"""
VkusVill Green Prices Scraper
Uses persistent Chrome profile - login once, never again!
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json
import os


# Persistent profile directory - Chrome will remember your login here
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chrome_profile")


def scrape_green_prices(auto_mode=False):
    """Scrape VkusVill green prices with persistent Chrome profile
    
    Args:
        auto_mode: If True, skip all user prompts (for scheduled runs)
    """
    print("=" * 60)
    print("VkusVill Green Prices Scraper")
    print("=" * 60)
    
    # Create profile directory
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    # Use persistent profile - your login will be saved!
    options.add_argument(f'--user-data-dir={PROFILE_DIR}')
    
    print("Starting Chrome with saved profile...")
    print(f"(Profile: {PROFILE_DIR})")
    
    # Run headless in auto mode (after initial login)
    driver = uc.Chrome(options=options, headless=auto_mode)
    
    try:
        # Navigate to cart
        print("\nOpening cart page...")
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(5)
        
        # Check if blocked
        if "403" in driver.title or "Forbidden" in driver.page_source:
            print("❌ Blocked by VkusVill!")
            print("Try using a VPN or different network.")
            return None
        
        page_source = driver.page_source
        
        # Check if logged in and green prices visible
        if "Зелёные ценники" not in page_source:
            print("\n" + "-" * 40)
            print("⚠️ Green prices not found!")
            print("-" * 40)
            print("Either:")
            print("1. You're not logged in - please log in now")
            print("2. No green price products available today")
            print("-" * 40)
            if not auto_mode:
                input("\nPress ENTER after logging in (or to continue)...")
            else:
                print("Auto mode: skipping login prompt")
                return None  # Can't continue without login in auto mode
            
            # Refresh
            driver.get("https://vkusvill.ru/cart/")
            time.sleep(5)
            page_source = driver.page_source
        
        # Check for green prices button
        if "Зелёные ценники" in page_source:
            print("✅ Green prices section found!")
        else:
            print("⚠️ No green prices available right now")
            print("This could mean:")
            print("  - No products with green labels today")
            print("  - You need to select a delivery address")
            if not auto_mode:
                input("\nPress ENTER to continue anyway...")
            else:
                return None  # Can't continue in auto mode
        
        # Try to find and click the show all button
        try:
            # Scroll to find the button
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)
            
            # Try clicking
            clicked = driver.execute_script("""
                const btn = document.getElementById('js-Delivery__Order-green-show-all');
                if (btn) {
                    btn.scrollIntoView();
                    btn.click();
                    return btn.innerText;
                }
                return null;
            """)
            
            if clicked:
                print(f"✅ Opened modal: {clicked}")
                time.sleep(3)
                use_modal = True
            else:
                print("ℹ️ No 'show all' button - scraping from cart page directly")
                use_modal = False
                
        except Exception as e:
            print(f"⚠️ Exception finding modal: {e}")
            use_modal = False
        
        # Extract products - either from modal or directly from cart
        if use_modal:
            # From modal
            print("Loading all products from modal...")
            for i in range(20):
                loaded = driver.execute_script("""
                    const modal = document.getElementById('js-modal-cart-prods-scroll');
                    if (modal) modal.scrollTop = modal.scrollHeight;
                    
                    const btn = document.querySelector('.js-prods-modal-load-more');
                    if (btn && btn.offsetParent !== null) {
                        btn.click();
                        return true;
                    }
                    return false;
                """)
                if loaded:
                    print(f"  Loading more... ({i+1})")
                    time.sleep(1)
                else:
                    break
            
            # Count and extract from modal
            products = driver.execute_script("""
                const modal = document.getElementById('js-modal-cart-prods-scroll');
                if (!modal) return [];
                
                return Array.from(modal.querySelectorAll('.ProductCard')).map(card => {
                    const nameEl = card.querySelector('.ProductCard__link');
                    const priceEl = card.querySelector('.Price__value');
                    const oldPriceEl = card.querySelector('.ProductCard__priceStrike');
                    const imgEl = card.querySelector('img');
                    const url = nameEl?.href || '';
                    const idMatch = url.match(/-(\\d+)\\.html/);
                    
                    return {
                        id: idMatch ? idMatch[1] : '',
                        name: nameEl?.innerText?.trim() || '',
                        url: url,
                        currentPrice: priceEl?.innerText?.replace(/\\D/g, '') || '0',
                        oldPrice: oldPriceEl?.innerText?.replace(/\\D/g, '') || '0',
                        image: imgEl?.src || null,
                        stock: null,
                        unit: 'шт'
                    };
                }).filter(p => p.name);
            """)
        else:
            # Scrape directly from cart page (green prices section)
            print("Extracting products from cart page...")
            time.sleep(2)
            
            # Get products from cart using correct VkusVill selectors
            products = driver.execute_script("""
                const products = [];
                
                // Find all product titles - they have data-id attribute
                document.querySelectorAll('a.HProductCard__Title').forEach(titleEl => {
                    const productId = titleEl.getAttribute('data-id') || '';
                    const name = titleEl.innerText.trim();
                    const url = titleEl.href || '';
                    
                    // Get parent container - walk up DOM to find row container
                    let row = titleEl.parentElement;
                    for (let i = 0; i < 5 && row; i++) {
                        if (row.querySelector('img') && row.querySelector('.HProductCard__Avail')) break;
                        row = row.parentElement;
                    }
                    if (!row) row = titleEl.parentElement.parentElement.parentElement;
                    
                    // Get image - try multiple selectors
                    const imgEl = row.querySelector('.HProductCard__ImgWrp img') || 
                                  row.querySelector('img[src*="vkusvill"]') ||
                                  row.querySelector('img');
                    
                    // Get stock from HProductCard__Avail
                    const stockEl = row.querySelector('.HProductCard__Avail');
                    const stockText = stockEl ? stockEl.innerText : '';
                    const stockMatch = stockText.match(/В наличии:?\\s*([\\d.,]+)\\s*(кг|шт)/i);
                    const outOfStock = stockText.toLowerCase().includes('не в наличии') || 
                                       stockText.toLowerCase().includes('нет в наличии');
                    
                    // Get price - try multiple strategies
                    const rowText = row.innerText || '';
                    let currentPrice = '0';
                    let oldPrice = '0';
                    
                    // Strategy 1: Look for price elements directly
                    const priceEl = row.querySelector('.Price__value, .HProductCard__Price, [class*="price"], [class*="Price"]');
                    if (priceEl) {
                        const priceText = priceEl.innerText || '';
                        const pMatch = priceText.match(/(\\d+[\\s,.]*\\d*)/);
                        if (pMatch) currentPrice = pMatch[1].replace(/\\s/g, '').replace(',', '.');
                    }
                    
                    // Strategy 2: Regex on row text - "XX ₽/кг" or "XX ₽" 
                    if (currentPrice === '0') {
                        const priceMatch = rowText.match(/(\\d+)\\s*₽/);
                        if (priceMatch) currentPrice = priceMatch[1];
                    }
                    
                    // Strategy 3: Look for all numbers followed by ruble sign
                    if (currentPrice === '0') {
                        const allPrices = rowText.match(/(\\d+)\\s*₽/g);
                        if (allPrices && allPrices.length > 0) {
                            // Take the last one (usually current price)
                            const lastMatch = allPrices[allPrices.length - 1].match(/(\\d+)/);
                            if (lastMatch) currentPrice = lastMatch[1];
                        }
                    }
                    
                    // Look for struck-through (old) price
                    const strikeEl = row.querySelector('[style*="line-through"], s, strike, del, .Price__old, [class*="old"]');
                    if (strikeEl) {
                        const strikeMatch = strikeEl.innerText.match(/(\\d+)/);
                        if (strikeMatch) oldPrice = strikeMatch[1];
                    }
                    
                    if (name && name.length > 2) {
                        products.push({
                            id: productId,
                            name: name,
                            url: url,
                            currentPrice: currentPrice,
                            oldPrice: oldPrice,
                            image: imgEl ? imgEl.src : null,
                            stock: stockMatch ? parseFloat(stockMatch[1].replace(',', '.')) : (outOfStock ? 0 : null),
                            unit: stockMatch ? stockMatch[2] : 'шт'
                        });
                    }
                });
                return products;
            """)
        
        print(f"✅ Found {len(products)} products")
        
        # Add all to cart
        print("Adding to cart for stock counts...")
        driver.execute_script("""
            const modal = document.getElementById('js-modal-cart-prods-scroll');
            if (modal) {
                modal.querySelectorAll('.CartButton__content--add, .js-delivery__basket--add')
                    .forEach(btn => { try { btn.click(); } catch(e) {} });
            }
        """)
        time.sleep(5)
        
        # Get stock from cart
        print("Getting stock counts...")
        driver.execute_script("document.querySelector('.VV22_Modal_Forgot__close')?.click()")
        time.sleep(2)
        
        stocks = driver.execute_script("""
            const stocks = {};
            // Look for cart items - they contain "В наличии: X" text
            document.querySelectorAll('.HProductCard, .CartProduct, [class*="cart-product"]').forEach(card => {
                const name = (card.querySelector('.HProductCard__Title, [class*="title"], [class*="name"]')?.innerText || '').trim();
                const text = card.innerText || '';
                
                // Parse "В наличии: X кг" or "В наличии: X шт"
                const stockMatch = text.match(/В наличии:?\\s*([\\d.,]+)\\s*(кг|шт)/i);
                
                if (name && stockMatch) {
                    stocks[name] = {
                        value: parseFloat(stockMatch[1].replace(',', '.')),
                        unit: stockMatch[2]
                    };
                } else if (name && text.includes('не в наличии')) {
                    // Out of stock
                    stocks[name] = { value: 0, unit: 'шт' };
                }
            });
            return stocks;
        """)
        
        print(f"  Got stock for {len(stocks)} products")
        
        # Update products with stock (new format: {value, unit})
        for p in products:
            if p['name'] in stocks:
                stock_info = stocks[p['name']]
                p['stock'] = stock_info.get('value', 0)
                p['unit'] = stock_info.get('unit', 'шт')
            else:
                p['stock'] = None
                p['unit'] = 'шт'
        
        # Add categories based on product name
        for p in products:
            name_lower = p['name'].lower()
            if any(x in name_lower for x in ['морковь', 'капуста', 'лук', 'картофель', 'свекла', 'огурц', 'помидор', 'перец', 'кабачок']):
                p['category'] = 'Овощи'
            elif any(x in name_lower for x in ['яблок', 'груша', 'банан', 'апельсин', 'мандарин', 'лимон', 'манго', 'виноград', 'киви', 'персик', 'нектарин', 'хурма']):
                p['category'] = 'Фрукты'
            elif any(x in name_lower for x in ['салат', 'микс', 'руккола', 'шпинат', 'латук']):
                p['category'] = 'Салаты'
            elif any(x in name_lower for x in ['икра', 'рыба', 'лосось', 'форель', 'креветк', 'кальмар', 'морепродукт']):
                p['category'] = 'Морепродукты'
            elif any(x in name_lower for x in ['мясо', 'говядин', 'свинин', 'курин', 'индейк', 'фарш', 'котлет', 'сосиск', 'колбас']):
                p['category'] = 'Мясо'
            elif any(x in name_lower for x in ['молок', 'кефир', 'йогурт', 'сметан', 'творог', 'сыр', 'масло']):
                p['category'] = 'Молочка'
            else:
                p['category'] = 'Другое'
        
        # Save to data/
        os.makedirs("data", exist_ok=True)
        with open("data/green_products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        # Also save to miniapp/public/data.json
        miniapp_data_path = os.path.join(os.path.dirname(__file__), "miniapp", "public", "data.json")
        if os.path.exists(os.path.dirname(miniapp_data_path)):
            with open(miniapp_data_path, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"  Also saved to miniapp/public/data.json")
        
        # Summary
        print("\n" + "=" * 60)
        print(f"✅ SAVED {len(products)} products to data/green_products.json")
        print("=" * 60)
        
        with_stock = len([p for p in products if p.get('stock') and p['stock'] > 0])
        print(f"Products with stock: {with_stock}")
        
        print("\nSample:")
        for p in products[:10]:
            stock_str = f"{p.get('stock', '?')} {p.get('unit', '')}" if p.get('stock') else "N/A"
            print(f"  {p['name'][:35]}... | {p['currentPrice']}₽ | В наличии: {stock_str}")
        
        return products
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        if not auto_mode:
            input("\nPress ENTER to close browser...")
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    scrape_green_prices()
