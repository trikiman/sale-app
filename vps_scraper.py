"""
VkusVill Scraper using regular Selenium with saved Chrome profile
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from pyvirtualdisplay import Display
import json
import os
import time

CHROME_PROFILE = os.path.expanduser("~/.config/google-chrome")
OUTPUT_FILE = os.path.expanduser("~/data.json")

def scrape_green_prices():
    print("=" * 60)
    print("VkusVill Green Prices Scraper")
    print("=" * 60)
    
    # Start virtual display
    display = Display(visible=False, size=(1920, 1080))
    display.start()
    
    try:
        print(f"Using Chrome profile: {CHROME_PROFILE}")
        
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--user-data-dir={CHROME_PROFILE}')
        options.add_argument('--lang=ru-RU')
        
        print("Starting Chrome...")
        driver = webdriver.Chrome(options=options)
        
        print("Opening VkusVill cart...")
        driver.get("https://vkusvill.ru/cart/")
        
        print("Waiting for page load...")
        time.sleep(10)
        
        page_source = driver.page_source
        title = driver.title
        print(f"Title: {title}")
        print(f"Page length: {len(page_source)} chars")
        
        # Check for green prices
        if "Зелёные ценники" in page_source:
            print("✅ Green prices found! Session is valid.")
        else:
            print("⚠️ Green prices not visible")
            if "qrator" in page_source.lower():
                print("   Blocked by Qrator")
            with open(os.path.expanduser("~/debug.html"), "w") as f:
                f.write(page_source)
            driver.quit()
            display.stop()
            return None
        
        # Click show all button
        try:
            driver.execute_script("""
                const btn = document.getElementById('js-Delivery__Order-green-show-all');
                if (btn) { btn.scrollIntoView(); btn.click(); }
            """)
            time.sleep(3)
            print("✅ Opened modal")
            use_modal = True
        except:
            use_modal = False
        
        # Load all products
        if use_modal:
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
        else:
            products = driver.execute_script("""
                const products = [];
                document.querySelectorAll('a.HProductCard__Title').forEach(el => {
                    const name = el.innerText.trim();
                    const url = el.href || '';
                    let row = el.parentElement;
                    for (let i = 0; i < 5 && row; i++) {
                        if (row.querySelector('img')) break;
                        row = row.parentElement;
                    }
                    const img = row?.querySelector('img')?.src;
                    const text = row?.innerText || '';
                    const priceMatch = text.match(/(\\d+)\\s*₽/);
                    if (name) products.push({id:'', name, url, currentPrice: priceMatch?priceMatch[1]:'0', oldPrice:'0', image:img, stock:null, unit:'шт'});
                });
                return products;
            """)
        
        print(f"✅ Found {len(products)} products")
        
        driver.quit()
        
        # Categories
        for p in products:
            n = p['name'].lower()
            if any(x in n for x in ['морковь','капуста','лук','картофель','свекла','огурц','помидор','перец','кабачок']):
                p['category'] = 'Овощи'
            elif any(x in n for x in ['яблок','груша','банан','апельсин','мандарин','лимон','манго','виноград']):
                p['category'] = 'Фрукты'
            elif any(x in n for x in ['салат','микс','руккола','шпинат']):
                p['category'] = 'Салаты'
            elif any(x in n for x in ['рыба','лосось','форель','креветк']):
                p['category'] = 'Морепродукты'
            elif any(x in n for x in ['мясо','говядин','свинин','курин','фарш']):
                p['category'] = 'Мясо'
            elif any(x in n for x in ['молок','кефир','йогурт','сметан','творог']):
                p['category'] = 'Молочка'
            else:
                p['category'] = 'Другое'
        
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
