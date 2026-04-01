"""
Green scraper shared utilities.
Used by both scrape_green_add.py (add items to cart) and scrape_green_data.py (read cart data).
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

from utils import parse_stock, clean_price, normalize_stock_unit

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GREEN_URL = "https://vkusvill.ru/cart/"
COOKIES_PATH = os.path.join(BASE_DIR, "data", "cookies.json")
TECH_PROFILE_DIR = os.path.join(DATA_DIR, "tech_profile")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "logs", "screenshots", "green")


# ── Screenshot ───────────────────────────────────────────────────────────────

async def step_screenshot(page, step_name: str, tag: str = "GREEN"):
    """Save a timestamped screenshot for debugging scraper steps."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = time.strftime('%H%M%S')
        safe_name = step_name.replace(' ', '_').replace('/', '_')[:40]
        path = os.path.join(SCREENSHOT_DIR, f"{ts}_{safe_name}.png")
        await page.save_screenshot(path)
        print(f"  [{tag}] 📸 {step_name}")
    except Exception as e:
        print(f"  [{tag}] 📸 screenshot failed ({step_name}): {e}")


# ── Unit / formatting helpers ────────────────────────────────────────────────

def normalize_unit(unit_raw):
    raw = str(unit_raw or 'шт').strip().lower()
    if not raw:
        return 'шт'
    if 'kg' in raw or 'кг' in raw:
        return 'кг'
    if 'g' in raw or 'гр' in raw or 'грамм' in raw:
        return 'г'
    if 'l' in raw or 'литр' in raw or 'л' == raw:
        return 'л'
    if 'ml' in raw or 'мл' in raw:
        return 'мл'
    if 'шт' in raw or 'pc' in raw or 'pcs' in raw:
        return 'шт'
    return 'шт'


def format_quantity(value):
    try:
        num = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return ''
    if num.is_integer():
        return str(int(num))
    return f"{num:.3f}".rstrip('0').rstrip('.')


def stock_text_from_map(stock_data: dict) -> str:
    if not stock_data:
        return ''
    quantity = format_quantity(stock_data.get('value'))
    if not quantity:
        return ''
    return f"В наличии: {quantity} {stock_data.get('unit', 'шт')}"


# ── Browser profile ─────────────────────────────────────────────────────────

def resolve_green_browser_profile_dir(preferred_dir: str = TECH_PROFILE_DIR):
    if preferred_dir and os.path.isdir(preferred_dir) and os.listdir(preferred_dir):
        return preferred_dir, False
    return tempfile.mkdtemp(prefix='uc_green_'), True


# ── Browser launch + cookies ─────────────────────────────────────────────────

async def launch_browser(tag: str = "GREEN"):
    """Launch stealth Chrome via shared chrome_stealth module."""
    browser, proc, tmp_profile, _is_temp = await launch_stealth_browser(
        tag=tag, offscreen=True
    )
    return browser, proc, tmp_profile


async def load_cookies(page, tag: str = "GREEN"):
    """Load VkusVill session cookies from cookies.json into browser via CDP."""
    if not os.path.exists(COOKIES_PATH):
        print(f"  [{tag}] No cookies.json found at {COOKIES_PATH}")
        print(f"  [{tag}] Run tech-login from admin panel to save session.")
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
        if c.get('expiry', 0) > 0:
            cp.expires = network.TimeSinceEpoch(c['expiry'])
        if 'sameSite' in c:
            cp.same_site = ss_map.get(c['sameSite'])
        cdp_cookies.append(cp)

    await page.send(network.set_cookies(cdp_cookies))
    print(f"  [{tag}] Loaded {len(cdp_cookies)}/{len(cookies)} cookies via CDP")
    return len(cdp_cookies) > 0


# ── JS helpers ───────────────────────────────────────────────────────────────

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


async def js(page, script):
    """Run JS via page.evaluate and deserialize the result."""
    raw = await page.evaluate(script)
    if isinstance(raw, dict) and 'type' in raw:
        return _deserialize(raw)
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and 'type' in raw[0]:
        return [_deserialize(item) for item in raw]
    return raw


async def navigate(page, url, wait=10):
    """Navigate the current tab to URL without hanging."""
    import nodriver.cdp.page as cdp_page
    try:
        await page.send(cdp_page.navigate(url=url))
    except Exception:
        pass
    await asyncio.sleep(wait)


# ── Nodriver response parsing ────────────────────────────────────────────────

def parse_nodriver_dict(raw):
    """Convert nodriver list-of-pairs response to a Python dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        parsed = {}
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                key = item[0]
                val = item[1]
                if isinstance(val, dict) and 'value' in val:
                    parsed[key] = val['value']
                else:
                    parsed[key] = val
        return parsed
    return {}


# ── Delivery modal ───────────────────────────────────────────────────────────

async def close_delivery_modal(page, tag: str = "GREEN"):
    """Force-close the 'Ассортимент зависит от времени доставки' delivery modal.
    Uses getComputedStyle for position:fixed modal visibility detection."""
    result = await js(page, r"""
        (() => {
            function isVisible(el) {
                if (!el) return false;
                const style = getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            }

            const deliverySelectors = [
                '.VV23_RWayModal',
                '[class*="RWayModal"]',
                '[class*="DeliveryModal"]',
                '[class*="delivery-modal"]'
            ];
            let deliveryModal = null;
            for (const sel of deliverySelectors) {
                const el = document.querySelector(sel);
                if (isVisible(el)) {
                    deliveryModal = el;
                    break;
                }
            }
            if (!deliveryModal) {
                const allModals = document.querySelectorAll('[class*="Modal"], .modal');
                for (const m of allModals) {
                    if (!isVisible(m)) continue;
                    const text = (m.innerText || '').substring(0, 300);
                    if (text.includes('Ассортимент зависит') || text.includes('Больше товаров') || text.includes('времени доставки')) {
                        deliveryModal = m;
                        break;
                    }
                }
            }
            if (!deliveryModal) return 'no_delivery_modal';

            const closeStrategies = [
                () => deliveryModal.querySelector('.VV_ModalCloser'),
                () => deliveryModal.querySelector('[data-dismiss="modal"]'),
                () => deliveryModal.querySelector('[class*="ModalCloser"]'),
                () => deliveryModal.querySelector('[class*="close"], [class*="Close"]'),
                () => deliveryModal.querySelector('button[aria-label="Close"]'),
                () => document.querySelector('.VV23_RWayModal .VV_ModalCloser'),
                () => document.querySelector('.Modal__close, .js-modal-close'),
            ];
            for (const strategy of closeStrategies) {
                try {
                    const btn = strategy();
                    if (btn && isVisible(btn)) {
                        btn.click();
                        return 'closed_button:' + (btn.className || btn.tagName);
                    }
                } catch(e) {}
            }

            const overlaySelectors = ['.modal-backdrop', '.Modal__overlay', '[class*="overlay"]', '[class*="Overlay"]'];
            for (const sel of overlaySelectors) {
                const overlay = document.querySelector(sel);
                if (overlay && isVisible(overlay)) {
                    overlay.click();
                    return 'closed_overlay';
                }
            }

            try {
                if (window.jQuery) {
                    window.jQuery('.VV23_RWayModal').modal('hide');
                    return 'closed_jquery';
                }
            } catch(e) {}

            return 'no_close_button';
        })()
    """)
    if result and result != 'no_delivery_modal':
        print(f"  [{tag}] Delivery modal: {result}")
        await asyncio.sleep(1.5)

        still_open = await js(page, r"""
            (() => {
                function isVisible(el) {
                    if (!el) return false;
                    const s = getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                }
                const dm = document.querySelector('.VV23_RWayModal, [class*="RWayModal"]');
                return dm && isVisible(dm) ? 'still_open' : 'closed';
            })()
        """)
        if still_open == 'still_open':
            print(f"  [{tag}] ⚠️ Delivery modal still open — trying Escape + backdrop click")
            await js(page, "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}))")
            await asyncio.sleep(0.5)
            await js(page, r"""
                (() => {
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) backdrop.click();
                    const dm = document.querySelector('.VV23_RWayModal');
                    if (dm) {
                        dm.classList.remove('show');
                        dm.style.display = 'none';
                    }
                    const body = document.body;
                    body.classList.remove('modal-open');
                    body.style.overflow = '';
                    body.style.paddingRight = '';
                    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                })()
            """)
            await asyncio.sleep(1)
            print(f"  [{tag}] Delivery modal force-removed from DOM")
    else:
        await js(page, "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}))")
        await asyncio.sleep(0.3)
    return result


async def close_green_modal(page):
    """Close the green items modal."""
    await js(page, """
        (() => {
            const closeBtn = document.querySelector('.Modal__close, .js-modal-close');
            if (closeBtn) closeBtn.click();
            else {
                const overlay = document.querySelector('.Modal__overlay');
                if (overlay) overlay.click();
            }
        })()
    """)


# ── Login check ──────────────────────────────────────────────────────────────

async def check_login(page, tag: str = "GREEN") -> bool:
    """Check if the browser session is logged into VkusVill. Returns True if logged in."""
    title = await js(page, 'document.title')
    print(f"  [{tag}] Page title: {title}")
    page_text = str(await js(page, 'document.body.innerText') or '')
    if "403" in str(title) or "Forbidden" in page_text or "запрещен" in page_text.lower():
        print(f"❌ [{tag}] Blocked (403)!")
        return False

    login_signals = await js(page, r"""
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
    print(f"  [{tag}] Login signals: {named}")

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
        print(f"❌ [{tag}] Not logged in! Aborting.")
    else:
        print(f"  [{tag}] Logged in OK")
    return is_logged_in


# ── Browser cleanup ──────────────────────────────────────────────────────────

def cleanup_browser(browser, proc, tmp_profile):
    """Safely close browser, kill process, remove temp profile."""
    if browser:
        try:
            browser.stop()
        except Exception:
            pass
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass
    if tmp_profile and os.path.isdir(tmp_profile):
        try:
            shutil.rmtree(tmp_profile, ignore_errors=True)
        except Exception:
            pass


# ── Basket API functions ─────────────────────────────────────────────────────

def fetch_basket_snapshot() -> dict:
    """Fetch basket_recalc via Python httpx (SOCKS proxy)."""
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
    """Build a stock map from basket_recalc response."""
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
            'unit': normalize_unit(item.get('UNIT') or item.get('UNITS')),
            'price': str(item.get('PRICE', '') or ''),
            'oldPrice': str(item.get('BASE_PRICE') or item.get('PRICE_OLD') or item.get('OLD_PRICE') or ''),
            'can_buy': item.get('CAN_BUY') == 'Y',
        }
    return stock_map


async def fetch_basket_via_cdp(page, tag: str = "GREEN") -> dict:
    """Fetch basket_recalc from INSIDE Chrome via sync XHR."""
    print(f"  [{tag}] Trying basket_recalc via CDP (in-browser XHR)...")

    try:
        current_url = await js(page, 'window.location.href')
        if not current_url or 'vkusvill.ru' not in str(current_url):
            print(f"  [{tag}] Page not on vkusvill.ru (at: {str(current_url)[:60]}), navigating...")
            await page.get('https://vkusvill.ru/cart/')
            await asyncio.sleep(3)
    except Exception as e:
        print(f"  [{tag}] Navigation check failed: {e}")

    result = await js(page, r"""
        (() => {
            try {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'https://vkusvill.ru/ajax/delivery_order/basket_recalc.php', false);
                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                xhr.send('COUPON=&BONUS=');
                if (xhr.status !== 200) return {error: 'HTTP ' + xhr.status};
                const data = JSON.parse(xhr.responseText);
                return JSON.stringify(data);
            } catch (e) {
                return JSON.stringify({error: e.message || String(e)});
            }
        })()
    """)

    if not result:
        print(f"  [{tag}] CDP basket fetch: empty result")
        return {}

    try:
        if isinstance(result, str):
            data = json.loads(result)
        elif isinstance(result, dict):
            data = result
        else:
            print(f"  [{tag}] CDP basket fetch: unexpected type {type(result).__name__}")
            return {}
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  [{tag}] CDP basket JSON parse error: {e}")
        return {}
    if data.get('error'):
        print(f"  [{tag}] CDP basket fetch error: {repr(data['error'])}")
        return {}

    basket = data.get('basket', {})
    if isinstance(basket, dict):
        pids = [str(v.get('PRODUCT_ID','')) for v in basket.values() if isinstance(v, dict)]
        print(f"  [{tag}] CDP basket fetch: got {len(basket)} items (PIDs: {pids})")
        return basket
    return {}


def extract_green_from_basket_dict(basket: dict, tag: str = "GREEN") -> list:
    """Extract ALL items from a basket dict for stock enrichment."""
    if not isinstance(basket, dict):
        return []

    stock_map = build_basket_stock_map(basket)
    products = []

    for item in basket.values():
        if not isinstance(item, dict):
            continue
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
        stock_unit = stock_data.get('unit') or normalize_unit(item.get('UNIT') or item.get('UNITS'))
        is_green = item.get('IS_GREEN') in ('1', 1, True)
        products.append({
            'id': pid,
            'name': item.get('NAME', ''),
            'url': url,
            'currentPrice': stock_data.get('price') or str(item.get('PRICE', '0')),
            'oldPrice': stock_data.get('oldPrice') or str(item.get('BASE_PRICE') or item.get('PRICE_OLD') or item.get('OLD_PRICE') or '0'),
            'image': img,
            'stock': stock_value if stock_value else 0,
            'stockText': stock_text_from_map(stock_data),
            'unit': stock_unit,
            'category': 'Зелёные ценники',
            'type': 'green',
            'can_buy': item.get('CAN_BUY') == 'Y',
            'is_green_api': is_green,
        })

    green_count = sum(1 for p in products if p.get('is_green_api'))
    print(f"  [{tag}] basket_recalc: {len(products)} total items ({green_count} IS_GREEN=1)")
    return products


async def fetch_green_from_basket_async(page, tag: str = "GREEN") -> tuple:
    """Try CDP first, fall back to Python httpx.
    Returns (green_products, full_stock_map)."""
    basket = await fetch_basket_via_cdp(page, tag)
    if basket:
        return extract_green_from_basket_dict(basket, tag), build_basket_stock_map(basket)

    print(f"  [{tag}] CDP fetch failed, trying Python httpx...")
    snapshot = fetch_basket_snapshot()
    if snapshot:
        return extract_green_from_basket_dict(snapshot, tag), build_basket_stock_map(snapshot)

    return [], {}


# ── Green section inspection ─────────────────────────────────────────────────

async def inspect_green_section(page) -> tuple:
    """Inspect the green section on the cart page.
    Returns (body_has_green_text, button_visible, live_count)."""
    state = await js(page, r"""
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

            const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
            if (greenSection) {
                let searchEl = greenSection;
                for (let d = 0; d < 4 && searchEl; d++) {
                    const links = searchEl.querySelectorAll('a, span, div, button');
                    for (const link of links) {
                        const t = normalize(link.innerText || '');
                        if (t.length < 40) {
                            const m = t.match(/(\d+)\s*товар/i);
                            if (m) {
                                const val = parseInt(m[1], 10);
                                if (val > liveCount) liveCount = val;
                            }
                        }
                    }
                    if (liveCount > 0) break;
                    searchEl = searchEl.parentElement;
                }
            }

            if (!liveCount && greenSection) {
                const ariaSlides = greenSection.querySelectorAll('.swiper-slide[aria-label]');
                if (ariaSlides.length > 0) {
                    const lastLabel = ariaSlides[ariaSlides.length - 1].getAttribute('aria-label') || '';
                    const totalMatch = lastLabel.match(/\/\s*(\d+)/);
                    if (totalMatch) liveCount = parseInt(totalMatch[1], 10);
                    if (!liveCount) liveCount = ariaSlides.length;
                }
            }

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
