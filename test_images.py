"""
Test sending products WITH IMAGES to Telegram
"""
import requests

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
CHAT_ID = 1534916944
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Products with real images from VkusVill
products = [
    {
        "name": "Банановый кекс с орехом",
        "price": 155,
        "old": 258,
        "stock": 9,
        "image": "https://img.vkusvill.ru/pim/images/site_MiniWebP/be8bac69-118e-470d-80c1-d686f502024d.webp?1723493066.0136",
        "cat": "🍰 ДЕСЕРТЫ"
    },
    {
        "name": "Бедро цыпленка бройлера, 1.3 кг",
        "price": 227,
        "old": 379,
        "stock": 2,  # 1.55 kg ~ 2 pieces
        "image": "https://img.vkusvill.ru/pim/images/site_MiniWebP/90fab100-9348-4cd8-9205-78d24bcb91e5.webp?1714734421.0903",
        "cat": "🥩 МЯСО"
    },
    {
        "name": "Борщ Украинский",
        "price": 132,
        "old": 220,
        "stock": 15,
        "image": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/dc804839-f372-474d-a716-dd3b6432db47.webp",
        "cat": "🍲 СУПЫ"
    },
    {
        "name": "Форель радужная х/к ломтики, 150 г",
        "price": 300,
        "old": 500,
        "stock": 5,
        "image": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/845ab3b6-749c-4430-b1cd-675f7276d3d7.webp",
        "cat": "🐟 РЫБА"
    },
]

def get_stock_emoji(stock):
    if stock <= 2: return "🔴"
    elif stock <= 5: return "🟠"
    elif stock <= 10: return "🟡"
    elif stock <= 15: return "🟢"
    else: return "✅"

def get_weight_emoji(name):
    import re
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(г|кг)', name)
    if match:
        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2)
        grams = value * 1000 if unit == 'кг' else value
        if grams <= 500: return "🥄"
        elif grams <= 1000: return "🍽️"
        elif grams <= 3000: return "🥡"
        else: return "📦"
    return "📦"

print("Sending products with images...")

# First send header
header = "🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b>\n\n📦 Примеры товаров с картинками:"
r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": CHAT_ID,
    "text": header,
    "parse_mode": "HTML",
    "disable_notification": True
})
print(f"Header: {r.json().get('ok')}")

# Send each product with its image
for i, p in enumerate(products, 1):
    weight_emoji = get_weight_emoji(p["name"])
    stock_emoji = get_stock_emoji(p["stock"])
    
    caption = (
        f"{weight_emoji}{stock_emoji} <b>{p['name']}</b>\n"
        f"💰 <s>{p['old']}₽</s> → <b>{p['price']}₽</b> (-40%)\n"
        f"📊 В наличии: {p['stock']} шт\n"
        f"📁 {p['cat']}"
    )
    
    # Send photo with caption
    r = requests.post(f"{BASE_URL}/sendPhoto", json={
        "chat_id": CHAT_ID,
        "photo": p["image"],
        "caption": caption,
        "parse_mode": "HTML",
        "disable_notification": True  # Silent
    })
    
    result = r.json()
    if result.get('ok'):
        print(f"Product {i}/{len(products)}: ✅ sent")
    else:
        print(f"Product {i}/{len(products)}: ❌ {result.get('description', 'error')}")

print("\n✅ Done!")
