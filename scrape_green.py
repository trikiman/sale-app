"""
Green prices scraper - standalone script for subagent
Scrapes "Зелёные ценники" from cart page
Uses nodriver (CDP) instead of undetected_chromedriver for Chrome 145+ compatibility.
"""
import asyncio
import json
import os
import sys
import time
import tempfile
import subprocess
import shutil
from chrome_stealth import launch_stealth_browser, find_chrome

from utils import normalize_category, parse_stock, clean_price, deduplicate_products, synthesize_discount, save_products_safe, check_vkusvill_available, normalize_stock_unit

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GREEN_URL = "https://vkusvill.ru/cart/"
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")
TECH_PROFILE_DIR = os.path.join(DATA_DIR, "tech_profile")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "logs", "screenshots", "green")


async def _step_screenshot(page, step_name: str):
    """Save a timestamped screenshot for debugging scraper steps.
    Files: logs/screenshots/green/HHMMSS_step_name.png
    """
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = time.strftime('%H%M%S')
        safe_name = step_name.replace(' ', '_').replace('/', '_')[:40]
        path = os.path.join(SCREENSHOT_DIR, f"{ts}_{safe_name}.png")
        await page.save_screenshot(path)
        print(f"  [GREEN] 📸 {step_name}")
    except Exception as e:
        print(f"  [GREEN] 📸 screenshot failed ({step_name}): {e}")


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


# _find_free_port and _find_chrome moved to chrome_stealth.py
def _find_chrome():
    return find_chrome()


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
    """Launch stealth Chrome via shared chrome_stealth module."""
    browser, proc, tmp_profile, _is_temp = await launch_stealth_browser(
        tag="GREEN", offscreen=True
    )
    return browser, proc, tmp_profile


async def _load_cookies(page):
    """Load VkusVill session cookies from cookies.json into browser via CDP."""
    if not os.path.exists(COOKIES_PATH):
        print(f"  [GREEN] No cookies.json found at {COOKIES_PATH}")
        print("  [GREEN] Run tech-login from admin panel to save session.")
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

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://vkusvill.ru',
        'Referer': 'https://vkusvill.ru/cart/',
    }
    cookies = {c['name']: c['value'] for c in raw}

    # Use httpx with SOCKS5 proxy — requests+PySocks is unreliable (timeouts)
    # Reduced timeout and retries to avoid long hangs that trigger IP bans
    import httpx
    for attempt in range(1):
        try:
            _proxy = os.environ.get("SOCKS_PROXY", "")
            client_kwargs = dict(timeout=15)
            if _proxy:
                client_kwargs['proxy'] = _proxy
            with httpx.Client(**client_kwargs) as client:
                r = client.post(
                    'https://vkusvill.ru/ajax/delivery_order/basket_recalc.php',
                    data={'COUPON': '', 'BONUS': ''},
                    headers=headers,
                    cookies=cookies,
                )
            data = r.json()
            basket = data.get('basket', {})
            return basket if isinstance(basket, dict) else {}
        except Exception as e:
            print(f"  [GREEN] basket_recalc httpx attempt {attempt+1} failed: {e}")

    print("  [GREEN] basket_recalc: httpx fallback failed")
    return {}



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


# NOTE: _fetch_green_from_basket() defined once below (line ~820+).
# Dead duplicate was removed here (BUG 1 fix).


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
    return r"""
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
                const isGreenSection = text.includes('Зелёные ценники')
                    || text.includes('Зеленые ценники');
                // Guard: reject nodes that also contain "Добавьте в заказ"
                const hasNonGreen = text.includes('Добавьте в заказ');
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
                const oldPriceEl = card.querySelector('.js-datalayer-catalog-list-price-old, .ProductCard__price--old, .ProductCard__OldPrice');
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

    # Batch ALL clicks in a SINGLE JS call to avoid Chrome WebSocket timeout
    # (137 individual _js() calls = 411 WebSocket evaluations → HTTP 500)
    # NOTE: Must be SYNCHRONOUS — nodriver can't await async IIFEs
    result_json = await _js(page, f"""
        (() => {{
            const results = {{no_scope: 0, no_card: 0, already_in_cart: 0, added: 0, no_button: 0}};
            const scope = {scope_expr};
            if (!scope) return JSON.stringify({{results, added: 0}});
            const cards = scope.querySelectorAll('.ProductCard, .ProductCards__item');
            let addedCount = 0;
            for (let i = 0; i < {total_cards}; i++) {{
                const card = cards[i];
                if (!card) {{ results.no_card++; continue; }}
                if (card.querySelector('.ProductCard__quantityControl, [class*="quantityControl"]')) {{
                    results.already_in_cart++;
                    continue;
                }}
                card.scrollIntoView({{behavior: 'instant', block: 'center'}});
                let clicked = false;
                const btns = card.querySelectorAll('button');
                for (const btn of btns) {{
                    if (btn.disabled) continue;
                    const text = (btn.innerText || '').toLowerCase().trim();
                    if (text.includes('в корзину') || text.includes('корзин') || text.includes('добавить')) {{
                        btn.click();
                        clicked = true;
                        break;
                    }}
                }}
                if (!clicked) {{
                    const cssBtn = card.querySelector(
                        '.js-delivery__basket--add, .CartButton__content--add, .CartButton__content, ' +
                        '.ProductCard__add, .ProductCard__addToCart'
                    );
                    if (cssBtn) {{ cssBtn.click(); clicked = true; }}
                }}
                if (clicked) {{
                    results.added++;
                    addedCount++;
                }} else {{
                    results.no_button++;
                }}
                // Dismiss popups inline (sync)
                const modals = document.querySelectorAll('[class*="Modal"]');
                for (const m of modals) {{
                    if (m.id === 'js-modal-cart-prods-scroll') continue;
                    const txt = m.innerText || '';
                    if (txt.includes('Уже работаем') || txt.includes('похожие товары')) {{
                        const close = m.querySelector('[class*="close"], [class*="Close"]');
                        if (close) close.click();
                    }}
                }}
            }}
            return JSON.stringify({{results, added: addedCount}});
        }})()
    """)

    # Parse the batched result
    try:
        if isinstance(result_json, str):
            data = json.loads(result_json)
        elif isinstance(result_json, dict):
            data = result_json
        else:
            data = {'results': {'added': 0}, 'added': 0}
        results_summary = data.get('results', {})
        added_count = data.get('added', 0)
    except (json.JSONDecodeError, TypeError):
        results_summary = {'added': 0, 'error': 1}
        added_count = 0

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


async def _close_delivery_modal(page):
    """Force-close the 'Ассортимент зависит от времени доставки' delivery modal.
    This modal auto-pops after every page reload and blocks the green items modal.
    Must be called before any green section interaction."""
    result = await _js(page, r"""
        (() => {
            // Check if delivery modal is visible
            const deliverySelectors = [
                '.VV23_RWayModal',
                '[class*="RWayModal"]',
                '[class*="DeliveryModal"]',
                '[class*="delivery-modal"]'
            ];
            let deliveryModal = null;
            for (const sel of deliverySelectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) {
                    deliveryModal = el;
                    break;
                }
            }
            // Also check by content — modal containing "Ассортимент зависит"
            if (!deliveryModal) {
                const allModals = document.querySelectorAll('[class*="Modal"]');
                for (const m of allModals) {
                    if (m.offsetParent === null) continue;
                    const text = (m.innerText || '').substring(0, 200);
                    if (text.includes('Ассортимент зависит') || text.includes('Больше товаров') || text.includes('времени доставки')) {
                        deliveryModal = m;
                        break;
                    }
                }
            }
            if (!deliveryModal) return 'no_delivery_modal';

            // Try to close it
            const closeSelectors = '.Modal__close, .js-modal-close, .VV_ModalClose, [class*="Modal"] [class*="close"], [class*="Modal"] [class*="Close"]';
            // Prefer close button INSIDE the delivery modal
            let closeBtn = deliveryModal.querySelector('[class*="close"], [class*="Close"], button[class*="close"]');
            if (!closeBtn) {
                closeBtn = document.querySelector(closeSelectors);
            }
            if (closeBtn) {
                closeBtn.click();
                return 'closed_button';
            }
            // Fallback: click overlay behind modal
            const overlay = document.querySelector('.Modal__overlay, [class*="overlay"], [class*="Overlay"]');
            if (overlay) {
                overlay.click();
                return 'closed_overlay';
            }
            return 'no_close_button';
        })()
    """)
    if result and result != 'no_delivery_modal':
        print(f"  [GREEN] Delivery modal: {result}")
        await asyncio.sleep(1)
    # Always send Escape as backup
    await _js(page, "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}))")
    await asyncio.sleep(0.5)
    return result


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
                    stock = 1;  // "в наличии" without number — item available, show at least 1
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
            p['unit'] = stock_data.get('unit', p.get('unit', 'шт'))

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
    return _extract_green_from_basket_dict(basket)


def _extract_green_from_basket_dict(basket: dict) -> list:
    """Extract ALL items from a basket dict for stock enrichment.
    Green filtering happens at the modal level — basket is just for stock data."""
    if not isinstance(basket, dict):
        return []

    stock_map = build_basket_stock_map(basket)
    products = []

    for item in basket.values():
        if not isinstance(item, dict):
            continue
        # Skip non-product entries (metadata, totals, etc.)
        if not item.get('PRODUCT_ID'):
            continue

        pid = str(item.get('PRODUCT_ID', ''))
        url = item.get('URL') or item.get('DETAIL_PAGE_URL', '')
        if url and not url.startswith('http'):
            url = f"https://vkusvill.ru{url}"

        img = item.get('IMG') or item.get('PICTURE') or item.get('PREVIEW_PICTURE') or ''
        if img and not img.startswith('http'):
            img = f"https://vkusvill.ru{img}"

        stock_data = stock_map.get(pid, {})
        stock_value = stock_data.get('value', 0)
        stock_unit = stock_data.get('unit') or _normalize_unit(item.get('UNIT') or item.get('UNITS'))
        is_green = item.get('IS_GREEN') in ('1', 1, True)
        products.append({
            'id': pid,
            'name': item.get('NAME', ''),
            'url': url,
            'currentPrice': stock_data.get('price') or str(item.get('PRICE', '0')),
            'oldPrice': stock_data.get('oldPrice') or str(item.get('BASE_PRICE') or item.get('PRICE_OLD') or item.get('OLD_PRICE') or '0'),
            'image': img,
            'stock': stock_value if stock_value else 0,
            'stockText': _stock_text_from_map(stock_data),
            'unit': stock_unit,
            'category': 'Зелёные ценники',
            'type': 'green',
            'can_buy': item.get('CAN_BUY') == 'Y',
            'is_green_api': is_green,
        })

    green_count = sum(1 for p in products if p.get('is_green_api'))
    print(f"  [GREEN] basket_recalc: {len(products)} total items ({green_count} IS_GREEN=1)")
    return products


async def _fetch_basket_via_cdp(page) -> dict:
    """Fetch basket_recalc from INSIDE Chrome via sync XHR — bypasses Python requests network issues.
    Uses synchronous XMLHttpRequest because nodriver's evaluate() can't await promises."""
    print("  [GREEN] Trying basket_recalc via CDP (in-browser XHR)...")

    # Ensure page is on vkusvill.ru — XHR with relative URL fails on chrome-error:// pages
    try:
        current_url = await _js(page, 'window.location.href')
        if not current_url or 'vkusvill.ru' not in str(current_url):
            print(f"  [GREEN] Page not on vkusvill.ru (at: {str(current_url)[:60]}), navigating...")
            await page.get('https://vkusvill.ru/cart/')
            import asyncio
            await asyncio.sleep(3)
    except Exception as e:
        print(f"  [GREEN] Navigation check failed: {e}")

    result = await _js(page, r"""
        (() => {
            try {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'https://vkusvill.ru/ajax/delivery_order/basket_recalc.php', false);
                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                xhr.send('COUPON=&BONUS=');
                if (xhr.status !== 200) return {error: 'HTTP ' + xhr.status};
                const data = JSON.parse(xhr.responseText);
                // Return just the basket keys+values as JSON string
                // to avoid nodriver deep-serialization issues
                return JSON.stringify(data);
            } catch (e) {
                return JSON.stringify({error: e.message || String(e)});
            }
        })()
    """)

    if not result:
        print("  [GREEN] CDP basket fetch: empty result")
        return {}

    # nodriver returns the JSON string directly
    try:
        if isinstance(result, str):
            data = json.loads(result)
        elif isinstance(result, dict):
            data = result
        else:
            print(f"  [GREEN] CDP basket fetch: unexpected type {type(result).__name__}")
            return {}
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  [GREEN] CDP basket JSON parse error: {e}")
        return {}
    if data.get('error'):  # Only fail on non-empty error (VkusVill returns error:'' on success)
        print(f"  [GREEN] CDP basket fetch error: {repr(data['error'])}")
        return {}

    basket = data.get('basket', {})
    if isinstance(basket, dict):
        print(f"  [GREEN] CDP basket fetch: got {len(basket)} items")
        return basket
    return {}


async def _fetch_green_from_basket_async(page) -> tuple:
    """Try CDP first (Chrome is already connected), fall back to Python httpx.
    Returns (green_products, full_stock_map) — stock_map has ALL basket items by product ID."""
    # Try CDP first — Chrome is already open and connected to vkusvill.ru
    basket = await _fetch_basket_via_cdp(page)
    if basket:
        return _extract_green_from_basket_dict(basket), build_basket_stock_map(basket)

    # Fallback: Python httpx with SOCKS proxy
    print("  [GREEN] CDP fetch failed, trying Python httpx...")
    snapshot = _fetch_basket_snapshot()
    if snapshot:
        return _extract_green_from_basket_dict(snapshot), build_basket_stock_map(snapshot)

    return [], {}


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

    # BUG 20 fix: check availability in async function too
    if not check_vkusvill_available():
        print("❌ [GREEN] VkusVill not available")
        return [], False

    browser = None
    proc = None
    tmp_profile = None
    products = []
    live_count = 0
    scrape_success = False

    try:
        # ── STEP 1: Launch browser, load cookies, go to /cart/ ──
        browser, proc, tmp_profile = await _launch_browser()

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

            # Close delivery modal (try multiple selectors + Escape key fallback)
            await _js(page, """
                (() => {
                    const selectors = '.Modal__close, .js-modal-close, .VV_ModalClose, [class*="Modal"] [class*="close"], [class*="Modal"] [class*="Close"], .VV23_RWayModal button[class*="close"]';
                    const closeBtn = document.querySelector(selectors);
                    if (closeBtn) { closeBtn.click(); return 'clicked'; }
                    // Fallback: click overlay
                    const overlay = document.querySelector('.Modal__overlay, [class*="overlay"], [class*="Overlay"]');
                    if (overlay) { overlay.click(); return 'overlay'; }
                    return 'not_found';
                })()
            """)
            await asyncio.sleep(1)
            # Escape key fallback to close any remaining modal
            await _js(page, "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}))")
            await asyncio.sleep(1)

            if toggle_state != 'on':
                # Reload page so the expanded assortment loads
                page = await browser.get(GREEN_URL)
                await asyncio.sleep(8)

        # ── STEP 2.5: Seed item — if cart is empty, page force-reloads on first
        # add-to-cart, which kills the green modal. Add one cheap item first. ──
        cart_check = await _js(page, r"""
            (() => {
                const bodyText = document.body.innerText || '';
                // Signal 1: empty cart text
                if (bodyText.includes('Корзина ждёт') || bodyText.includes('Корзина пуста')) {
                    return {empty: true, reason: 'empty_text'};
                }
                // Signal 2: count actual cart items using the correct selector
                // .js-delivery-basket-item = real cart items (NOT green section, NOT recommendations)
                const cartItems = document.querySelectorAll('.js-delivery-basket-item, .Delivery__Order__BasketItem');
                if (cartItems.length > 0) {
                    return {empty: false, reason: 'cart_items_' + cartItems.length};
                }
                // Signal 3: no "Очистить корзину" button = likely no items
                const clearBtn = [...document.querySelectorAll('*')].find(el => 
                    (el.textContent || '').trim().includes('Очистить корзину') && 
                    (el.textContent || '').trim().length < 30
                );
                if (clearBtn) {
                    // Clear button exists but no items detected — page may still be loading
                    return {empty: false, reason: 'clear_btn_exists_but_0_items'};
                }
                return {empty: true, reason: 'no_items_no_clear'};
            })()
        """)
        print(f"  [GREEN] Cart check: {cart_check}")
        # nodriver returns JS objects as list of [key, {type, value}] pairs
        # Convert to Python dict
        if isinstance(cart_check, list):
            parsed = {}
            for item in cart_check:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    key = item[0]
                    val = item[1]
                    if isinstance(val, dict) and 'value' in val:
                        parsed[key] = val['value']
                    else:
                        parsed[key] = val
            cart_check = parsed
        cart_empty = isinstance(cart_check, dict) and cart_check.get('empty', False)
        print(f"  [GREEN] Cart empty: {cart_empty} (parsed: {cart_check})")
        if cart_empty:
            print("  [GREEN] Step 2.5: Cart is empty — adding seed item...")
            await _step_screenshot(page, "cart_empty_before_seed")
            seed_added = await _js(page, r"""
                (() => {
                    // Find "Добавьте в заказ" section and click first "В корзину" button
                    const sections = document.querySelectorAll('.VV23_CartPage_Section, [class*="Recommend"], [class*="recommend"]');
                    for (const section of sections) {
                        const title = section.querySelector('h2, h3, [class*="title"], [class*="Title"]');
                        if (title && (title.textContent || '').includes('Добавьте в заказ')) {
                            section.scrollIntoView({behavior: 'instant', block: 'center'});
                            const btn = section.querySelector('.js-delivery__basket--add, .CartButton__content, button[class*="cart"], button[class*="Cart"]');
                            if (btn) {
                                btn.scrollIntoView({behavior: 'instant', block: 'center'});
                                btn.click();
                                return 'added_from_recommend';
                            }
                        }
                    }
                    // Fallback: click the first "В корзину" button NOT in the green section
                    const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
                    const allBtns = document.querySelectorAll('.js-delivery__basket--add, .CartButton__content--add');
                    for (const btn of allBtns) {
                        if (greenSection && greenSection.contains(btn)) continue;
                        btn.scrollIntoView({behavior: 'instant', block: 'center'});
                        btn.click();
                        return 'added_fallback';
                    }
                    // Last resort: find any button with cart text
                    const allButtons = document.querySelectorAll('button');
                    for (const btn of allButtons) {
                        const t = (btn.innerText || '').toLowerCase();
                        if (t.includes('корзин') && !greenSection?.contains(btn)) {
                            btn.scrollIntoView({behavior: 'instant', block: 'center'});
                            btn.click();
                            return 'added_text_match';
                        }
                    }
                    return 'no_button_found';
                })()
            """)
            print(f"  [GREEN] Seed item: {seed_added}")
            if seed_added and seed_added != 'no_button_found':
                # Wait for page to reload after first cart addition
                await asyncio.sleep(5)
                await _step_screenshot(page, "after_seed_reload")
                # Navigate back to cart page (page may have reloaded)
                page = await browser.get(GREEN_URL)
                await asyncio.sleep(8)
                await _step_screenshot(page, "after_seed_navigate")
                print("  [GREEN] Seed item added — cart is now non-empty")
            else:
                print("  [GREEN] Could not add seed item — cart may still be empty")
        else:
            print("  [GREEN] Cart already has items — skipping seed")

        # ── STEP 2.9: Clear unavailable items from cart ──
        # VkusVill cart has ~300 item limit. Unavailable (faded/half-alpha)
        # items are dead weight that block adding new green items for stock check.
        print("  [GREEN] Step 2.9: Clearing unavailable items from cart...")
        clear_result = await _js(page, r"""
            (() => {
                // SAFE button: removes ONLY unavailable items (faded/alpha)
                // Selector: button.js-delivery__basket_unavailable--clear
                // Located in: .js-delivery__basket_footer--items-unavailable section
                // DANGEROUS button to AVOID: button.js-delivery__basket--clear (clears ENTIRE cart!)

                // Method 1: Direct selector for the unavailable-clear button
                const safeBtn = document.querySelector('button.js-delivery__basket_unavailable--clear');
                if (safeBtn) {
                    safeBtn.click();
                    return {method: 'unavailable_clear_btn', status: 'clicked'};
                }

                // Method 2: Find "Удалить" inside the unavailable footer ONLY
                const unavailFooter = document.querySelector('.js-delivery__basket_footer--items-unavailable');
                if (unavailFooter) {
                    const deleteEls = unavailFooter.querySelectorAll('a, button, span, div');
                    for (const el of deleteEls) {
                        const text = (el.textContent || '').trim();
                        if (text.includes('Удалить') && text.length < 30) {
                            el.click();
                            return {method: 'footer_delete_text', status: 'clicked'};
                        }
                    }
                    return {method: 'none', status: 'footer_found_no_button'};
                }

                // No unavailable section found
                return {method: 'none', status: 'no_unavailable_section'};
            })()
        """)
        # Parse nodriver response
        if isinstance(clear_result, list):
            parsed = {}
            for item in clear_result:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    key = item[0]
                    val = item[1]
                    parsed[key] = val.get('value') if isinstance(val, dict) and 'value' in val else val
            clear_result = parsed
        print(f"  [GREEN] Cart cleanup result: {clear_result}")

        if isinstance(clear_result, dict) and clear_result.get('status') == 'clicked':
            await asyncio.sleep(2)  # Wait for VkusVill to process deletion
            print(f"  [GREEN] ✅ Cleared unavailable items via {clear_result.get('method')}")
            # Reload page after clearing (per plan step 2.9)
            page = await browser.get(GREEN_URL)
            await asyncio.sleep(8)
            await _step_screenshot(page, "after_clear_unavailable")
        else:
            status = clear_result.get('status', 'unknown') if isinstance(clear_result, dict) else str(clear_result)
            print(f"  [GREEN] No unavailable items to clear ({status})")

        # ── STEP 2.95: Force-close delivery modal before green section ──
        # VkusVill reopens the delivery time modal after every page reload.
        # If not closed, it blocks clicks on the green "show all" button and
        # prevents the green items modal from opening.
        print("  [GREEN] Step 2.95: Closing any delivery modal...")
        for _attempt in range(3):
            dm_result = await _close_delivery_modal(page)
            if dm_result == 'no_delivery_modal':
                break
            print(f"  [GREEN] Delivery modal close attempt {_attempt+1}: {dm_result}")
            await asyncio.sleep(1)

        # ── STEP 3: Find "Зелёные ценники" section ──
        print("  [GREEN] Step 3: Looking for green section...")
        # Scroll green section into viewport — VkusVill lazy-loads cards via
        # Intersection Observer. Cards show as gray placeholders until visible
        # for ~3 seconds. scrollIntoView is more reliable than fixed pixel scroll.
        await _js(page, """
            (() => {
                const gs = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (gs) {
                    gs.scrollIntoView({behavior: 'instant', block: 'center'});
                } else {
                    // Fallback: scroll down to trigger any lazy sections
                    window.scrollTo(0, document.body.scrollHeight);
                }
            })()
        """)
        await asyncio.sleep(4)  # Wait 4s for lazy-loaded cards to render

        # BUG 7 fix: get actual live_count from page inspection
        _, _, live_count = await _inspect_green_section(page)
        print(f"  [GREEN] Inspected: live_count={live_count}")

        await _step_screenshot(page, "page_loaded_green_section")

        # ── STEP 4 (pre): Scrape green items from green section NOW ──
        # After add-to-cart + reload, items move out of green section
        print("  [GREEN] Step 4: Scraping green items from green section...")

        # BUG-067: Paginate the Swiper to force ALL lazy-loaded slides to render
        # The Swiper only renders ~5 visible slides; we need all of them
        paginated_total = await _js(page, r"""
            (async () => {
                const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (!section) return 0;
                const swiperEl = section.querySelector('.swiper-container, .swiper');
                if (!swiperEl || !swiperEl.swiper) return -1;
                const s = swiperEl.swiper;
                const total = s.slides ? s.slides.length : 0;
                if (total <= 0) return 0;
                // Slide through all positions to force lazy rendering
                for (let i = 0; i < total; i += 3) {
                    s.slideTo(Math.min(i, total - 1), 0);
                    await new Promise(r => setTimeout(r, 300));
                }
                // Return to start
                s.slideTo(0, 0);
                return total;
            })()
        """) or 0
        if paginated_total and paginated_total > 0:
            print(f"  [GREEN] Swiper paginated: {paginated_total} slides force-loaded")
            await asyncio.sleep(2)  # Wait for lazy slides to fully render
        elif paginated_total == -1:
            print("  [GREEN] Swiper not found — using scroll fallback")
        else:
            print("  [GREEN] Green section empty or no slides")

        # Scroll green section into view (ensures any remaining lazy content loads)
        await _js(page, """
            (() => {
                const gs = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (gs) gs.scrollIntoView({behavior: 'instant', block: 'center'});
            })()
        """)
        await asyncio.sleep(2)

        raw_products = await _js(page, r"""
            (() => {
                const products = [];
                const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (!greenSection) return products;
                const cards = greenSection.querySelectorAll('.ProductCard, .HProductCard');
                cards.forEach(card => {
                    // Name: use .ProductCard__link innerText (same as red scraper)
                    const titleEl = card.querySelector('.ProductCard__link');
                    if (!titleEl) return;
                    const name = titleEl.innerText.trim();
                    if (!name) return;

                    // Price - check all children for price-like text
                    let currentPrice = '';
                    const priceSelectors = [
                        '.HProductCard__Price', '.ProductCard__price', '.Price__value',
                        '[class*="price"]', '[class*="Price"]'
                    ];
                    for (const sel of priceSelectors) {
                        const el = card.querySelector(sel);
                        if (el) {
                            currentPrice = (el.innerText || '').trim();
                            if (currentPrice) break;
                        }
                    }

                    const oldPriceEl = card.querySelector(
                        '.js-datalayer-catalog-list-price-old, [class*="OldPrice"], [class*="oldPrice"], [class*="old-price"], [class*="old_price"], del, s'
                    );
                    const oldPrice = oldPriceEl ? (oldPriceEl.innerText || '').trim() : '';

                    const imgEl = card.querySelector('img');
                    const image = imgEl ? (imgEl.src || '') : '';

                    const linkEl = card.querySelector('a[href*="/goods/"]') || card.querySelector('a');
                    const url = linkEl ? linkEl.href : '';

                    // Extract product ID from data-id attribute or URL
                    let productId = '';
                    const dataIdEl = card.querySelector('[data-id]');
                    if (dataIdEl) {
                        productId = dataIdEl.getAttribute('data-id') || '';
                    }
                    if (!productId && url) {
                        const idMatch = url.match(/-(\d+)\.html/);
                        if (idMatch) productId = idMatch[1];
                    }

                    products.push({ id: productId, name, currentPrice, oldPrice, stockText: '', image, url });
                });
                return products;
            })()
        """) or []
        if not isinstance(raw_products, list):
            raw_products = []
        print(f"  [GREEN] Green section: found {len(raw_products)} green items")

        # ── STEP 4 (button): Check green button #js-Delivery__Order-green-show-all ──
        # 3 states: VISIBLE → modal, HIDDEN → inline, NOT IN DOM → no new items
        green_button = await _js(page, r"""
            (() => {
                const btn = document.getElementById('js-Delivery__Order-green-show-all');
                if (!btn) return 'not_in_dom';
                if (btn.classList.contains('_hidden')) {
                    // Button hidden (_hidden class) — items exist but <5
                    const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                    const inlineCards = section ? section.querySelectorAll('.ProductCard').length : 0;
                    return 'hidden:' + inlineCards;
                }
                return 'visible';
            })()
        """) or 'not_in_dom'
        green_button = str(green_button)
        print(f"  [GREEN] Button state: {green_button}")

        if green_button == 'visible':
            # ── STEP 3.1: Button visible → click → modal → scrape + add all ──
            print("  [GREEN] Step 3.1: Button visible — clicking to open modal...")
            await _step_screenshot(page, "before_modal_click")

            modal_ready = False
            for modal_attempt in range(3):
                # Ensure delivery modal is closed before clicking green button
                dm_check = await _close_delivery_modal(page)
                if dm_check != 'no_delivery_modal':
                    print(f"  [GREEN] Closed delivery modal before green button (attempt {modal_attempt+1})")
                    await asyncio.sleep(1)

                await _js(page, r"""
                    (() => {
                        const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                        if (section) section.scrollIntoView({behavior: 'instant', block: 'center'});
                    })()
                """)
                await asyncio.sleep(1)

                clicked = await _js(page, r"""
                    (() => {
                        const btn = document.getElementById('js-Delivery__Order-green-show-all');
                        if (btn && !btn.classList.contains('_hidden') && btn.offsetParent !== null) {
                            btn.click();
                            return true;
                        }
                        return false;
                    })()
                """)
                print(f"  [GREEN] Button clicked: {clicked} (attempt {modal_attempt+1})")
                await asyncio.sleep(3)

                # Check if GREEN modal opened (not delivery modal)
                modal_state = await _js(page, r"""
                    (() => {
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (!modal || modal.offsetParent === null) return 'not_open';

                        // Verify no delivery modal is blocking it
                        const deliverySelectors = ['.VV23_RWayModal', '[class*="RWayModal"]', '[class*="DeliveryModal"]'];
                        for (const sel of deliverySelectors) {
                            const dm = document.querySelector(sel);
                            if (dm && dm.offsetParent !== null) return 'blocked_by_delivery';
                        }
                        // Also check by content
                        const allModals = document.querySelectorAll('[class*="Modal"]');
                        for (const m of allModals) {
                            if (m === modal || m.contains(modal) || modal.contains(m)) continue;
                            if (m.offsetParent === null) continue;
                            const text = (m.innerText || '').substring(0, 200);
                            if (text.includes('Ассортимент зависит') || text.includes('времени доставки')) {
                                return 'blocked_by_delivery';
                            }
                        }

                        // Verify modal has actual product cards (not empty)
                        const cards = modal.querySelectorAll('.ProductCard');
                        if (cards.length === 0) return 'open_but_empty';
                        return 'ready:' + cards.length;
                    })()
                """) or 'not_open'
                modal_state = str(modal_state)
                print(f"  [GREEN] Modal state: {modal_state} (attempt {modal_attempt+1})")

                if modal_state.startswith('ready:'):
                    modal_ready = True
                    break
                elif modal_state == 'blocked_by_delivery':
                    print(f"  [GREEN] ⚠️ Delivery modal blocking green modal — closing...")
                    await _close_delivery_modal(page)
                    await asyncio.sleep(2)
                    # Close the green modal too (it may be in bad state)
                    await _close_green_modal(page)
                    await asyncio.sleep(1)
                    continue
                elif modal_state == 'open_but_empty':
                    # Modal opened but empty — wait a bit, might still be loading
                    print(f"  [GREEN] Modal open but no cards yet — waiting...")
                    await asyncio.sleep(3)
                    recheck = await _js(page, """
                        (() => {
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            return modal ? modal.querySelectorAll('.ProductCard').length : 0;
                        })()
                    """) or 0
                    if int(recheck or 0) > 0:
                        modal_ready = True
                        break
                    continue
                else:
                    # not_open — try again
                    continue

            print(f"  [GREEN] Modal final status: ready={modal_ready}")

            if modal_ready:
                await _step_screenshot(page, "modal_opened")

                # ── STEP 3.1.1: Scroll modal to load ALL items ──
                print("  [GREEN] Step 3.1.1: Loading all modal items...")
                prev_count = 0
                no_change = 0
                for i in range(50):
                    state = await _js(page, r"""
                        (() => {
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            if (!modal) return [0, false];
                            modal.scrollTop = modal.scrollHeight;
                            // Try multiple selectors for "load more" button
                            const selectors = ['.js-prods-modal-load-more', '.ProductCard__more', 
                                               '.ModalProds__more', '[class*="load-more"]', '[class*="show-more"]'];
                            let clicked = false;
                            for (const sel of selectors) {
                                const btn = document.querySelector(sel);
                                if (btn && btn.offsetParent !== null) { btn.click(); clicked = true; break; }
                            }
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
                await _step_screenshot(page, "modal_all_loaded")

                # ── STEP 3.1.2: Scrape products from modal BEFORE adding to cart ──
                # The modal shows ALL green items (not just ~12 from Swiper)
                print("  [GREEN] Step 3.1.2: Scraping products from modal...")
                modal_products = await _js(page, r"""
                    (() => {
                        const products = [];
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (!modal) return products;
                        const cards = modal.querySelectorAll('.ProductCard');
                        cards.forEach(card => {
                            // Try multiple selectors - VkusVill modal uses different card layout
                            const nameSelectors = [
                                '.ProductCard__link', '.ProductCard__title', '.ProductCard__name',
                                'a[href*="/goods/"]', 'a[href*="/product/"]',
                                '[class*="name"]', '[class*="title"]', '[class*="Name"]', '[class*="Title"]'
                            ];
                            let name = '';
                            let linkEl = null;
                            for (const sel of nameSelectors) {
                                const el = card.querySelector(sel);
                                if (el) {
                                    const t = (el.innerText || el.textContent || '').trim();
                                    if (t && t.length > 2 && !/^\d/.test(t) && !t.includes('корзин')) {
                                        name = t;
                                        if (el.tagName === 'A') linkEl = el;
                                        break;
                                    }
                                }
                            }
                            if (!name) {
                                // Last resort: find any <a> with text
                                const links = card.querySelectorAll('a');
                                for (const a of links) {
                                    const t = (a.innerText || '').trim();
                                    if (t && t.length > 2 && !/^\d/.test(t) && !t.includes('корзин')) {
                                        name = t;
                                        linkEl = a;
                                        break;
                                    }
                                }
                            }
                            if (!name) return;

                            let currentPrice = '';
                            const priceSelectors = [
                                '.HProductCard__Price', '.ProductCard__price', '.Price__value',
                                '[class*="price"]', '[class*="Price"]'
                            ];
                            for (const sel of priceSelectors) {
                                const el = card.querySelector(sel);
                                if (el) {
                                    currentPrice = (el.innerText || '').trim();
                                    if (currentPrice) break;
                                }
                            }

                            const oldPriceEl = card.querySelector(
                                '.js-datalayer-catalog-list-price-old, [class*="OldPrice"], [class*="oldPrice"], [class*="old-price"], del, s'
                            );
                            const oldPrice = oldPriceEl ? (oldPriceEl.innerText || '').trim() : '';

                            const imgEl = card.querySelector('img');
                            const image = imgEl ? (imgEl.src || '') : '';

                            if (!linkEl) linkEl = card.querySelector('a[href*="/goods/"]') || card.querySelector('a');
                            const url = linkEl ? linkEl.href : '';

                            let productId = '';
                            const dataIdEl = card.querySelector('[data-id]');
                            if (dataIdEl) productId = dataIdEl.getAttribute('data-id') || '';
                            if (!productId && url) {
                                const idMatch = url.match(/-(\d+)\.html/);
                                if (idMatch) productId = idMatch[1];
                            }

                            products.push({ id: productId, name, currentPrice, oldPrice, stockText: '', image, url });
                        });
                        return products;
                    })()
                """) or []
                if not isinstance(modal_products, list):
                    modal_products = []
                print(f"  [GREEN] Modal scraped: {len(modal_products)} products")

                # Merge modal products into raw_products (modal has items the section Swiper missed)
                existing_ids = {str(p.get('id')): True for p in raw_products if p.get('id')}
                modal_new = 0
                for mp in modal_products:
                    mp_id = str(mp.get('id', ''))
                    if mp_id and mp_id not in existing_ids:
                        raw_products.append(mp)
                        existing_ids[mp_id] = True
                        modal_new += 1
                    elif not mp_id:
                        # No ID — check by name
                        existing_names = {p.get('name', '').strip().lower() for p in raw_products}
                        if mp.get('name', '').strip().lower() not in existing_names:
                            raw_products.append(mp)
                            modal_new += 1
                if modal_new > 0:
                    print(f"  [GREEN] Modal added {modal_new} NEW products (total: {len(raw_products)})")

                # ── STEP 3.1.3: Add all to cart ──
                if total_in_modal > 0:
                    print(f"  [GREEN] Step 3.1.3: Adding {total_in_modal} items to cart...")
                    results_summary, added = await _add_green_cards_to_cart(page, 'modal', total_in_modal)
                    print(f"  [GREEN] Modal add-to-cart: {results_summary}")
                    print(f"  [GREEN] Added {added}/{total_in_modal} items to cart")
                    await _step_screenshot(page, "after_add_to_cart")

                await _close_green_modal(page)
                await asyncio.sleep(2)
            else:
                print("  [GREEN] Modal didn't open")
                await _step_screenshot(page, "modal_failed")

        elif green_button.startswith('hidden:'):
            # ── STEP 3.2: Button hidden → add inline items ──
            inline_count = int(green_button.split(':')[1] or 0)
            print(f"  [GREEN] Step 3.2: Button hidden — {inline_count} inline items")
            if inline_count > 0:
                print(f"  [GREEN] Adding {inline_count} inline green items to cart...")
                results_summary, added = await _add_green_cards_to_cart(page, 'inline', inline_count)
                print(f"  [GREEN] Inline add-to-cart: {results_summary}")
                print(f"  [GREEN] Added {added}/{inline_count} items to cart")
            else:
                print("  [GREEN] No inline cards found")

        else:
            # ── STEP 3.3: Button not in DOM ──
            # Button missing doesn't mean no items — green cards may be inline
            # on the page with "В корзину" buttons even without the "show all" button.
            if len(raw_products) > 0:
                print(f"  [GREEN] Step 3.3: Button not in DOM but {len(raw_products)} green items found — adding inline...")
                # Scroll green section into view + wait for lazy-loaded cards to render
                await _js(page, """
                    (() => {
                        const gs = document.getElementById('js-Delivery__Order-green-state-not-empty');
                        if (gs) gs.scrollIntoView({behavior: 'instant', block: 'center'});
                    })()
                """)
                await asyncio.sleep(3)  # Wait for lazy cards to load
                results_summary, added = await _add_green_cards_to_cart(page, 'inline', len(raw_products))
                print(f"  [GREEN] Inline add-to-cart: {results_summary}")
                print(f"  [GREEN] Added {added}/{len(raw_products)} items to cart")
            else:
                print("  [GREEN] Step 3.3: Button not in DOM — no green items to add")

        # ── STEP 5: Reload page ──
        print("  [GREEN] Reloading page...")
        page = await browser.get(GREEN_URL)
        await asyncio.sleep(8)
        await _step_screenshot(page, "after_reload")

        # ── STEP 6: Enrich modal products with basket_recalc stock data ──
        # raw_products already has ALL green items from the modal DOM.
        # basket_recalc provides accurate stock/price — merge it IN, don't replace.
        print("  [GREEN] Step 6: Fetching stock data from basket_recalc API...")
        basket_products = _fetch_green_from_basket() or []
        if basket_products:
            print(f"  [GREEN] Basket API: {len(basket_products)} products with stock data")
            # Build lookup by product ID
            basket_by_id = {}
            for bp in basket_products:
                pid = str(bp.get('id', ''))
                if pid:
                    basket_by_id[pid] = bp
            # Enrich existing raw_products with basket stock data
            enriched = 0
            for p in raw_products:
                pid = str(p.get('id', ''))
                if pid and pid in basket_by_id:
                    bp = basket_by_id[pid]
                    p['stock'] = bp.get('stock', p.get('stock', 0))
                    p['unit'] = bp.get('unit', p.get('unit', 'шт'))
                    p['can_buy'] = bp.get('can_buy', True)
                    if bp.get('currentPrice') and bp['currentPrice'] != '0':
                        p['currentPrice'] = bp['currentPrice']
                    if bp.get('oldPrice') and bp['oldPrice'] != '0':
                        p['oldPrice'] = bp['oldPrice']
                    if bp.get('image'):
                        p['image'] = bp['image']
                    p['stockText'] = bp.get('stockText', '')
                    enriched += 1
                else:
                    # Not in basket — keep from DOM, mark stock as unknown
                    if 'stock' not in p or p.get('stock') is None:
                        p['stock'] = 0
                    if 'can_buy' not in p:
                        p['can_buy'] = True
                    if 'unit' not in p or not p.get('unit'):
                        p['unit'] = 'шт'
                p['type'] = 'green'
            # Add any basket items not found in raw_products (edge case)
            existing_ids = {str(p.get('id', '')) for p in raw_products}
            new_from_basket = 0
            for pid, bp in basket_by_id.items():
                if pid not in existing_ids:
                    raw_products.append(bp)
                    new_from_basket += 1
            print(f"  [GREEN] Enriched {enriched}/{len(raw_products)} with basket stock, {new_from_basket} new from basket")
        else:
            print("  [GREEN] ⚠️ Basket API returned 0 — keeping modal data without stock enrichment")
            for p in raw_products:
                if 'stock' not in p or p.get('stock') is None:
                    p['stock'] = 0
                if 'can_buy' not in p:
                    p['can_buy'] = True
                p['type'] = 'green'

        # ── STEP 6.5: DOM fallback for items still missing stock ──
        # The cart page shows "В наличии X шт" for every item.
        # Use _scrape_cart_stock_map to read stock from DOM for items basket API missed.
        missing_stock = [p for p in raw_products if not p.get('stock')]
        if missing_stock:
            print(f"  [GREEN] Step 6.5: {len(missing_stock)} items still missing stock — trying cart DOM fallback...")
            try:
                # Scroll cart page to ensure all items are rendered
                await _js(page, "window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                dom_stock_map = await _scrape_cart_stock_map(page)
                dom_filled = 0
                for p in missing_stock:
                    pid = str(p.get('id', ''))
                    if pid and pid in dom_stock_map:
                        sd = dom_stock_map[pid]
                        if sd.get('value') and sd['value'] not in (99,):
                            p['stock'] = sd['value']
                            p['unit'] = sd.get('unit', p.get('unit', 'шт'))
                            if sd.get('price') and sd['price'] != '1':
                                p['currentPrice'] = sd['price']
                            if sd.get('oldPrice'):
                                p['oldPrice'] = sd['oldPrice']
                            dom_filled += 1
                            print(f"    DOM stock for {p.get('name','')[:30]}: {p['stock']} {p['unit']}")
                print(f"  [GREEN] DOM fallback filled {dom_filled}/{len(missing_stock)} items")
            except Exception as e:
                print(f"  [GREEN] DOM fallback failed: {e}")

        # ── STEP 6.9: Last resort — green items on the page ARE available ──
        # If still stock=0 after all enrichment, default to 1
        # (being on the green page is proof the item exists and can be bought)
        still_missing = [p for p in raw_products if not p.get('stock')]
        if still_missing:
            for p in still_missing:
                p['stock'] = 1
                if not p.get('unit'):
                    p['unit'] = 'шт'
            print(f"  [GREEN] Step 6.9: Defaulted {len(still_missing)} items to stock=1 (available on green page)")

        section_found = green_button != 'not_in_dom'

        # Save stock cache for fallback in future cycles
        try:
            stock_cache = {}
            for p in raw_products:
                pid = str(p.get('id', ''))
                sv = p.get('stock')
                if pid and sv is not None and sv != 99 and sv != 0:
                    stock_cache[pid] = {'stock': sv, 'unit': p.get('unit', 'шт')}
            if stock_cache:
                cache_path = os.path.join(DATA_DIR, 'green_stock_cache.json')
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(stock_cache, f, ensure_ascii=False)
                print(f"  [GREEN] Saved {len(stock_cache)} stock values to cache")
        except Exception as e:
            print(f"  [GREEN] Failed to save stock cache: {e}")

        if raw_products:
            # Only flag as unavailable if ALL items explicitly say "нет в наличии"
            unavailable = [p for p in raw_products
                           if 'нет в наличии' in p.get('stockText', '').lower()]
            if len(unavailable) == len(raw_products):
                print("⚠️ [GREEN] ALL items unavailable — green price is gone.")
                raw_products = []

        # Suspicious result checks
        existing_count = _load_existing_green_product_count()
        if is_suspicious_empty_green_result(section_found, live_count, len(raw_products), existing_count):
            print("⚠️ [GREEN] Empty result suspicious — preserving existing snapshot.")
            return [], False
        if is_suspicious_single_green_result(live_count, len(raw_products), existing_count):
            print("⚠️ [GREEN] Single-item result suspicious — preserving existing snapshot.")
            return [], False

        # Load stock cache as fallback for when basket_recalc fails
        # (green_stock_cache.json is updated only when basket_recalc succeeds with real stock)
        prev_stock_map = {}
        try:
            cache_path = os.path.join(DATA_DIR, 'green_stock_cache.json')
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    prev_stock_map = json.load(f)
                if prev_stock_map:
                    print(f"  [GREEN] Loaded {len(prev_stock_map)} cached stock values as fallback")
        except Exception:
            pass

        # Process products
        products = []
        for p in raw_products:
            if not isinstance(p, dict) or 'name' not in p:
                continue
            p.pop('unavailable', None)
            p['currentPrice'] = clean_price(p.get('currentPrice', '0'))
            p['oldPrice'] = clean_price(p.get('oldPrice', '0'))
            p = synthesize_discount(p)
            # Preserve existing numeric stock set by basket_recalc (authoritative)
            existing_stock = p.get('stock')
            if existing_stock and existing_stock not in [0, '0']:
                p['stock'] = existing_stock
            else:
                p['stock'] = parse_stock(p.get('stockText', ''))
            p['unit'] = normalize_stock_unit(p.get('unit'), p['stock'])

            # Fallback: if stock=0 (unknown/failed enrichment),
            # use previous known-good stock from cache (but NOT old 99 placeholders)
            if p['stock'] in (0, 99):
                pid = str(p.get('id', ''))
                if pid in prev_stock_map:
                    cached = prev_stock_map[pid]
                    cached_stock = cached['stock']
                    if cached_stock and cached_stock not in (0, 99):
                        old_stock = p['stock']
                        p['stock'] = cached_stock
                        p['unit'] = cached['unit']
                        print(f"  [GREEN] Cache fallback for {p.get('name','')[:25]}: {old_stock} → {p['stock']} {p['unit']}")

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
                proc.wait(timeout=5)  # BUG 11 fix: wait for process to actually die
            except subprocess.TimeoutExpired:
                proc.kill()  # Force kill if still running
            except Exception:
                pass
        if tmp_profile and os.path.isdir(tmp_profile):
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
                save_products_safe(output_data, output_path)  # BUG 15: atomic write
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
