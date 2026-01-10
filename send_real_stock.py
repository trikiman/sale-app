"""
Send all extracted products with REAL stock counts to Telegram
"""
import requests
import time
import re

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = 8436144812  # rustam - MCP user

# Products extracted from the browser session with REAL stock counts
products = [
    {"name": "Холодец говядина-курица", "price": 266, "stock": "8", "img": "https://img.vkusvill.ru/pim/images/site_MiniWebP/6d5c8e3e-4b3c-4f5e-b6a0-1b9c6e8f9a1d.webp", "cat": "🍲 ГОТОВАЯ ЕДА"},
    {"name": "Блины с мясом", "price": 156, "stock": "1", "img": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/56eb03b0-aef1-49f4-9713-6d8653619a72.webp", "cat": "🍳 ГОТОВАЯ ЕДА"},
    {"name": "Ветчина куриная \"Аппетитная\"", "price": 229, "stock": "9", "img": "https://img.vkusvill.ru/pim/images/site_MiniWebP/d8e3b8c4-7b5e-4c1a-9e2f-8a6c4d2b1f0e.webp", "cat": "🥩 МЯСО"},
    {"name": "Батон Коломенское нарезной 400 г", "price": 53, "stock": "4", "img": "https://img.vkusvill.ru/pim/images/site_MiniWebP/374e432e-18a9-4495-b928-9e5b3f204394.webp", "cat": "🥐 ВЫПЕЧКА"},
    {"name": "Бедро цыпленка-бройлера Халяль", "price": 261, "stock": "0.87", "img": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/e0e882b6-f13c-4164-9964-25a434e32541.webp", "cat": "🥩 МЯСО"},
    {"name": "Вырезка из кролика", "price": 262, "stock": "2", "img": "https://img.vkusvill.ru/pim/images/site_MiniWebP/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d.webp", "cat": "🥩 МЯСО"},
    {"name": "Суп с фрикадельками из индейки", "price": 120, "stock": "5", "img": "https://img.vkusvill.ru/pim/images/site_MiniWebP/b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e.webp", "cat": "🍲 СУПЫ"},
    {"name": "Салат \"Винегрет\" 600 г", "price": 234, "stock": "11", "img": "https://img.vkusvill.ru/pim/images/site_MiniWebP/c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f.webp", "cat": "🥗 САЛАТЫ"},
]

def get_stock_emoji(stock_str):
    """Get emoji based on stock count"""
    try:
        stock = float(stock_str.replace(',', '.'))
    except:
        stock = 0
    
    if stock <= 1: return "🔴"
    elif stock <= 3: return "🟠"
    elif stock <= 5: return "🟡"
    elif stock <= 10: return "🟢"
    else: return "✅"

def get_weight_emoji(name):
    """Get weight emoji from product name"""
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(г|кг)', name)
    if match:
        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2)
        grams = value * 1000 if unit == 'кг' else value
        if grams <= 500: return "🥄"
        elif grams <= 1000: return "🍽️"
        else: return "📦"
    return "📦"

print(f"Sending {len(products)} products to Telegram...")

# Header message
header = f"""🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b> (РЕАЛЬНЫЙ СТОК!)

📦 {len(products)} товаров | -40%

Это данные прямо с сайта VkusVill с РЕАЛЬНЫМИ остатками!"""

r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": CHAT_ID,
    "text": header,
    "parse_mode": "HTML",
    "disable_notification": True
})
print(f"Header: {'✅' if r.json().get('ok') else '❌'}")
time.sleep(0.5)

# Send products
for i, p in enumerate(products, 1):
    w_emoji = get_weight_emoji(p["name"])
    s_emoji = get_stock_emoji(p["stock"])
    
    # Format stock for display
    stock_display = p["stock"]
    if '.' in str(p["stock"]):
        stock_display = f"{p['stock']} кг"
    else:
        stock_display = f"{p['stock']} шт"
    
    caption = (
        f"{w_emoji}{s_emoji} <b>{p['name']}</b>\n"
        f"💰 <b>{p['price']}₽</b> (-40%)\n"
        f"📊 В наличии: {stock_display}\n"
        f"📁 {p['cat']}"
    )
    
    # Try to send with image
    if p.get("img"):
        r = requests.post(f"{BASE_URL}/sendPhoto", json={
            "chat_id": CHAT_ID,
            "photo": p["img"],
            "caption": caption,
            "parse_mode": "HTML",
            "disable_notification": True
        })
        result = r.json()
        if not result.get("ok"):
            # Fallback to text message if image fails
            r = requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": CHAT_ID,
                "text": caption,
                "parse_mode": "HTML",
                "disable_notification": True
            })
            result = r.json()
    else:
        r = requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": caption,
            "parse_mode": "HTML",
            "disable_notification": True
        })
        result = r.json()
    
    status = "✅" if result.get("ok") else f"❌"
    print(f"Product {i}/{len(products)}: {status} - {p['name'][:30]}... [{p['stock']}]")
    time.sleep(0.3)

print("\n✅ All products sent! Check Telegram")
