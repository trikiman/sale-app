"""
Yellow prices scraper - standalone script
Scrapes "Скидка по вашей карте" from VkusVill offers page.
Uses nodriver (CDP) instead of undetected_chromedriver for Chrome 145+ compatibility.
"""
import asyncio
import json
import os
import sys
import socket
import subprocess
import tempfile
import shutil

from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount, save_products_safe, check_vkusvill_available, normalize_stock_unit

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
YELLOW_URL = "https://vkusvill.ru/offers/?F%5B212%5D%5B%5D=278&F%5BDEF_3%5D=1&sf4=Y&statepop"
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")


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


async def _launch_browser():
    import nodriver as uc
    port = _find_free_port()
    tmp_profile = tempfile.mkdtemp(prefix='uc_yellow_')
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
    print(f"  [YELLOW] Launching Chrome on port {port}...")
    proc = subprocess.Popen(args)
    await asyncio.sleep(3)
    browser = await uc.Browser.create(host='127.0.0.1', port=port)
    browser._process_pid = proc.pid
    return browser, proc, tmp_profile


async def _load_cookies(page):
    if not os.path.exists(COOKIES_PATH):
        print(f"  [YELLOW] No cookies.json found. Run tech-login from admin panel.")
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
    print(f"  [YELLOW] Loaded {len(cdp_cookies)}/{len(cookies)} cookies via CDP")
    return len(cdp_cookies) > 0


def _deserialize(val):
    if not isinstance(val, dict) or 'type' not in val:
        return val
    t = val.get('type')
    v = val.get('value')
    if t in ('string', 'number', 'boolean'):
        return v
    if t in ('undefined', 'null'):
        return None
    if t == 'array':
        return [_deserialize(item) for item in (v or [])]
    if t == 'object':
        if isinstance(v, list):
            return {pair[0]: _deserialize(pair[1]) for pair in v if isinstance(pair, (list, tuple)) and len(pair) == 2}
        return v
    return v


async def _js(page, script):
    raw = await page.evaluate(script)
    if isinstance(raw, dict) and 'type' in raw:
        return _deserialize(raw)
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and 'type' in raw[0]:
        return [_deserialize(item) for item in raw]
    return raw


async def scrape_yellow_prices_async():
    print("🔄 [YELLOW] Starting...")
    browser = None
    proc = None
    tmp_profile = None
    products = []
    scrape_success = False

    try:
        browser, proc, tmp_profile = await _launch_browser()

        page = await browser.get('https://vkusvill.ru')
        await asyncio.sleep(3)

        await _load_cookies(page)

        page = await browser.get(YELLOW_URL)
        await asyncio.sleep(10)

        # Check if logged in
        page_text = await _js(page, 'document.body.innerText')
        is_logged_in = "Войти" not in str(page_text) and ("Кабинет" in str(page_text) or "Выход" in str(page_text))
        if not is_logged_in:
            print("⚠️ [YELLOW] Not logged in! Results may be for wrong location.")

        is_active = await _js(page, """
            (() => {
                return document.querySelectorAll('.ProductCard').length > 0;
            })()
        """)
        print(f"  [YELLOW] Products visible: {is_active}")

        # Smart pagination: scroll + click "Показать ещё" until no new in-stock products
        prev_in_stock = 0
        no_increase_count = 0

        for batch in range(20):
            await _js(page, """
                (() => {
                    const btn = Array.from(document.querySelectorAll('button, a')).find(
                        b => b.innerText.toLowerCase().includes('\u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0435\u0449') && b.offsetParent
                    );
                    if (btn) btn.click();
                })()
            """)
            await asyncio.sleep(2)

            await _js(page, 'window.scrollBy(0, 500)')
            await asyncio.sleep(1)

            total_count = await _js(page, "document.querySelectorAll('.ProductCard').length")
            in_stock_count = await _js(page, """
                (() => {
                    let count = 0;
                    document.querySelectorAll('.ProductCard').forEach(card => {
                        const text = card.innerText;
                        if (text.includes('\u0412 \u043d\u0430\u043b\u0438\u0447\u0438\u0438') && !text.includes('\u041d\u0435 \u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c')) count++;
                    });
                    return count;
                })()
            """)

            print(f"  [YELLOW] Total: {total_count}, In-stock: {in_stock_count}")

            if (in_stock_count or 0) <= prev_in_stock:
                no_increase_count += 1
                if no_increase_count >= 2:
                    print("  [YELLOW] No new in-stock products - done")
                    break
            else:
                no_increase_count = 0

            prev_in_stock = in_stock_count or 0

        raw_products = await _js(page, r"""
            (() => {
                const products = [];
                document.querySelectorAll('.ProductCard').forEach(card => {
                    const cardText = card.innerText;
                    if (cardText.includes('\u041d\u0435 \u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c')) return;
                    if (!cardText.includes('\u0412 \u043d\u0430\u043b\u0438\u0447\u0438\u0438')) return;

                    const titleEl = card.querySelector('.ProductCard__link');
                    const priceEl = card.querySelector('.js-datalayer-catalog-list-price');
                    const oldPriceEl = card.querySelector('.js-datalayer-catalog-list-price-old');
                    const imgEl = card.querySelector('.ProductCard__imageLink img') || card.querySelector('img');
                    const catEl = card.querySelector('.js-datalayer-catalog-list-category');

                    if (titleEl) {
                        const url = titleEl.href || '';
                        const idMatch = url.match(/(\d+)\.html/);
                        let imgSrc = '';
                        if (imgEl) imgSrc = imgEl.getAttribute('data-src') || imgEl.src || '';
                        if (!imgSrc || imgSrc.includes('data:image')) {
                            const source = card.querySelector('picture source[srcset]');
                            if (source && source.srcset) imgSrc = source.srcset.split(' ')[0];
                        }
                        if (!imgSrc || imgSrc.includes('data:image')) {
                            const bgEl = card.querySelector('.ProductCard__imageLink, .ProductCard__image');
                            if (bgEl) {
                                const bg = window.getComputedStyle(bgEl).backgroundImage;
                                if (bg && bg !== 'none' && bg.startsWith('url'))
                                    imgSrc = bg.replace(/^url\(['"]?/, '').replace(/['"]?\)$/, '');
                            }
                        }
                        if (imgSrc && (imgSrc.includes('no-image.svg') || imgSrc.includes('data:image') || imgSrc.includes('spacer.gif')))
                            imgSrc = '';

                        products.push({
                            id: idMatch ? idMatch[1] : '',
                            name: titleEl.innerText.trim(),
                            url: url,
                            currentPrice: priceEl ? priceEl.innerText.trim() : '0',
                            oldPrice: oldPriceEl ? oldPriceEl.innerText.trim() : '0',
                            image: imgSrc,
                            stockText: cardText,
                            unit: '\u0448\u0442',
                            rawCategory: catEl ? catEl.innerText.trim() : '',
                            type: 'yellow'
                        });
                    }
                });
                return products;
            })()
        """)
        raw_products = raw_products or []

        for p in raw_products:
            if not isinstance(p, dict):
                continue
            p['currentPrice'] = clean_price(p.get('currentPrice', '0'))
            p['oldPrice'] = clean_price(p.get('oldPrice', '0'))
            p = synthesize_discount(p)
            p['stock'] = parse_stock(p.get('stockText', ''))
            p['unit'] = normalize_stock_unit(p.get('unit'), p['stock'])
            if 'stockText' in p:
                del p['stockText']
            raw_cat = p.get('rawCategory', '').split('//')[0].strip()
            p['category'] = normalize_category(raw_cat, p.get('name', ''), p.get('id'))
            if 'rawCategory' in p:
                del p['rawCategory']
            products.append(p)

        products = deduplicate_products(products)
        print(f"✅ [YELLOW] Found {len(products)} products")
        scrape_success = True

    except Exception as e:
        print(f"❌ [YELLOW] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        if tmp_profile and os.path.isdir(tmp_profile):
            try:
                shutil.rmtree(tmp_profile, ignore_errors=True)
            except Exception:
                pass

        output_path = os.path.join(DATA_DIR, "yellow_products.json")
        save_products_safe(products, output_path, success=scrape_success)

    return products


def scrape_yellow_prices():
    if not check_vkusvill_available():
        return []
    return asyncio.run(scrape_yellow_prices_async())


if __name__ == "__main__":
    scrape_yellow_prices()
