import re

def normalize_category(raw_cat, product_name):
    """
    Normalizes category based on the raw category string and product name.
    Maps VkusVill categories to the simplified list used in the App.
    """
    raw_cat = raw_cat.lower() if raw_cat else ""
    name = product_name.lower()

    # Priority 1: Keyword matching in Name (fixes "Green Tag" vague categories)
    if 'запеканка' in name or 'блины' in name or 'сырники' in name or 'каша' in name or 'суп' in name or 'сэндвич' in name or 'плов' in name or 'паста' in name or 'салат' in name:
        return 'Готовая еда'
    if 'мандарин' in name or 'яблок' in name or 'банан' in name or 'апельсин' in name or 'груша' in name or 'киви' in name or 'ягод' in name or 'клубник' in name or 'малин' in name:
        return 'Фрукты'
    if 'огурец' in name or 'томат' in name or 'помидор' in name or 'картоф' in name or 'зелень' in name or 'капуст' in name or 'морков' in name:
        return 'Овощи'
    if 'йогурт' in name or 'творог' in name or 'кефир' in name or 'сметана' in name or 'молоко' in name or 'сыр' in name or 'масло' in name:
        return 'Молочка'
    if 'колбаса' in name or 'сосиски' in name or 'сардельки' in name or 'карбонад' in name or 'филе' in name or 'куриц' in name or 'фарш' in name or 'говядин' in name or 'свинин' in name or 'индейк' in name:
        return 'Мясо'
    if 'торт' in name or 'пирожн' in name or 'эклеры' in name or 'печенье' in name or 'шоколад' in name or 'конфет' in name or 'вафли' in name or 'зефир' in name:
        return 'Сладости'
    if 'хлеб' in name or 'батон' in name or 'лаваш' in name or 'булочка' in name or 'чиабатта' in name:
        return 'Хлеб'
    if 'рыба' in name or 'форель' in name or 'семга' in name or 'сельдь' in name or 'креветк' in name or 'краб' in name or 'мидии' in name:
        return 'Рыба'
    if 'вода' in name or 'сок' in name or 'лимонад' in name or 'чай' in name or 'кофе' in name or 'напиток' in name or 'морс' in name:
        return 'Напитки'

    # Priority 2: Raw Category Mapping (if available and meaningful)
    if not raw_cat or 'зеленые ценники' in raw_cat or 'зелёные ценники' in raw_cat:
        # If it's just "Green Tags", we rely on the keyword matching above.
        # If no keywords matched (fell through to here), we can return "Другое"
        # but let's see if we can catch more keywords first or just let it fall through.
        pass
    elif 'овощи' in raw_cat: return 'Овощи'
    if 'фрукты' in raw_cat or 'ягоды' in raw_cat: return 'Фрукты'
    if 'мясо' in raw_cat or 'птица' in raw_cat or 'колбас' in raw_cat: return 'Мясо'
    if 'рыба' in raw_cat or 'икра' in raw_cat: return 'Рыба'
    if 'молочн' in raw_cat or 'сыр' in raw_cat: return 'Молочка'
    if 'хлеб' in raw_cat or 'выпечка' in raw_cat: return 'Хлеб'
    if 'сладости' in raw_cat or 'десерт' in raw_cat or 'торты' in raw_cat: return 'Сладости'
    if 'кулинария' in raw_cat or 'готовая' in raw_cat: return 'Готовая еда'
    if 'замороз' in raw_cat or 'мороженое' in raw_cat: return 'Заморозка'
    if 'напитки' in raw_cat or 'воды' in raw_cat: return 'Напитки'
    if 'косметика' in raw_cat or 'гигиена' in raw_cat: return 'Косметика'
    if 'животн' in raw_cat or 'зоо' in raw_cat: return 'Зоотовары'

    # Fallback
    return 'Другое'

def parse_stock(text):
    """
    Extracts stock count from text like "В наличии 5 шт" or "В наличии: 5".
    Returns 99 if valid but no specific number, or 0 if out of stock.
    """
    if not text:
        return 0

    text = text.lower()

    if 'не осталось' in text or 'нет в наличии' in text:
        return 0

    # Match "5 шт", "5шт", ": 5"
    match = re.search(r'(\d+)\s*шт', text)
    if match:
        return int(match.group(1))

    match = re.search(r'наличии[:\s]*(\d+)', text)
    if match:
        return int(match.group(1))

    # If it says "In stock" but no number, assume plenty
    if 'в наличии' in text:
        return 99

    return 0

def clean_price(price_str):
    """Returns clean integer string from price (e.g., '120 ₽' -> '120')"""
    if not price_str:
        return '0'
    clean = re.sub(r'[^\d]', '', str(price_str))
    return clean if clean else '0'

def synthesize_discount(product):
    """
    Synthesizes oldPrice for products that have a currentPrice but no oldPrice.
    Specifically for Green Tags (approx 40% off).
    """
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
