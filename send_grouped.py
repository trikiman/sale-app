"""
Send green products to Telegram GROUPED by category
"""
import requests
import json
import time
from collections import defaultdict

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = 8436144812

# Category mapping based on product names
CATEGORIES = {
    "🍎 ФРУКТЫ": ["банан", "манго", "мандарин", "апельсин", "яблок", "груша", "киви", "лимон"],
    "🥬 ОВОЩИ": ["морковь", "лук", "картоф", "капуст", "огурц", "помидор", "тыква", "свёкл", "перец"],
    "🥗 САЛАТЫ": ["салат", "мимоза", "оливье", "шуба", "винегрет", "сельдь под"],
    "🥩 МЯСО": ["колбас", "ветчин", "сосиск", "курин", "говяд", "свинин", "индейк", "бедро", "филе"],
    "🥛 МОЛОЧКА": ["йогурт", "кефир", "молоко", "творог", "сметан", "сыр", "масло"],
    "🍞 ВЫПЕЧКА": ["хлеб", "батон", "булк", "круассан", "лаваш"],
    "🍲 ГОТОВАЯ ЕДА": ["суп", "блин", "каша", "пирож", "пицца", "бургер"],
}

def get_category(name):
    """Determine product category"""
    name_lower = name.lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    return "📦 ДРУГОЕ"

def get_stock_emoji(stock, unit):
    """Get emoji based on stock count"""
    try:
        value = float(stock.replace(',', '.'))
    except:
        value = 0
    
    if unit == "кг":
        if value <= 1: return "🔴"
        elif value <= 3: return "🟠"
        elif value <= 5: return "🟡"
        else: return "🟢"
    else:
        if value <= 1: return "🔴"
        elif value <= 3: return "🟠"
        elif value <= 5: return "🟡"
        else: return "🟢"

# Load products
with open("data/green_products.json", "r", encoding="utf-8") as f:
    products = json.load(f)

# Group products by category
grouped = defaultdict(list)
for p in products:
    cat = get_category(p["name"])
    grouped[cat].append(p)

print(f"Sending {len(products)} products in {len(grouped)} categories...")

# Send header
header = f"""🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b>

📦 {len(products)} товаров | -40%
⏰ {time.strftime('%H:%M')} МСК

<i>Сгруппировано по категориям:</i>"""

r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": CHAT_ID,
    "text": header,
    "parse_mode": "HTML",
    "disable_notification": True
})
print(f"Header: {'✅' if r.json().get('ok') else '❌'}")
time.sleep(0.5)

# Send each category as a single message with all products
for cat, cat_products in grouped.items():
    # Build message for this category
    lines = [f"<b>{cat}</b>\n"]
    
    for p in cat_products:
        unit = p.get("unit", "шт")
        emoji = get_stock_emoji(p["stock"], unit)
        lines.append(f"{emoji} {p['name']}")
        lines.append(f"   💰 {p['price']}₽ | 📊 {p['stock']} {unit}")
    
    msg = "\n".join(lines)
    
    r = requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_notification": True
    })
    
    result = r.json()
    status = "✅" if result.get("ok") else "❌"
    print(f"{status} {cat}: {len(cat_products)} products")
    time.sleep(0.3)

print("\n✅ Done! Check Telegram for grouped messages")
