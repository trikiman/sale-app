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


def cleanup_profile_locks(profile_dir):
    """Remove stale Chrome LOCK files left over from killed/crashed Chrome processes."""
    import glob
    for lock_path in glob.glob(os.path.join(profile_dir, '**', 'LOCK'), recursive=True):
        try:
            os.remove(lock_path)
            print(f"  [RED] Removed stale LOCK: {lock_path}")
        except Exception:
            pass


def init_driver():
    # Use dedicated profile for Red scraper
    profile = os.path.join(BASE_DIR, "data", "chrome_profile_red")
    os.makedirs(profile, exist_ok=True)

    # Clean up stale LOCK files before starting Chrome
    cleanup_profile_locks(profile)

    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={profile}')

    # Use global lock to prevent race conditions during Chrome startup
    # WinError 183 occurs when multiple processes try to initialize Chrome profiles simultaneously
    with ChromeLock():
        try:
            driver = uc.Chrome(options=options, headless=False, version_main=144)
            return driver
        except OSError as e:
            # Fallback retry just in case, though lock should prevent most collisions
            if "WinError 183" in str(e):
                print(f"⚠️ [RED] WinError 183 despite lock, retrying once...")
                time.sleep(2)
                driver = uc.Chrome(options=options, headless=False, version_main=144)
                return driver
            raise e


def scrape_red_prices():
    print("🔄 [RED] Starting...")
    driver = None
    products = []

    try:
        driver = init_driver()
        driver.get(RED_URL)
        time.sleep(10)  # Wait for initial load

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
        prev_total = 0
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

            # Stop if total count didn't increase (no new content loaded)
            if total_count <= prev_total:
                no_increase_count += 1
                if no_increase_count >= 2:
                    print(f"  [RED] No new content loaded - done")
                    break
            else:
                no_increase_count = 0

            prev_total = total_count

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

    except Exception as e:
        print(f"❌ [RED] Error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    # Save to temp file
    output_path = os.path.join(DATA_DIR, "red_products.json")
    save_products_safe(products, output_path)
    return products


if __name__ == "__main__":
    scrape_red_prices()
