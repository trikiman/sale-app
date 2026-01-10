"""
VkusVill Green Prices Scraper for VPS
Uses saved Chrome profile session
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pyvirtualdisplay import Display
import time
import json
import os

CHROME_PROFILE = os.path.expanduser("~/.config/google-chrome")
OUTPUT_FILE = os.path.expanduser("~/data.json")


def scrape_green_prices():
    print("=" * 60)
    print("VkusVill Green Prices Scraper (VPS)")
    print("=" * 60)
    
    display = Display(visible=False, size=(1920, 1080))
    display.start()
    
    try:
        print(f"Using Chrome profile: {CHROME_PROFILE}")
        
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--lang=ru-RU')
        options.add_argument(f'--user-data-dir={CHROME_PROFILE}')
        
        print("Starting Chrome...")
        driver = webdriver.Chrome(options=options)
        
        print("Opening cart page...")
        driver.get("https://vkusvill.ru/cart/")
        time.sleep(10)
        
        page_source = driver.page_source
        title = driver.title
        print(f"Title: {title}")
        
        # Check for blocking
        if "403" in title or "qrator" in page_source.lower():
            print("❌ Blocked!")
            driver.quit()
            display.stop()
            return None
        
        # Check for green prices
        if "Зелёные ценники" not in page_source:
            print("⚠️ Green prices not found - need to log in")
            with open(os.path.expanduser("~/debug.html"), "w") as f:
                f.write(page_source)
            driver.quit()
            display.stop()
            return None
        
        print("✅ Green prices found!")
        
        # Try to open modal
        try:
            driver.execute_script("""
                const btn = document.getElementById('js-Delivery__Order-green-show-all');
                if (btn) { btn.scrollIntoView(); btn.click(); }
            """)
            time.sleep(3)
            
            modal = driver.find_element("id", "js-modal-cart-prods-scroll")
            if modal:
                print("✅ Opened modal")
                # Load all products
                for i in range(20):
                    loaded = driver.execute_script("""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (modal) modal.scrollTop = modal.scrollHeight;
                        const btn = document.querySelector('.js-prods-modal-load-more');
                        if (btn && btn.offsetParent !== null) { btn.click(); return true; }
                        return false;
                    """)
                    if loaded:
                        print(f"  Loading... ({i+1})")
                        time.sleep(1)
                    else:
                        break
                
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
                            stock: null, unit: 'шт'
                        };
                    }).filter(p => p.name);
                """)
        except:
            pass
        
        # Fallback: scrape from cart page directly
        if not products or len(products) == 0:
            print("ℹ️ Scraping from cart page directly...")
            products = driver.execute_script("""
                const products = [];
                document.querySelectorAll('a.HProductCard__Title').forEach(titleEl => {
                    const productId = titleEl.getAttribute('data-id') || '';
                    const name = titleEl.innerText.trim();
                    const url = titleEl.href || '';
                    
                    let row = titleEl.parentElement;
                    for (let i = 0; i < 5 && row; i++) {
                        if (row.querySelector('img')) break;
                        row = row.parentElement;
                    }
                    if (!row) row = titleEl.parentElement.parentElement.parentElement;
                    
                    const imgEl = row.querySelector('img');
                    
                    // Get price - try multiple strategies
                    const rowText = row.innerText || '';
                    let currentPrice = '0';
                    let oldPrice = '0';
                    
                    // Strategy 1: Look for price elements
                    const priceEl = row.querySelector('.Price__value, .HProductCard__Price, [class*="price"], [class*="Price"]');
                    if (priceEl) {
                        const priceText = priceEl.innerText || '';
                        const pMatch = priceText.match(/(\\d+[\\s,.]*\\d*)/);
                        if (pMatch) currentPrice = pMatch[1].replace(/\\s/g, '').replace(',', '.');
                    }
                    
                    // Strategy 2: Regex on text
                    if (currentPrice === '0') {
                        const priceMatch = rowText.match(/(\\d+)\\s*₽/);
                        if (priceMatch) currentPrice = priceMatch[1];
                    }
                    
                    // Strategy 3: All prices
                    if (currentPrice === '0') {
                        const allPrices = rowText.match(/(\\d+)\\s*₽/g);
                        if (allPrices && allPrices.length > 0) {
                            const lastMatch = allPrices[allPrices.length - 1].match(/(\\d+)/);
                            if (lastMatch) currentPrice = lastMatch[1];
                        }
                    }
                    
                    // Old price
                    const strikeEl = row.querySelector('[style*="line-through"], s, strike, del, .Price__old');
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
                            stock: null, unit: 'шт'
                        });
                    }
                });
                return products;
            """)
        
        print(f"✅ Found {len(products)} products")
        
        driver.quit()
        
        # Add categories
        for p in products:
            n = p['name'].lower()
            if any(x in n for x in ['морковь','капуста','лук','картофель','свекла','огурц','помидор','перец','кабачок']):
                p['category'] = 'Овощи'
            elif any(x in n for x in ['яблок','груша','банан','апельсин','мандарин','лимон','манго','виноград']):
                p['category'] = 'Фрукты'
            elif any(x in n for x in ['салат','микс','руккола','шпинат']):
                p['category'] = 'Салаты'
            elif any(x in n for x in ['рыба','лосось','форель','креветк','икра']):
                p['category'] = 'Морепродукты'
            elif any(x in n for x in ['мясо','говядин','свинин','курин','фарш']):
                p['category'] = 'Мясо'
            elif any(x in n for x in ['молок','кефир','йогурт','сметан','творог']):
                p['category'] = 'Молочка'
            else:
                p['category'] = 'Другое'
        
        # Save
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ SAVED {len(products)} products to {OUTPUT_FILE}")
        for p in products[:5]:
            print(f"  {p['name'][:40]}... | {p['currentPrice']}₽")
        
        return products
        
    finally:
        display.stop()


if __name__ == "__main__":
    scrape_green_prices()
