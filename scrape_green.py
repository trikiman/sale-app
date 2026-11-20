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
from nodriver import cdp

from green_empty import classify_empty_state
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


def _is_dead_ws_error(exc: BaseException) -> bool:
    """Detect Chromium CDP WebSocket failure modes.

    nodriver propagates two patterns when the underlying CDP target was
    closed/replaced under us (page reload, tab swap, browser process
    eviction): ``server rejected WebSocket connection: HTTP 500`` from
    websockets, and assorted ``ConnectionClosed*`` errors from the same
    library. Both mean: the page handle we hold is stale, retrying with
    a fresh tab handle is the right move.
    """
    msg = str(exc)
    if "WebSocket" in msg and "HTTP 500" in msg:
        return True
    name = type(exc).__name__
    return name in {
        "ConnectionClosed",
        "ConnectionClosedError",
        "ConnectionClosedOK",
        "InvalidStatusCode",
        "InvalidStatus",
        # v1.30 (2026-11-18): a hung evaluate is the same class of failure as a
        # closed socket — the tab stopped answering. Retrying on a fresh handle is
        # what recovered every previous case, and it keeps _safe_js's 3-attempt
        # budget honest instead of letting the first TimeoutError kill the cycle.
        "TimeoutError",
    }


async def _refresh_page_handle(browser, fallback_url: str = GREEN_URL):
    """Return a live tab handle after a CDP WebSocket failure.

    Tries the browser's recorded tabs (newest first) before falling back
    to a fresh ``browser.get(fallback_url)``. We never want this helper
    to raise: callers use it as a recovery path and the caller's own
    error handling decides what to do if even this fails.
    """
    tabs = getattr(browser, "tabs", None) or []
    for candidate in reversed(list(tabs)):
        try:
            await candidate.evaluate("1")
        except Exception:  # noqa: BLE001 — recovery path
            continue
        return candidate
    return await browser.get(fallback_url)


async def _navigate_and_settle(browser, url: str, sleep_seconds: float = 8.0):
    """``browser.get(url)`` + sleep, with one CDP-WS retry.

    After a navigation triggered by an in-page action (e.g. add-to-cart
    forcing a reload), the next ``page.evaluate`` against the returned
    handle sometimes fails with HTTP 500 from the websockets library —
    Chromium replaced the target while the old WS was still held. The
    legacy code path crashed the whole scraper cycle right after seed
    insertion. We probe the new handle once and rebuild it on failure.
    """
    page = await browser.get(url)
    await asyncio.sleep(sleep_seconds)
    try:
        await page.evaluate("1")
        return page
    except Exception as exc:  # noqa: BLE001 — diagnostic path
        if not _is_dead_ws_error(exc):
            return page
        print(f"  [GREEN] CDP WS dead after navigate ({exc}); re-acquiring tab")
        return await _refresh_page_handle(browser, fallback_url=url)


async def _safe_js(page, browser, script: str):
    """``_js(page, script)`` that survives one CDP-WS hiccup by retrying
    on a freshly-acquired tab handle.

    Returns ``(result, page)`` so callers can keep using the (possibly
    refreshed) page handle for subsequent operations without each step
    needing its own retry.
    """
    last_exc = None
    for attempt in range(3):
        try:
            return await _js(page, script), page
        except Exception as exc:  # noqa: BLE001 — diagnostic path
            if not _is_dead_ws_error(exc):
                raise
            last_exc = exc
            print(f"  [GREEN] CDP WS dead during eval "
                  f"(attempt {attempt + 1}/3: {exc}); re-acquiring tab")
            # First retry: cheapest recovery, reuse any live tab. Later
            # retries: full re-navigation — after a cart clear the whole
            # target tree can be replaced, and a stale tab list keeps
            # handing back dead handles.
            page = (await _refresh_page_handle(browser) if attempt == 0
                    else await _reacquire_page(browser))
            await asyncio.sleep(2)
    raise last_exc


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


def _touch_existing_green_file() -> bool:
    """v1.26 Phase 84.6: bump green_products.json mtime to "now" without
    rewriting its content.

    Used by the suspicious-empty / suspicious-single-result safety guards.
    These guards INTENTIONALLY preserve the existing snapshot when a fresh
    scrape comes back with 0 or 1 items but the previous snapshot had more
    — the assumption is a transient page/cart issue, not a real change.

    Side-effect on file content: NONE. The bytes on disk are unchanged.
    Side-effect on mtime: updated to current wall-clock time.

    Why we want the mtime bump: ``_build_source_freshness`` (in
    ``backend/main.py``) reads ``os.path.getmtime`` to compute
    ``ageMinutes`` and the user-facing "Обновлено: N мин" banner. Without
    this touch, the user sees a stale banner even though the system just
    actively verified the data is still current. With this touch, the
    banner correctly reflects "checked at this time, no change needed".

    Returns True on success, False if the file is missing or unwriteable
    (caller can fall back to logging — the scrape exit code is unchanged
    so cycle-state reporting still surfaces the suspicious-result case).
    """
    path = os.path.join(DATA_DIR, "green_products.json")
    if not os.path.exists(path):
        return False
    try:
        now = time.time()
        os.utime(path, (now, now))
        return True
    except OSError:
        return False


def is_suspicious_empty_green_result(section_found: bool, live_count: int, product_count: int, existing_product_count: int = 0, empty_explicit: bool = False) -> bool:
    """Detect empty results that are more likely scraper failure than true zero green items.

    v1.27: when ``empty_explicit`` is True (VkusVill itself shows the
    "Зелёных ценников сейчас нет" banner), trust that signal and treat
    the empty result as authoritative — caller should wipe the stale
    snapshot instead of preserving it. Without this override, the guard
    would always preserve when ``existing_product_count > 0`` and the
    user would see stale items long after VkusVill removed them.
    """
    if empty_explicit:
        return False
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
        raw = json.load(f)
    # v1.27 hotfix 2026-05-26: accept both legacy list format and per-phone
    # dict format. Same fix as scrape_red.py / scrape_yellow.py.
    if isinstance(raw, dict) and isinstance(raw.get('cookies'), list):
        cookies = raw['cookies']
    elif isinstance(raw, list):
        cookies = raw
    else:
        print(f"  [GREEN] cookies.json has unexpected shape: {type(raw).__name__}")
        return False

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
    # Reduced timeout and retries to avoid long hangs that trigger IP bans.
    # Egress order: env SOCKS_PROXY (xray pool) then URnetwork RU residential;
    # the dynamic pool is usually empty, which made this time out every cycle.
    import httpx

    try:
        from vless.urnetwork import proxy_candidates as _urn_candidates

        _proxies = _urn_candidates()
    except Exception:
        _env_proxy = os.environ.get("SOCKS_PROXY", "").strip()
        _proxies = [_env_proxy] if _env_proxy else []
    if not _proxies:
        _proxies = [""]  # direct

    for _proxy in _proxies:
        try:
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
            basket = data.get('basket')
            if isinstance(basket, dict) and basket:
                if 'bringyour' in _proxy:
                    print("  [GREEN] basket_recalc OK via URnetwork RU residential")
                return basket
            # VkusVill answered but no usable basket — surface why
            _err = data.get('error') if isinstance(data, dict) else None
            _ok = data.get('success') if isinstance(data, dict) else None
            _n = len(basket) if isinstance(basket, dict) else 'null'
            print(f"  [GREEN] basket_recalc via {('urn' if 'bringyour' in _proxy else 'env')}: "
                  f"HTTP {getattr(r,'status_code','?')} success={_ok} error={_err!r} "
                  f"basket={_n} — session may lack delivery address")
        except Exception as e:
            if 'bringyour' in _proxy:
                try:
                    from urllib.parse import urlparse as _up
                    _hp = _up(_proxy).hostname or '?'
                    _hp += f":{_up(_proxy).port or '?'}"
                except Exception:
                    _hp = '?'
                _tag = f"urnetwork-ru({_hp})"
            else:
                _tag = _proxy or "direct"
            print(f"  [GREEN] basket_recalc via {_tag} failed: {e}")

    print("  [GREEN] basket_recalc: all egress attempts failed")
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


# v1.30 (2026-11-17): every navigation gets a hard deadline. Measured that night:
# the run printed "Loaded 48/48 cookies via CDP" at 03:55:42 and then said nothing
# for SEVEN minutes until the 420 s watchdog killed it — `page.get()` was awaiting a
# tunnel that never answered (pool at 0-1 nodes, URnetwork route). An unbounded CDP
# navigation turns one bad exit into a lost cycle.
PAGE_GET_TIMEOUT_S = 90


async def _page_get(page, url: str, *, timeout: float = PAGE_GET_TIMEOUT_S):
    """``page.get`` with a deadline, so a dead tunnel cannot hang the cycle."""
    import asyncio

    try:
        return await asyncio.wait_for(page.get(url), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"  [GREEN] page.get({url}) timed out after {timeout:.0f}s — tunnel stalled")
        raise


# v1.30 (2026-11-18): every JS evaluation gets a deadline too. The 420 s watchdog
# fires on silence, but a single hung `page.evaluate` produces silence for 15-17
# minutes (observed: two runs killed at 1027 s and 864 s, both after "Loaded 48/48
# cookies"), which in turn opened a 69.4-min gap in the uptime series. A stalled CDP
# round-trip now costs 45 s and surfaces as a recoverable error instead.
JS_EVAL_TIMEOUT_S = 45


async def _js(page, script):
    """Run JS via page.evaluate and deserialize the result."""
    import asyncio

    raw = await asyncio.wait_for(page.evaluate(script), timeout=JS_EVAL_TIMEOUT_S)
    # nodriver may return deep-serialized objects for complex results
    if isinstance(raw, dict) and 'type' in raw:
        return _deserialize(raw)
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and 'type' in raw[0]:
        return [_deserialize(item) for item in raw]
    return raw


async def _inspect_green_section(page) -> tuple[bool, bool, int, bool]:
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

            // v1.27: detect VkusVill's explicit "no green tags right now" banner
            // ("Зелёных ценников сейчас нет" / "Товаров со скидкой 40% не осталось").
            // When VkusVill itself shows this, it's authoritative — we should wipe
            // the existing snapshot instead of preserving stale items via the
            // suspicious-empty safety guard. Without this signal we can't tell
            // "transient scraper glitch" (preserve) from "VkusVill genuinely has
            // 0 green items right now" (wipe). User-facing bug: app showed 2
            // stale green items while VkusVill UI said 0.
            const emptyExplicit = (
                bodyText.includes('Зелёных ценников сейчас нет') ||
                bodyText.includes('Зеленых ценников сейчас нет') ||
                bodyText.includes('со скидкой 40% не осталось')
            );

            const greenButton = document.querySelector('[data-action="GreenLabels"]');
            const buttonVisible = isVisible(greenButton);

            let liveCount = 0;

            const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');

            // Method 1 (PRIORITY): Text-based "N товаров" from green section itself only.
            if (greenSection) {
                const candidates = greenSection.querySelectorAll('a, span, div, p, h2, h3');
                for (const el of candidates) {
                    const ownText = normalize(el.textContent || '');
                    if (ownText.length < 50 && /\d+\s*товар/i.test(ownText)) {
                        liveCount = extractCount(ownText);
                        break;
                    }
                }
            }

            // Method 2: Search line-level text inside the green section only.
            if (!liveCount && greenSection) {
                const lines = normalize(greenSection.innerText || '').split(/\n+/);
                for (const raw of lines) {
                    const text = normalize(raw);
                    if (text.length < 80 && /\d+\s*товар/i.test(text)) {
                        liveCount = extractCount(text);
                        break;
                    }
                }
            }

            // Method 3: Swiper slide count (fallback)
            if (!liveCount && greenSection) {
                const ariaSlides = greenSection.querySelectorAll('.swiper-slide[aria-label]');
                if (ariaSlides.length > 0) {
                    const lastLabel = ariaSlides[ariaSlides.length - 1].getAttribute('aria-label') || '';
                    const totalMatch = lastLabel.match(/\/\s*(\d+)/);
                    if (totalMatch) liveCount = parseInt(totalMatch[1], 10);
                    if (!liveCount) liveCount = ariaSlides.length;
                }
            }

            // Method 4: Read count from the button itself only.
            if (!liveCount && buttonVisible) {
                const text = normalize(greenButton.innerText || greenButton.textContent || '');
                if (text) {
                    liveCount = Math.max(liveCount, extractCount(text));
                }
            }

            return [bodyHasGreenText, buttonVisible, liveCount, emptyExplicit];
        })()
    """) or [False, False, 0, False]

    if not isinstance(state, list) or len(state) < 3:
        return False, False, 0, False

    body_has_green_text = bool(state[0])
    button_visible = bool(state[1])
    try:
        live_count = int(state[2] or 0)
    except (TypeError, ValueError):
        live_count = 0
    # v1.27: 4th element = explicit "no green tags right now" banner detection
    empty_explicit = bool(state[3]) if len(state) >= 4 else False
    return body_has_green_text, button_visible, live_count, empty_explicit


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
                const idMatch = url.match(/-(\\d+)\\/?$/) || url.match(/(\\d+)\\.html/);
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
                // The button is not always a <button>: the diagnostics showed five
                // "В корзину" controls inside one card while this loop still reported
                // no_button. Match the text on any clickable element and record
                // disabled ones separately — "disabled" and "absent" are different bugs.
                // A bare .click() does not reach VkusVill's handler on these nodes:
                // the control exists and is enabled (diagnostics: kinds a/div/button,
                // buttons ['В корзину', ...]) yet nothing is added — the cart stayed
                // empty for hours and the green list was wiped to 0. Dispatch the full
                // pointer/mouse/click sequence on real coordinates instead.
                const fireClick = (el) => {{
                    let r = {{left: 0, top: 0, width: 0, height: 0}};
                    try {{ r = el.getBoundingClientRect(); }} catch (e) {{}}
                    const opt = {{
                        bubbles: true, cancelable: true, composed: true, view: window,
                        clientX: r.left + (r.width || 0) / 2,
                        clientY: r.top + (r.height || 0) / 2,
                        button: 0
                    }};
                    const seq = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                    for (const t of seq) {{
                        try {{
                            const Ctor = (t.indexOf('pointer') === 0 && typeof PointerEvent === 'function')
                                ? PointerEvent : MouseEvent;
                            el.dispatchEvent(new Ctor(t, opt));
                        }} catch (e) {{
                            try {{ el.dispatchEvent(new MouseEvent(t, opt)); }} catch (e2) {{}}
                        }}
                    }}
                    try {{ el.click(); }} catch (e) {{}}
                }};
                const btns = card.querySelectorAll('button, a, [role="button"], [class*="Button"], span, div');
                for (const btn of btns) {{
                    const text = (btn.innerText || '').toLowerCase().trim();
                    if (!text || text.length > 30) continue;
                    if (text.indexOf('в корзину') < 0 && text.indexOf('корзин') < 0 && text.indexOf('добавить') < 0) continue;
                    if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') {{
                        results.disabled = (results.disabled || 0) + 1;
                        continue;
                    }}
                    // Prefer the innermost element carrying the label: walking span/div
                    // keeps us on the node VkusVill binds to.
                    fireClick(btn);
                    clicked = true;
                    results.via = (btn.tagName || '').toLowerCase();
                    break;
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

    if isinstance(results_summary, dict) and results_summary.get('no_button'):
        await _diagnose_no_button_cards(page)

    return results_summary, added_count


async def _diagnose_no_button_cards(page, limit: int = 4) -> None:
    """Log what the GREEN cards offer when the add-to-cart click fails.

    First version scanned every .ProductCard on the page and reported ordinary cart
    items ("Лук репчатый", "Сметана") — useless, because the failing cards live inside
    the green section. This version uses the same scope expression as the clicker, so
    the log describes the cards that actually failed.

    Raw JS on purpose (no f-string braces), regexes kept minimal.
    """
    try:
        scope_expr = _green_card_scope_expr('inline')
        raw = await _js(page, """
            (() => {
                const scope = """ + scope_expr + """;
                if (!scope) return JSON.stringify({in_scope: 0, cards: []});
                const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                const cards = Array.from(scope.querySelectorAll('.ProductCard'));
                const out = cards.slice(0, 4).map(c => {
                    const text = (c.innerText || '').replace(/ +/g, ' ');
                    const clicks = Array.from(c.querySelectorAll('button, a, [role="button"], [class*="Button"]'))
                        .slice(0, 6)
                        .map(b => ({
                            kind: b.tagName.toLowerCase() + (b.disabled ? ':disabled' : '') + (vis(b) ? '' : ':hidden'),
                            cls: (b.className || '').toString().slice(0, 40),
                            text: (b.innerText || b.textContent || '').replace(/ +/g, ' ').trim().slice(0, 24)
                        }));
                    return {
                        name: text.slice(0, 40),
                        controls: clicks,
                        has_add_text: /в корзину/i.test(text)
                    };
                });
                return JSON.stringify({in_scope: cards.length, cards: out});
            })()
        """)
        import json as _json
        parsed = _json.loads(raw) if isinstance(raw, str) else (raw or {})
        if not isinstance(parsed, dict):
            parsed = {}
        cards = parsed.get('cards') if isinstance(parsed.get('cards'), list) else []
        print(f"  [GREEN] Green section cards in scope: {parsed.get('in_scope')}")
        for c in cards[:limit]:
            if not isinstance(c, dict):
                continue
            print(f"  [GREEN]   card {c.get('name')!r} has_add_text={c.get('has_add_text')}")
            print(f"  [GREEN]     controls={c.get('controls')}")
    except Exception as exc:  # noqa: BLE001 — diagnostics must never break the run
        print(f"  [GREEN] No-button diagnostics failed: {type(exc).__name__}: {exc}")


async def _close_green_modal(page):
    # v1.26 Phase 84.6: safe-click handles SVG / non-HTMLElement targets that
    # don't have a direct .click() method. Falls back to a synthetic
    # MouseEvent dispatch.
    await _js(page, """
        (() => {
            const safeClick = (el) => {
                if (!el) return false;
                try {
                    if (typeof el.click === 'function') {
                        el.click();
                        return true;
                    }
                } catch (e) { /* fall through to dispatchEvent */ }
                try {
                    el.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window
                    }));
                    return true;
                } catch (e) {
                    return false;
                }
            };
            const closeBtn = document.querySelector('.Modal__close, .js-modal-close');
            if (closeBtn) safeClick(closeBtn);
            else {
                const overlay = document.querySelector('.Modal__overlay');
                if (overlay) safeClick(overlay);
            }
        })()
    """)


async def _reacquire_page(browser):
    """Get a fresh, working page handle after a DOM-triggered reload.

    Chromium replaces the CDP target when the page navigates itself (which the
    cart does after the first add). The previous handle then fails on every
    call with "Connection closed" / "no close frame received or sent", killing
    the whole scrape — this was the recurring crash site right after the seed
    item was inserted. Retries a few times before giving up.
    """
    last = None
    page = None  # v1.30 GREEN-UP-02: bound even when every attempt raises, else
    # the `return page` below crashed with UnboundLocalError and took the whole
    # cycle down right at the recovery point.
    for attempt in range(3):
        try:
            page = await _navigate_and_settle(browser, GREEN_URL, sleep_seconds=8)
            if page is not None:
                return page
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"  [GREEN] _reacquire_page attempt {attempt + 1} failed: {exc}")
            await asyncio.sleep(3)
    print(f"  [GREEN] _reacquire_page exhausted retries (last: {last})")
    return page


# ── Delivery-slot helpers (shared by the first attempt and the post-open retry) ──
# Why a retry exists: opening the picker used to be the LAST step of
# _ensure_delivery_slot — the function clicked `.js-delivery-slots-load` and returned
# without ever choosing a slot. The next call in the pipeline, _close_delivery_modal,
# then pressed Escape and closed the picker. Net effect: no slot, every "в корзину"
# button stays hidden (`hidden:4`, `no_button: 4`, `Seed item: no_button_found`), the
# cart never fills, VkusVill renders its "Зелёных ценников сейчас нет" banner, and the
# green snapshot is wiped to 0 while real markdowns exist on the site.
_SLOT_CLICKABLE = ('a, button, [role="button"], label, [onclick], '
                   '[class*="Button"], [class*="button"], [class*="btn"], '
                   '[class*="slot"], [class*="Slot"], [class*="time"], [class*="Time"]')

_SLOT_SCAN_JS = """
            (() => {
                const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                const modalSel = '[class*="Modal"], [role="dialog"], [class*="modal"]';
                const clickSel = '""" + _SLOT_CLICKABLE + """';
                const chosen = document.querySelector(
                    '[class*="Slot"][class*="active"], [class*="slot"][class*="active"], ' +
                    '[class*="Slot"][class*="selected"], [class*="slot"][class*="selected"]'
                );
                const cards = Array.from(document.querySelectorAll('.ProductCard, .HProductCard, .BasketItem')).filter(vis);
                const addBtns = cards.flatMap(c => Array.from(c.querySelectorAll('button, a, [role="button"], [class*="Button"]')).filter(vis))
                    .filter(el => /^\\\\s*в корзину\\\\s*$/i.test(txt(el)));
                const chosenTxt = chosen && vis(chosen) ? txt(chosen).slice(0, 60) : '';
                // "A slot element exists" is NOT proof that a slot is chosen:
                // [class*="Slot"][class*="active"] also matches filter/tab elements (their
                // text often carries a time), and trusting it made the scraper skip picking a
                // slot while every add-to-cart button inside the cards stayed hidden
                // (hidden:4 / no_button: 4) - the cart never filled and the green snapshot
                // was wiped to 0. The only trustworthy evidence is a visible "В корзину"
                // button INSIDE a product card ("В корзине" must not count).
                if (addBtns.length > 0) {
                    return JSON.stringify({status: 'already', chosen: chosenTxt, modals: [], add_buttons: addBtns.length});
                }
                const modals = Array.from(document.querySelectorAll(modalSel)).filter(vis);
                const info = modals.map((m, i) => {
                    const btns = Array.from(m.querySelectorAll(clickSel)).filter(vis);
                    return {i: i, text: txt(m).slice(0, 80), buttons: btns.length,
                            samples: btns.map(b => txt(b).slice(0, 45)).filter(t => t).slice(0, 8)};
                });
                const dlv = info.filter(m => /доставк|самовывоз|времени доставки|слот/i.test(m.text));
                const best = dlv.sort((a, b) => b.buttons - a.buttons)[0] || null;
                return JSON.stringify({status: info.length ? 'modal_open' : 'no_modal',
                                       modals: info, best: best, delivery_candidates: dlv.length});
            })()
"""

_SLOT_PICK_JS = """
                (() => {
                    const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                    const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    const modalSel = '[class*="Modal"], [role="dialog"], [class*="modal"]';
                    const clickSel = '""" + _SLOT_CLICKABLE + """';
                    const modals = Array.from(document.querySelectorAll(modalSel)).filter(vis)
                        .map(m => ({m: m, n: Array.from(m.querySelectorAll(clickSel)).filter(vis).length}));
                    const dlv = modals.filter(x => /доставк|самовывоз|времени доставки|слот/i.test(txt(x.m)));
                    if (!dlv.length) return 'no_delivery_modal';
                    const scope = dlv.sort((a, b) => b.n - a.n)[0].m;
                    const timeRe = /(\\d{1,2}[:.]\\d{2}\\s*[–-]\\s*\\d{1,2}[:.]\\d{2})|(сегодня|завтра|ближайш)/i;
                    for (const el of Array.from(scope.querySelectorAll(clickSel)).filter(vis)) {
                        const t = txt(el);
                        if (!t || t.length > 70) continue;
                        if (!timeRe.test(t)) continue;
                        if (/недоступ|занят|нет мест/i.test(t)) continue;
                        try { el.click(); } catch (e) { continue; }
                        return 'picked:' + t.slice(0, 50);
                    }
                    return 'no_slot_found';
                })()
"""

_SLOT_CONFIRM_JS = """
                    (() => {
                        const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                        const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                        const words = ['Сохранить', 'Применить', 'Выбрать', 'Подтвердить', 'Готово', 'Продолжить'];
                        const btns = Array.from(document.querySelectorAll('button, a, [role="button"], [class*="Button"]')).filter(vis);
                        for (const b of btns) {
                            const t = txt(b);
                            if (words.some(w => t.toLowerCase().includes(w.toLowerCase()))) {
                                try { b.click(); return 'confirmed:' + t.slice(0, 40); } catch (e) {}
                            }
                        }
                        return 'no_confirm_button';
                    })()
"""


async def _log_delivery_modal_state(page) -> None:
    """Dump what the delivery modal actually shows when the address step fails.

    `modal_not_ready` alone is not diagnosable: on the cart page the header control may
    not exist, or the modal may open on a different step than it does on the catalogue.
    Without this dump the next fix is a guess again — and guessing has already cost a day.
    """
    try:
        raw = await _js(page, """
            (() => {
                const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                const norm = (s) => (s || '').split(String.fromCharCode(10)).join(' ').split(String.fromCharCode(160)).join(' ').split(String.fromCharCode(9)).join(' ').trim();
                const modals = Array.from(document.querySelectorAll('.Modal__inner, [role="dialog"]'))
                    .filter(vis)
                    .slice(0, 4)
                    .map(m => ({
                        cls: (m.className || '').toString().slice(0, 50),
                        text: norm(m.innerText).slice(0, 160)
                    }));
                const header = Array.from(document.querySelectorAll('.HeaderATDToggler__Link, [class*="HeaderATDToggler"]'))
                    .filter(vis).length;
                const buttons = Array.from(document.querySelectorAll('button, a'))
                    .filter(vis)
                    .map(b => norm(b.innerText))
                    .filter(t => t && t.length < 30
                        && /достав|адрес|самовывоз|выбрать|сохранить|применить|время/i.test(t))
                    .slice(0, 12);
                return JSON.stringify({
                    modals: modals,
                    header_controls: header,
                    action_buttons: buttons
                });
            })()
        """)
        import json as _json
        data = _json.loads(raw) if isinstance(raw, str) else {}
        if not isinstance(data, dict):
            data = {}
        print(f"  [GREEN] Delivery modal state: header_controls={data.get('header_controls')} "
              f"modals={len(data.get('modals') or [])}")
        for m in (data.get("modals") or [])[:4]:
            if isinstance(m, dict):
                print(f"  [GREEN]   modal {m.get('cls')!r}: {m.get('text')!r}")
        print(f"  [GREEN]   action buttons: {data.get('action_buttons')}")
    except Exception as exc:  # noqa: BLE001 — diagnostics must never break the run
        print(f"  [GREEN] Delivery modal dump failed: {type(exc).__name__}: {exc}")


async def _ensure_delivery_address(page) -> str:
    """Pick a saved delivery address inside the delivery modal.

    Proven on the live site (20.11): without a delivery address the "В корзину" button
    is present, visible, enabled — and does nothing (a JS click and a trusted coordinate
    click both leave `CartButton--notAdded`). Then the cart stays empty, VkusVill shows
    its "Зелёных ценников сейчас нет" banner, and the green snapshot is wiped to 0.

    The address list inside the modal is loaded asynchronously, so a single immediate
    scan reports `no_saved_address` even when the account does have one. We therefore
    poll a few times before giving up, and log which attempt succeeded.

    Returns a short status for the log.
    """
    last = "unknown"
    for attempt in range(1, 4):
        try:
            raw = await _js(page, """
                (() => {
                    const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                    const norm = (s) => (s || '').split(String.fromCharCode(10)).join(' ').split(String.fromCharCode(160)).join(' ').split(String.fromCharCode(9)).join(' ').trim();
                    // What does the header say right now? 'Выберите способ и время доставки'
                    // means no address; showing a street means an address is set.
                    const hdr = document.querySelector('.HeaderATDToggler__Text');
                    const headerText = hdr ? norm(hdr.innerText).slice(0, 60) : '';
                    // On the cart page the header opens the SLOT picker
                    // ('Ассортимент зависит от времени доставки … Применить'), which has no
                    // address at all. The address lives behind 'Доставка и оплата'.
                    const slotPicker = /ассортимент зависит от времени доставки/i.test(norm(document.body.innerText));
                    const toAddress = Array.from(document.querySelectorAll('button, a'))
                        .filter(vis)
                        .find(e => /доставка и оплата|доставка и  оплата|доставка иоплата/i.test(norm(e.innerText)));
                    if (slotPicker && toAddress) {{
                        toAddress.click();
                        return 'opened_delivery_and_payment|header=' + headerText;
                    }}
                    const pick = Array.from(document.querySelectorAll('button, a, [role="button"]'))
                        .filter(vis)
                        .find(b => (/выбрать/i.test(norm(b.innerText)) || /^выбрать$/i.test(norm(b.innerText)))
                                   && norm(b.innerText).length < 20);
                    if (pick) { pick.click(); return 'picked_saved_address|header=' + headerText; }
                    const row = Array.from(document.querySelectorAll('[class*="Address"]'))
                        .filter(vis)
                        .find(e => /москва|обл|улица|проспект|переулок|шоссе|дом/i.test(norm(e.innerText))
                                   && norm(e.innerText).length < 120
                                   && !/город, улица, дом/i.test(norm(e.innerText)));
                    if (row) { row.click(); return 'clicked_address_row'; }
                    const add = Array.from(document.querySelectorAll('button, a'))
                        .filter(vis)
                        .find(e => /добавить новый адрес/i.test(norm(e.innerText)));
                    if (add) return 'form_only_no_saved_address';
                    return 'modal_not_ready';
                })()
            """)
            last = raw if isinstance(raw, str) else str(raw)
            if last.startswith("opened_delivery_and_payment"):
                print(f"  [GREEN] Delivery address: {last} — switching to the address screen")
                await asyncio.sleep(2.0)
                continue
            if last.startswith("picked_saved_address") or last.startswith("clicked_address_row"):
                print(f"  [GREEN] Delivery address: {last} (attempt {attempt})")
                return last
            if last == "form_only_no_saved_address":
                print(f"  [GREEN] Delivery address: {last} (attempt {attempt}) — account needs one address")
                return last
        except Exception as exc:  # noqa: BLE001 — never break the run
            last = f"error: {type(exc).__name__}"
        await asyncio.sleep(1.5)

    print(f"  [GREEN] Delivery address: {last} (3 attempts)")
    if last in ("modal_not_ready", "unknown") or last.startswith("error"):
        await _log_delivery_modal_state(page)
    return last


async def _select_slot_after_open(page) -> str:
    """Choose a slot after the picker was just opened by a click.

    Returns 'selected_after_open' only when a time-like slot was actually clicked;
    otherwise the caller keeps its previous status so the log shows what failed.
    """
    import json as _json

    def _parse(raw):
        if isinstance(raw, str):
            try:
                return _json.loads(raw)
            except Exception:
                return {}
        return raw if isinstance(raw, dict) else {}

    await asyncio.sleep(3)
    state = _parse(await _js(page, _SLOT_SCAN_JS))
    if state.get('status') == 'already':
        print(f"  [GREEN] Slot active after open: {state.get('chosen')!r}")
        return 'already'
    print(f"  [GREEN] After opening picker: modals={len(state.get('modals') or [])} "
          f"delivery_candidates={state.get('delivery_candidates')}")
    best = state.get('best') or {}
    if (best.get('buttons') or 0) <= 0:
        return 'no_delivery_modal_after_open'
    picked = await _js(page, _SLOT_PICK_JS) or ''
    print(f"  [GREEN] Delivery slot pick (after open): {picked}")
    if not (isinstance(picked, str) and picked.startswith('picked')):
        return 'no_slot_found_after_open'
    await asyncio.sleep(2)
    confirm = await _js(page, _SLOT_CONFIRM_JS) or ''
    print(f"  [GREEN] Delivery slot confirm (after open): {confirm}")
    await asyncio.sleep(3)
    return 'selected_after_open'


async def _ensure_delivery_slot(page) -> str:
    """Select a delivery slot when none is chosen.

    Why this matters: with an empty delivery slot VkusVill renders the cart
    without "в корзину" buttons (observed: ``Inline add-to-cart: no_button: 4``
    and ``Seed item: no_button_found``), so green items can never be added and
    ``basket_recalc`` keeps returning ``delivery: []  basket: []``.

    Returns a short status string for the log. Never raises.

    All evaluates return ``JSON.stringify(...)`` — nodriver deep-serializes
    plain objects into an empty dict otherwise.
    """
    import json as _json

    def _parse(raw):
        if isinstance(raw, str):
            try:
                return _json.loads(raw)
            except Exception:
                return {}
        return raw if isinstance(raw, dict) else {}

    # Broad selector set: VkusVill buttons are often <div class="...Button...">,
    # not <button>, and slots are list items with data attributes.
    # NOTE: every selector here must be valid CSS — "li[data-*]" is NOT and
    # made querySelectorAll throw SyntaxError, which killed the whole evaluate
    # and surfaced as "Delivery modal scan: unknown, 0 visible modal(s)".
    CLICKABLE = ('a, button, [role="button"], label, [onclick], '
                 '[class*="Button"], [class*="button"], [class*="btn"], '
                 '[class*="slot"], [class*="Slot"], [class*="time"], [class*="Time"]')

    try:
        _raw_scan = await _js(page, """
            (() => {
                const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                const modalSel = '[class*="Modal"], [role="dialog"], [class*="modal"]';
                const clickSel = '""" + CLICKABLE + """';

                const chosen = document.querySelector(
                    '[class*="Slot"][class*="active"], [class*="slot"][class*="active"], ' +
                    '[class*="Slot"][class*="selected"], [class*="slot"][class*="selected"]'
                );
                const cards = Array.from(document.querySelectorAll('.ProductCard, .HProductCard, .BasketItem')).filter(vis);
                const addBtns = cards.flatMap(c => Array.from(c.querySelectorAll('button, a, [role="button"], [class*="Button"]')).filter(vis))
                    .filter(el => /^\\\\s*в корзину\\\\s*$/i.test(txt(el)));
                const chosenTxt = chosen && vis(chosen) ? txt(chosen).slice(0, 60) : '';
                // "A slot element exists" is NOT proof that a slot is chosen:
                // [class*="Slot"][class*="active"] also matches filter/tab elements (their
                // text often carries a time), and trusting it made the scraper skip picking a
                // slot while every add-to-cart button inside the cards stayed hidden
                // (hidden:4 / no_button: 4) - the cart never filled and the green snapshot
                // was wiped to 0. The only trustworthy evidence is a visible "В корзину"
                // button INSIDE a product card ("В корзине" must not count).
                if (addBtns.length > 0) {
                    return JSON.stringify({status: 'already', chosen: chosenTxt, modals: [], add_buttons: addBtns.length});
                }

                const modals = Array.from(document.querySelectorAll(modalSel)).filter(vis);
                const info = modals.map((m, i) => {
                    const btns = Array.from(m.querySelectorAll(clickSel)).filter(vis);
                    return {
                        i: i,
                        text: txt(m).slice(0, 80),
                        buttons: btns.length,
                        samples: btns.map(b => txt(b).slice(0, 45)).filter(t => t).slice(0, 8)
                    };
                });
                const dlv = info.filter(m => /доставк|самовывоз|времени доставки|слот/i.test(m.text));
                const best = (dlv.length ? dlv : []).sort((a, b) => b.buttons - a.buttons)[0] || null;
                return JSON.stringify({
                    status: info.length ? 'modal_open' : 'no_modal',
                    modals: info,
                    best: best,
                    delivery_candidates: dlv.length
                });
            })()
        """)
        state = _parse(_raw_scan)
        if not isinstance(state, dict) or 'status' not in state:
            # nodriver may hand back a deep-serialized structure instead of the
            # JSON string we return from JS — surface exactly what came back.
            print(f"  [GREEN] Delivery modal scan: UNEXPECTED result "
                  f"type={type(_raw_scan).__name__} raw={str(_raw_scan)[:220]!r}")
            if isinstance(_raw_scan, dict):
                state = _raw_scan.get('value') if isinstance(_raw_scan.get('value'), dict) else state

        status = state.get('status', 'unknown')
        infos = state.get('modals') or []
        print(f"  [GREEN] Delivery modal scan: {status}, {len(infos)} visible modal(s)")
        for m in infos:
            print(f"  [GREEN]   modal[{m.get('i')}] buttons={m.get('buttons')} text={m.get('text')!r}")
            for s in (m.get('samples') or [])[:6]:
                print(f"  [GREEN]      btn: {s!r}")

        if status == 'already':
            print(f"  [GREEN] Delivery slot already set: {state.get('chosen')!r}")
            return 'already'

        best = state.get('best') or {}
        print(f"  [GREEN] Delivery-looking modals: {state.get('delivery_candidates')}")
        if status == 'modal_open' and (best.get('buttons') or 0) > 0:
            picked = await _js(page, """
                (() => {
                    const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                    const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    const modalSel = '[class*="Modal"], [role="dialog"], [class*="modal"]';
                    const clickSel = '""" + CLICKABLE + """';
                    const modals = Array.from(document.querySelectorAll(modalSel)).filter(vis)
                        .map(m => ({m: m, n: Array.from(m.querySelectorAll(clickSel)).filter(vis).length}));
                    const dlv = modals.filter(x => /доставк|самовывоз|времени доставки|слот/i.test(txt(x.m)));
                    if (!dlv.length) return 'no_delivery_modal';
                    const scope = dlv.sort((a, b) => b.n - a.n)[0].m;
                    const timeRe = /(\\d{1,2}[:.]\\d{2}\\s*[–-]\\s*\\d{1,2}[:.]\\d{2})|(сегодня|завтра|ближайш)/i;
                    const cands = Array.from(scope.querySelectorAll(clickSel)).filter(vis);
                    for (const el of cands) {
                        const t = txt(el);
                        if (!t || t.length > 70) continue;
                        if (!timeRe.test(t)) continue;
                        if (/недоступ|занят|нет мест/i.test(t)) continue;
                        try { el.click(); } catch (e) { continue; }
                        return 'picked:' + t.slice(0, 50);
                    }
                    // No time-like slot text: do NOT click arbitrary controls —
                    // a generic click landed on the "Скоро исчезнут с полок"
                    // filter and destabilised the page.
                    return 'no_slot_found';
                })()
            """) or ''
            print(f"  [GREEN] Delivery slot pick: {picked}")

            if isinstance(picked, str) and picked.startswith('picked'):
                await asyncio.sleep(2)
                confirm = await _js(page, """
                    (() => {
                        const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                        const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                        const words = ['Сохранить', 'Применить', 'Выбрать', 'Подтвердить', 'Готово', 'Продолжить'];
                        const btns = Array.from(document.querySelectorAll('button, a, [role="button"], [class*="Button"]')).filter(vis);
                        for (const b of btns) {
                            const t = txt(b);
                            if (words.some(w => t.toLowerCase().includes(w.toLowerCase()))) {
                                try { b.click(); return 'confirmed:' + t.slice(0, 40); } catch (e) {}
                            }
                        }
                        return 'no_confirm_button';
                    })()
                """) or ''
                print(f"  [GREEN] Delivery slot confirm: {confirm}")
                await asyncio.sleep(3)
                return 'selected'

        # Nothing useful open — try to open the delivery picker explicitly
        opened = await _js(page, """
            (() => {
                const vis = (el) => !!(el && el.offsetParent !== null && el.offsetWidth > 0);
                const txt = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                // WHAT ACTUALLY OPENS THE PICKER (verified in a live browser, 20.11):
                // the header control reading "Выберите способ и время доставки" opens the
                // "Мои адреса / Доставка / Самовывоз" modal. The .js-delivery-slots-load
                // link does NOT — clicking it first left 4 unrelated modals open
                // ("Выберите способ оплаты", "Подарочные карты", "Показать все") and
                // delivery_candidates=0, so the retry could never find a slot.
                for (const el of document.querySelectorAll('a, button, [role="button"], [class*="Button"]')) {
                    const t = txt(el);
                    if (!vis(el) || !t || t.length > 70) continue;
                    if (/способ и время доставки|выберите адрес|укажите адрес|выбрать адрес|изменить адрес/i.test(t)) {
                        el.click(); return 'opened_header';
                    }
                }
                const links = document.querySelectorAll('.js-delivery-slots-load, a[class*="delivery-slots"]');
                for (const l of links) if (vis(l)) { l.click(); return 'opened_link'; }
                for (const el of document.querySelectorAll('a, button, [class*="Button"]')) {
                    const t = txt(el);
                    if (vis(el) && /выбер|выбрать|изменить|время/i.test(t) && /доставк|время|слот/i.test(t)) {
                        el.click(); return 'opened_text';
                    }
                }
                return 'not_found';
            })()
        """) or ''
        print(f"  [GREEN] Delivery picker open attempt: {opened}")
        if isinstance(opened, str) and opened.startswith('opened'):
            await _ensure_delivery_address(page)
            after = await _select_slot_after_open(page)
            if after in ('selected_after_open', 'already'):
                return after
            print(f"  [GREEN] Slot after open: {after}")
        return f'open_attempt_{opened}'
    except Exception as exc:  # noqa: BLE001 — never break the scrape
        print(f"  [GREEN] _ensure_delivery_slot error: {exc}")
        return f'error:{type(exc).__name__}'


async def _close_delivery_modal(page):
    """Force-close the 'Ассортимент зависит от времени доставки' delivery modal.
    This modal auto-pops after every page reload and blocks the green items modal.
    Must be called before any green section interaction.

    v1.26 Phase 84.6: every .click() call goes through a safeClick(el) helper
    that handles SVG / non-HTMLElement targets via dispatchEvent fallback.
    Pre-fix, the [class*="close"] selector could match SVG elements where
    `.click` is not directly callable, causing a TypeError that bubbled up
    from CDP and exited scrape_green.py with code 1. Symptom: green file
    stuck stale, Phase 84.5 stall-recovery firing every 5 min indefinitely.
    """
    result = await _js(page, r"""
        (() => {
            const safeClick = (el) => {
                if (!el) return false;
                try {
                    if (typeof el.click === 'function') {
                        el.click();
                        return true;
                    }
                } catch (e) { /* fall through to dispatchEvent */ }
                try {
                    el.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window
                    }));
                    return true;
                } catch (e) {
                    return false;
                }
            };
            // Strategy 1: Find any visible modal with delivery text and close it
            const allModals = document.querySelectorAll('[class*="Modal"], [class*="modal"], .js-modal');
            for (const m of allModals) {
                const style = window.getComputedStyle(m);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                const text = (m.innerText || '').substring(0, 300);
                if (text.includes('Ассортимент зависит') || text.includes('Больше товаров') || text.includes('времени доставки')) {
                    // Found the delivery modal — try close buttons inside it
                    const closeBtns = m.querySelectorAll('[class*="close"], [class*="Close"], button[aria-label="close"], button[aria-label="Close"], .Modal__close');
                    for (const btn of closeBtns) {
                        if (safeClick(btn)) return 'closed_button';
                    }
                    // Try any SVG close icon inside
                    const svgClose = m.querySelector('svg');
                    if (svgClose && svgClose.closest('button, a, div[role="button"]')) {
                        if (safeClick(svgClose.closest('button, a, div[role="button"]'))) return 'closed_svg';
                    }
                }
            }

            // Strategy 2: Click any generic close button on visible modals
            const closeButtons = document.querySelectorAll('.Modal__close, .js-modal-close, .VV_ModalClose, [class*="Modal"] [class*="close"], [class*="Modal"] [class*="Close"]');
            for (const btn of closeButtons) {
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    if (safeClick(btn)) return 'closed_generic';
                }
            }

            // Strategy 3: Click overlay
            const overlays = document.querySelectorAll('.Modal__overlay, [class*="overlay"], [class*="Overlay"]');
            for (const ov of overlays) {
                const rect = ov.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    if (safeClick(ov)) return 'closed_overlay';
                }
            }

            return 'no_delivery_modal';
        })()
    """)
    if result and result != 'no_delivery_modal':
        print(f"  [GREEN] Delivery modal: {result}")
        await asyncio.sleep(1)
    # Always send Escape as backup (works for most modals)
    await _js(page, "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}))")
    await asyncio.sleep(0.5)
    # Double-tap Escape on the active element too
    await _js(page, "document.activeElement && document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}))")
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
                const idMatch = url.match(/-(\\d+)\\/?$/) || url.match(/(\\d+)\\.html/);
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
                const idMatch = url.match(/-(\\d+)\\/?$/) || url.match(/(\\d+)\\.html/);
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
                # NEVER invent an "old" price. This used to write
                # round(current / 0.6), i.e. assume a flat 40% markdown, and it
                # silently published wrong data: broccoli at 141 ₽ showed
                # "было 235 ₽" while VkusVill actually displayed "было 295 ₽".
                # If the card carries no struck-out price we simply have none —
                # leave it empty so the UI does not render a fake discount.
                p['oldPrice'] = ''
                print(f"  [GREEN] no old price on card, leaving empty: "
                      f"{str(p.get('name', ''))[:40]} (id={pid})")
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
            await _page_get(page, 'https://vkusvill.ru/cart/')
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
        pids = [str(v.get('PRODUCT_ID','')) for v in basket.values() if isinstance(v, dict)]
        print(f"  [GREEN] CDP basket fetch: got {len(basket)} items (PIDs: {pids})")
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


async def _fetch_stock_per_product(page, products: list) -> int:
    """Navigate to each product page and read stock from rendered DOM.
    Returns count of products enriched."""
    import nodriver
    from cart.bridge_semaphore import scraper_slot  # v1.20 PERF-07
    enriched = 0
    original_url = None
    try:
        original_url = await _js(page, 'window.location.href')
    except Exception:
        pass

    # v1.20 PERF-07: acquire the shared-bridge slot ONCE around the whole
    # detail-fetch batch so cart-add serializes vs. this loop on the shared
    # VLESS bridge. Up to 10 s wait, then graceful degradation.
    async with scraper_slot("scrape_green"):
        for p in products:
            url = p.get('url', '')
            if not url:
                continue
            try:
                await _page_get(page, url)
                await asyncio.sleep(3)  # Wait for JS rendering
                stock_text = await _js(page, r"""
                    (() => {
                        // Priority 1: data-quantity attribute (most reliable on VkusVill)
                        const qEl = document.querySelector('[data-quantity]');
                        if (qEl) {
                            const v = qEl.getAttribute('data-quantity');
                            const elText = (qEl.innerText || '').trim();
                            if (v && parseFloat(v) > 0) return elText || ('\u0412 \u043d\u0430\u043b\u0438\u0447\u0438\u0438 ' + v + ' \u0448\u0442');
                        }
                        // Priority 2: text search
                        const text = document.body.innerText || '';
                        const patterns = [
                            /(?:\u0412 \u043d\u0430\u043b\u0438\u0447\u0438\u0438|\u0432 \u043d\u0430\u043b\u0438\u0447\u0438\u0438)[\s:]*([\d.,]+)\s*(\u0448\u0442|\u043a\u0433)/i,
                            /(?:\u0417\u0430\u0432\u0442\u0440\u0430 \u0431\u0443\u0434\u0435\u0442|\u0437\u0430\u0432\u0442\u0440\u0430 \u0431\u0443\u0434\u0435\u0442)[\s:]*([\d.,]+)\s*(\u0448\u0442|\u043a\u0433)/i,
                            /(?:\u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c|\u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c)[\s:]*([\d.,]+)\s*(\u0448\u0442|\u043a\u0433)/i
                        ];
                        for (const pat of patterns) {
                            const m = text.match(pat);
                            if (m) return m[0];
                        }
                        if (/\u041c\u0430\u043b\u043e|\u043c\u0430\u043b\u043e/.test(text)) return '\u041c\u0430\u043b\u043e';
                        if (/\u0412 \u043d\u0430\u043b\u0438\u0447\u0438\u0438/i.test(text)) return '\u0412 \u043d\u0430\u043b\u0438\u0447\u0438\u0438';
                        return null;
                    })()
                """)
                if stock_text:
                    parsed = parse_stock(str(stock_text))
                    if parsed and parsed not in (99,):
                        p['stock'] = parsed
                        enriched += 1
                        print(f"    Page stock for {p.get('name','')[:30]}: {parsed} ('{stock_text[:40]}')")
                    elif not p.get('stock'):
                        p['stock'] = 1
                        print(f"    Page '{stock_text}' for {p.get('name','')[:30]} -> 1")
                else:
                    print(f"    Page: no stock data for {p.get('name','')[:30]}")
            except Exception as e:
                print(f"    Page fetch failed for {p.get('name','')[:30]}: {e}")

    # Navigate back to cart page
    if original_url:
        try:
            await _page_get(page, str(original_url))
            await asyncio.sleep(3)
        except Exception:
            pass
    return enriched


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

        page = await _navigate_and_settle(browser, GREEN_URL, sleep_seconds=10)

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

        # ── STEP 1.5: Ensure a delivery slot is selected ──
        # Without a slot VkusVill hides every "в корзину" button, so green
        # items can never reach the cart and basket_recalc returns empty.
        slot_status = await _ensure_delivery_slot(page)
        print(f"  [GREEN] Step 1.5 delivery slot: {slot_status}")
        await _close_delivery_modal(page)
        await asyncio.sleep(1)

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
                page = await _navigate_and_settle(browser, GREEN_URL, sleep_seconds=8)

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
                    // Clear button exists but no items detected — treat as empty
                    // (the button may persist in DOM even with empty cart)
                    return {empty: true, reason: 'clear_btn_exists_but_0_items'};
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
                # Phase 58-02: after the first cart addition Chromium swaps the
                # CDP target out from under the held handle — every call made
                # through the OLD handle dies with "Connection closed" /
                # "no close frame received or sent". So: no screenshot and no
                # evaluate through `page` here, re-acquire the handle first.
                await asyncio.sleep(5)
                page = await _reacquire_page(browser)
                try:
                    await _step_screenshot(page, "after_seed_navigate")
                except Exception as exc:  # noqa: BLE001 — screenshot must never kill the run
                    print(f"  [GREEN] screenshot after seed skipped: {exc}")
                print("  [GREEN] Seed item added — cart is now non-empty")
            else:
                print("  [GREEN] Could not add seed item — cart may still be empty")
        else:
            print("  [GREEN] Cart already has items — skipping seed")

        # ── STEP 2.9: Clear unavailable items from cart ──
        # VkusVill cart has ~300 item limit. Unavailable (faded/half-alpha)
        # items are dead weight that block adding new green items for stock check.
        # Phase 58-02: Step 2.9 was the historical crash site — `_js(page,...)`
        # right after a force-reload would surface the CDP-WS HTTP 500 from
        # the prior navigation and abort the whole cycle. _safe_js retries
        # once on a fresh tab handle; if that also fails we skip cleanup
        # rather than aborting (cleanup is best-effort, not critical).
        print("  [GREEN] Step 2.9: Clearing unavailable items from cart...")
        clear_result, page = await _safe_js(page, browser, r"""
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
            # Reload page after clearing (per plan step 2.9).
            page = await _navigate_and_settle(browser, GREEN_URL, sleep_seconds=8)
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
            try:
                dm_result = await _close_delivery_modal(page)
            except Exception as _dm_exc:  # noqa: BLE001
                # Phase 58-02: the cart force-reload right before this step
                # swaps the CDP target; without recovery here the whole cycle
                # died with "no close frame received or sent" *after* a
                # successful clear — green data then aged out and the API
                # stripped every green card as stale.
                if not _is_dead_ws_error(_dm_exc):
                    raise
                print(f"  [GREEN] WS dead closing delivery modal; re-acquiring tab ({_dm_exc})")
                page = await _reacquire_page(browser)
                continue
            if dm_result == 'no_delivery_modal':
                break
            print(f"  [GREEN] Delivery modal close attempt {_attempt+1}: {dm_result}")
            await asyncio.sleep(1)

        # ── STEP 3: Find "Зелёные ценники" section ──
        print("  [GREEN] Step 3: Looking for green section...")
        # Scroll green section into viewport — VkusVill lazy-loads cards via
        # Intersection Observer. Cards show as gray placeholders until visible
        # for ~3 seconds. scrollIntoView is more reliable than fixed pixel scroll.
        try:
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
        except Exception as _sc_exc:  # noqa: BLE001
            if not _is_dead_ws_error(_sc_exc):
                raise
            print(f"  [GREEN] WS dead while scrolling to green section; re-acquiring tab ({_sc_exc})")
            page = await _reacquire_page(browser)
        await asyncio.sleep(4)  # Wait 4s for lazy-loaded cards to render

        # BUG 7 fix: get actual live_count from page inspection
        # v1.27: also capture empty_explicit — VkusVill's "Зелёных ценников
        # сейчас нет" banner. When set, the suspicious-empty safety guard
        # below treats this as authoritative empty (wipe stale snapshot)
        # rather than a transient scraper glitch.
        try:
            _, _, live_count, empty_explicit = await _inspect_green_section(page)
        except Exception as _in_exc:  # noqa: BLE001
            if not _is_dead_ws_error(_in_exc):
                raise
            print(f"  [GREEN] WS dead while inspecting green section; re-acquiring tab ({_in_exc})")
            page = await _reacquire_page(browser)
            _, _, live_count, empty_explicit = await _inspect_green_section(page)
        print(f"  [GREEN] Inspected: live_count={live_count} empty_explicit={empty_explicit}")

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

                    // Stock: Priority 1 — data-max on add-to-cart button (most reliable for green items)
                    let dataMax = '';
                    const addBtn = card.querySelector('.js-delivery__basket--add, [data-max], button[class*="Cart"]');
                    if (addBtn && addBtn.getAttribute('data-max')) {
                        dataMax = addBtn.getAttribute('data-max');
                    }
                    // Also check quantity control for items already in cart
                    if (!dataMax) {
                        const qtyCtrl = card.querySelector('[data-max]');
                        if (qtyCtrl) dataMax = qtyCtrl.getAttribute('data-max') || '';
                    }

                    // Stock: Priority 2 — text patterns from card
                    let stockText = '';
                    if (dataMax && parseFloat(dataMax) > 0) {
                        // Determine unit from price text
                        const priceText = card.innerText || '';
                        const unit = /кг/.test(priceText) ? 'кг' : 'шт';
                        stockText = 'В наличии ' + dataMax + ' ' + unit;
                    } else {
                        const cardText = card.innerText || '';
                        const stockPatterns = [
                            /(?:В наличии|в наличии)[:\s]*([\d.,]+)\s*(шт|кг)/i,
                            /(?:Осталось|осталось)\s*([\d.,]+)\s*(шт|кг)/i,
                            /([\d.,]+)\s*(шт|кг)\s*(?:в наличии|осталось)/i
                        ];
                        for (const pat of stockPatterns) {
                            const m = cardText.match(pat);
                            if (m) {
                                stockText = 'В наличии ' + m[1] + ' ' + m[2];
                                break;
                            }
                        }
                        if (!stockText && /(?:В наличии|Мало|мало)/i.test(cardText)) {
                            stockText = 'В наличии';
                        }
                    }

                    products.push({ id: productId, name, currentPrice, oldPrice, stockText, dataMax, image, url });
                });
                return products;
            })()
        """) or []
        if not isinstance(raw_products, list):
            raw_products = []
        print(f"  [GREEN] Green section: found {len(raw_products)} green items")
        for rp in raw_products:
            st = rp.get('stockText', '')
            dm = rp.get('dataMax', '')
            print(f"    → id={rp.get('id','?'):>6} {rp.get('name','')[:30]:30s} dataMax='{dm}' stockText='{st}'")

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

                # ── STEP 3.1.1: Scroll modal to load ALL items (CDP Network-aware) ──
                # Instead of fragile DOM polling with arbitrary timeouts, we use CDP
                # Network interception to watch AJAX responses from "показать ещё" clicks.
                # This tells us deterministically when all items have been loaded.
                print("  [GREEN] Step 3.1.1: Loading all modal items (CDP Network-aware)...")

                # Enable CDP Network monitoring to watch for AJAX pagination responses
                ajax_responses = []  # Collected AJAX response data
                ajax_event = asyncio.Event()  # Signaled when a new AJAX response arrives

                async def _on_response(event: cdp.network.ResponseReceived):
                    """Intercept XHR/Fetch responses from modal pagination."""
                    try:
                        url = event.response.url or ''
                        res_type = str(event.type_) if hasattr(event, 'type_') else str(getattr(event, 'type', ''))
                        # Look for AJAX calls related to modal product loading
                        is_ajax = 'xhr' in res_type.lower() or 'fetch' in res_type.lower()
                        is_modal_ajax = is_ajax and (
                            'ajax' in url.lower()
                            or 'cart' in url.lower()
                            or 'prods' in url.lower()
                            or 'green' in url.lower()
                            or 'load' in url.lower()
                            or 'modal' in url.lower()
                        )
                        if is_modal_ajax:
                            try:
                                body_result = await page.send(
                                    cdp.network.get_response_body(request_id=event.request_id)
                                )
                                body_text = body_result[0] if isinstance(body_result, tuple) else str(body_result)
                                ajax_responses.append({
                                    'url': url,
                                    'body_len': len(body_text) if body_text else 0,
                                    'time': time.time(),
                                })
                                print(f"    [CDP] AJAX response: {url[:80]} ({len(body_text)} bytes)")
                            except Exception:
                                ajax_responses.append({'url': url, 'body_len': 0, 'time': time.time()})
                            ajax_event.set()
                    except Exception as e:
                        pass  # Don't crash the scraper for CDP monitoring errors

                try:
                    await page.send(cdp.network.enable())
                    page.add_handler(cdp.network.ResponseReceived, _on_response)
                    cdp_enabled = True
                    print("    [CDP] Network monitoring enabled")
                except Exception as e:
                    cdp_enabled = False
                    print(f"    [CDP] Network monitoring failed: {e} — using DOM fallback")

                prev_count = 0
                no_change = 0
                max_iters = 100  # Safety limit
                for i in range(max_iters):
                    ajax_event.clear()  # Reset before scroll/click

                    # First: scroll modal to bottom
                    await _js(page, r"""
                        (() => {
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            if (!modal) return;
                            const cards = modal.querySelectorAll('.ProductCard');
                            if (cards.length > 0) {
                                cards[cards.length - 1].scrollIntoView({behavior: 'instant', block: 'end'});
                            }
                            modal.scrollTop = modal.scrollHeight;
                            modal.dispatchEvent(new Event('scroll', {bubbles: true}));
                        })()
                    """)
                    # Wait for "показать ещё" button to appear after scroll
                    await asyncio.sleep(0.5)

                    # Then: check card count and find/click button
                    state = await _js(page, r"""
                        (() => {
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            if (!modal) return [0, false, 0, false];

                            const cards = modal.querySelectorAll('.ProductCard');

                            // Find and click "показать ещё" / "load more" button
                            let clicked = false;
                            let btnExists = false;

                            // CSS selectors for known load-more buttons
                            // Search INSIDE the modal, not globally
                            const selectors = [
                                '.js-prods-modal-load-more', '.ProductCard__more',
                                '.ModalProds__more', '[class*="load-more"]', '[class*="show-more"]',
                                '[class*="LoadMore"]', '[class*="ShowMore"]',
                                '[class*="loadMore"]', '[class*="showMore"]'
                            ];
                            for (const sel of selectors) {
                                // Search inside modal AND globally (button might be outside)
                                let btn = modal.querySelector(sel) || document.querySelector(sel);
                                if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
                                    btn.click();
                                    clicked = true;
                                    btnExists = true;
                                    break;
                                }
                            }

                            // Text-based search for load-more button — search in modal AND its parent
                            if (!clicked) {
                                const searchScope = modal.closest('.Modal, [class*="Modal"]') || modal;
                                const allBtns = searchScope.querySelectorAll('button, a, span, div');
                                for (const el of allBtns) {
                                    const t = (el.innerText || '').trim().toLowerCase();
                                    // Match various Russian "load more" texts
                                    if ((t.includes('показать ещё') || t.includes('загрузить ещё') ||
                                         t.includes('показать еще') || t.includes('загрузить еще') ||
                                         t.includes('ещё товар') || t.includes('еще товар') ||
                                         t === 'ещё' || t === 'еще' || t === 'ещё ►' || t === 'еще ►' ||
                                         t.includes('показать всё') || t.includes('показать все') ||
                                         t.includes('больше товар')) && t.length < 80) {
                                        if (el.offsetParent !== null || el.offsetWidth > 0) {
                                            el.click();
                                            clicked = true;
                                            btnExists = true;
                                            break;
                                        }
                                    }
                                }
                            }

                            // Log what's at the bottom of the modal for debugging
                            let bottomText = '';
                            const lastCards = Array.from(cards).slice(-2);
                            if (lastCards.length > 0) {
                                const lastCard = lastCards[lastCards.length - 1];
                                // Check what's right after the last card
                                let sibling = lastCard.nextElementSibling;
                                while (sibling && bottomText.length < 200) {
                                    bottomText += (sibling.innerText || '').trim().substring(0, 100) + ' | ';
                                    sibling = sibling.nextElementSibling;
                                }
                            }

                            return [cards.length, clicked, modal.scrollHeight, btnExists, bottomText.substring(0, 200)];
                        })()
                    """) or [0, False, 0, False, '']
                    if not isinstance(state, list) or len(state) < 2:
                        state = [0, False, 0, False]
                    count = int(state[0] or 0)
                    clicked_more = bool(state[1])
                    scroll_h = int(state[2] or 0) if len(state) > 2 else 0
                    btn_exists = bool(state[3]) if len(state) > 3 else False
                    bottom_text = str(state[4])[:200] if len(state) > 4 and state[4] else ''

                    if i % 5 == 0 or count != prev_count or clicked_more:
                        print(f"    iter {i+1}: cards={count}, clicked_more={clicked_more}, btn_exists={btn_exists}, scrollH={scroll_h}")
                        if bottom_text and i < 3:
                            print(f"    bottom_text: {bottom_text[:100]}")

                    if clicked_more:
                        # Button was clicked — wait for AJAX response or DOM change
                        old_count = count
                        if cdp_enabled:
                            # Wait up to 5s for AJAX response via CDP
                            try:
                                await asyncio.wait_for(ajax_event.wait(), timeout=5.0)
                                print(f"    [CDP] AJAX response received after click")
                            except asyncio.TimeoutError:
                                print(f"    [CDP] No AJAX response in 5s — checking DOM")
                        # Poll DOM until card count increases or timeout (5s max)
                        for wait_step in range(10):
                            await asyncio.sleep(0.5)
                            new_count = await _js(page, r"""
                                (() => {
                                    const m = document.getElementById('js-modal-cart-prods-scroll');
                                    return m ? m.querySelectorAll('.ProductCard').length : 0;
                                })()
                            """) or 0
                            new_count = int(new_count)
                            if new_count > old_count:
                                count = new_count
                                print(f"    DOM updated: {old_count} → {new_count} cards")
                                break
                        if count == old_count:
                            # Last chance — one more quick check
                            await asyncio.sleep(1)
                            count = int(await _js(page, r"""
                                (() => {
                                    const m = document.getElementById('js-modal-cart-prods-scroll');
                                    return m ? m.querySelectorAll('.ProductCard').length : 0;
                                })()
                            """) or 0)
                    else:
                        await asyncio.sleep(0.5)

                    # Stop condition: no "показать ещё" button AND card count stopped growing
                    if not btn_exists and not clicked_more and count == prev_count:
                        no_change += 1
                        # With CDP: if no AJAX AND no button AND count stable for 3 iters → done
                        threshold = 3
                        if no_change >= threshold:
                            print(f"    ✅ All items loaded: {count} cards (no button, count stable for {threshold} iters)")
                            break
                    else:
                        no_change = 0

                    # Extra check: if we've reached live_count and no button, we're done
                    if live_count > 0 and count >= live_count and not btn_exists:
                        print(f"    ✅ All items loaded: {count} cards (matches live_count={live_count})")
                        break

                    prev_count = count

                # Disable CDP Network monitoring
                try:
                    if cdp_enabled:
                        await page.send(cdp.network.disable())
                except Exception:
                    pass

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

                # If every card lacked a button, the usual cause is a missing
                # delivery slot (VkusVill hides "в корзину" until it is picked).
                # Select one and retry the add once.
                if added == 0 and inline_count > 0:
                    retry_slot = await _ensure_delivery_slot(page)
                    print(f"  [GREEN] Slot retry after hidden buttons: {retry_slot}")
                    await _close_delivery_modal(page)
                    await asyncio.sleep(2)
                    results_summary, added = await _add_green_cards_to_cart(page, 'inline', inline_count)
                    print(f"  [GREEN] Inline add-to-cart (retry): {results_summary}")
                    print(f"  [GREEN] Added {added}/{inline_count} items to cart (retry)")
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
        # Page reload with 150+ items in cart can OOM on t3.micro.
        # If it hangs, skip it — we already have all data from the modal.
        print("  [GREEN] Reloading page...")
        reload_ok = False
        try:
            page = await asyncio.wait_for(
                _navigate_and_settle(browser, GREEN_URL, sleep_seconds=8),
                timeout=45,
            )
            await _step_screenshot(page, "after_reload")
            reload_ok = True
        except asyncio.TimeoutError:
            print("  [GREEN] ⚠️ Page reload timed out after 45s — skipping basket_recalc (using modal data + data-max)")
        except Exception as e:
            print(f"  [GREEN] ⚠️ Page reload failed: {e} — skipping basket_recalc")

        # ── STEP 6: Enrich modal products with basket_recalc stock data ──
        # raw_products already has ALL green items from the modal DOM.
        # basket_recalc provides accurate stock/price — merge it IN, don't replace.
        # Use async version: tries CDP (in-browser XHR) first, then falls back to httpx.
        basket_products, full_stock_map = [], {}
        if reload_ok:
            print("  [GREEN] Step 6: Fetching stock data from basket_recalc API...")
            try:
                basket_products, full_stock_map = await asyncio.wait_for(
                    _fetch_green_from_basket_async(page), timeout=60
                )
            except asyncio.TimeoutError:
                print("  [GREEN] ⚠️ basket_recalc timed out after 60s — proceeding with modal data + data-max stock")
                basket_products, full_stock_map = [], {}
            except Exception as e:
                print(f"  [GREEN] ⚠️ basket_recalc error: {e} — proceeding with modal data")
                basket_products, full_stock_map = [], {}
        else:
            print("  [GREEN] Step 6: Skipped basket_recalc (page reload failed)")
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
                    # Not in green product list — try full stock map (all basket items)
                    if pid and pid in full_stock_map:
                        sm = full_stock_map[pid]
                        if sm.get('value') and sm['value'] not in (0, 99):
                            p['stock'] = sm['value']
                            p['unit'] = sm.get('unit', 'шт')
                            enriched += 1
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
            print("  [GREEN] ⚠️ No green items from basket — trying full stock map...")
            sm_enriched = 0
            for p in raw_products:
                pid = str(p.get('id', ''))
                if pid and full_stock_map and pid in full_stock_map:
                    sm = full_stock_map[pid]
                    if sm.get('value') and sm['value'] not in (0, 99):
                        p['stock'] = sm['value']
                        p['unit'] = sm.get('unit', 'шт')
                        sm_enriched += 1
                if 'stock' not in p or p.get('stock') is None:
                    p['stock'] = 0
                if 'can_buy' not in p:
                    p['can_buy'] = True
                p['type'] = 'green'
            if sm_enriched:
                print(f"  [GREEN] Full stock map enriched {sm_enriched}/{len(raw_products)} items")

        # ── STEP 6.5: Enrich missing items from card's data-max attribute ──
        missing_stock = [p for p in raw_products if not p.get('stock')]
        if missing_stock:
            dm_filled = 0
            for p in missing_stock:
                dm = p.get('dataMax', '')
                if dm:
                    try:
                        val = float(dm.replace(',', '.'))
                        if val > 0:
                            p['stock'] = val if '.' in str(dm) else int(val)
                            # Determine unit from price text
                            cp = p.get('currentPrice', '')
                            p['unit'] = 'кг' if 'кг' in cp else 'шт'
                            dm_filled += 1
                            print(f"  [GREEN] Step 6.5: data-max stock for {p.get('name','')[:30]}: {p['stock']}")
                    except (ValueError, TypeError):
                        pass
            print(f"  [GREEN] Step 6.5: data-max enriched {dm_filled}/{len(missing_stock)} items")

        # ── STEP 6.9: Last resort — parse stockText/dataMax from card, or default to 1 ──
        still_missing = [p for p in raw_products if not p.get('stock')]
        if still_missing:
            parsed_count = 0
            default_count = 0
            for p in still_missing:
                # Try dataMax first (from card's button data-max attribute)
                dm = p.get('dataMax', '')
                if dm:
                    try:
                        val = float(dm.replace(',', '.'))
                        if val > 0:
                            p['stock'] = val if '.' in str(dm) else int(val)
                            parsed_count += 1
                            print(f"  [GREEN] Parsed stock from data-max: {p.get('name','')[:30]} → {p['stock']}")
                            continue
                    except (ValueError, TypeError):
                        pass
                # Try stockText (text patterns from card)
                st = p.get('stockText', '')
                parsed = parse_stock(st) if st else 0
                if parsed and parsed not in (99,):
                    p['stock'] = parsed
                    parsed_count += 1
                    print(f"  [GREEN] Parsed stock from card text: {p.get('name','')[:30]} → {parsed}")
                else:
                    p['stock'] = 1  # being on green page = available
                    default_count += 1
                if not p.get('unit'):
                    p['unit'] = 'шт'
            print(f"  [GREEN] Step 6.9: {parsed_count} from data-max/card, {default_count} defaulted to 1")

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

        # v1.27: when VkusVill explicitly shows "Зелёных ценников сейчас нет"
        # banner, that's authoritative — wipe any stale snapshot. Without
        # this short-circuit the suspicious-empty guard below would preserve
        # the stale items because existing_count > 0, and the user would see
        # phantom green items long after VkusVill removed them.
        if empty_explicit and len(raw_products) == 0:
            print(f"⚠️ [GREEN] VkusVill explicit empty banner detected — wiping stale snapshot ({existing_count} → 0).")
            # Fall through to the save path below; raw_products is already []
            # so save_products_safe will write an empty list. Don't return early.
        elif is_suspicious_empty_green_result(section_found, live_count, len(raw_products), existing_count, empty_explicit=empty_explicit):
            print("⚠️ [GREEN] Empty result suspicious — preserving existing snapshot.")
            # v1.26 Phase 84.6: bump mtime so freshness banner reflects
            # "checked at this time, no new data" rather than a stale gap.
            if _touch_existing_green_file():
                print(f"  [GREEN] Touched existing snapshot mtime ({existing_count} items preserved)")
            return [], False
        elif is_suspicious_single_green_result(live_count, len(raw_products), existing_count):
            print("⚠️ [GREEN] Single-item result suspicious — preserving existing snapshot.")
            # v1.26 Phase 84.6: same as above — verified, no change needed.
            if _touch_existing_green_file():
                print(f"  [GREEN] Touched existing snapshot mtime ({existing_count} items preserved)")
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

        # Save results with count validation gate (SCRP-13)
        output_path = os.path.join(DATA_DIR, "green_products.json")
        if scrape_success:
            # Count validation: refuse to save if gap between live_count and scraped is >10%
            scraped_count = len(products)
            if live_count > 0 and scraped_count > 0:
                gap_pct = abs(live_count - scraped_count) / live_count * 100
                if scraped_count < live_count and gap_pct > 10:
                    existing_count = _load_existing_green_product_count()
                    print(f"⚠️ [GREEN] COUNT MISMATCH: scraped={scraped_count}, live={live_count}, gap={gap_pct:.0f}%")
                    if existing_count > scraped_count:
                        print(f"⚠️ [GREEN] Existing snapshot has {existing_count} items — preserving it")
                        scrape_success = False  # Don't overwrite with worse data
                        # v1.26 Phase 84.6: bump mtime so the freshness banner
                        # reflects "checked, no upgrade available" rather than
                        # a stale gap.
                        if _touch_existing_green_file():
                            print(f"  [GREEN] Touched existing snapshot mtime ({existing_count} items preserved)")
                    else:
                        print(f"⚠️ [GREEN] Existing snapshot has {existing_count} items — saving new (still better)")
                else:
                    if gap_pct > 0:
                        print(f"  [GREEN] Count OK: scraped={scraped_count}, live={live_count}, gap={gap_pct:.1f}% (within 10% tolerance)")

        if scrape_success:
            # 2026-08-13: record WHY the list is empty so the API/frontend can
            # tell "VkusVill has no green items right now" apart from "our tech
            # account lost its session". Previously the backend inferred
            # greenMissing purely from len(products)==0 and the UI always blamed
            # authorization, which was wrong every night when VkusVill simply
            # has nothing marked down.
            #   "ok"            — items found
            #   "source_empty"  — VkusVill itself showed the explicit
            #                     "Зелёных ценников сейчас нет" banner
            #   "unknown_empty" — empty without that banner; could be markup
            #                     drift, a failed cart seed, or auth trouble
            empty_reason, empty_is_proven = classify_empty_state(products, empty_explicit)
            if not empty_is_proven:
                # An empty section WITHOUT VkusVill's own "Зелёных ценников сейчас
                # нет" banner is not proof that nothing is marked down: it can be
                # markup drift, a failed cart seed or a half-rendered page. Claiming
                # exit 0 here is precisely the false zero v1.30 forbids — it produced
                # one on 20.11 05:12 UTC — so report a failure and keep the previous
                # snapshot instead of overwriting it with an unproven empty list.
                print(
                    "⚠️ [GREEN] Empty section and no VkusVill empty banner — cannot "
                    "prove the list is really empty; failing instead of reporting 0"
                )
                scrape_success = False
            output_data = {
                "live_count": live_count,
                "scraped_count": len(products),
                "empty_reason": empty_reason,
                # Always True here: the scraper returns early at STEP 1 when
                # is_logged_in is False, so reaching the save path means the
                # tech-account session was valid for this run.
                "logged_in": bool(is_logged_in),
                "products": products
            }
            if not scrape_success:
                print(f"⚠️ Unknown-empty run — keeping the existing {output_path}")
            else:
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
    # Cycle accounting (the 168-hour uptime proof) is done by the PARENT:
    # scheduler_service.run_script records it. A record written here would be
    # lost whenever the watchdog SIGKILLs this process, and would double-count
    # when it does not.
    raise SystemExit(0 if scrape_green_prices() else 1)
