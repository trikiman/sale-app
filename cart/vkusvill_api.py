"""
VkusVill Cart API — добавление товаров в корзину через HTTP API.
Без Chrome/Selenium — чистый requests.

Usage:
    from cart.vkusvill_api import VkusVillCart
    
    cart = VkusVillCart(cookies_path="data/cookies.json")
    result = cart.add(product_id=42530, price_type=1)
"""
import requests
import json
import os
import logging

logger = logging.getLogger(__name__)

BASKET_ADD_URL = "https://vkusvill.ru/ajax/delivery_order/basket_add.php"
VKUSVILL_BASE = "https://vkusvill.ru"


class VkusVillCart:
    """Client for VkusVill cart operations via their internal AJAX API."""
    
    def __init__(self, cookies_path: str, user_id: int = 6443332):
        """
        Args:
            cookies_path: Path to cookies JSON file (Selenium format).
            user_id: VkusVill internal user ID (from account).
        """
        self.cookies_path = cookies_path
        self.user_id = user_id
        self.session = None
        self._initialized = False
    
    def _ensure_session(self):
        """Create session and warm it up with a GET request."""
        if self._initialized and self.session:
            return
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        
        # Load cookies from file
        if not os.path.exists(self.cookies_path):
            raise FileNotFoundError(f"Cookies file not found: {self.cookies_path}")
        
        with open(self.cookies_path, 'r', encoding='utf-8') as f:
            cookies_list = json.load(f)
        
        for c in cookies_list:
            self.session.cookies.set(
                c['name'], c['value'],
                domain=c.get('domain', '.vkusvill.ru')
            )
        
        logger.info(f"Loaded {len(cookies_list)} cookies from {self.cookies_path}")
        
        # Warm up session — VkusVill needs an initial GET to set server-side session
        try:
            r = self.session.get(VKUSVILL_BASE, timeout=15)
            if r.status_code == 200:
                self._initialized = True
                logger.info(f"Session initialized ({len(self.session.cookies)} cookies)")
            else:
                logger.warning(f"Session warmup returned status {r.status_code}")
        except requests.RequestException as e:
            logger.error(f"Session warmup failed: {e}")
            raise
    
    def is_logged_in(self) -> bool:
        """Check if the current session is logged in to VkusVill."""
        self._ensure_session()
        try:
            r = self.session.get(
                f"{VKUSVILL_BASE}/personal/",
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
            product_id: VkusVill product ID (e.g. 42530).
            price_type: Price type (1=regular, 222=red/sale price).
            is_green: 1 if green price item, 0 otherwise.
            quantity: How many times to call add (API adds 1 per call).
        
        Returns:
            dict with keys: success (bool), product_name, cart_total, error
        """
        self._ensure_session()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Origin': VKUSVILL_BASE,
            'Referer': f'{VKUSVILL_BASE}/',
        }
        
        last_result = None
        for _ in range(quantity):
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
                'isGreen': is_green,
                'user_id': self.user_id,
                'skip_analogs': '',
                'is_app': '',
                'is_default_button': 'Y',
                'cssInited': 'N',
                'price_type': price_type,
            }
            
            try:
                r = self.session.post(
                    BASKET_ADD_URL, data=data, headers=headers, timeout=15
                )
                last_result = r.json()
            except requests.RequestException as e:
                logger.error(f"Cart API request failed: {e}")
                return {'success': False, 'error': str(e)}
            except json.JSONDecodeError:
                logger.error(f"Cart API returned non-JSON: {r.text[:200]}")
                return {'success': False, 'error': 'Invalid response from VkusVill'}
        
        if not last_result:
            return {'success': False, 'error': 'No response'}
        
        success = last_result.get('success') == 'Y'
        error = last_result.get('error', '')
        
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
                'can_buy': ba.get('CAN_BUY') == 'Y',
                'max_q': ba.get('MAX_Q', 0),
            })
            logger.info(f"✅ Added {ba.get('NAME', product_id)} to cart "
                        f"(Q={ba.get('Q')}, Cart: {totals.get('Q_ITEMS')} items)")
        else:
            logger.warning(f"❌ Failed to add {product_id}: {error}")
        
        return result
    
    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
            self.session = None
            self._initialized = False
