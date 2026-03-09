"""
VkusVill Scraper 2.0 (Red/Yellow Prices)
Uses nodriver (CDP) for Chrome 145+ compatibility.
Loads session cookies from cookies.json for location-aware results.
"""
import asyncio
import json
import os
import sys
import tempfile
import subprocess
import socket
import shutil
from datetime import datetime
from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIES_PATH = os.path.join(DATA_DIR, "cookies.json")
RED_BOOK_URL = "https://vkusvill.ru/offers/?F%5B212%5D%5B%5D=284&F%5BDEF_3%5D=1&sf4=Y&statepop"
YELLOW_PRICE_URL = "https://vkusvill.ru/offers/?F%5BDEF_3%5D=1&sf4=Y&statepop"


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _find_chrome():
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    found = shutil.which('chrome') or shutil.which('google-chrome')
    if found:
        return found
    raise FileNotFoundError("Chrome not found. Install Google Chrome.")


def _deserialize(val):
    """Deserialize nodriver's deep-serialized CDP response to plain Python objects."""
    if not isinstance(val, dict) or 'type' not in val:
        return val
    t = val.get('type')
    v = val.get('value')
    if t in ('string', 'number', 'boolean'):
        return v
    if t == 'undefined' or t == 'null':
        return None
    if t == 'array':
        return [_deserialize(item) for item in (v or [])]
    if t == 'object':
        if isinstance(v, list):
            return {pair[0]: _deserialize(pair[1]) for pair in v if isinstance(pair, (list, tuple)) and len(pair) == 2}
        return v
    return v


async def _js(page, script):
    """Run JS via page.evaluate and deserialize the result."""
    raw = await page.evaluate(script)
    if isinstance(raw, dict) and 'type' in raw:
        return _deserialize(raw)
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and 'type' in raw[0]:
        return [_deserialize(item) for item in raw]
    return raw


async def _launch_browser():
    import nodriver as uc
    port = _find_free_port()
    tmp_profile = tempfile.mkdtemp(prefix='uc_prices_')
    chrome_path = _find_chrome()

    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={tmp_profile}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=LocalNetworkAccessChecks',
        '--lang=ru-RU',
        '--start-maximized',
    ]

    print(f"  Launching Chrome on port {port}...")
    proc = subprocess.Popen(args)
    await asyncio.sleep(3)

    browser = await uc.Browser.create(host='127.0.0.1', port=port)
    browser._process_pid = proc.pid
    return browser, proc, tmp_profile


async def _load_cookies(page):
    """Load VkusVill session cookies from cookies.json into browser via CDP."""
    if not os.path.exists(COOKIES_PATH):
        print(f"  ⚠️ No cookies.json — location may be wrong. Run tech-login from admin.")
        return False

    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    from nodriver.cdp import network

    ss_map = {
        'Lax': network.CookieSameSite.LAX,
        'Strict': network.CookieSameSite.STRICT,
        'None': network.CookieSameSite.NONE,
    }

    cdp_cookies = []
    for c in cookies:
        cp = network.CookieParam(
            name=c['name'],
            value=c['value'],
            domain=c.get('domain', 'vkusvill.ru'),
            path=c.get('path', '/'),
            secure=c.get('secure', False),
            http_only=c.get('httpOnly', False),
        )
        if 'expiry' in c:
            cp.expires = network.TimeSinceEpoch(c['expiry'])
        if 'sameSite' in c:
            cp.same_site = ss_map.get(c['sameSite'])
        cdp_cookies.append(cp)

    await page.send(network.set_cookies(cdp_cookies))
    print(f"  ✅ Loaded {len(cdp_cookies)} cookies via CDP")
    return True


async def scrape_catalog_page(page, browser, url, product_type):
    """Scrape standard catalog pages (Red Book, Yellow Prices)"""
    print(f"\n{'='*60}")
    print(f"Scanning {product_type.upper()} page: {url}")
    print(f"{'='*60}")
    products = []

    try:
        page = await browser.get(url)
        await asyncio.sleep(5)

        # Scroll and load pages until OOS boundary ("Не осталось" / "Привезите ещё")
        # VkusVill sorts in-stock items first, then OOS after a divider
        for i in range(50):
            await _js(page, 'window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)

            # Check if we hit the OOS boundary — stop loading
            hit_oos = await _js(page, """
                (() => {
                    const text = document.body.innerText;
                    return text.includes('Не осталось') || text.includes('Привезите ещё') || text.includes('привезите ещё');
                })()
            """)
            if hit_oos:
                print(f"  Hit OOS boundary after {i+1} loads — stopping.")
                break

            # Click "Показать ещё" / load more button if present
            has_more = await _js(page, """
                (() => {
                    const btns = document.querySelectorAll('.Pagination__loadMore, .js-pagination-load-more, button, a');
                    for (const btn of btns) {
                        const t = btn.innerText.trim().toLowerCase();
                        if ((t.includes('показать ещё') || t.includes('показать еще') || t.includes('загрузить ещё')) && btn.offsetParent !== null) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })()
            """)
            if not has_more and i >= 2:
                break
            if has_more:
                print(f"  Loading more... (iter {i+1})")
                await asyncio.sleep(2)

        # Check page loaded
        title = await _js(page, 'document.title')
        print(f"  Page title: {title}")

        raw = await _js(page, f"""
            (() => {{
                const products = [];
                const type = "{product_type}";

                const cards = document.querySelectorAll('.ProductCard');
                for (const card of cards) {{
                    // Stop at OOS boundary: check if this card or its preceding siblings
                    // contain the "Не осталось" / "Привезите ещё" divider
                    let prev = card.previousElementSibling;
                    while (prev) {{
                        const t = prev.innerText || '';
                        if (t.includes('Не осталось') || t.includes('Привезите ещё')) {{
                            return products; // All remaining cards are OOS
                        }}
                        prev = prev.previousElementSibling;
                    }}

                    // Also check parent section for OOS heading
                    let parent = card.parentElement;
                    for (let d = 0; d < 3 && parent; d++) {{
                        const heading = parent.querySelector('h2, h3, .Catalog__title');
                        if (heading) {{
                            const ht = heading.innerText || '';
                            if (ht.includes('Не осталось') || ht.includes('Привезите ещё')) {{
                                return products;
                            }}
                        }}
                        parent = parent.parentElement;
                    }}

                    // Filter: must have "В корзину" button (in-stock)
                    const btn = card.querySelector('.js-delivery__basket--add');
                    if (!btn || btn.innerText.trim() !== 'В корзину') {{
                        continue;
                    }}

                    const titleEl = card.querySelector('.ProductCard__link');
                    const priceEl = card.querySelector('.Price.subtitle');
                    const oldPriceEl = card.querySelector('.Price._last');
                    const imgEl = card.querySelector('.ProductCard__imageImg');
                    const catEl = card.querySelector('.js-datalayer-catalog-list-category');
                    const category = catEl ? catEl.innerText.trim() : '';

                    if (titleEl && priceEl) {{
                        const url = titleEl.href || '';
                        const idMatch = url.match(/(?:-)?(\\d+)\\.html/);

                        products.push({{
                            id: idMatch ? idMatch[1] : '',
                            name: titleEl.innerText.trim(),
                            url: url,
                            currentPrice: priceEl.innerText.replace(/[^0-9.,]/g, ''),
                            oldPrice: oldPriceEl ? oldPriceEl.innerText.replace(/[^0-9.,]/g, '') : '',
                            image: imgEl ? imgEl.src : '',
                            stock: 99,
                            unit: 'шт',
                            category: category,
                            type: type
                        }});
                    }}
                }}
                return products;
            }})()
        """)

        raw = raw or []
        for p in raw:
            if not isinstance(p, dict) or 'name' not in p:
                continue
            p['currentPrice'] = clean_price(p.get('currentPrice'))
            p['oldPrice'] = clean_price(p.get('oldPrice'))
            raw_cat = p.get('category', '').split('//')[0].strip()
            p['category'] = normalize_category(raw_cat, p.get('name', ''), p.get('id'))
            p = synthesize_discount(p)
            products.append(p)

        print(f"✅ Found {len(products)} {product_type} items")
        return products, page

    except Exception as e:
        print(f"⚠️ Error scraping {product_type}: {e}")
        import traceback
        traceback.print_exc()
        return [], page


async def main_async():
    browser = None
    proc = None
    tmp_profile = None
    red_items = []
    yellow_items = []
    scrape_success = False

    try:
        browser, proc, tmp_profile = await _launch_browser()

        # Navigate to domain first for cookie scope
        page = await browser.get('https://vkusvill.ru')
        await asyncio.sleep(3)

        # Load cookies for location
        await _load_cookies(page)

        # Red Book
        red_items, page = await scrape_catalog_page(page, browser, RED_BOOK_URL, 'red')

        # Yellow Prices
        yellow_items, page = await scrape_catalog_page(page, browser, YELLOW_PRICE_URL, 'yellow')

        # Deduplicate
        red_items = deduplicate_products(red_items)
        yellow_items = deduplicate_products(yellow_items)

        scrape_success = True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        scrape_success = False
    finally:
        # Always save whatever we collected (even partial results)
        red_path = os.path.join(DATA_DIR, "red_products.json")
        yellow_path = os.path.join(DATA_DIR, "yellow_products.json")

        if scrape_success or red_items:
            with open(red_path, 'w', encoding='utf-8') as f:
                json.dump({"products": red_items}, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Saved {len(red_items)} red products -> {red_path}")

        if scrape_success or yellow_items:
            with open(yellow_path, 'w', encoding='utf-8') as f:
                json.dump({"products": yellow_items}, f, ensure_ascii=False, indent=2)
            print(f"✅ Saved {len(yellow_items)} yellow products -> {yellow_path}")

        print("\n" + "=" * 60)
        print(f"{'✅' if scrape_success else '⚠️'} TOTAL: {len(red_items) + len(yellow_items)} products")
        print(f"  🔴 Red: {len(red_items)}")
        print(f"  🟡 Yellow: {len(yellow_items)}")
        print("=" * 60)

        if browser:
            try:
                browser.stop()
            except Exception:
                pass
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        # Clean up temp Chrome profile directory
        if tmp_profile and os.path.isdir(tmp_profile):
            try:
                shutil.rmtree(tmp_profile, ignore_errors=True)
            except Exception:
                pass


def main():
    """Sync wrapper for backward compatibility."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
