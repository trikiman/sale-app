"""
Green prices scraper - standalone script for subagent
Scrapes "Зелёные ценники" from cart page
Uses nodriver (CDP) instead of undetected_chromedriver for Chrome 145+ compatibility.
"""
import asyncio
import json
import os
import requests as _requests
import sys
import time
import tempfile
import subprocess
import socket
import shutil

from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount, save_products_safe, check_vkusvill_available, normalize_stock_unit

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GREEN_URL = "https://vkusvill.ru/cart/"
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")
TECH_PROFILE_DIR = os.path.join(DATA_DIR, "tech_profile")


def _normalize_unit(unit_raw):
    raw = str(unit_raw or 'шт').strip().lower()
    if not raw:
        return 'шт'
    if 'kg' in raw or 'кг' in raw:
        return 'кг'
    if raw in ('ml', 'мл'):
        return 'мл'
    if raw in ('l', 'л'):
        return 'л'
    if raw in ('гр', 'г'):
        return 'г'
    return 'шт'


def _format_quantity(value):
    try:
        num = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return ''
    if num.is_integer():
        return str(int(num))
    return f"{num:.3f}".rstrip('0').rstrip('.')


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _find_chrome():
    """Find Chrome executable on Windows."""
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


def resolve_green_browser_profile_dir(preferred_dir: str = TECH_PROFILE_DIR):
    if preferred_dir and os.path.isdir(preferred_dir) and os.listdir(preferred_dir):
        return preferred_dir, False
    return tempfile.mkdtemp(prefix='uc_green_'), True


def _load_existing_green_product_count() -> int:
    path = os.path.join(DATA_DIR, "green_products.json")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return 0

    if isinstance(data, dict):
        products = data.get('products', [])
    elif isinstance(data, list):
        products = data
    else:
        products = []
    return len(products) if isinstance(products, list) else 0


def is_suspicious_empty_green_result(section_found: bool, live_count: int, product_count: int, existing_product_count: int = 0) -> bool:
    """Detect empty results that are more likely scraper failure than true zero green items."""
    return product_count == 0 and ((not section_found) or live_count > 0 or existing_product_count > 0)


def is_suspicious_single_green_result(live_count: int, product_count: int, existing_product_count: int = 0) -> bool:
    """Guard against partial green scrapes collapsing a known-good snapshot to one random item."""
    try:
        live_count = int(live_count or 0)
    except (TypeError, ValueError):
        live_count = 0
    try:
        product_count = int(product_count or 0)
    except (TypeError, ValueError):
        product_count = 0
    try:
        existing_product_count = int(existing_product_count or 0)
    except (TypeError, ValueError):
        existing_product_count = 0

    return product_count == 1 and live_count <= 1 and existing_product_count >= 5


def should_scrape_inline_green_cards(show_all_clicked, inline_product_count: int) -> bool:
    try:
        inline_product_count = int(inline_product_count or 0)
    except (TypeError, ValueError):
        inline_product_count = 0
    return str(show_all_clicked or '') == 'not_found' and inline_product_count > 0


def resolve_green_live_count(live_count: int, product_count: int) -> int:
    """Prefer the larger of the badge count and the actually scraped product count."""
    try:
        live_count = int(live_count or 0)
    except (TypeError, ValueError):
        live_count = 0
    try:
        product_count = int(product_count or 0)
    except (TypeError, ValueError):
        product_count = 0
    return max(live_count, product_count)


def has_real_green_section(body_has_green_text: bool, button_visible: bool, live_count: int) -> bool:
    try:
        live_count = int(live_count or 0)
    except (TypeError, ValueError):
        live_count = 0
    return bool(body_has_green_text or button_visible or live_count > 0)


def filter_available_green_cart_products(products: list) -> list:
    filtered = []
    for product in products or []:
        if not isinstance(product, dict):
            continue
        unavailable = product.get("unavailable")
        if unavailable is None:
            text = str(product.get("stockText") or "").lower()
            unavailable = "нет в наличии" in text
        if unavailable:
            continue
        filtered.append(product)
    return filtered


async def _launch_browser():
    """Launch Chrome via subprocess + connect via nodriver CDP."""
    import nodriver as uc

    port = _find_free_port()
    tmp_profile, is_temp_profile = resolve_green_browser_profile_dir()
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

    print(f"  [GREEN] Launching Chrome on port {port}...")
    proc = subprocess.Popen(args)
    await asyncio.sleep(3)

    browser = await uc.Browser.create(host='127.0.0.1', port=port)
    browser._process_pid = proc.pid
    return browser, proc, tmp_profile, is_temp_profile


async def _load_cookies(page):
    """Load VkusVill session cookies from cookies.json into browser via CDP."""
    if not os.path.exists(COOKIES_PATH):
        print(f"  [GREEN] No cookies.json found at {COOKIES_PATH}")
        print(f"  [GREEN] Run tech-login from admin panel to save session.")
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
        if c.get('expiry', 0) > 0:  # skip session cookies saved as expiry=0
            cp.expires = network.TimeSinceEpoch(c['expiry'])
        if 'sameSite' in c:
            cp.same_site = ss_map.get(c['sameSite'])
        cdp_cookies.append(cp)

    await page.send(network.set_cookies(cdp_cookies))
    print(f"  [GREEN] Loaded {len(cdp_cookies)}/{len(cookies)} cookies via CDP")
    return len(cdp_cookies) > 0


def _fetch_basket_snapshot() -> dict:
    if not os.path.exists(COOKIES_PATH):
        return {}

    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in raw)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://vkusvill.ru',
        'Referer': 'https://vkusvill.ru/cart/',
        'Cookie': cookie_str,
    }

    try:
        r = _requests.post(
            'https://vkusvill.ru/ajax/delivery_order/basket_recalc.php',
            data={'COUPON': '', 'BONUS': ''},
            headers=headers,
            timeout=15,
        )
        data = r.json()
    except Exception as e:
        print(f"  [GREEN] basket_recalc fetch failed: {e}")
        return {}

    basket = data.get('basket', {})
    return basket if isinstance(basket, dict) else {}


def build_basket_stock_map(basket: dict) -> dict:
    stock_map = {}

    for item in basket.values():
        if not isinstance(item, dict):
            continue

        pid = str(item.get('PRODUCT_ID', '')).strip()
        if not pid:
            continue

        raw_value = item.get('MAX_Q')
        if raw_value in (None, ''):
            raw_value = item.get('STORE_MAX_Q')

        try:
            value = float(str(raw_value).replace(',', '.'))
        except (TypeError, ValueError):
            continue

        if value.is_integer():
            value = int(value)

        stock_map[pid] = {
            'value': value,
            'unit': _normalize_unit(item.get('UNIT') or item.get('UNITS')),
            'price': str(item.get('PRICE', '') or ''),
            'oldPrice': str(item.get('BASE_PRICE') or item.get('PRICE_OLD') or item.get('OLD_PRICE') or ''),
            'can_buy': item.get('CAN_BUY') == 'Y',
        }

    return stock_map


def _stock_text_from_map(stock_data: dict) -> str:
    if not stock_data:
        return ''

    quantity = _format_quantity(stock_data.get('value'))
    if not quantity:
        return ''

    return f"В наличии: {quantity} {stock_data.get('unit', 'шт')}"


def _fetch_green_from_basket() -> list:
    """Read green-priced items directly from basket_recalc.php using Python requests.
    Basket items with IS_GREEN=1 are green prices already in the technical account's cart.
    These are hidden from the "Зелёные ценники" recommendation section by VkusVill.
    """
    if not os.path.exists(COOKIES_PATH):
        return []
    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in raw)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://vkusvill.ru',
        'Referer': 'https://vkusvill.ru/cart/',
        'Cookie': cookie_str,
    }
    try:
        r = _requests.post(
            'https://vkusvill.ru/ajax/delivery_order/basket_recalc.php',
            data={'COUPON': '', 'BONUS': ''}, headers=headers, timeout=15
        )
        data = r.json()
    except Exception as e:
        print(f"  [GREEN] basket_recalc fetch failed: {e}")
        return []

    basket = data.get('basket', {})
    products = []
    for item in basket.values():
        if not isinstance(item, dict):
            continue
        if not (item.get('IS_GREEN') == '1' or item.get('IS_GREEN') is True
                or item.get('IS_GREEN') == 1):
            continue
        if item.get('CAN_BUY') != 'Y':
            continue
        pid = str(item.get('PRODUCT_ID', ''))
        url = item.get('URL') or item.get('DETAIL_PAGE_URL', '')
        if url and not url.startswith('http'):
            url = f"https://vkusvill.ru{url}"
        img = item.get('IMG') or item.get('PICTURE') or item.get('PREVIEW_PICTURE') or ''
        if img and not img.startswith('http'):
            img = f"https://vkusvill.ru{img}"
        unit_raw = str(item.get('UNIT', item.get('UNITS', 'шт'))).lower()
        unit = 'кг' if 'кг' in unit_raw or 'kg' in unit_raw else 'шт'
        max_q = item.get('MAX_Q')
        stock_val = max_q if max_q is not None else (item.get('STORE_MAX_Q') or 99)
        can_buy = item.get('CAN_BUY') == 'Y'
        products.append({
            'id': pid,
            'name': item.get('NAME', ''),
            'url': url,
            'currentPrice': str(item.get('PRICE', '0')),
            'oldPrice': str(item.get('BASE_PRICE') or item.get('PRICE_OLD') or item.get('OLD_PRICE') or '0'),
            'image': img,
            'stockText': f"В наличии: {stock_val}",
            'unit': unit,
            'category': 'Зелёные ценники',
            'type': 'green',
            'can_buy': can_buy,
        })
    print(f"  [GREEN] basket_recalc: {len(products)} green items (IS_GREEN=1) out of {len(basket)} total")
    return products


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
        # value is list of [key, val_descriptor] pairs
        if isinstance(v, list):
            return {pair[0]: _deserialize(pair[1]) for pair in v if isinstance(pair, (list, tuple)) and len(pair) == 2}
        return v
    return v


async def _js(page, script):
    """Run JS via page.evaluate and deserialize the result."""
    raw = await page.evaluate(script)
    # nodriver may return deep-serialized objects for complex results
    if isinstance(raw, dict) and 'type' in raw:
        return _deserialize(raw)
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and 'type' in raw[0]:
        return [_deserialize(item) for item in raw]
    return raw


async def _inspect_green_section(page) -> tuple[bool, bool, int]:
    state = await _js(page, r"""
        (() => {
            const normalize = (text) => (text || '')
                .replace(/\u00a0/g, ' ')
                .replace(/\s+/g, ' ')
                .trim();
            const isVisible = (el) => !!(el && el.offsetParent !== null && !el.classList.contains('_hidden'));
            const extractCount = (text) => {
                const match = normalize(text).match(/(\d+)\s*товар/i);
                return match ? parseInt(match[1], 10) : 0;
            };

            const bodyText = normalize(document.body.innerText || '');
            const bodyHasGreenText = bodyText.includes('Зелёные ценники') || bodyText.includes('Зеленые ценники');

            const greenButton = document.querySelector('[data-action="GreenLabels"]');
            const buttonVisible = isVisible(greenButton);

            let liveCount = 0;

            // Method 1: count swiper slides with aria-label (most reliable)
            const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
            if (greenSection) {
                const ariaSlides = greenSection.querySelectorAll('.swiper-slide[aria-label]');
                if (ariaSlides.length > 0) {
                    // aria-label is like "3 / 12" — the total is in the second number
                    const lastLabel = ariaSlides[ariaSlides.length - 1].getAttribute('aria-label') || '';
                    const totalMatch = lastLabel.match(/\/\s*(\d+)/);
                    if (totalMatch) liveCount = parseInt(totalMatch[1], 10);
                    if (!liveCount) liveCount = ariaSlides.length;
                }
            }

            // Method 2: text-based count from container nodes
            if (!liveCount) {
                const containers = document.querySelectorAll('section, article, div');
                for (const node of containers) {
                    if (!isVisible(node)) continue;
                    const text = normalize(node.innerText || '');
                    if (!text) continue;
                    if ((text.includes('Зелёные ценники') || text.includes('Зеленые ценники')) && /\d+\s*товар/i.test(text)) {
                        liveCount = Math.max(liveCount, extractCount(text));
                    }
                }
            }

            // Method 3: walk up from button
            if (!liveCount && buttonVisible) {
                let current = greenButton;
                for (let depth = 0; depth < 6 && current; depth += 1) {
                    const text = normalize(current.innerText || current.textContent || '');
                    if (text) {
                        liveCount = Math.max(liveCount, extractCount(text));
                    }
                    current = current.parentElement;
                }
            }

            return [bodyHasGreenText, buttonVisible, liveCount];
        })()
    """) or [False, False, 0]

    if not isinstance(state, list) or len(state) != 3:
        return False, False, 0

    body_has_green_text = bool(state[0])
    button_visible = bool(state[1])
    try:
        live_count = int(state[2] or 0)
    except (TypeError, ValueError):
        live_count = 0
    return body_has_green_text, button_visible, live_count


def _green_inline_scope_expr() -> str:
    return """
        (() => {
            const isVisible = (el) => !!(el && el.offsetParent !== null && !el.classList.contains('_hidden'));
            const directGreenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
            if (isVisible(directGreenSection) && directGreenSection.querySelector('.ProductCard')) {
                return directGreenSection;
            }

            const candidates = [];
            const pushCandidate = (candidate) => {
                if (candidate && !candidates.includes(candidate)) {
                    candidates.push(candidate);
                }
            };

            const action = document.querySelector('[data-action="GreenLabels"]');
            if (action) {
                pushCandidate(action.closest('section, [class*="Section"], [class*="Tizer"], [class*="Cart"]'));
                let current = action.parentElement;
                for (let depth = 0; depth < 6 && current; depth += 1) {
                    pushCandidate(current);
                    current = current.parentElement;
                }
            }

            document.querySelectorAll('section, div, article').forEach((node) => {
                const text = (node.textContent || '').replace(/\u00a0/g, ' ');
                const isGreenSection = text.includes('\u0417\u0435\u043b\u0451\u043d\u044b\u0435 \u0446\u0435\u043d\u043d\u0438\u043a\u0438')
                    || text.includes('\u0417\u0435\u043b\u0435\u043d\u044b\u0435 \u0446\u0435\u043d\u043d\u0438\u043a\u0438');
                // Guard: reject nodes that also contain the "Добавьте в заказ" section
                // to avoid confusing regular product recommendations with green prices
                const hasNonGreen = text.includes('\u0414\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u0432 \u0437\u0430\u043a\u0430\u0437');
                if (isGreenSection && !hasNonGreen && node.querySelector('.ProductCard')) {
                    pushCandidate(node);
                }
            });

            for (const candidate of candidates) {
                if (candidate && candidate.querySelector('.ProductCard')) {
                    return candidate;
                }
            }
            return null;
        })()
    """


def _green_card_scope_expr(card_source: str) -> str:
    if card_source == 'modal':
        return "document.getElementById('js-modal-cart-prods-scroll')"
    return _green_inline_scope_expr()


def _green_product_cards_script(card_source: str) -> str:
    scope_expr = _green_card_scope_expr(card_source)
    return f"""
        (() => {{
            const products = [];
            const seen = new Set();
            const scope = {scope_expr};
            if (!scope) return products;

            // VkusVill uses Swiper carousel which duplicates cards for infinite
            // loop.  Real slides have aria-label like "3 / 12"; clones do not.
            // We only process slides with aria-label to avoid duplicates.
            const slides = scope.querySelectorAll('.swiper-slide[aria-label]');
            const cards = slides.length > 0
                ? Array.from(slides).map(s => s.querySelector('.ProductCard')).filter(Boolean)
                : Array.from(scope.querySelectorAll('.ProductCard'));

            cards.forEach((card) => {{
                // Try multiple selectors for the product link/name.
                // In the slider layout .ProductCard__link text can be empty;
                // fall back to .ProductCard__title or any goods link.
                const goodsLinks = Array.from(card.querySelectorAll(
                    '.ProductCard__link, .ProductCard__title, a[href*="/goods/"]'
                ));
                let nameEl = goodsLinks.find((el) => (el.innerText || '').trim());
                // Even if no element has text, pick the first link for URL
                const linkEl = goodsLinks.find((el) => el.href && el.href.includes('/goods/')) || goodsLinks[0];
                if (!linkEl) return;

                const url = linkEl.href || '';
                const idMatch = url.match(/(\\d+)\\.html/);
                const id = idMatch ? idMatch[1] : '';

                // Extract name: prefer nameEl text, fall back to card title or card text
                let name = nameEl ? (nameEl.innerText || '').trim() : '';
                if (!name) {{
                    const titleEl = card.querySelector('.ProductCard__Title, [class*="ProductCard__title"], [class*="title"]');
                    name = titleEl ? (titleEl.innerText || '').trim() : '';
                }}
                if (!name) {{
                    // Last resort: extract from full card text (first non-price line)
                    const lines = (card.innerText || '').split('\\n').map(l => l.trim()).filter(Boolean);
                    name = lines.find(l => !l.match(/^\\d/) && !l.includes('\\u20bd') && !l.includes('\\u0440\\u0443\\u0431') && l.length > 3) || '';
                }}

                const dedupeKey = id || url || name;
                if (!dedupeKey || seen.has(dedupeKey)) return;
                seen.add(dedupeKey);

                const priceEl = card.querySelector('.ProductCard__price--current, .Price__value, .ProductCard__price');
                const oldPriceEl = card.querySelector('.ProductCard__price--old, .ProductCard__OldPrice');
                const imgEl = card.querySelector('.ProductCard__image img, .ProductCard__imageLink img, img');
                const text = card.innerText || '';

                let imgSrc = '';
                if (imgEl) {{
                    imgSrc = imgEl.getAttribute('data-src') || imgEl.getAttribute('src') || imgEl.src || '';
                }}
                if (!imgSrc || imgSrc.includes('data:image')) {{
                    const source = card.querySelector('picture source[srcset]');
                    if (source && source.srcset) imgSrc = source.srcset.split(' ')[0];
                }}
                if (!imgSrc || imgSrc.includes('data:image')) {{
                    const bgEl = card.querySelector('.ProductCard__imageLink, .ProductCard__image');
                    if (bgEl) {{
                        const bg = window.getComputedStyle(bgEl).backgroundImage;
                        if (bg && bg !== 'none' && bg.startsWith('url')) {{
                            imgSrc = bg.replace(/^url\\(['"]?/, '').replace(/['"]?\\)$/, '');
                        }}
                    }}
                }}
                if (imgSrc && (imgSrc.includes('no-image.svg') || imgSrc.includes('data:image') || imgSrc.includes('spacer.gif'))) {{
                    imgSrc = '';
                }}

                const isWeightItem = name.includes('\\u0412\\u0415\\u0421')
                    || name.toLowerCase().includes('/\\u043a\\u0433')
                    || text.includes('/\\u043a\\u0433')
                    || (priceEl && priceEl.innerText.includes('/\\u043a\\u0433'));

                products.push({{
                    id,
                    name,
                    url,
                    currentPrice: priceEl ? priceEl.innerText : '0',
                    oldPrice: oldPriceEl ? oldPriceEl.innerText : '0',
                    image: imgSrc,
                    stockText: text,
                    unit: isWeightItem ? '\\u043a\\u0433' : '\\u0448\\u0442',
                    category: '\\u0417\\u0435\\u043b\\u0451\\u043d\\u044b\\u0435 \\u0446\\u0435\\u043d\\u043d\\u0438\\u043a\\u0438',
                    type: 'green'
                }});
            }});
            return products;
        }})()
    """


async def _extract_green_cards(page, card_source: str) -> list:
    return await _js(page, _green_product_cards_script(card_source)) or []


async def _add_green_cards_to_cart(page, card_source: str, total_cards: int):
    scope_expr = _green_card_scope_expr(card_source)
    added_count = 0
    results_summary = {'no_scope': 0, 'no_card': 0, 'already_in_cart': 0, 'added': 0, 'no_button': 0}

    for idx in range(total_cards):
        result = await _js(page, f"""
            (() => {{
                const scope = {scope_expr};
                const isVisible = (el) => !!(el && el.offsetParent !== null && !el.classList.contains('_hidden'));
                if (!scope) return 'no_scope';
                const cards = scope.querySelectorAll('.ProductCard');
                const card = cards[{idx}];
                if (!card) return 'no_card';
                const btn = card.querySelector('.js-delivery__basket--add, .CartButton__content--add, .CartButton__content, .ProductCard__add, .ProductCard__addToCart, button');
                if (btn && isVisible(btn)) {{
                    btn.click();
                    return 'added';
                }}
                if (card.querySelector('.ProductCard__quantityControl')) return 'already_in_cart';
                return 'no_button';
            }})()
        """)
        result = str(result) if result else 'no_button'
        results_summary[result] = results_summary.get(result, 0) + 1
        if result == 'added':
            added_count += 1
        await asyncio.sleep(1.0)  # 1s delay between cart adds (human-like, avoid bot ban)

    return results_summary, added_count


async def _close_green_modal(page):
    await _js(page, """
        (() => {
            const closeBtn = document.querySelector('.Modal__close, .js-modal-close');
            if (closeBtn) closeBtn.click();
            else {
                const overlay = document.querySelector('.Modal__overlay');
                if (overlay) overlay.click();
            }
        })()
    """)


async def _scrape_cart_stock_map(page) -> dict:
    stock_map = await _js(page, """
        (() => {
            const stockMap = {};
            document.querySelectorAll('.HProductCard, .BasketItem').forEach(card => {
                const nameEl = card.querySelector('.HProductCard__Title, .BasketItem__title');
                if (!nameEl) return;

                const url = nameEl.href || '';
                const idMatch = url.match(/(\\d+)\\.html/);
                if (!idMatch) return;

                const text = card.innerText;
                let stock = 0;
                let stockUnit = '\\u0448\\u0442';

                const kgMatch = text.match(/\\u043d\\u0430\\u043b\\u0438\\u0447\\u0438\\u0438[:\\s]*([\\d.,]+)\\s*\\u043a\\u0433/i);
                const shtMatch = text.match(/\\u043d\\u0430\\u043b\\u0438\\u0447\\u0438\\u0438[:\\s]*(\\d+)/i)
                    || text.match(/(\\d+)\\s*\\u0448\\u0442/);

                if (kgMatch) {
                    stock = parseFloat(kgMatch[1].replace(',', '.'));
                    stockUnit = '\\u043a\\u0433';
                } else if (shtMatch) {
                    stock = parseInt(shtMatch[1]);
                    stockUnit = '\\u0448\\u0442';
                } else if (text.includes('\\u041c\\u0430\\u043b\\u043e') || text.includes('\\u043c\\u0430\\u043b\\u043e')) {
                    stock = 3;
                } else if (text.includes('\\u043d\\u0430\\u043b\\u0438\\u0447\\u0438\\u0438')) {
                    stock = 99;
                }

                let price = null;
                let oldPrice = null;

                const priceDataEl = card.querySelector('.js-datalayer-catalog-list-price');
                const oldPriceDataEl = card.querySelector('.js-datalayer-catalog-list-price-old');
                if (priceDataEl) price = priceDataEl.innerText.trim();
                if (oldPriceDataEl) oldPrice = oldPriceDataEl.innerText.trim();

                if (price === '1' && stockUnit === '\\u043a\\u0433') {
                    const normalizedText = text.replace(/\\n/g, ' ');
                    const rubKgMatch = normalizedText.match(/(\\d[\\d\\s]*)\\s*\\u20bd\\s*\\/\\s*\\u043a\\u0433/i);
                    if (rubKgMatch) price = rubKgMatch[1].replace(/\\s/g, '');
                }

                if (!price || price === '1') {
                    const priceSelectors = ['.HProductCard__Price', '.Price__value', '.BasketItem__price', '[class*="price"]', '[class*="Price"]'];
                    for (const sel of priceSelectors) {
                        const el = card.querySelector(sel);
                        if (!el) continue;
                        const priceText = el.innerText.trim();
                        const perKgMatch = priceText.match(/([\\d\\s]+)\\s*\\u20bd\\/\\u043a\\u0433/i);
                        if (perKgMatch) {
                            price = perKgMatch[1].replace(/\\s/g, '');
                            break;
                        }
                        const priceMatch = priceText.match(/([\\d\\s]+)\\s*\\u20bd/);
                        if (priceMatch && priceMatch[1] !== '1') {
                            price = priceMatch[1].replace(/\\s/g, '');
                            break;
                        }
                    }
                }

                if (!price || price === '1') {
                    const perKgTextMatch = text.match(/([\\d\\s]+)\\s*\\u20bd\\/\\u043a\\u0433/);
                    if (perKgTextMatch) price = perKgTextMatch[1].replace(/\\s/g, '');
                }

                stockMap[idMatch[1]] = { value: stock, unit: stockUnit, price: price, oldPrice: oldPrice };
            });
            return stockMap;
        })()
    """)
    return stock_map or {}


async def _extract_green_cart_items(page) -> list:
    products = await _js(page, """
        (() => {
            const products = [];
            const seen = new Set();

            document.querySelectorAll('.HProductCard, .BasketItem').forEach((card) => {
                const nameEl = card.querySelector('.HProductCard__Title, .BasketItem__title');
                if (!nameEl) return;

                const url = nameEl.href || '';
                const idMatch = url.match(/(\\d+)\\.html/);
                const id = idMatch ? idMatch[1] : '';
                const dedupeKey = id || url || (nameEl.innerText || '').trim();
                if (seen.has(dedupeKey)) return;
                seen.add(dedupeKey);

                const priceEl = card.querySelector('.js-datalayer-catalog-list-price, .HProductCard__Price, .Price__value, .BasketItem__price, [class*="price"], [class*="Price"]');
                const oldPriceEl = card.querySelector('.js-datalayer-catalog-list-price-old');
                const imgEl = card.querySelector('img');
                const text = card.innerText || '';
                const priceText = priceEl ? priceEl.innerText.trim() : '0';
                const isWeightItem = text.includes('/\\u043a\\u0433') || priceText.includes('/\\u043a\\u0433');
                const unavailable = card.classList.contains('_disabled');

                products.push({
                    id,
                    name: (nameEl.innerText || '').trim(),
                    url,
                    currentPrice: priceText,
                    oldPrice: oldPriceEl ? oldPriceEl.innerText.trim() : '0',
                    image: imgEl ? (imgEl.getAttribute('src') || imgEl.src || '') : '',
                    stockText: text,
                    unit: isWeightItem ? '\\u043a\\u0433' : '\\u0448\\u0442',
                    category: '\\u0417\\u0435\\u043b\\u0451\\u043d\\u044b\\u0435 \\u0446\\u0435\\u043d\\u043d\\u0438\\u043a\\u0438',
                    type: 'green',
                    unavailable
                });
            });

            return products;
        })()
    """)
    return products or []


def _merge_green_cart_data(raw_products: list, stock_map: dict) -> list:
    basket_snapshot = _fetch_basket_snapshot()
    basket_stock_map = build_basket_stock_map(basket_snapshot)
    if basket_stock_map:
        stock_map = basket_stock_map
        print(f"  [GREEN] Replaced DOM stock map with basket_recalc data for {len(stock_map)} items.")

    print("  [GREEN] Checking basket for green-priced items already in cart...")
    cart_green_raw = _fetch_green_from_basket()
    if cart_green_raw:
        existing_ids = {p.get('id') for p in raw_products}
        added_from_cart = 0
        for cg in cart_green_raw:
            if cg.get('id') and cg['id'] not in existing_ids:
                raw_products.append(cg)
                existing_ids.add(cg['id'])
                added_from_cart += 1
        print(f"  [GREEN] Added {added_from_cart} green items from cart.")

    for p in raw_products:
        pid = p.get('id', '')
        if pid and pid in stock_map:
            stock_data = stock_map[pid]
            p['stockText'] = _stock_text_from_map(stock_data) or p.get('stockText', '')
            p['unit'] = stock_data.get('unit', p.get('unit', 'ÑˆÑ‚'))

            cur_price = str(p.get('currentPrice', '0'))
            old_price = str(p.get('oldPrice', '0'))
            cart_price = stock_data.get('price')
            cart_old_price = stock_data.get('oldPrice')

            if cart_price and cur_price in ['0', '1', '', 'None']:
                p['currentPrice'] = cart_price

            if cart_old_price and old_price in ['0', '1', '', 'None']:
                p['oldPrice'] = cart_old_price
            elif not old_price or old_price in ['0', '1', '', 'None']:
                try:
                    current = int(p.get('currentPrice', 0))
                    if current > 1:
                        p['oldPrice'] = str(int(round(current / 0.6)))
                except (ValueError, TypeError):
                    pass
        elif p.get('currentPrice') in ['0', '1', '']:
            print(f"  [DEBUG] Product not in cart, price=1: {p.get('name', '')[:40]} (id={pid})")

    return raw_products


async def _reveal_green_card_stock(page, raw_products: list, card_source: str) -> list:
    print(f"  [GREEN] Adding {len(raw_products)} {card_source} cards to cart to reveal stock...")
    results_summary, added_count = await _add_green_cards_to_cart(page, card_source, len(raw_products))
    print(f"  [GREEN] Add-to-cart results: {results_summary}")
    print(f"  [GREEN] Added {added_count} items to cart.")

    if card_source == 'modal':
        await _close_green_modal(page)
        await asyncio.sleep(2)

    print("  [GREEN] Scrolling cart page to load all items...")
    await _js(page, 'window.scrollTo(0, document.body.scrollHeight)')
    await asyncio.sleep(2)
    await _js(page, 'window.scrollTo(0, 0)')
    await asyncio.sleep(1)

    print("  [GREEN] Scraping stock and prices from cart...")
    stock_map = await _scrape_cart_stock_map(page)
    print(f"  [GREEN] Got stock for {len(stock_map)} items from cart.")

    return _merge_green_cart_data(raw_products, stock_map)


def _fetch_green_from_basket() -> list:
    """Read green items from basket_recalc with reliable stock/unit data."""
    basket = _fetch_basket_snapshot()
    if not basket:
        return []

    stock_map = build_basket_stock_map(basket)
    products = []

    for item in basket.values():
        if not isinstance(item, dict):
            continue
        if not (item.get('IS_GREEN') == '1' or item.get('IS_GREEN') is True or item.get('IS_GREEN') == 1):
            continue
        if item.get('CAN_BUY') != 'Y':
            continue

        pid = str(item.get('PRODUCT_ID', ''))
        url = item.get('URL') or item.get('DETAIL_PAGE_URL', '')
        if url and not url.startswith('http'):
            url = f"https://vkusvill.ru{url}"

        img = item.get('IMG') or item.get('PICTURE') or item.get('PREVIEW_PICTURE') or ''
        if img and not img.startswith('http'):
            img = f"https://vkusvill.ru{img}"

        stock_data = stock_map.get(pid, {})
        products.append({
            'id': pid,
            'name': item.get('NAME', ''),
            'url': url,
            'currentPrice': stock_data.get('price') or str(item.get('PRICE', '0')),
            'oldPrice': stock_data.get('oldPrice') or str(item.get('BASE_PRICE') or item.get('PRICE_OLD') or item.get('OLD_PRICE') or '0'),
            'image': img,
            'stockText': _stock_text_from_map(stock_data),
            'unit': stock_data.get('unit') or _normalize_unit(item.get('UNIT') or item.get('UNITS')),
            'category': 'Зелёные ценники',
            'type': 'green',
            'can_buy': item.get('CAN_BUY') == 'Y',
        })

    print(f"  [GREEN] basket_recalc: {len(products)} green items (IS_GREEN=1) out of {len(basket)} total")
    return products


async def scrape_green_prices_async():
    """
    Green scraper — simplified flow:
    1. Go to /cart/
    2. Turn on "Больше товаров" switch
    3. Find "Зелёные ценники" section
       3.1 If "X товаров" / "показать все" button exists → click to open modal
           3.1.1 In modal: scroll + click "В корзину" under each card
                 until card disappears or button no longer says "в корзину"
           3.1.2 Reload page
       3.2 If no button (inline items): add all one-by-one, skip if none
           3.2.0 Same stopping rule: until card gone or no "в корзину"
           3.2.1 Reload page
    4. Scroll through cart items — scrape GREEN-labeled items only
       - Skip GRAY labels
       - Stop scrolling at "нет в наличии" / stock 0
       - If ALL are unavailable → green price is gone
    5. Process & save
    6. Close Chrome
    """
    print("🔄 [GREEN] Starting...")
    browser = None
    proc = None
    tmp_profile = None
    using_temp_profile = True
    products = []
    live_count = 0
    scrape_success = False

    try:
        # ── STEP 1: Launch browser, load cookies, go to /cart/ ──
        browser, proc, tmp_profile, using_temp_profile = await _launch_browser()

        page = await browser.get('https://vkusvill.ru')
        await asyncio.sleep(3)

        cookies_ok = await _load_cookies(page)
        if not cookies_ok:
            print("⚠️ [GREEN] No cookies loaded. Run tech-login from admin panel first.")

        page = await browser.get(GREEN_URL)
        await asyncio.sleep(10)

        # Check for 403 block
        title = await _js(page, 'document.title')
        print(f"  [GREEN] Page title: {title}")
        page_text = str(await _js(page, 'document.body.innerText') or '')
        if "403" in str(title) or "Forbidden" in page_text or "запрещен" in page_text.lower():
            print("❌ [GREEN] Blocked (403)!")
            return [], False

        # Check if logged in
        login_signals = await _js(page, r"""
            (() => {
                const text = document.body.innerText || '';
                return [
                    text.includes('Войти'),
                    text.includes('Кабинет') || text.includes('Выход'),
                    /\+7\s*\(\d{3}\)\s*\d{3}/.test(text),
                    text.includes('Способ оплаты') || text.includes('Наличными') || text.includes('Картой'),
                    text.includes('Ваши данные') || text.includes('Номер телефона'),
                    document.querySelectorAll('.HProductCard, .BasketItem, .VV_CartItem').length > 0,
                    !!document.getElementById('js-Delivery__Order-green-state-not-empty')
                ];
            })()
        """) or []
        if not isinstance(login_signals, list) or len(login_signals) < 7:
            login_signals = [True, False, False, False, False, False, False]
        labels = ['hasLogin', 'hasKabinet', 'hasPhone', 'hasPayment', 'hasUserData', 'hasCartItems', 'hasGreenSection']
        named = {labels[i]: bool(login_signals[i]) for i in range(len(labels))}
        print(f"  [GREEN] Login signals: {named}")

        is_logged_in = (
            not named['hasLogin']
            or named['hasKabinet']
            or named['hasPhone']
            or named['hasPayment']
            or named['hasUserData']
            or named['hasCartItems']
            or named['hasGreenSection']
        )
        if not is_logged_in:
            print("❌ [GREEN] Not logged in! Aborting.")
            return [], False
        print("  [GREEN] Logged in OK")

        # ── STEP 2: Turn on "Больше товаров" switch ──
        print("  [GREEN] Step 2: Checking 'Больше товаров' toggle...")
        modal_opened = await _js(page, """
            (() => {
                const links = document.querySelectorAll('.js-delivery-slots-load, a[class*="delivery-slots"]');
                for (const link of links) {
                    if (link.offsetParent !== null || link.offsetWidth > 0) {
                        link.click();
                        return 'clicked_link';
                    }
                }
                const allLinks = document.querySelectorAll('a, button');
                for (const el of allLinks) {
                    if (el.innerText.trim() === 'Изменить' && el.closest('[class*="delivery"], [class*="Delivery"]')) {
                        el.click();
                        return 'clicked_text';
                    }
                }
                return 'not_found';
            })()
        """)
        print(f"  [GREEN] Delivery modal trigger: {modal_opened}")

        if modal_opened != 'not_found':
            await asyncio.sleep(3)

            # Find and enable the "Больше товаров" toggle
            # Strategy: find it, check its state, click if OFF, verify it's ON
            toggle_result = await _js(page, """
                (() => {
                    // Search for "Больше товаров" text in the delivery modal
                    const allText = document.querySelectorAll('*');
                    let toggleContainer = null;
                    for (const el of allText) {
                        if (el.children.length > 3) continue; // skip containers
                        const t = (el.textContent || '').trim();
                        if (t.includes('Больше товаров') && t.length < 100) {
                            // Walk up to find the toggle container (label or parent with toggle)
                            toggleContainer = el.closest('label') || el.closest('[class*="Toggler"]') || el.parentElement;
                            break;
                        }
                    }
                    if (!toggleContainer) return ['not_found', ''];

                    // Check if toggle is ON by looking for checked input or active class
                    const input = toggleContainer.querySelector('input[type="checkbox"]');
                    const isChecked = input && input.checked;
                    const hasActiveClass = toggleContainer.innerHTML.includes('active') ||
                                           toggleContainer.innerHTML.includes('Active');

                    return [isChecked ? 'on' : 'off', toggleContainer.className.substring(0, 100)];
                })()
            """) or ['not_found', '']
            if isinstance(toggle_result, list) and len(toggle_result) >= 2:
                toggle_state = str(toggle_result[0])
                toggle_class = str(toggle_result[1])
            else:
                toggle_state = str(toggle_result)
                toggle_class = ''
            print(f"  [GREEN] 'Больше товаров' toggle: {toggle_state} (class: {toggle_class})")

            if toggle_state != 'on':
                print("  [GREEN] Enabling 'Больше товаров'...")
                # Try clicking the toggle/input/label
                clicked = await _js(page, """
                    (() => {
                        const allText = document.querySelectorAll('*');
                        let toggleContainer = null;
                        for (const el of allText) {
                            if (el.children.length > 3) continue;
                            const t = (el.textContent || '').trim();
                            if (t.includes('Больше товаров') && t.length < 100) {
                                toggleContainer = el.closest('label') || el.closest('[class*="Toggler"]') || el.parentElement;
                                break;
                            }
                        }
                        if (!toggleContainer) return 'not_found';

                        // Try clicking the toggle switch button
                        const toggler = toggleContainer.querySelector('[class*="Toggler__Btn"], [class*="toggle"], [class*="Toggle"], [class*="switch"], [class*="Switch"]');
                        if (toggler) { toggler.click(); return 'clicked_toggler'; }

                        // Try the input checkbox
                        const input = toggleContainer.querySelector('input[type="checkbox"]');
                        if (input) { input.click(); return 'clicked_input'; }

                        // Try the label itself
                        toggleContainer.click();
                        return 'clicked_container';
                    })()
                """)
                print(f"  [GREEN] Toggle click: {clicked}")
                await asyncio.sleep(5)

                # Verify it actually toggled ON
                verify = await _js(page, """
                    (() => {
                        const allText = document.querySelectorAll('*');
                        for (const el of allText) {
                            if (el.children.length > 3) continue;
                            const t = (el.textContent || '').trim();
                            if (t.includes('Больше товаров') && t.length < 100) {
                                const container = el.closest('label') || el.closest('[class*="Toggler"]') || el.parentElement;
                                if (!container) return 'no_container';
                                const input = container.querySelector('input[type="checkbox"]');
                                return input && input.checked ? 'on' : 'still_off';
                            }
                        }
                        return 'not_found';
                    })()
                """)
                print(f"  [GREEN] Toggle verify: {verify}")

                if str(verify) == 'still_off':
                    # Last resort: try clicking the entire label area
                    await _js(page, """
                        (() => {
                            const labels = document.querySelectorAll('label');
                            for (const l of labels) {
                                if ((l.textContent || '').includes('Больше товаров')) {
                                    l.click();
                                    return 'clicked_label';
                                }
                            }
                        })()
                    """)
                    await asyncio.sleep(3)

            # Close delivery modal
            await _js(page, """
                (() => {
                    const closeBtn = document.querySelector('.Modal__close, .js-modal-close, .VV_ModalClose');
                    if (closeBtn) closeBtn.click();
                })()
            """)
            await asyncio.sleep(1)

            if toggle_state != 'on':
                # Reload page so the expanded assortment loads
                page = await browser.get(GREEN_URL)
                await asyncio.sleep(8)

        # ── STEP 3: Find "Зелёные ценники" section ──
        print("  [GREEN] Step 3: Looking for green section...")
        await _js(page, 'window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(2)
        await _js(page, 'window.scrollTo(0, 2000)')  # Green section is ~2000px down
        await asyncio.sleep(2)

        # Debug: check what's on the page
        try:
            debug_path = os.path.join(DATA_DIR, "debug_green_page.png")
            await page.save_screenshot(debug_path)
            print(f"  [GREEN] Debug screenshot saved: {debug_path}")
        except Exception as e:
            print(f"  [GREEN] Screenshot failed: {e}")

        # Quick debug: return flat array [hasGreenSection, hasGreenText, cartItemCount, greenIdList]
        green_debug = await _js(page, r"""
            (() => {
                const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                const bodyText = document.body.innerText || '';
                const hasText = bodyText.includes('Зелёные ценники') || bodyText.includes('Зеленые ценники');
                const cartItems = document.querySelectorAll('.HProductCard, .BasketItem, .VV_CartItem').length;
                const greenIds = Array.from(document.querySelectorAll('[id*="green"], [id*="Green"]')).map(el => el.id);
                return [!!section, hasText, cartItems, greenIds.join(',')];
            })()
        """) or []
        if isinstance(green_debug, list) and len(green_debug) >= 4:
            print(f"    Section element exists: {green_debug[0]}")
            print(f"    'Зелёные ценники' text on page: {green_debug[1]}")
            print(f"    Cart items on page: {green_debug[2]}")
            print(f"    Green IDs found: {green_debug[3]}")
        else:
            print(f"    Debug returned: {green_debug}")

        # Check if green section exists — return FLAT ARRAY [found, buttonText, inlineCards]
        green_info = await _js(page, r"""
            (() => {
                const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (!section) return [false, '', 0];

                // Look for "X товаров" / "показать все" button near the section
                let buttonText = '';
                let container = section;
                for (let depth = 0; depth < 4; depth++) {
                    const links = container.querySelectorAll('a, button, [class*="Link"]');
                    for (const link of links) {
                        const text = (link.innerText || '').trim();
                        if ((text.includes('Показать все') || text.includes('показать все') ||
                             /^\d+\s*товар/i.test(text)) && link.offsetParent !== null) {
                            buttonText = text;
                            break;
                        }
                    }
                    if (buttonText) break;
                    container = container.parentElement;
                    if (!container) break;
                }

                // Count inline product cards
                const inlineCards = section.querySelectorAll('.ProductCard').length;
                return [true, buttonText, inlineCards];
            })()
        """) or []
        if not isinstance(green_info, list) or len(green_info) < 3:
            green_info = [False, '', 0]

        section_found = bool(green_info[0])
        show_all_button = str(green_info[1] or '')
        inline_count = int(green_info[2] or 0)

        if not section_found:
            print("⚠️ [GREEN] Green section not found on page!")
            # Try basket API fallback
            raw_products = _fetch_green_from_basket()
            if raw_products:
                print(f"  [GREEN] Fallback: got {len(raw_products)} items from basket API.")
            else:
                existing = _load_existing_green_product_count()
                if existing > 0:
                    print("⚠️ [GREEN] Preserving existing snapshot.")
                    return [], False
                print("  [GREEN] No green items anywhere.")
                raw_products = []
        else:
            print(f"  [GREEN] Green section found! Button: '{show_all_button}', inline cards: {inline_count}")

            raw_products = []

            if show_all_button:
                # ── STEP 3.1: Click "показать все" / "X товаров" to open modal ──
                print(f"  [GREEN] Step 3.1: Clicking '{show_all_button}'...")
                # Scroll to green section first
                await _js(page, r"""
                    (() => {
                        const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                        if (section) section.scrollIntoView({behavior: 'instant', block: 'center'});
                    })()
                """)
                await asyncio.sleep(1)

                clicked = await _js(page, r"""
                    (() => {
                        const isVisible = (el) => !!(el && el.offsetParent !== null);
                        const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                        if (!section) return false;

                        let container = section;
                        for (let depth = 0; depth < 4; depth++) {
                            const links = container.querySelectorAll('a, button, [class*="Link"]');
                            for (const link of links) {
                                const text = (link.innerText || '').trim();
                                if ((text.includes('Показать все') || text.includes('показать все') ||
                                     /^\d+\s*товар/i.test(text)) && isVisible(link)) {
                                    link.click();
                                    return true;
                                }
                            }
                            container = container.parentElement;
                            if (!container) break;
                        }
                        return false;
                    })()
                """)
                print(f"  [GREEN] Button clicked: {clicked}")
                await asyncio.sleep(3)

                # Check if modal opened
                modal_ready = await _js(page, """
                    (() => {
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        return modal && modal.offsetParent !== null;
                    })()
                """)
                print(f"  [GREEN] Modal opened: {modal_ready}")

                if modal_ready:
                    # ── STEP 3.1.1: Scroll modal + click "В корзину" on each card ──
                    print("  [GREEN] Step 3.1.1: Adding items from modal...")

                    # First scroll modal to load all items
                    prev_count = 0
                    no_change = 0
                    for i in range(50):
                        state = await _js(page, r"""
                            (() => {
                                const modal = document.getElementById('js-modal-cart-prods-scroll');
                                if (!modal) return [0, false];
                                modal.scrollTop = modal.scrollHeight;
                                const btn = document.querySelector('.js-prods-modal-load-more');
                                let clicked = false;
                                if (btn && btn.offsetParent !== null) { btn.click(); clicked = true; }
                                return [modal.querySelectorAll('.ProductCard').length, clicked];
                            })()
                        """) or [0, False]
                        if not isinstance(state, list) or len(state) < 2:
                            state = [0, False]
                        count = int(state[0] or 0)
                        clicked_more = bool(state[1])
                        print(f"    iter {i+1}: cards={count}, loaded_more={clicked_more}")
                        await asyncio.sleep(2.5 if clicked_more else 1.5)
                        if count == prev_count and not clicked_more:
                            no_change += 1
                            if no_change >= 3:
                                break
                        else:
                            no_change = 0
                        prev_count = count

                    total_in_modal = prev_count
                    print(f"  [GREEN] Modal loaded: {total_in_modal} cards")

                    # ── ADD ALL MODAL ITEMS TO CART ──
                    # Click "В корзину" on each card (best effort — DOM selectors may vary)
                    if total_in_modal > 0:
                        print(f"  [GREEN] Adding {total_in_modal} items to cart...")
                        added = 0
                        for idx in range(total_in_modal):
                            result = await _js(page, f"""
                                (() => {{
                                    const modal = document.getElementById('js-modal-cart-prods-scroll');
                                    if (!modal) return 'no_modal';
                                    const cards = modal.querySelectorAll('.ProductCard, .ProductCards__item');
                                    const card = cards[{idx}];
                                    if (!card) return 'card_gone';
                                    const btns = card.querySelectorAll('button');
                                    for (const btn of btns) {{
                                        if (btn.disabled) continue;
                                        const text = (btn.innerText || '').toLowerCase().trim();
                                        if (text.includes('в корзину')) {{
                                            btn.click();
                                            return 'added';
                                        }}
                                    }}
                                    return 'no_button';
                                }})()
                            """)
                            if str(result) == 'added':
                                added += 1
                            await asyncio.sleep(1.0)  # 1s delay — simulate human clicking

                            # Dismiss any popup that blocks the modal
                            await _js(page, """
                                (() => {
                                    const modals = document.querySelectorAll('[class*="Modal"]');
                                    for (const m of modals) {
                                        if (m.id === 'js-modal-cart-prods-scroll') continue;
                                        const text = m.innerText || '';
                                        if (text.includes('Уже работаем') || text.includes('похожие товары')) {
                                            const close = m.querySelector('[class*="close"], [class*="Close"]');
                                            if (close) close.click();
                                        }
                                    }
                                })()
                            """)

                        print(f"  [GREEN] Added {added}/{total_in_modal} items to cart")

                    # Close modal
                    await _js(page, """
                        (() => {
                            const closeBtn = document.querySelector('.Modal__close, .js-modal-close');
                            if (closeBtn) closeBtn.click();
                        })()
                    """)
                    await asyncio.sleep(2)

                else:
                    print("  [GREEN] Modal didn't open")

            else:
                print("  [GREEN] No 'Показать все' button — using inline items")

            # ── STEP 4: Get green products from basket API ──
            # The basket API is the RELIABLE source — it knows exactly which items
            # are green (IS_GREEN=1) with accurate prices and stock data
            print("  [GREEN] Step 4: Fetching green products from basket API...")
            raw_products = _fetch_green_from_basket() or []
            if raw_products:
                print(f"  [GREEN] Basket API: {len(raw_products)} green products")
            else:
                print("  [GREEN] ⚠️ Basket API returned 0 green products")
            # Enrich with stock data from basket_recalc
            basket_snapshot = _fetch_basket_snapshot()
            basket_stock_map = build_basket_stock_map(basket_snapshot)
            if basket_stock_map:
                print(f"  [GREEN] Got stock data for {len(basket_stock_map)} items from basket API")
                for p in raw_products:
                    pid = p.get('id', '')
                    if pid and pid in basket_stock_map:
                        stock_data = basket_stock_map[pid]
                        p['stockText'] = _stock_text_from_map(stock_data) or p.get('stockText', '')
                        p['unit'] = stock_data.get('unit', p.get('unit', 'шт'))
                        cart_price = stock_data.get('price')
                        cart_old = stock_data.get('oldPrice')
                        cur = str(p.get('currentPrice', '0'))
                        if cart_price and cur in ['0', '1', '', 'None']:
                            p['currentPrice'] = cart_price
                        old = str(p.get('oldPrice', '0'))
                        if cart_old and old in ['0', '1', '', 'None']:
                            p['oldPrice'] = cart_old

        # ── STEP 5: Check if all unavailable (green price is gone) ──
        if raw_products:
            available = [p for p in raw_products
                         if 'нет в наличии' not in p.get('stockText', '').lower()
                         and p.get('currentPrice', '0') not in ['0', '', 'None']]
            if not available:
                print("⚠️ [GREEN] ALL items unavailable — green price is gone.")
                raw_products = []

        # Suspicious result checks
        existing_count = _load_existing_green_product_count()
        if is_suspicious_empty_green_result(True, live_count, len(raw_products), existing_count):
            print("⚠️ [GREEN] Empty result suspicious — preserving existing snapshot.")
            return [], False
        if is_suspicious_single_green_result(live_count, len(raw_products), existing_count):
            print("⚠️ [GREEN] Single-item result suspicious — preserving existing snapshot.")
            return [], False

        # Process products
        products = []
        for p in raw_products:
            if not isinstance(p, dict) or 'name' not in p:
                continue
            p.pop('unavailable', None)
            p['currentPrice'] = clean_price(p.get('currentPrice', '0'))
            p['oldPrice'] = clean_price(p.get('oldPrice', '0'))
            p = synthesize_discount(p)
            p['stock'] = parse_stock(p.get('stockText', ''))
            p['unit'] = normalize_stock_unit(p.get('unit'), p['stock'])
            if 'stockText' in p:
                del p['stockText']
            p['category'] = normalize_category('Зелёные ценники', p.get('name', ''), p.get('id'))
            products.append(p)

        products = deduplicate_products(products)
        live_count = resolve_green_live_count(live_count, len(products))
        print(f"✅ [GREEN] Found {len(products)} green products")
        scrape_success = True

    except Exception as e:
        print(f"❌ [GREEN] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # ── STEP 6: Close Chrome ──
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
        if using_temp_profile and tmp_profile and os.path.isdir(tmp_profile):
            try:
                shutil.rmtree(tmp_profile, ignore_errors=True)
            except Exception:
                pass

        # Save results
        output_path = os.path.join(DATA_DIR, "green_products.json")
        if scrape_success:
            output_data = {
                "live_count": live_count,
                "scraped_count": len(products),
                "products": products
            }
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Saved {len(products)} products (live_count={live_count}) -> {output_path}")
            except Exception as e:
                print(f"❌ Error saving {output_path}: {e}")
        else:
            print(f"⚠️ Scraper failed — keeping existing {output_path}")

    return products, scrape_success


def scrape_green_prices():
    """Sync wrapper for backward compatibility."""
    if not check_vkusvill_available():
        return False
    _, scrape_success = asyncio.run(scrape_green_prices_async())
    return scrape_success


if __name__ == "__main__":
    raise SystemExit(0 if scrape_green_prices() else 1)
