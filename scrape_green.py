"""
Green prices scraper - standalone script for subagent
Scrapes "Зелёные ценники" from cart page
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import json
import os
import sys
from utils import normalize_category, parse_stock, clean_price, deduplicate_products

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GREEN_URL = "https://vkusvill.ru/cart/"

def init_driver():
    # Use dedicated profile for Green scraper
    profile = os.path.join(BASE_DIR, "data", "chrome_profile_green")
    os.makedirs(profile, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={profile}')

    # Retry logic for WinError 183 (race condition)
    for attempt in range(1, 4):
        try:
            driver = uc.Chrome(options=options, headless=False)
            return driver
        except OSError as e:
            if "WinError 183" in str(e) and attempt < 3:
                print(f"⚠️ [GREEN] Race condition detected (WinError 183), retrying in {attempt*3}s...")
                time.sleep(attempt * 3)
            else:
                raise e


def scrape_green_prices():
    print("🔄 [GREEN] Starting...")
    driver = None
    products = []

    try:
        driver = init_driver()
        driver.get(GREEN_URL)
        time.sleep(10)  # Wait longer for page load

        # Check if logged in
        is_logged_in = driver.execute_script("""
            return !document.body.innerText.includes('Войти') &&
                   (document.body.innerText.includes('Кабинет') ||
                    document.body.innerText.includes('Выход'));
        """)

        if not is_logged_in:
            print("⚠️ [GREEN] Not logged in! Please login first.")
            if sys.stdin.isatty():  # Interactive terminal
                input("Press Enter after logging in...")
                driver.refresh()
                time.sleep(5)
            else:  # Automation/non-interactive mode
                print("❌ [GREEN] Aborting - no TTY for login prompt")
                return []

        # Check for green section
        if "Зелёные ценники" not in driver.page_source:
            print("⚠️ [GREEN] Section not found on page")
            return []

        print("✅ [GREEN] Found section, scrolling to load...")

        # Scroll down to load the green section
        driver.execute_script("window.scrollTo(0, 1400);")
        time.sleep(3)

        # Click the "Show all" button by its specific ID
        show_all_clicked = driver.execute_script("""
            // Try the specific button ID first
            const showAllBtn = document.getElementById('js-Delivery__Order-green-show-all');
            if (showAllBtn) {
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
                    return 'no_button';
                }
            }
            return 'not_found';
        """)
        print(f"  [GREEN] Show all button: {show_all_clicked}")

        if show_all_clicked.startswith('clicked'):
            time.sleep(3)  # Wait for modal to open

            # Wait for modal to appear
            modal_ready = driver.execute_script("""
                const modal = document.getElementById('js-modal-cart-prods-scroll');
                return modal && modal.offsetParent !== null;
            """)
            print(f"  [GREEN] Modal opened: {modal_ready}")

            if modal_ready:
                # 1. Scroll modal to load all products
                print("  [GREEN] Loading products in modal...")
                for i in range(30):
                    loaded_more = driver.execute_script("""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (modal) {
                            const oldHeight = modal.scrollHeight;
                            modal.scrollTop = modal.scrollHeight;
                            const btn = document.querySelector('.js-prods-modal-load-more');
                            if (btn && btn.offsetParent !== null) {
                                btn.click();
                                return 'loading';
                            }
                            return modal.scrollHeight > oldHeight ? 'scrolled' : 'done';
                        }
                        return 'no_modal';
                    """)
                    if loaded_more == 'done':
                        break
                    time.sleep(0.5)

                # 2. Add products to cart ONE BY ONE with delays to avoid blocking
                print("  [GREEN] Adding products to cart slowly (0.5s per item)...")

                # Get total product count first
                total_cards = driver.execute_script("""
                    const modal = document.getElementById('js-modal-cart-prods-scroll');
                    return modal ? modal.querySelectorAll('.ProductCard').length : 0;
                """)

                added_count = 0
                max_items = min(total_cards, 50)  # Limit to 50

                for i in range(max_items):
                    result = driver.execute_script(f"""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (!modal) return 'no_modal';

                        const cards = modal.querySelectorAll('.ProductCard');
                        const card = cards[{i}];
                        if (!card) return 'no_card';

                        // Skip if already in cart
                        if (card.querySelector('.ProductCard__quantityControl')) return 'already_in_cart';

                        // Find and click add button
                        const btn = card.querySelector('.ProductCard__add, .js-add-to-cart, button.ProductCard__button, button');
                        if (btn) {{
                            btn.click();
                            return 'added';
                        }}
                        return 'no_button';
                    """)

                    if result == 'added':
                        added_count += 1

                    # Delay between each add to seem human-like
                    time.sleep(0.5)

                    # Progress every 10 items
                    if (i + 1) % 10 == 0:
                        print(f"    [GREEN] Progress: {i + 1}/{max_items} processed, {added_count} added")

                print(f"  [GREEN] Added {added_count} items to cart.")

                # 3. Close modal
                driver.execute_script("""
                    const closeBtn = document.querySelector('.Modal__close, .js-modal-close');
                    if (closeBtn) closeBtn.click();
                    else {
                        const overlay = document.querySelector('.Modal__overlay');
                        if (overlay) overlay.click();
                    }
                """)
                time.sleep(2)

        # 4. Scrape from Main Cart List
        # Scrape all items in cart
        print("  [GREEN] Scraping items from cart...")
        raw_products = driver.execute_script("""
            const products = [];
            document.querySelectorAll('.HProductCard, .BasketItem').forEach(card => {
                const nameEl = card.querySelector('.HProductCard__Title, .BasketItem__title');
                const text = card.innerText;

                // key checks
                const isOutOfStock = text.includes('Нет в наличии') || text.includes('Не осталось');

                if (!isOutOfStock && nameEl) {
                    const url = nameEl.href || '';
                    const idMatch = url.match(/(\d+)\.html/);
                    const priceEl = card.querySelector('.Price__value, .HProductCard__Price');
                    const oldPriceEl = card.querySelector('.HProductCard__OldPrice');
                    // Try multiple selectors for cart image
                    const imgEl = card.querySelector('.HProductCard__Photo img, .HProductCard__Image, .BasketItem__image, img');

                    products.push({
                        id: idMatch ? idMatch[1] : '',
                        name: nameEl.innerText.trim(),
                        url: url,
                        currentPrice: priceEl ? priceEl.innerText : '0',
                        oldPrice: oldPriceEl ? oldPriceEl.innerText : '0',
                        image: imgEl ? imgEl.src : '',
                        stockText: text,
                        unit: 'шт',
                        category: 'Зелёные ценники',
                        type: 'green'
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

            # Fix missing oldPrice (approx 40% discount logic)
            if p['oldPrice'] == '0' and p['currentPrice'] != '0':
                try:
                    curr = float(p['currentPrice'])
                    p['oldPrice'] = str(int(curr / 0.6))
                except:
                    pass

            # Parse stock
            p['stock'] = parse_stock(p.get('stockText', ''))
            if 'stockText' in p:
                del p['stockText']

            # Normalize Category
            p['category'] = normalize_category('Зелёные ценники', p['name'])

            products.append(p)

        # Deduplicate
        products = deduplicate_products(products)

        print(f"✅ [GREEN] Found {len(products)} products with revealed stock")

    except Exception as e:
        print(f"❌ [GREEN] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    # Save to temp file
    output_path = os.path.join(DATA_DIR, "green_products.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved {len(products)} green products to {output_path}")
    return products


if __name__ == "__main__":
    scrape_green_prices()
