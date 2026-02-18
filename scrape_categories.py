"""
Category scraper - builds product ID to category mapping from VkusVill catalog
Run daily to keep the category database updated
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json
import os
import sys
from datetime import datetime
from utils import ChromeLock

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "category_db.json")

# VkusVill category URLs (from their catalog menu - using /offers/ path)
CATEGORIES = [
    {"name": "Готовая еда", "url": "https://vkusvill.ru/offers/gotovaya-eda/"},
    {"name": "Орехи, чипсы, снеки", "url": "https://vkusvill.ru/offers/orekhi-chipsy-sneki/"},
    {"name": "Овощи, фрукты, ягоды, зелень", "url": "https://vkusvill.ru/offers/ovoshchi-frukty-yagody-zelen/"},
    {"name": "Сладости и десерты", "url": "https://vkusvill.ru/offers/sladosti-i-deserty/"},
    {"name": "Молочные продукты", "url": "https://vkusvill.ru/offers/molochnye-produkty/"},
    {"name": "Выпечка и хлеб", "url": "https://vkusvill.ru/offers/vypechka-i-khleb/"},
    {"name": "Мясо, Мясные деликатесы", "url": "https://vkusvill.ru/offers/myaso-myasnye-delikatesy/"},
    {"name": "Сыры", "url": "https://vkusvill.ru/offers/syry/"},
    {"name": "Рыба, икра и морепродукты", "url": "https://vkusvill.ru/offers/ryba-ikra-i-moreprodukty/"},
    {"name": "Мороженое", "url": "https://vkusvill.ru/offers/morozhenoe/"},
    {"name": "Замороженные продукты", "url": "https://vkusvill.ru/offers/zamorozhennye-produkty/"},
    {"name": "Напитки", "url": "https://vkusvill.ru/offers/napitki/"},
    {"name": "Бакалея", "url": "https://vkusvill.ru/offers/bakaleya/"},
    {"name": "Консервация", "url": "https://vkusvill.ru/offers/konservatsiya/"},
    {"name": "Косметика и гигиена", "url": "https://vkusvill.ru/offers/kosmetika-i-gigiena/"},
    {"name": "Бытовая химия и хозтовары", "url": "https://vkusvill.ru/offers/bytovaya-khimiya-i-khoztovary/"},
    {"name": "Товары для детей", "url": "https://vkusvill.ru/offers/tovary-dlya-detey/"},
    {"name": "Подарки и сувениры", "url": "https://vkusvill.ru/offers/podarki-i-suveniry/"},
    {"name": "Зоотовары", "url": "https://vkusvill.ru/offers/zootovary/"},
    {"name": "Канцтовары", "url": "https://vkusvill.ru/offers/kantstovary/"},
    {"name": "Товары для дома и дачи", "url": "https://vkusvill.ru/offers/tovary-dlya-doma-i-dachi/"},
    {"name": "1000 мелочей", "url": "https://vkusvill.ru/offers/1000-melochey/"},
    {"name": "Полуфабрикаты кулинарные", "url": "https://vkusvill.ru/offers/polufabrikaty-kulinarnye-vysokoy-gotovnosti/"},
]


def init_driver():
    profile = os.path.join(BASE_DIR, "data", "chrome_profile_categories")
    os.makedirs(profile, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={profile}')

    # Use global lock to prevent race conditions during Chrome startup
    with ChromeLock():
        try:
            driver = uc.Chrome(options=options, headless=False)
            return driver
        except OSError as e:
            if "WinError 183" in str(e):
                print(f"⚠️ Race condition, retrying in 2s...")
                time.sleep(2)
                driver = uc.Chrome(options=options, headless=False)
                return driver
            raise e


def load_existing_db():
    """Load existing database if it exists"""
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"last_updated": None, "products": {}}


def save_db(db):
    """Save database to file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    db["last_updated"] = datetime.now().isoformat()
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def scrape_category_products(driver, category_url, category_name, max_products=500):
    """Scrape all products from a category page"""
    products = []
    
    driver.get(category_url)
    time.sleep(3)
    
    # Scroll to load all products (pagination via infinite scroll)
    last_count = 0
    scroll_attempts = 0
    max_scroll_attempts = 50
    
    while scroll_attempts < max_scroll_attempts:
        # Get current product count
        current_count = driver.execute_script("""
            return document.querySelectorAll('.ProductCard').length;
        """)
        
        if current_count >= max_products:
            break
            
        if current_count == last_count:
            scroll_attempts += 1
            if scroll_attempts >= 5:  # No new products after 5 scrolls
                break
        else:
            scroll_attempts = 0
            last_count = current_count
        
        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        # Click "Load more" button if present
        driver.execute_script("""
            const btn = document.querySelector('.js-catalog-show-more, .Pagination__loadMore');
            if (btn && btn.offsetParent !== null) btn.click();
        """)
        time.sleep(0.5)
    
    # Extract all products
    products = driver.execute_script("""
        const items = [];
        document.querySelectorAll('.ProductCard').forEach(card => {
            // Get the main link (ProductCard__link or any link with product URL)
            const link = card.querySelector('.ProductCard__link, a[href*=".html"]');
            if (link) {
                const url = link.href;
                // Match both /goods/XXXXX and -XXXXX.html patterns
                let idMatch = url.match(/goods\\/(\\d+)/);
                if (!idMatch) {
                    idMatch = url.match(/-(\\d+)\\.html/);
                }
                if (!idMatch) {
                    idMatch = url.match(/(\\d+)\\.html/);
                }
                
                const nameEl = card.querySelector('.ProductCard__link, .ProductCard__title');
                
                if (idMatch && nameEl) {
                    items.push({
                        id: idMatch[1],
                        name: nameEl.innerText.trim(),
                        url: url
                    });
                }
            }
        });
        return items;
    """)
    
    return products


def scrape_all_categories():
    """Main function to scrape all categories"""
    print("🔄 Starting category scraper...")
    
    db = load_existing_db()
    driver = None
    total_new = 0
    total_updated = 0
    
    try:
        driver = init_driver()
        
        for cat in CATEGORIES:
            print(f"\n📁 Scraping: {cat['name']}...")
            
            try:
                products = scrape_category_products(driver, cat['url'], cat['name'])
                
                for p in products:
                    pid = p['id']
                    if pid in db['products']:
                        # Update if category changed
                        if db['products'][pid]['category'] != cat['name']:
                            db['products'][pid]['category'] = cat['name']
                            db['products'][pid]['name'] = p['name']
                            total_updated += 1
                    else:
                        # New product
                        db['products'][pid] = {
                            'name': p['name'],
                            'category': cat['name']
                        }
                        total_new += 1
                
                print(f"   ✅ Found {len(products)} products")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                continue
            
            # Small delay between categories
            time.sleep(2)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # Save database
    save_db(db)
    
    print(f"\n✅ Done! {total_new} new products, {total_updated} updated")
    print(f"💾 Database saved to {DB_PATH} ({len(db['products'])} total products)")
    
    return db


if __name__ == "__main__":
    scrape_all_categories()
