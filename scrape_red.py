"""
Red prices scraper - standalone script for subagent
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json
import os
import sys
from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount, save_products_safe, ChromeLock

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RED_URL = "https://vkusvill.ru/offers/?F%5B212%5D%5B%5D=284&F%5BDEF_3%5D=1&sf4=Y&statepop"
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")


def load_cookies(driver):
    """Load VkusVill session cookies from cookies.json into Chrome."""
    if not os.path.exists(COOKIES_PATH):
        print(f"  [RED] No cookies.json found at {COOKIES_PATH}")
        print(f"  [RED] Run 'python login.py' to save your VkusVill session.")
        return False

    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    # Must navigate to the domain first before adding cookies
    driver.get("https://vkusvill.ru")
    time.sleep(2)

    added = 0
    for cookie in cookies:
        try:
            clean = {k: v for k, v in cookie.items()
                     if k in ('name', 'value', 'domain', 'path', 'secure', 'httpOnly', 'expiry')}
            if clean.get('domain', '').startswith('.'):
                clean['domain'] = clean['domain'][1:]
            driver.add_cookie(clean)
            added += 1
        except Exception:
            pass

    print(f"  [RED] Loaded {added}/{len(cookies)} cookies from cookies.json")
    return added > 0


def init_driver():
    """Initialize Chrome without a persistent profile (cookie-based auth)."""
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-features=LocalNetworkAccessChecks')

    with ChromeLock():
        try:
            driver = uc.Chrome(options=options, headless=False, version_main=145)
            return driver
        except OSError as e:
            if "WinError 183" in str(e):
                print(f"⚠️ [RED] WinError 183 despite lock, retrying once...")
                time.sleep(2)
                driver = uc.Chrome(options=options, headless=False, version_main=145)
                return driver
            raise e


def scrape_red_prices():
    print("🔄 [RED] Starting...")
    driver = None
    products = []
    scrape_success = False

    try:
        driver = init_driver()

        # Load session cookies
        cookies_ok = load_cookies(driver)
        if not cookies_ok:
            print("⚠️ [RED] No cookies loaded. Run 'python login.py' first.")

        driver.get(RED_URL)
        time.sleep(10)  # Wait for initial load

        # Check if logged in
        is_logged_in = driver.execute_script("""
            return !document.body.innerText.includes('Войти') &&
                   (document.body.innerText.includes('Кабинет') ||
                    document.body.innerText.includes('Выход'));
        """)
        if not is_logged_in:
            print("⚠️ [RED] Not logged in! Results may be for wrong location.")
            print("  [RED] Run 'python login.py' to fix.")

        # Validate that RED filter "Скоро исчезнут с полок" is active
        is_active = driver.execute_script("""
            const buttons = document.querySelectorAll('.VV_Teaser__link, .js-filter-link, [class*="filter"]');
            for (const btn of buttons) {
                if (btn.textContent.includes('Скоро исчезнут') &&
                    (btn.classList.contains('active') || btn.classList.contains('is-active') ||
                     getComputedStyle(btn).borderColor.includes('rgb(76, 175, 80)') ||
                     btn.closest('.active'))) {
                    return true;
                }
            }
            // Also check if URL filter applied correctly
            return document.querySelectorAll('.ProductCard').length > 0;
        """)
        print(f"  [RED] Filter active: {is_active}")

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

            # Count TOTAL products loaded (not just in-stock) to detect new content
            total_count = driver.execute_script("""
                return document.querySelectorAll('.ProductCard').length;
            """)

            # Also count in-stock for logging
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

            print(f"  [RED] Total: {total_count}, In-stock: {in_stock_count}")

            # Stop if in-stock count didn't increase (no new relevant products)
            if in_stock_count <= prev_in_stock:
                no_increase_count += 1
                if no_increase_count >= 2:
                    print(f"  [RED] No new in-stock products - done")
                    break
            else:
                no_increase_count = 0

            prev_in_stock = in_stock_count

        raw_products = driver.execute_script("""
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
                    const idMatch = url.match(/(\\d+)\\.html/);
                    const currentPrice = priceEl ? priceEl.innerText.trim() : '0';
                    const oldPrice = oldPriceEl ? oldPriceEl.innerText.trim() : '0';
                    const category = catEl ? catEl.innerText.trim() : '';

                    // Image extraction: Prioritize data-src (lazy load) and check multiple sources
                    let imgSrc = '';
                    
                    // 1. Try standard img tag
                    if (imgEl) {
                        imgSrc = imgEl.getAttribute('data-src') || imgEl.src || '';
                    }

                    // 2. Try picture source
                    if (!imgSrc || imgSrc.includes('data:image')) {
                        const source = card.querySelector('picture source[srcset]');
                        if (source) {
                            const srcset = source.srcset;
                            if (srcset) imgSrc = srcset.split(' ')[0];
                        }
                    }

                    // 3. Try background image
                    if (!imgSrc || imgSrc.includes('data:image')) {
                         const bgEl = card.querySelector('.ProductCard__imageLink, .ProductCard__image');
                         if (bgEl) {
                             const bg = window.getComputedStyle(bgEl).backgroundImage;
                             if (bg && bg !== 'none' && bg.startsWith('url')) {
                                 imgSrc = bg.replace(/^url\\(['"]?/, '').replace(/['"]?\\)$/, '');
                             }
                         }
                    }

                    // Filter out known placeholders
                    if (imgSrc.includes('no-image.svg') || imgSrc.includes('data:image') || imgSrc.includes('spacer.gif')) {
                         imgSrc = '';
                    }

                    products.push({
                        id: idMatch ? idMatch[1] : '',
                        name: titleEl.innerText.trim(),
                        url: url,
                        currentPrice: currentPrice,
                        oldPrice: oldPrice,
                        image: imgSrc,
                        stockText: cardText,
                        unit: 'шт',
                        rawCategory: category,
                        type: 'red'
                    });
                }
            });
            return products;
        """)

        # Process with utils
        products = []
        for p in raw_products:
            # Clean prices
            p['currentPrice'] = clean_price(p['currentPrice'])
            p['oldPrice'] = clean_price(p['oldPrice'])

            # Synthesize discount if missing
            p = synthesize_discount(p)

            # Parse stock from full text
            p['stock'] = parse_stock(p.get('stockText', ''))
            if 'stockText' in p:
                del p['stockText']

            # Normalize Category (using raw breadcrumb + name)
            raw_cat = p.get('rawCategory', '').split('//')[0].strip()
            p['category'] = normalize_category(raw_cat, p['name'], p.get('id'))
            if 'rawCategory' in p:
                del p['rawCategory']

            products.append(p)

        # Deduplicate
        products = deduplicate_products(products)

        print(f"✅ [RED] Found {len(products)} products")
        scrape_success = True

    except Exception as e:
        print(f"❌ [RED] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.__class__.__del__ = lambda self: None
            except Exception:
                pass
            try:
                driver.quit()
            except OSError:
                pass

        # Save to temp file
        # Moved inside finally block so it always runs, using scrape_success to know if it's safe to overwrite
        output_path = os.path.join(DATA_DIR, "red_products.json")
        save_products_safe(products, output_path, success=scrape_success)

    return products


if __name__ == "__main__":
    scrape_red_prices()
