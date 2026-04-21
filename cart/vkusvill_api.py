"""
VkusVill Cart API — добавление товаров в корзину через HTTP API.
Без Chrome/Selenium — чистый httpx с ProxyManager rotation.

Usage:
    from cart.vkusvill_api import VkusVillCart
    
    cart = VkusVillCart(cookies_path="data/browser_cookies_live.json")
    result = cart.add(product_id=731, price_type=1)

IMPORTANT: Cookie files must include sessid and user_id fields
alongside cookie data. The login flow must export these.
"""
import httpx
import os
import json
import time

import re
import logging

logger = logging.getLogger(__name__)

BASKET_ADD_URL = "https://vkusvill.ru/ajax/delivery_order/basket_add.php"
BASKET_UPDATE_URL = "https://vkusvill.ru/ajax/delivery_order/basket_update.php"
BASKET_RECALC_URL = "https://vkusvill.ru/ajax/delivery_order/basket_recalc.php"
BASKET_CLEAR_URL = "https://vkusvill.ru/ajax/delivery_order/basket_clear.php"
VKUSVILL_BASE = "https://vkusvill.ru"
CART_REQUEST_TIMEOUT = httpx.Timeout(connect=2.0, read=3.0, write=3.0, pool=2.0)
CART_ADD_HOT_PATH_DEADLINE_SECONDS = 3.5
CART_ADD_REQUEST_TIMEOUT = httpx.Timeout(CART_ADD_HOT_PATH_DEADLINE_SECONDS)
SESSID_STALE_SECONDS = 1800  # 30 minutes — refresh sessid if older than this
SESSID_REFRESH_TIMEOUT = httpx.Timeout(connect=10.0, read=10.0, write=3.0, pool=3.0)


def _coerce_numeric(value, default=0):
    try:
        num = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return default
    if num.is_integer():
        return int(num)
    return num


class VkusVillCart:
    """Client for VkusVill cart operations via their internal AJAX API.
    
    Uses raw Cookie header instead of requests cookie jar because
    __Host-PHPSESSID cookies are not handled correctly by requests.
    """
    
    def __init__(self, cookies_path: str, user_id: int = 0, sessid: str = "", proxy_manager=None):
        """
        Args:
            cookies_path: Path to cookies JSON file (exported from browser).
            user_id: VkusVill internal Bitrix user ID (from lk-user-id).
                     If 0, will try to load from cookie file metadata.
            sessid: CSRF token. If empty, will try to load from cookie file
                    metadata or extract from warmup page.
            proxy_manager: ProxyManager instance for proxy rotation.
                          If None, connects directly (no proxy).
        """
        self.cookies_path = cookies_path
        self.user_id = user_id
        self.sessid = sessid
        self._proxy_manager = proxy_manager
        self._cookie_str = ""
        self._initialized = False
        self._sessid_ts = None
        self._session_stale = False

    def _ensure_session(self):
        """Load cookies and build raw Cookie header string."""
        if self._initialized:
            return
        
        # Load cookies from file
        if not os.path.exists(self.cookies_path):
            raise FileNotFoundError(f"Cookies file not found: {self.cookies_path}")
        
        with open(self.cookies_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Support both formats:
        # 1. List of cookies: [{name, value, domain}, ...]  
        # 2. Object with metadata: {cookies: [...], sessid: "...", user_id: 123}
        if isinstance(data, dict):
            cookies_list = data.get('cookies', [])
            if not self.sessid:
                self.sessid = data.get('sessid') or ''
            if not self.user_id:
                metadata_user_id = data.get('user_id')
                if metadata_user_id not in (None, ''):
                    try:
                        self.user_id = int(metadata_user_id)
                    except (TypeError, ValueError):
                        self.user_id = metadata_user_id
            self._sessid_ts = data.get('sessid_ts')  # Unix timestamp when sessid was extracted
        else:
            cookies_list = data
            self._sessid_ts = None
        
        # Build raw Cookie header string
        # This bypasses requests cookie jar which mangles __Host-PHPSESSID
        self._cookie_str = '; '.join(
            f"{c['name']}={c['value']}" for c in cookies_list
        )
        
        logger.info(f"Loaded {len(cookies_list)} cookies from {self.cookies_path}")
        
        # Stale sessid detection: do not refresh here.
        # Inline stale refresh was consuming the full cart hot-path budget in live use.
        if self.sessid and self.user_id and self._sessid_ts:
            age_seconds = time.time() - self._sessid_ts
            if age_seconds > SESSID_STALE_SECONDS:
                self._session_stale = True
                logger.info(
                    f"sessid is stale ({age_seconds:.0f}s old > {SESSID_STALE_SECONDS}s), "
                    "using existing session first"
                )

        # Do NOT call _extract_session_params() here — warmup GET is too slow for cart-add hot path.
        # If sessid/user_id not in cookie metadata, cart.add() will return auth_expired.
        if not self.sessid or not self.user_id:
            logger.warning("sessid/user_id not found in cookie metadata — skipping warmup GET (hot path)")

        if not self.sessid or not self.user_id:
            logger.warning(f"Session params missing after init: sessid={'present' if self.sessid else 'MISSING'}, user_id={'present' if self.user_id else 'MISSING'}")

        self._initialized = True
        logger.info(f"Session ready (user_id={self.user_id}, sessid={self.sessid[:8] if self.sessid else 'NONE'}...)")
    
    def _transport_candidates(self):
        """Return transport order for cart requests.

        Prefer direct when recent connectivity says VkusVill is reachable, but keep
        a proxy fallback available when direct goes unhealthy.
        """
        direct_ok = False

        if self._proxy_manager:
            if hasattr(self._proxy_manager, "check_direct_cached"):
                try:
                    direct_ok = bool(self._proxy_manager.check_direct_cached())
                except Exception:
                    direct_ok = False

        if direct_ok:
            return [None]

        if self._proxy_manager:
            addr = self._proxy_manager.get_working_proxy(allow_refresh=False)
            if addr:
                return [f"socks5://{addr}", None]

        return [None]

    def _get_proxy_url(self):
        """Compatibility helper for older call sites/tests."""
        for candidate in self._transport_candidates():
            if candidate:
                return candidate
        return None

    def _perform_http_request(self, method: str, url: str, *, headers: dict, data=None, timeout=None, follow_redirects: bool = False):
        """Run a request with direct/proxy fallback and direct-health cache updates."""
        client_kwargs = dict(timeout=timeout or CART_REQUEST_TIMEOUT)
        last_exc = None
        candidates = self._transport_candidates()

        for idx, proxy_url in enumerate(candidates):
            attempt_kwargs = dict(client_kwargs)
            attempt_label = "direct"
            if proxy_url:
                attempt_kwargs["proxy"] = proxy_url
                attempt_label = proxy_url

            try:
                with httpx.Client(**attempt_kwargs) as client:
                    if method == "GET":
                        response = client.get(url, headers=headers, follow_redirects=follow_redirects)
                    else:
                        response = client.post(url, data=data, headers=headers, follow_redirects=follow_redirects)
                if self._proxy_manager and proxy_url is None and hasattr(self._proxy_manager, "note_direct_result"):
                    self._proxy_manager.note_direct_result(True)
                if idx > 0:
                    logger.info(f"{method} {url} fallback via {attempt_label} succeeded")
                return response
            except httpx.HTTPError as exc:
                last_exc = exc
                if self._proxy_manager and proxy_url is None and hasattr(self._proxy_manager, "note_direct_result"):
                    self._proxy_manager.note_direct_result(False)
                if proxy_url and self._proxy_manager and hasattr(self._proxy_manager, "remove_proxy"):
                    try:
                        self._proxy_manager.remove_proxy(proxy_url.removeprefix("socks5://"))
                    except Exception:
                        pass
                if idx < len(candidates) - 1:
                    logger.warning(f"{method} {url} via {attempt_label} failed: {exc} — retrying fallback")
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError(f"{method} {url} failed without attempts")

    def _extract_session_params(self):
        """GET the main page to extract sessid and user_id.
        
        NOTE: This only works if __Host-PHPSESSID is properly sent,
        which requires raw Cookie header. The response will contain
        sessid and user_id matching the session from the cookies.
        """
        try:
            # Use longer timeout for warmup — proxy SOCKS5 handshake needs more than 2s
            warmup_timeout = httpx.Timeout(connect=5.0, read=5.0, write=3.0, pool=3.0)
            r = self._perform_http_request(
                "GET",
                VKUSVILL_BASE,
                timeout=warmup_timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
                    'Cookie': self._cookie_str,
                },
            )

            if r.status_code != 200:
                logger.warning(f"Warmup GET returned status {r.status_code}")
                return

            # Extract sessid
            if not self.sessid:
                match = re.search(r"name=['\"]sessid['\"].*?value=['\"]([^'\"]+)['\"]", r.text)
                if match:
                    self.sessid = match.group(1)
                    logger.info(f"Extracted sessid from page: {self.sessid[:8]}...")

            # Extract user_id
            if not self.user_id:
                uid_match = re.search(r'id=["\']lk-user-id["\'].*?value=["\'](\d+)["\']', r.text)
                if not uid_match:
                    uid_match = re.search(r'"USER_ID"\s*:\s*"(\d+)"', r.text)
                if uid_match:
                    self.user_id = int(uid_match.group(1))
                    logger.info(f"Extracted user_id from page: {self.user_id}")
                    
        except httpx.HTTPError as e:
            logger.warning(f"Failed to extract session params: {e}")

    def _refresh_stale_session(self):
        """Refresh a stale sessid via warmup GET and persist updated metadata."""
        old_sessid = self.sessid
        try:
            # Use longer timeout for refresh — this is pre-cart-add, not in hot path
            r = self._perform_http_request(
                "GET",
                VKUSVILL_BASE,
                timeout=SESSID_REFRESH_TIMEOUT,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
                    'Cookie': self._cookie_str,
                },
            )

            if r.status_code != 200:
                logger.warning(f"Stale refresh GET returned status {r.status_code}")
                return

            match = re.search(r"name=['\"]sessid['\"].*?value=['\"]([^'\"]+)['\"]", r.text)
            if match:
                self.sessid = match.group(1)

            uid_match = re.search(r'id=["\']lk-user-id["\'].*?value=["\'](\d+)["\']', r.text)
            if not uid_match:
                uid_match = re.search(r'"USER_ID"\s*:\s*"(\d+)"', r.text)
            if uid_match:
                self.user_id = int(uid_match.group(1))

            # Persist updated metadata back to cookies.json
            self._sessid_ts = time.time()
            self._session_stale = False
            self._persist_session_metadata()

            if self.sessid != old_sessid:
                logger.info(f"Stale refresh: sessid changed {old_sessid[:8]}... -> {self.sessid[:8]}...")
            else:
                logger.info(f"Stale refresh: sessid confirmed (unchanged), ts updated")

        except httpx.HTTPError as e:
            logger.warning(f"Stale refresh failed: {e} — using existing sessid as best-effort")

    def _persist_session_metadata(self):
        """Write updated sessid, user_id, sessid_ts back to cookies.json without touching cookie list."""
        try:
            with open(self.cookies_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                data['sessid'] = self.sessid
                data['user_id'] = self.user_id
                data['sessid_ts'] = self._sessid_ts
                with open(self.cookies_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"Persisted refreshed session metadata to {self.cookies_path}")
            else:
                logger.warning("Cannot persist session metadata — cookies.json is list format, not dict")
        except Exception as e:
            logger.warning(f"Failed to persist session metadata: {e}")

    def _request(self, url: str, data: dict, referer: str = '/', timeout=None) -> dict:
        """Make a POST request using raw Cookie header via ProxyManager rotation."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': VKUSVILL_BASE,
            'Referer': f'{VKUSVILL_BASE}{referer}',
            'Cookie': self._cookie_str,
        }

        r = self._perform_http_request("POST", url, data=data, headers=headers, timeout=timeout or CART_REQUEST_TIMEOUT)
        try:
            return r.json()
        except json.JSONDecodeError:
            logger.error(f"Non-JSON response from {url}: {r.text[:200]}")
            raise

    def _find_cart_item(self, cart_payload: dict, product_id: int) -> dict | None:
        basket = cart_payload.get('raw', {}).get('basket', {})
        for item in basket.values():
            if isinstance(item, dict) and str(item.get('PRODUCT_ID', '')) == str(product_id):
                return item
        return None
    
    def is_logged_in(self) -> bool:
        """Check if the current session is logged in to VkusVill."""
        self._ensure_session()
        try:
            r = self._perform_http_request(
                "GET",
                f"{VKUSVILL_BASE}/personal/",
                timeout=CART_REQUEST_TIMEOUT,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Cookie': self._cookie_str,
                },
                follow_redirects=False,
            )
            return r.status_code == 200
        except httpx.HTTPError:
            return False
    
    def add(
        self,
        product_id: int,
        price_type: int = 1,
        is_green: int = 0,
        quantity: int = 1,
    ) -> dict:
        """
        Add a product to the VkusVill cart.
        
        Args:
            product_id: VkusVill product ID (e.g. 731).
            price_type: Price type (1=regular, 222=red/sale/green price).
            is_green: 1 if green price item, 0 otherwise.
            quantity: How many times to call add (API adds 1 per call).
        
        Returns:
            dict with keys: success (bool), product_name, cart_total, error
        """
        t_start = time.monotonic()
        self._ensure_session()
        t_session = time.monotonic()
        logger.info(f"🛒 [CART-ADD] product={product_id} | _ensure_session took {(t_session - t_start)*1000:.0f}ms")

        if not self.sessid:
            return {'success': False, 'error': 'No sessid available after session init', 'error_type': 'auth_expired'}
        if not self.user_id:
            return {'success': False, 'error': 'No user_id available after session init', 'error_type': 'auth_expired'}

        deadline = time.monotonic() + CART_ADD_HOT_PATH_DEADLINE_SECONDS

        last_result = None
        for _ in range(quantity):
            is_green_val = 1 if is_green else 0

            # Full 16-field payload (see docs/memory/KNOWLEDGE_BASE.md)
            data = {
                'id': product_id,
                'xmlid': product_id,
                'max': 1,
                'delivery_no_set': 'N',
                'koef': 1,
                'step': 1,
                'coupon': '',
                'isExperiment': 'N',
                'isOnlyOnline': '',
                'isGreen': is_green_val,
                'user_id': self.user_id,
                'skip_analogs': '',
                'is_app': '',
                'is_default_button': 'Y',
                'cssInited': 'N',
                'price_type': price_type,
            }
            if self.sessid:
                data['sessid'] = self.sessid
            
            try:
                request_timeout_seconds = max(0.1, deadline - time.monotonic())
                logger.info(f"🛒 [CART-ADD] product={product_id} | sending request, timeout={request_timeout_seconds:.2f}s, elapsed={(time.monotonic() - t_start)*1000:.0f}ms")
                t_req = time.monotonic()
                last_result = self._request(
                    BASKET_ADD_URL,
                    data,
                    timeout=httpx.Timeout(request_timeout_seconds),
                )
                logger.info(f"🛒 [CART-ADD] product={product_id} | VkusVill responded in {(time.monotonic() - t_req)*1000:.0f}ms, total={(time.monotonic() - t_start)*1000:.0f}ms")
            except httpx.TimeoutException as e:
                logger.error(f"🛒 [CART-ADD] product={product_id} | TIMEOUT after {(time.monotonic() - t_start)*1000:.0f}ms: {e}")
                return {
                    'success': False,
                    'pending': True,
                    'error': 'pending_timeout',
                    'error_type': 'pending_timeout',
                    'raw': {'deadline_seconds': CART_ADD_HOT_PATH_DEADLINE_SECONDS},
                }
            except httpx.ConnectError as e:
                logger.error(f"🛒 [CART-ADD] product={product_id} | ConnectError after {(time.monotonic() - t_start)*1000:.0f}ms: {e}")
                return {'success': False, 'error': str(e), 'error_type': 'transient'}
            except httpx.HTTPError as e:
                logger.error(f"🛒 [CART-ADD] product={product_id} | HTTP error after {(time.monotonic() - t_start)*1000:.0f}ms: {e}")
                return {'success': False, 'error': str(e), 'error_type': 'http'}
            except json.JSONDecodeError:
                logger.error(f"🛒 [CART-ADD] product={product_id} | non-JSON after {(time.monotonic() - t_start)*1000:.0f}ms")
                return {'success': False, 'error': 'Invalid response from VkusVill', 'error_type': 'invalid_response'}
        
        if not last_result:
            return {'success': False, 'error': 'No response'}
        
        # Parse response
        success_val = last_result.get('success')
        success = str(success_val).upper() in ['Y', 'TRUE', '1']
        error = last_result.get('error', '')
        
        # Classify error_type based on response content
        error_type = None
        if not success:
            popup_analogs = last_result.get('POPUP_ANALOGS')
            basket_added = last_result.get('basketAdded')
            if popup_analogs and popup_analogs != 'N':
                error = "Товар распродан или недоступен для заказа"
                error_type = 'product_gone'
                logger.warning(f"Failed to add {product_id}: {error}")
            elif not basket_added and success_val and str(success_val).upper() == 'N':
                error_type = 'auth_expired'
            else:
                error_type = last_result.get('error_type', 'api')
            # Log raw response for debugging (truncated to 500 chars, never sent to frontend)
            logger.warning(f"VkusVill raw response for product={product_id}: {json.dumps(last_result, ensure_ascii=False, default=str)[:500]}")

        result = {
            'success': success,
            'error': error,
            'error_type': error_type,
            'raw': last_result,
        }
        
        if success:
            ba = last_result.get('basketAdded', {})
            totals = last_result.get('totals', {})
            result.update({
                'product_name': ba.get('NAME', ''),
                'product_id': ba.get('PRODUCT_ID'),
                'quantity': ba.get('Q', 0),
                'price': ba.get('PRICE', 0),
                'cart_items': totals.get('Q_ITEMS', 0),
                'cart_total': totals.get('PRICE_FINAL', 0),
                'can_buy': ba.get('CAN_BUY') == 'Y' or ba.get('CAN_BUY') is True,
                'max_q': ba.get('MAX_Q', 0),
            })
            logger.info(f"✅ Added {ba.get('NAME', product_id)} to cart "
                        f"(Q={ba.get('Q')}, Cart: {totals.get('Q_ITEMS')} items)")
        else:
            logger.warning(f"❌ Failed to add {product_id}: {error} (type={type(success_val)}, val={success_val})")
        
        return result
    
    def get_cart(self) -> dict:
        """
        Fetch the current VkusVill cart state using basket_recalc.php (read-only).
        """
        self._ensure_session()

        data = {'COUPON': '', 'BONUS': ''}
        if self.sessid:
            data['sessid'] = self.sessid

        try:
            result = self._request(BASKET_RECALC_URL, data, referer='/cart/')
        except Exception as e:
            logger.error(f"Failed to fetch cart: {e}")
            return {'success': False, 'error': str(e)}

        basket = result.get('basket', {})
        totals = result.get('totals', {})

        return {
            'success': True,
            'items_count': totals.get('Q_ITEMS', 0),
            'total_price': totals.get('PRICE_FINAL', 0),
            'items': basket,
            'raw': result
        }

    def remove(self, product_id: int, basket_key: str = None) -> dict:
        """Remove a product from the VkusVill cart.

        Uses basket_update.php with type=del and the basket key (e.g. '731_0').
        If basket_key is not provided, fetches the cart to find it.
        """
        self._ensure_session()

        # Find the basket key if not provided
        old_q = 1
        is_green = 0
        if not basket_key:
            cart_data = self.get_cart()
            if not cart_data.get('success'):
                return {'success': False, 'error': 'Could not fetch cart to find basket key'}
            basket = cart_data.get('raw', {}).get('basket', {})
            for key, item in basket.items():
                if isinstance(item, dict) and str(item.get('PRODUCT_ID', '')) == str(product_id):
                    basket_key = key
                    old_q = item.get('Q', 1)
                    is_green = 1 if item.get('IS_GREEN') else 0
                    break
            if not basket_key:
                logger.warning(f"Product {product_id} not found in cart, nothing to remove")
                return {'success': True, 'items_count': 0, 'total_price': 0}

        data = {
            'id': basket_key,
            'productId': product_id,
            'isGreen': is_green,
            'q': 0,
            'q_old': old_q,
            'koef': 1,
            'step': 1,
            'coupon': '',
            'bonus': '',
            'type': 'del',
            'typeBtn': '',
        }
        if self.sessid:
            data['sessid'] = self.sessid

        try:
            result = self._request(BASKET_UPDATE_URL, data, referer='/cart/')
        except Exception as e:
            logger.error(f"Cart remove failed: {e}")
            return {'success': False, 'error': str(e)}

        success = str(result.get('success', '')).upper() in ['Y', 'TRUE', '1']
        totals = result.get('totals', {})

        logger.info(f"{'✅' if success else '❌'} Remove {product_id} (key={basket_key}): {result.get('error', 'ok')}")
        return {
            'success': success,
            'items_count': totals.get('Q_ITEMS', 0),
            'total_price': totals.get('PRICE_FINAL', 0),
        }

    def set_quantity(self, product_id: int, quantity: float, basket_key: str = None) -> dict:
        """Set the quantity for an existing basket line via basket_update.php."""
        self._ensure_session()

        target_q = _coerce_numeric(quantity, 0)
        if target_q <= 0:
            return self.remove(product_id, basket_key=basket_key)

        cart_data = self.get_cart()
        if not cart_data.get('success'):
            return {'success': False, 'error': 'Could not fetch cart to find basket key'}

        basket = cart_data.get('raw', {}).get('basket', {})
        old_q = 0
        is_green = 0
        koef = 1
        step = 1
        max_q = 0

        for key, item in basket.items():
            if isinstance(item, dict) and str(item.get('PRODUCT_ID', '')) == str(product_id):
                basket_key = key
                old_q = _coerce_numeric(item.get('Q', 0), 0)
                is_green = 1 if item.get('IS_GREEN') else 0
                koef = _coerce_numeric(item.get('KOEF', 1), 1)
                step = _coerce_numeric(item.get('STEP', 1), 1)
                max_q = _coerce_numeric(item.get('MAX_Q', 0), 0)
                break

        if not basket_key:
            logger.warning(f"Product {product_id} not found in cart for set_quantity")
            return {'success': False, 'error': 'Product not found in cart'}

        if max_q and target_q > max_q:
            target_q = max_q

        if target_q == old_q:
            return {
                'success': True,
                'items_count': cart_data.get('items_count', 0),
                'total_price': cart_data.get('total_price', 0),
                'quantity': target_q,
                'max_q': max_q,
            }

        update_type = 'basket_up' if target_q > old_q else 'basket_down'
        data = {
            'id': basket_key,
            'productId': product_id,
            'isGreen': is_green,
            'q': target_q,
            'q_old': old_q,
            'koef': koef,
            'step': step,
            'coupon': '',
            'bonus': '',
            'type': update_type,
            'typeBtn': '',
        }
        if self.sessid:
            data['sessid'] = self.sessid

        try:
            result = self._request(BASKET_UPDATE_URL, data, referer='/cart/')
        except Exception as e:
            logger.error(f"Cart set_quantity failed: {e}")
            return {'success': False, 'error': str(e)}

        success = str(result.get('success', '')).upper() in ['Y', 'TRUE', '1']
        totals = result.get('totals', {})

        logger.info(f"{'✅' if success else '❌'} Set quantity {product_id} -> {target_q}: {result.get('error', 'ok')}")
        return {
            'success': success,
            'items_count': totals.get('Q_ITEMS', 0),
            'total_price': totals.get('PRICE_FINAL', 0),
            'quantity': target_q,
            'max_q': max_q,
            'raw': result,
        }

    def clear_all(self) -> dict:
        """Remove all items from the VkusVill cart using basket_clear.php (single call)."""
        self._ensure_session()

        data = {}
        if self.sessid:
            data['sessid'] = self.sessid

        try:
            result = self._request(BASKET_CLEAR_URL, data, referer='/cart/')
        except Exception as e:
            logger.error(f"Cart clear failed: {e}")
            return {'success': False, 'error': str(e)}

        success = str(result.get('success', '')).upper() in ['Y', 'TRUE', '1']
        logger.info(f"{'🗑' if success else '❌'} Cart clear: {result}")
        return {'success': success, 'removed': result.get('item_count', 0)}

    def close(self):
        """Clear session data."""
        self._cookie_str = ""
        self._initialized = False
