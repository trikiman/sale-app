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
from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount, save_products_safe, ChromeLock

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GREEN_URL = "https://vkusvill.ru/cart/"

def cleanup_profile_locks(profile_dir):
    """Remove stale Chrome LOCK files AND fix 'chrome not reachable' crash-recovery issue.
    
    When Chrome is force-killed, it marks exit_type='Crashed' in Preferences. On next startup,
    Chrome shows a 'Profile crashed - restore?' dialog which blocks the debug port, causing
    'session not created: chrome not reachable'. This function:
    1. Removes LOCK files
    2. Resets exit_type to 'Normal' in Preferences so Chrome starts cleanly
    3. Deletes Last Session/Last Tabs files that trigger session restore
    """
    import glob
    import json as _json

    # 1. Remove LOCK files (LevelDB locks)
    for lock_path in glob.glob(os.path.join(profile_dir, '**', 'LOCK'), recursive=True):
        try:
            os.remove(lock_path)
            print(f"  [GREEN] Removed stale LOCK: {lock_path}")
        except Exception:
            pass

    # 2. Fix Preferences: set exit_type=Normal so Chrome doesn't show crash recovery dialog
    prefs_path = os.path.join(profile_dir, 'Default', 'Preferences')
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, 'r', encoding='utf-8') as f:
                prefs = _json.load(f)
            profile_prefs = prefs.setdefault('profile', {})
            if profile_prefs.get('exit_type') != 'Normal' or not profile_prefs.get('exited_cleanly', True):
                profile_prefs['exit_type'] = 'Normal'
                profile_prefs['exited_cleanly'] = True
                with open(prefs_path, 'w', encoding='utf-8') as f:
                    _json.dump(prefs, f)
                print(f"  [GREEN] Fixed Preferences: exit_type=Normal")
        except Exception as e:
            print(f"  [GREEN] Could not fix Preferences: {e}")

    # 3. Delete session crash files that trigger restore dialog
    for session_file in ['Last Session', 'Last Tabs', 'Current Session', 'Current Tabs']:
        fpath = os.path.join(profile_dir, 'Default', session_file)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                print(f"  [GREEN] Removed session file: {session_file}")
            except Exception:
                pass


COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")


def load_cookies(driver):
    """Load VkusVill session cookies from cookies.json into Chrome.
    This replaces the persistent user-data-dir approach which is fragile.
    Run login.py to refresh cookies when session expires.
    """
    if not os.path.exists(COOKIES_PATH):
        print(f"  [GREEN] No cookies.json found at {COOKIES_PATH}")
        print(f"  [GREEN] Run 'python login.py' to save your VkusVill session.")
        return False

    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    # Must navigate to the domain first before adding cookies
    driver.get("https://vkusvill.ru")
    time.sleep(2)

    added = 0
    for cookie in cookies:
        try:
            # Remove keys that Selenium doesn't accept
            clean = {k: v for k, v in cookie.items()
                     if k in ('name', 'value', 'domain', 'path', 'secure', 'httpOnly', 'expiry')}
            # Fix domain format (remove leading dot for Selenium)
            if clean.get('domain', '').startswith('.'):
                clean['domain'] = clean['domain'][1:]
            driver.add_cookie(clean)
            added += 1
        except Exception:
            pass

    print(f"  [GREEN] Loaded {added}/{len(cookies)} cookies from cookies.json")
    return added > 0


def init_driver():
    """Initialize Chrome without a persistent profile (cookie-based auth).
    This avoids profile corruption issues caused by force-killing Chrome processes.
    """
    options = uc.ChromeOptions()
    options.add_argument('--lang=ru-RU')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    # NOTE: No --user-data-dir to avoid profile corruption issues
    # Session is managed via cookies.json (see login.py)

    with ChromeLock():
        try:
            driver = uc.Chrome(options=options, headless=False, version_main=144)
            return driver
        except OSError as e:
            if "WinError 183" in str(e):
                print(f"⚠️ [GREEN] WinError 183 despite lock, retrying once...")
                time.sleep(2)
                driver = uc.Chrome(options=options, headless=False, version_main=144)
                return driver
            raise e


def scrape_green_prices():
    print("🔄 [GREEN] Starting...")
    driver = None
    products = []
    live_count = 0  # Count shown on VkusVill live page (for staleness check)

    try:
        driver = init_driver()

        # Load session cookies from cookies.json (replaces user-data-dir approach)
        cookies_ok = load_cookies(driver)
        if not cookies_ok:
            print("⚠️ [GREEN] No cookies loaded. Run 'python login.py' first.")

        # Navigate to cart page (now with session cookies)
        driver.get(GREEN_URL)
        time.sleep(10)  # Wait longer for page load

        # Check for 403 block
        if "403" in driver.title or "Forbidden" in driver.page_source or "запрещен" in driver.page_source.lower():
            print("❌ [GREEN] Blocked (403)! IP may be banned or need to login.")
            print(f"   Page title: {driver.title}")
            return []

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

        # Scroll to bottom to ensure all sections are loaded
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 1400);")
        time.sleep(2)

        # Extract LIVE count from the "Зелёные ценники" section BEFORE clicking.
        # Root cause of live_count=0 bug: TreeWalker exact text match fails because
        # the heading element has child badge elements splitting the text node.
        # Fix: use data-action="GreenLabels" which is unique to the green section button,
        # then walk up looking for a section that does NOT include "Добавьте в заказ".
        live_count = driver.execute_script("""
            // Method 1: Use data-action="GreenLabels" — unique to Зелёные ценники button
            const greenBtn = document.querySelector('[data-action="GreenLabels"]');
            if (greenBtn) {
                const span = greenBtn.querySelector('.js-vv-tizers-section__link-text');
                if (span) {
                    const m = span.innerText.replace(/\\u00a0/g, ' ').match(/(\\d+)/);
                    if (m) return parseInt(m[1]);
                }
            }
            // Method 2: Find count spans and check ancestry for green section
            const countSpans = document.querySelectorAll('.js-vv-tizers-section__link-text');
            for (const span of countSpans) {
                let el = span.parentElement;
                let depth = 0;
                while (el && el.tagName !== 'BODY' && depth < 8) {
                    const txt = el.textContent || '';
                    // Must contain "Зелёные ценники" but NOT "Добавьте в заказ"
                    if (txt.includes('\\u0417\\u0435\\u043b\\u0451\\u043d\\u044b\\u0435') &&
                        !txt.includes('\\u0414\\u043e\\u0431\\u0430\\u0432\\u044c\\u0442\\u0435')) {
                        const m = span.innerText.replace(/\\u00a0/g, ' ').match(/(\\d+)/);
                        if (m) return parseInt(m[1]);
                    }
                    el = el.parentElement;
                    depth++;
                }
            }
            return 0;
        """)
        print(f"  [GREEN] Live count (Зелёные ценники section): {live_count}")

        # Click the "Show all" button for the Зелёные ценники section.
        # Root cause of "clicked_link" bug: the fallback was iterating ALL
        # VV_TizersSection__Link elements and clicking the first one (which could be
        # "Добавьте в заказ" with 92 items instead of "Зелёные ценники" with 35).
        # Fix: use data-action="GreenLabels" as the primary selector (most reliable),
        # then fall back to button ID, then specifically within green section.
        show_all_clicked = driver.execute_script("""
            // 1. Use data-action="GreenLabels" — unique to Зелёные ценники button
            const greenActionBtn = document.querySelector('[data-action="GreenLabels"]');
            if (greenActionBtn) {
                greenActionBtn.click();
                return 'clicked_green_action';
            }

            // 2. Try the button ID
            const showAllBtn = document.getElementById('js-Delivery__Order-green-show-all');
            if (showAllBtn) {
                showAllBtn.click();
                return 'clicked_by_id';
            }

            // 3. Find button specifically in section containing "Зелёные ценники"
            //    but NOT "Добавьте в заказ" (to avoid clicking the wrong section)
            const allSections = document.querySelectorAll('section, [class*="Section"], [class*="Tizer"]');
            for (const section of allSections) {
                const sectionText = section.textContent || '';
                if (sectionText.includes('\\u0417\\u0435\\u043b\\u0451\\u043d\\u044b\\u0435 \\u0446\\u0435\\u043d\\u043d\\u0438\\u043a\\u0438') &&
                    !sectionText.includes('\\u0414\\u043e\\u0431\\u0430\\u0432\\u044c\\u0442\\u0435')) {
                    const btn = section.querySelector('[class*="TizersSection__Link"], [class*="js-prods-modal"]');
                    if (btn) {
                        btn.click();
                        return 'clicked_section_green';
                    }
                }
            }
            return 'not_found';
        """)
        print(f"  [GREEN] Show all button: {show_all_clicked}")

        raw_products = []  # Initialize before modal block
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
                # NOTE: height check must be in a SEPARATE JS call with Python sleep between,
                # otherwise the DOM update is async and the synchronous check always returns 'done'.
                print("  [GREEN] Loading products in modal...")
                for i in range(100):
                    # Step 1: Record height before scrolling
                    old_height = driver.execute_script("""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        return modal ? modal.scrollHeight : 0;
                    """)

                    # Step 2: Scroll to bottom + click "load more" if visible
                    driver.execute_script("""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (modal) modal.scrollTop = modal.scrollHeight;
                        const btn = document.querySelector('.js-prods-modal-load-more');
                        if (btn && btn.offsetParent !== null) btn.click();
                    """)

                    # Step 3: Wait for lazy-loaded content to render
                    time.sleep(1.5)

                    # Step 4: Check new height and button in separate call
                    new_height = driver.execute_script("""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        return modal ? modal.scrollHeight : 0;
                    """)
                    has_more_btn = driver.execute_script("""
                        const btn = document.querySelector('.js-prods-modal-load-more');
                        return btn && btn.offsetParent !== null;
                    """)

                    card_count = driver.execute_script("""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        return modal ? modal.querySelectorAll('.ProductCard').length : 0;
                    """)
                    print(f"  [GREEN] iter {i+1}: cards={card_count}, height={old_height}→{new_height}, has_more={has_more_btn}")

                    if new_height <= old_height and not has_more_btn:
                        # No new content loaded and no button — we're done
                        break

                # 2. Scrape DIRECTLY from Modal (Bypass Add to Cart)
                print("  [GREEN] Scraping products directly from modal...")
                
                raw_products = driver.execute_script("""
                    const products = [];
                    const modal = document.getElementById('js-modal-cart-prods-scroll');
                    if (!modal) return products;

                    modal.querySelectorAll('.ProductCard').forEach(card => {
                        const nameEl = card.querySelector('.ProductCard__link');
                        const priceEl = card.querySelector('.ProductCard__price--current, .Price__value, .ProductCard__price'); 
                        const oldPriceEl = card.querySelector('.ProductCard__price--old, .ProductCard__OldPrice');
                        const imgEl = card.querySelector('.ProductCard__image img, .ProductCard__imageLink img, img');
                        
                        // Extract text for OOS check
                        const text = card.innerText;
                        
                        if (nameEl) {
                            const url = nameEl.href || '';
                            const idMatch = url.match(/(\\d+)\\.html/);
                            
                            // Image extraction (consistent with Red/Yellow)
                            let imgSrc = '';
                            if (imgEl) {
                                imgSrc = imgEl.getAttribute('data-src') || imgEl.src || '';
                            }
                            // Fallback to picture/bg if needed
                            if (!imgSrc || imgSrc.includes('data:image')) {
                                const source = card.querySelector('picture source[srcset]');
                                if (source && source.srcset) imgSrc = source.srcset.split(' ')[0];
                            }
                            if (!imgSrc || imgSrc.includes('data:image')) {
                                 const bgEl = card.querySelector('.ProductCard__imageLink, .ProductCard__image');
                                 if (bgEl) {
                                     const bg = window.getComputedStyle(bgEl).backgroundImage;
                                     if (bg && bg !== 'none' && bg.startsWith('url')) {
                                         imgSrc = bg.replace(/^url\\(['"]?/, '').replace(/['"]?\\)$/, '');
                                     }
                                 }
                            }
                            // Filter placeholders
                            if (imgSrc.includes('no-image.svg') || imgSrc.includes('data:image') || imgSrc.includes('spacer.gif')) {
                                 imgSrc = '';
                            }

                            // Detect weight-based items (ВЕС = weight sold by kg)
                            const name = nameEl.innerText.trim();
                            const isWeightItem = name.includes('ВЕС') || 
                                                 name.toLowerCase().includes('/кг') ||
                                                 (priceEl && priceEl.innerText.includes('/кг'));

                            products.push({
                                id: idMatch ? idMatch[1] : '',
                                name: name,
                                url: url,
                                currentPrice: priceEl ? priceEl.innerText : '0',
                                oldPrice: oldPriceEl ? oldPriceEl.innerText : '0',
                                image: imgSrc,
                                stockText: text, // approximate stock text
                                unit: isWeightItem ? 'кг' : 'шт',
                                category: 'Зелёные ценники',
                                type: 'green'
                            });
                        }
                    });
                    return products;
                """)

                # 3. Add items to cart to reveal stock counts
                print("  [GREEN] Adding items to cart to reveal stock...")
                total_cards = len(raw_products)
                added_count = 0
                results_summary = {'no_modal': 0, 'no_card': 0, 'already_in_cart': 0, 'added': 0, 'no_button': 0}
                for i in range(total_cards):
                    result = driver.execute_script(f"""
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (!modal) return 'no_modal';
                        const cards = modal.querySelectorAll('.ProductCard');
                        const card = cards[{i}];
                        if (!card) return 'no_card';
                        // Skip if already in cart
                        if (card.querySelector('.ProductCard__quantityControl')) return 'already_in_cart';
                        const btn = card.querySelector('.ProductCard__add, button');
                        if (btn) {{
                            btn.click();
                            return 'added';
                        }}
                        return 'no_button';
                    """)
                    results_summary[result] = results_summary.get(result, 0) + 1
                    if result == 'added':
                        added_count += 1
                    time.sleep(0.3)
                print(f"  [GREEN] Add-to-cart results: {results_summary}")
                print(f"  [GREEN] Added {added_count} items to cart.")

                # 4. Close modal
                driver.execute_script("""
                    const closeBtn = document.querySelector('.Modal__close, .js-modal-close');
                    if (closeBtn) closeBtn.click();
                    else {
                        const overlay = document.querySelector('.Modal__overlay');
                        if (overlay) overlay.click();
                    }
                """)
                time.sleep(2)  # Wait for cart to update

                # 5. Scrape stock AND price from cart page
                print("  [GREEN] Scraping stock and prices from cart...")
                stock_map = driver.execute_script("""
                    const stockMap = {};
                    document.querySelectorAll('.HProductCard, .BasketItem').forEach(card => {
                        const nameEl = card.querySelector('.HProductCard__Title, .BasketItem__title');
                        if (nameEl) {
                            const url = nameEl.href || '';
                            const idMatch = url.match(/(\\d+)\\.html/);
                            if (idMatch) {
                                const text = card.innerText;
                                // Look for stock pattern like "В наличии: 5 шт" or "0.41 кг"
                                let stock = 0;
                                let stockUnit = 'шт';
                                
                                // Match decimal kg (e.g., "В наличии: 0.41 кг")
                                const kgMatch = text.match(/наличии[:\\s]*([\\d.,]+)\\s*кг/i);
                                // Match integer шт (e.g., "В наличии: 5 шт" or just "5 шт")
                                const shtMatch = text.match(/наличии[:\\s]*(\\d+)/i) || text.match(/(\\d+)\\s*шт/);
                                
                                if (kgMatch) {
                                    // Keep decimal kg value (e.g., 0.41)
                                    stock = parseFloat(kgMatch[1].replace(',', '.'));
                                    stockUnit = 'кг';
                                } else if (shtMatch) {
                                    stock = parseInt(shtMatch[1]);
                                    stockUnit = 'шт';
                                } else if (text.includes('Мало') || text.includes('мало')) {
                                    stock = 3;
                                } else if (text.includes('наличии')) {
                                    stock = 99;
                                }
                                
                                // Extract price - FIRST try hidden datalayer spans (most reliable)
                                let price = null;
                                let oldPrice = null;
                                
                                // Best source: hidden datalayer spans with exact prices
                                const priceDataEl = card.querySelector('.js-datalayer-catalog-list-price');
                                const oldPriceDataEl = card.querySelector('.js-datalayer-catalog-list-price-old');
                                if (priceDataEl) {
                                    price = priceDataEl.innerText.trim();
                                }
                                if (oldPriceDataEl) {
                                    oldPrice = oldPriceDataEl.innerText.trim();
                                }
                                
                                // If datalayer has placeholder "1" for weighted items, search for visible per-kg price
                                if (price === '1' && stockUnit === 'кг') {
                                    // Normalize text: replace newlines with spaces
                                    const normalizedText = text.replace(/\\n/g, ' ');
                                    
                                    // Look for pattern: number + руб + / + кг OR number + ₽/кг
                                    // Format: "1 771 руб / кг" or "1 210 ₽/кг"
                                    const rubKgMatch = normalizedText.match(/(\\d[\\d\\s]*)\\s*руб\\s*\\/\\s*кг/i);
                                    const rublKgMatch = normalizedText.match(/(\\d[\\d\\s]*)\\s*₽\\s*\\/\\s*кг/i);
                                    
                                    if (rubKgMatch) {
                                        price = rubKgMatch[1].replace(/\\s/g, '');
                                    } else if (rublKgMatch) {
                                        price = rublKgMatch[1].replace(/\\s/g, '');
                                    }
                                }
                                
                                // Fallback: try visible price selectors if still no price
                                if (!price || price === '1') {
                                    const priceSelectors = [
                                        '.HProductCard__Price',
                                        '.Price__value',
                                        '.BasketItem__price',
                                        '[class*="price"]',
                                        '[class*="Price"]'
                                    ];
                                    for (const sel of priceSelectors) {
                                        const el = card.querySelector(sel);
                                        if (el) {
                                            const priceText = el.innerText.trim();
                                            // Look for per-kg price pattern (e.g., "1 210 ₽/кг")
                                            const perKgMatch = priceText.match(/([\\d\\s]+)\\s*₽\\/кг/i);
                                            if (perKgMatch) {
                                                price = perKgMatch[1].replace(/\\s/g, '');
                                                break;
                                            }
                                            // Generic price pattern (only if not placeholder)
                                            const priceMatch = priceText.match(/([\\d\\s]+)\\s*₽/);
                                            if (priceMatch && priceMatch[1] !== '1') {
                                                price = priceMatch[1].replace(/\\s/g, '');
                                                break;
                                            }
                                        }
                                    }
                                }
                                // Final fallback: search full card text for any price pattern
                                if (!price || price === '1') {
                                    const perKgTextMatch = text.match(/([\\d\\s]+)\\s*₽\\/кг/);
                                    if (perKgTextMatch) {
                                        price = perKgTextMatch[1].replace(/\\s/g, '');
                                    }
                                }
                                
                                // Store stock value, unit, price, and oldPrice
                                stockMap[idMatch[1]] = { value: stock, unit: stockUnit, price: price, oldPrice: oldPrice };
                            }
                        }
                    });
                    return stockMap;
                """)
                print(f"  [GREEN] Got stock for {len(stock_map)} items from cart.")

                # 6. Merge stock AND price into raw_products
                for p in raw_products:
                    pid = p.get('id', '')
                    if pid and pid in stock_map:
                        stock_data = stock_map[pid]
                        stock_val = stock_data.get('value', 0)
                        stock_unit = stock_data.get('unit', 'шт')
                        cart_price = stock_data.get('price')
                        cart_old_price = stock_data.get('oldPrice')
                        
                        # Format decimal for kg, integer for шт
                        if stock_unit == 'кг':
                            p['stockText'] = f"В наличии: {stock_val} кг"
                            p['unit'] = 'кг'  # Override unit to кг
                        else:
                            p['stockText'] = f"В наличии: {int(stock_val)} шт"
                        
                        # Fix placeholder price "1" for weighted items using cart datalayer
                        if cart_price and p.get('currentPrice') in ['0', '1', '']:
                            p['currentPrice'] = cart_price
                        
                        # Use oldPrice from cart datalayer if available
                        if cart_old_price and p.get('oldPrice') in ['0', '1', '']:
                            p['oldPrice'] = cart_old_price
                        # Synthesize oldPrice only if still missing
                        elif not p.get('oldPrice') or p.get('oldPrice') in ['0', '1', '']:
                            try:
                                current = int(p.get('currentPrice', 0))
                                if current > 1:
                                    p['oldPrice'] = str(int(current * 1.67))  # ~40% discount means 1.67x markup
                            except:
                                pass
                    else:
                        # Debug: product not in cart
                        if p.get('currentPrice') in ['0', '1', '']:
                            print(f"  [DEBUG] Product not in cart, price=1: {p.get('name', '')[:40]} (id={pid})")
                    # Keep original stockText if not found in cart (fallback)


        # Process with utils
        products = []
        for p in raw_products:
            # Clean prices
            p['currentPrice'] = clean_price(p['currentPrice'])
            p['oldPrice'] = clean_price(p['oldPrice'])

            # Fix missing oldPrice using helper
            p = synthesize_discount(p)

            # Parse stock
            p['stock'] = parse_stock(p.get('stockText', ''))
            if 'stockText' in p:
                del p['stockText']

            # Normalize Category (with product ID for DB lookup)
            p['category'] = normalize_category('Зелёные ценники', p['name'], p.get('id'))

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

    # Save to file — enhanced format with live_count metadata for staleness detection
    output_path = os.path.join(DATA_DIR, "green_products.json")
    if products:
        output_data = {
            "live_count": live_count,
            "scraped_count": len(products),
            "products": products
        }
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"✅ Saved {len(products)} products (live_count={live_count}) → {output_path}")
        except Exception as e:
            print(f"❌ Error saving {output_path}: {e}")
    else:
        print(f"⚠️ No products found — keeping existing {output_path} to prevent data loss.")
    return products


if __name__ == "__main__":
    scrape_green_prices()
