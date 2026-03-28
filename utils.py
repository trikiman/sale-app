import re
import os
import json
import time
import sys

# Path to category database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORY_DB_PATH = os.path.join(BASE_DIR, "data", "category_db.json")


_WEIGHT_RE = re.compile(
    r'[,\s]\s*(\d[\d.,]*)\s*(г|гр|кг|мл|л)\b',
    re.IGNORECASE | re.UNICODE
)

def extract_weight(name: str) -> str:
    """Extract package weight/volume from product name.
    E.g. 'Морс детский, 250 мл' -> '250 мл', 'Ямс, 500 гр' -> '500 г'
    Returns empty string if not found.
    """
    m = _WEIGHT_RE.search(name or '')
    if not m:
        return ''
    val = m.group(1).replace(',', '.').rstrip('.')
    unit = m.group(2).lower()
    if unit == 'гр':
        unit = 'г'
    return f"{val} {unit}"


def normalize_stock_unit(unit, stock):
    """Normalize selling unit when stock shape clearly indicates weight-based sale."""
    raw = str(unit or '').strip().lower()
    if raw == 'kg':
        return 'кг'
    if raw == 'ml':
        return 'мл'
    if raw == 'l':
        return 'л'
    if raw == 'гр':
        return 'г'
    if raw == 'pcs':
        raw = 'шт'
    if not raw:
        raw = 'шт'

    try:
        stock_num = float(stock)
    except (TypeError, ValueError):
        return raw

    if raw == 'шт' and stock_num > 0 and not stock_num.is_integer():
        return 'кг'
    return raw


def check_vkusvill_available(strict: bool = False) -> bool:
    """Check if VkusVill is reachable before scraping.

    Uses SOCKS5 proxy (same as scrapers) since the main IP may be banned.
    By default this probe is advisory because browser-driven scrapers can still
    work even when this call times out.
    """
    try:
        import httpx
        _proxy = os.environ.get("SOCKS_PROXY", "")
        client_kwargs = dict(timeout=10)
        if _proxy:
            client_kwargs['proxy'] = _proxy
        with httpx.Client(**client_kwargs) as client:
            r = client.get(
                'https://vkusvill.ru/',
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            )
        if r.status_code == 200:
            print('  [CHECK] VkusVill OK (200)')
            return True
        print(f'  [CHECK] VkusVill returned {r.status_code} — possible IP ban or downtime. Aborting scrape.')
        return False
    except Exception as e:
        if strict:
            print(f'  [CHECK] VkusVill unreachable: {e} - Aborting scrape.')
            return False
        print(f'  [CHECK] VkusVill probe failed: {e} - continuing with browser scraper.')
        return True

class ChromeLock:
    """
    Cross-platform file lock to prevent race conditions during Chrome initialization.
    Uses msvcrt on Windows and fcntl on Linux/macOS.
    """
    def __init__(self, filename="chrome_init.lock", timeout=120):
        self.filename = os.path.join(BASE_DIR, filename)
        self.timeout = timeout
        self.file_handle = None

    def acquire(self):
        start_time = time.time()
        while True:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    self.file_handle = open(self.filename, 'w')
                    # Lock the first byte
                    msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    self.file_handle = open(self.filename, 'w')
                    fcntl.flock(self.file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (IOError, OSError):
                if self.file_handle:
                    try:
                        self.file_handle.close()
                    except Exception:
                        pass
                    self.file_handle = None

                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Timeout waiting for Chrome lock: {self.filename}")
                time.sleep(1)

    def release(self):
        if self.file_handle:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file_handle, fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                self.file_handle.close()
                self.file_handle = None

        # Try to remove the lock file, but don't fail if we can't
        try:
            if os.path.exists(self.filename):
                os.remove(self.filename)
        except Exception:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

# Cache for category database (with TTL to pick up scraper updates)
_category_db_cache = None
_category_db_mtime = 0

def load_category_db():
    """Load the category database from disk (cached, refreshes if file changed)"""
    global _category_db_cache, _category_db_mtime
    try:
        current_mtime = os.path.getmtime(CATEGORY_DB_PATH) if os.path.exists(CATEGORY_DB_PATH) else 0
    except OSError:
        current_mtime = 0
    if _category_db_cache is None or current_mtime != _category_db_mtime:
        if os.path.exists(CATEGORY_DB_PATH):
            try:
                with open(CATEGORY_DB_PATH, 'r', encoding='utf-8') as f:
                    _category_db_cache = json.load(f)
                _category_db_mtime = current_mtime
            except Exception:
                _category_db_cache = {"products": {}}
        else:
            _category_db_cache = {"products": {}}
    return _category_db_cache

def lookup_category_db(product_id):
    """Look up product category in database by ID"""
    if not product_id:
        return None
    db = load_category_db()
    product_id = str(product_id)
    if product_id in db.get("products", {}):
        return db["products"][product_id].get("category")
    return None

def keyword_fallback(product_name):
    """Fallback keyword matching for truly unknown products"""
    name = product_name.lower()
    
    # Meat keywords (expanded)
    if any(kw in name for kw in ['колбаса', 'сосиски', 'сардельки', 'карбонад', 'филе', 'куриц', 'курин', 
                                   'фарш', 'говядин', 'свинин', 'индейк', 'утка', 'утёнок', 'утенок',
                                   'гусь', 'баранин', 'кролик', 'печен', 'сердце', 'язык', 'ветчин']):
        return 'Мясо, Мясные деликатесы'
    
    # Ready food
    if any(kw in name for kw in ['запеканка', 'блины', 'сырники', 'каша', 'суп', 'сэндвич', 'плов', 
                                   'паста', 'салат', 'котлет', 'пельмен', 'вареник', 'голубц']):
        return 'Готовая еда'
    
    # Fruits
    if any(kw in name for kw in ['мандарин', 'яблок', 'банан', 'апельсин', 'груша', 'киви', 'ягод', 
                                   'клубник', 'малин', 'черник', 'виноград', 'персик', 'абрикос', 'слив']):
        return 'Овощи, фрукты, ягоды, зелень'
    
    # Vegetables
    if any(kw in name for kw in ['огурец', 'томат', 'помидор', 'картоф', 'зелень', 'капуст', 'морков',
                                   'лук', 'чеснок', 'перец', 'баклажан', 'кабачок', 'свекл', 'редис']):
        return 'Овощи, фрукты, ягоды, зелень'
    
    # Dairy
    if any(kw in name for kw in ['йогурт', 'творог', 'кефир', 'сметана', 'молоко', 'сливки', 'ряженка']):
        return 'Молочные продукты'

    # Eggs
    if 'яйц' in name or 'яиц' in name:
        return 'Яйца'

    # Cheese (separate category in VkusVill)
    if 'сыр' in name:
        return 'Сыры'
    
    # Sweets
    if any(kw in name for kw in ['торт', 'пирожн', 'эклер', 'печенье', 'шоколад', 'конфет', 'вафли', 
                                   'зефир', 'мармелад', 'пряник', 'халва']):
        return 'Сладости и десерты'
    
    # Bread
    if any(kw in name for kw in ['хлеб', 'батон', 'лаваш', 'булочк', 'чиабатта', 'багет', 'круассан']):
        return 'Выпечка и хлеб'
    
    # Fish
    if any(kw in name for kw in ['рыба', 'форель', 'семга', 'сельдь', 'креветк', 'краб', 'мидии',
                                   'лосось', 'треска', 'скумбри', 'икра', 'кальмар']):
        return 'Рыба, икра и морепродукты'
    
    # Drinks
    if any(kw in name for kw in ['вода', 'сок', 'лимонад', 'чай', 'кофе', 'напиток', 'морс', 'компот']):
        return 'Напитки'
    
    # Frozen
    if any(kw in name for kw in ['замороженн', 'заморож']):
        return 'Замороженные продукты'
    
    # Ice cream
    if 'мороженое' in name or 'пломбир' in name:
        return 'Мороженое'

    # Groceries / Pantry
    if any(kw in name for kw in ['крупа', 'рис', 'гречка', 'макарон', 'спагетти', 'мука', 'сахар',
                                   'соль', 'масло растит', 'консерв', 'горох', 'фасоль', 'чечевиц']):
        return 'Бакалея'

    # Bakery items (pastries, cakes)
    if any(kw in name for kw in ['кольцо', 'сдоба', 'сдобн', 'пирог', 'ватрушк', 'слойка', 'кекс']):
        return 'Выпечка и хлеб'

    return 'Другое'


# Canonical category map: merge VkusVill's inconsistent names into clean groups
_CATEGORY_ALIASES = {
    # Bread variants
    'хлеб, хлебные изделия': 'Хлеб и выпечка',
    'выпечка и хлеб': 'Хлеб и выпечка',
    'хлеб и выпечка': 'Хлеб и выпечка',
    'хлебобулочные изделия': 'Хлеб и выпечка',
    # Dairy variants
    'молочные продукты, яйцо': 'Молочные продукты',
    'молочные продукты': 'Молочные продукты',
    'молоко, сливки': 'Молочные продукты',
    # Meat variants
    'мясо, мясные деликатесы': 'Мясо, птица',
    'мясо, птица': 'Мясо, птица',
    'мясо и птица': 'Мясо, птица',
    'мясная гастрономия': 'Мясо, птица',
    'птица': 'Мясо, птица',
    # Fish variants
    'рыба, икра и морепродукты': 'Рыба и морепродукты',
    'рыба и морепродукты': 'Рыба и морепродукты',
    'рыбная гастрономия': 'Рыба и морепродукты',
    # Sweets variants
    'сладости и десерты': 'Сладости и десерты',
    'торты, пирожные, десерты': 'Сладости и десерты',
    'кондитерские изделия': 'Сладости и десерты',
    # Veggies variants
    'овощи, фрукты, ягоды, зелень': 'Овощи и фрукты',
    'овощи и фрукты': 'Овощи и фрукты',
    'фрукты': 'Овощи и фрукты',
    'овощи': 'Овощи и фрукты',
    # Frozen variants
    'замороженные продукты': 'Замороженные продукты',
    'заморозка': 'Замороженные продукты',
}


def _apply_category_alias(category: str) -> str:
    """Normalize category name through alias map."""
    if not category:
        return category
    key = category.lower().replace('ё', 'е').strip()
    return _CATEGORY_ALIASES.get(key, category)


def normalize_category(raw_cat, product_name, product_id=None):
    """
    Normalizes category using a three-tier approach:
    1. Database lookup by product ID (most accurate)
    2. Use raw VkusVill category if meaningful
    3. Keyword fallback for unknown items
    All results are passed through _apply_category_alias() to merge duplicates.
    """
    # Tier 1: Database lookup (most accurate)
    if product_id:
        db_category = lookup_category_db(product_id)
        if db_category:
            return _apply_category_alias(db_category)
    
    # Tier 2: Use raw category if it's meaningful (not just "Green/Red tags")
    if raw_cat:
        raw_lower = raw_cat.lower().replace('ё', 'е')  # Normalize ё to е for matching
        # Skip generic tag categories
        if 'зелен' not in raw_lower and 'красн' not in raw_lower and 'желт' not in raw_lower:
            return _apply_category_alias(raw_cat)
    
    # Tier 3: Keyword fallback for unknown items
    if product_name:
        kw_result = keyword_fallback(product_name)
        if kw_result and kw_result != 'Другое':
            return _apply_category_alias(kw_result)

    # Tier 4: Not in DB, no meaningful raw category, no keyword match → 'Новинки'
    return 'Новинки'

def parse_stock(text):
    """
    Extracts stock count from text like "В наличии 5 шт" or "В наличии: 0.41 кг".
    Returns float for kg items, int for шт items, 99 if valid but no number, or 0 if OOS.
    """
    if not text:
        return 0

    text_lower = text.lower()

    if 'не осталось' in text_lower or 'нет в наличии' in text_lower:
        return 0

    # Match decimal kg (e.g., "0.41 кг", "2.06 кг")
    kg_match = re.search(r'([\d.,]+)\s*кг', text_lower)
    if kg_match:
        return float(kg_match.group(1).replace(',', '.'))

    # Match "5 шт", "5шт", ": 5"
    match = re.search(r'(\d+)\s*шт', text_lower)
    if match:
        return int(match.group(1))

    match = re.search(r'наличии[:\s]*(\d+)', text_lower)
    if match:
        return int(match.group(1))

    # "Осталось мало" / "мало" means low stock but still available
    if 'мало' in text_lower or 'осталось' in text_lower:
        return 3  # Low stock indicator

    # If it says "In stock" but no number → at least 1 available
    if 'в наличии' in text_lower:
        return 1  # Item available, show at least 1

    return 0

def clean_price(price_str):
    """Returns clean integer string from price (e.g., '1 399 ₽/кг' -> '1399', '120.50' -> '120')"""
    if not price_str:
        return '0'
    s = str(price_str)
    # Remove non-breaking spaces and HTML entities used as thousands separators
    s = s.replace('&nbsp;', '').replace('\u00a0', '')
    # Collapse spaces between digits (thousands separator: "1 399" -> "1399")
    s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)
    s = s.replace(',', '.')
    match = re.search(r'(\d+(?:\.\d+)?)', s)
    if match:
        return str(int(float(match.group(1))))
    return '0'

def synthesize_discount(product):
    """
    Synthesizes oldPrice ONLY for Green Tags (approx 40% off).
    Red and yellow products have different discount structures — do NOT fabricate
    their oldPrice using the green formula, as it produces wrong data shown to users.
    """
    if product.get('type') != 'green':
        return product  # Only synthesize for green products

    curr_price = product.get('currentPrice')
    old_price = product.get('oldPrice')

    if curr_price and (not old_price or old_price == '0' or old_price == 0):
        try:
            curr = float(curr_price)
            if curr > 0:
                # Green tags are typically 40% off, so current = old * 0.6
                product['oldPrice'] = str(int(round(curr / 0.6)))
        except (ValueError, TypeError):
            pass
    return product

def deduplicate_products(products):
    """
    Removes products with duplicate IDs or Names.
    If duplicates exist, keeps the one with the lowest currentPrice.
    """
    product_map = {}

    for p in products:
        # Use ID if available, otherwise use Name as fallback ID
        pid = str(p.get('id') or '').strip()
        name = str(p.get('name') or '').strip().lower()

        # Unique key is ID if exists, otherwise Name
        key = pid if pid and pid != '0' else f"name_{name}"

        if not key or key == 'name_':
            continue

        current_p = product_map.get(key)

        # If new to map, or cheaper than existing, replace it
        if not current_p:
            product_map[key] = p
        else:
            try:
                old_price = float(clean_price(current_p.get('currentPrice', 0)))
                new_price = float(clean_price(p.get('currentPrice', 0)))

                # Keep the one with a price > 0. If both > 0, keep cheaper.
                if old_price <= 0 and new_price > 0:
                    product_map[key] = p
                elif new_price > 0 and new_price < old_price:
                    product_map[key] = p
            except (ValueError, TypeError):
                pass # Keep existing if price parsing fails

    return list(product_map.values())

def save_products_safe(products, output_path, success=True):
    """
    Safely saves products to a JSON file.
    - If success is False (scraper error/blocked), does NOT overwrite existing file.
    - If success is True, SAVES the file even if products list is empty (reflecting live OOS state).
    - Creates directory if needed.
    - Saves with UTF-8 encoding and indent=2.
    """
    if not success:
        print(f"⚠️ Scraper did not complete successfully. Skipping save to {output_path} to preserve previous data for staleness detection.")
        return False

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        # Count actual products, not dict keys
        if isinstance(products, dict) and 'products' in products:
            count = len(products['products'])
        elif isinstance(products, list):
            count = len(products)
        else:
            count = len(products)
        print(f"\u2705 Successfully saved {count} products to {output_path}")
        return True
    except Exception as e:
        print(f"❌ Error saving file {output_path}: {e}")
        return False
