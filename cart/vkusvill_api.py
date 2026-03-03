"""
VkusVill Cart API — добавление товаров в корзину через HTTP API.
Без Chrome/Selenium — чистый requests.

Usage:
    from cart.vkusvill_api import VkusVillCart
    
    cart = VkusVillCart(cookies_path="data/browser_cookies_live.json")
    result = cart.add(product_id=731, price_type=1)

IMPORTANT: Cookie files must include sessid and user_id fields
alongside cookie data. The login flow must export these.
"""
import requests
import json
import os
import re
import logging

logger = logging.getLogger(__name__)

BASKET_ADD_URL = "https://vkusvill.ru/ajax/delivery_order/basket_add.php"
VKUSVILL_BASE = "https://vkusvill.ru"


class VkusVillCart:
    """Client for VkusVill cart operations via their internal AJAX API.
    
    Uses raw Cookie header instead of requests cookie jar because
    __Host-PHPSESSID cookies are not handled correctly by requests.
    """
    
    def __init__(self, cookies_path: str, user_id: int = 0, sessid: str = ""):
        """
        Args:
            cookies_path: Path to cookies JSON file (exported from browser).
            user_id: VkusVill internal Bitrix user ID (from lk-user-id).
                     If 0, will try to load from cookie file metadata.
            sessid: CSRF token. If empty, will try to load from cookie file
                    metadata or extract from warmup page.
        """
        self.cookies_path = cookies_path
        self.user_id = user_id
        self.sessid = sessid
        self._cookie_str = ""
        self._initialized = False
    
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
                self.sessid = data.get('sessid', '')
            if not self.user_id:
                self.user_id = data.get('user_id', 0)
        else:
            cookies_list = data
        
        # Build raw Cookie header string
        # This bypasses requests cookie jar which mangles __Host-PHPSESSID
        self._cookie_str = '; '.join(
            f"{c['name']}={c['value']}" for c in cookies_list
        )
        
        logger.info(f"Loaded {len(cookies_list)} cookies from {self.cookies_path}")
        
        # If sessid or user_id not provided, try to extract from a page GET
        if not self.sessid or not self.user_id:
            self._extract_session_params()
        
        self._initialized = True
        logger.info(f"Session ready (user_id={self.user_id}, sessid={self.sessid[:8]}...)")
    
    def _extract_session_params(self):
        """GET the main page to extract sessid and user_id.
        
        NOTE: This only works if __Host-PHPSESSID is properly sent,
        which requires raw Cookie header. The response will contain
        sessid and user_id matching the session from the cookies.
        """
        try:
            r = requests.get(VKUSVILL_BASE, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
                'Cookie': self._cookie_str,
            }, timeout=15)
            
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
                    
        except requests.RequestException as e:
            logger.warning(f"Failed to extract session params: {e}")
    
    def _request(self, url: str, data: dict) -> dict:
        """Make a POST request using raw Cookie header."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': VKUSVILL_BASE,
            'Referer': f'{VKUSVILL_BASE}/',
            'Cookie': self._cookie_str,
        }
        
        r = requests.post(url, data=data, headers=headers, timeout=15)
        return r.json()
    
    def is_logged_in(self) -> bool:
        """Check if the current session is logged in to VkusVill."""
        self._ensure_session()
        try:
            r = requests.get(
                f"{VKUSVILL_BASE}/personal/",
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Cookie': self._cookie_str,
                },
                timeout=15,
                allow_redirects=False
            )
            return r.status_code == 200
        except requests.RequestException:
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
        self._ensure_session()
        
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
                last_result = self._request(BASKET_ADD_URL, data)
            except requests.RequestException as e:
                logger.error(f"Cart API request failed: {e}")
                return {'success': False, 'error': str(e)}
            except json.JSONDecodeError:
                logger.error(f"Cart API returned non-JSON")
                return {'success': False, 'error': 'Invalid response from VkusVill'}
        
        if not last_result:
            return {'success': False, 'error': 'No response'}
        
        # Parse response
        success_val = last_result.get('success')
        success = str(success_val).upper() in ['Y', 'TRUE', '1']
        error = last_result.get('error', '')
        
        # Check for out-of-stock (POPUP_ANALOGS)
        if not success and last_result.get('POPUP_ANALOGS') and last_result.get('POPUP_ANALOGS') != 'N':
            error = "Товар распродан или недоступен для заказа"
            logger.warning(f"Failed to add {product_id}: {error}")
        
        result = {
            'success': success,
            'error': error,
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
        Fetch the current VkusVill cart state.
        Uses a dummy request to basket_add.php which safely returns the basket JSON.
        """
        self._ensure_session()
        
        # A minimal payload causes fail but returns basket data
        data = {'id': 42530}
        
        try:
            result = self._request(BASKET_ADD_URL, data)
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

    def remove(self, product_id: int) -> dict:
        """Remove a product from the VkusVill cart."""
        self._ensure_session()
        
        url = "https://vkusvill.ru/ajax/delivery_order/basket_remove.php"
        data = {
            'id': product_id,
            'user_id': self.user_id,
        }
        if self.sessid:
            data['sessid'] = self.sessid
        
        try:
            result = self._request(url, data)
        except Exception as e:
            logger.error(f"Cart remove failed: {e}")
            return {'success': False, 'error': str(e)}
        
        success = str(result.get('success', '')).upper() in ['Y', 'TRUE', '1']
        totals = result.get('totals', {})
        
        logger.info(f"{'✅' if success else '❌'} Remove {product_id}: {result.get('error', 'ok')}")
        return {
            'success': success,
            'items_count': totals.get('Q_ITEMS', 0),
            'total_price': totals.get('PRICE_FINAL', 0),
        }

    def clear_all(self) -> dict:
        """Remove all items from the VkusVill cart."""
        self._ensure_session()
        
        # First get all items
        cart = self.get_cart()
        if not cart.get('success'):
            return cart
        
        raw = cart.get('raw', {})
        basket = raw.get('basket', {})
        removed = 0
        
        for key, item in basket.items():
            if isinstance(item, dict) and item.get('PRODUCT_ID'):
                pid = item['PRODUCT_ID']
                self.remove(int(pid))
                removed += 1
        
        logger.info(f"🗑 Cleared {removed} items from cart")
        return {'success': True, 'removed': removed}

    def close(self):
        """Clear session data."""
        self._cookie_str = ""
        self._initialized = False
