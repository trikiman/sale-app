import re
import os
import json
import time
import sys

# Path to category database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORY_DB_PATH = os.path.join(BASE_DIR, "data", "category_db.json")

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

# Cache for category database
_category_db_cache = None

def load_category_db():
    """Load the category database from disk (cached)"""
    global _category_db_cache
    if _category_db_cache is None:
        if os.path.exists(CATEGORY_DB_PATH):
            try:
                with open(CATEGORY_DB_PATH, 'r', encoding='utf-8') as f:
                    _category_db_cache = json.load(f)
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


def normalize_category(raw_cat, product_name, product_id=None):
    """
    Normalizes category using a three-tier approach:
    1. Database lookup by product ID (most accurate)
    2. Use raw VkusVill category if meaningful
    3. Keyword fallback for unknown items
    """
    # Tier 1: Database lookup (most accurate)
    if product_id:
        db_category = lookup_category_db(product_id)
        if db_category:
            return db_category
    
    # Tier 2: Use raw category if it's meaningful (not just "Green/Red tags")
    if raw_cat:
        raw_lower = raw_cat.lower().replace('ё', 'е')  # Normalize ё to е for matching
        # Skip generic tag categories
        if 'зелен' not in raw_lower and 'красн' not in raw_lower and 'желт' not in raw_lower:
            # Return the raw category as-is (VkusVill's actual category)
            return raw_cat
    
    # Tier 3: Keyword fallback for truly unknown items
    return keyword_fallback(product_name)

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
        return 5  # Assume low stock = 5 items

    # If it says "In stock" but no number, assume plenty
    if 'в наличии' in text_lower:
        return 99

    return 0

def clean_price(price_str):
    """Returns clean integer string from price (e.g., '120 ₽' -> '120', '120.50' -> '120')"""
    if not price_str:
        return '0'
    # Handle decimal separators - replace comma with dot, then extract number
    s = str(price_str).replace(',', '.')
    # Extract numeric value (including decimal)
    match = re.search(r'(\d+(?:\.\d+)?)', s)
    if match:
        # Return integer part only (floor the value)
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
                product['oldPrice'] = str(int(curr / 0.6))
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
        print(f"✅ Successfully saved {len(products)} products to {output_path}")
        return True
    except Exception as e:
        print(f"❌ Error saving file {output_path}: {e}")
        return False
