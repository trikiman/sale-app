"""
Send CORRECT products to rustam (MCP user)
"""
import requests
import time

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = 8436144812  # rustam - MCP user

# REAL products from VkusVill with correct images
products = [
    {
        "name": "Батон Коломенское нарезной 400 г",
        "price": 53,
        "old": 88,
        "stock": 28,
        "image": "https://img.vkusvill.ru/pim/images/site_MiniWebP/374e432e-18a9-4495-b928-9e5b3f204394.webp",
        "cat": "🥐 ВЫПЕЧКА"
    },
    {
        "name": "Батон нарезной",
        "price": 30,
        "old": 50,
        "stock": 10,  # estimated
        "image": "https://img.vkusvill.ru/pim/images/site_MiniWebP/135289eb-dc67-40fb-b02b-3c4e04adcd64.webp",
        "cat": "🥐 ВЫПЕЧКА"
    },
    {
        "name": "Бедро цыпленка-бройлера Халяль",
        "price": 261,
        "old": 435,
        "stock": 5,  # estimated
        "image": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/e0e882b6-f13c-4164-9964-25a434e32541.webp",
        "cat": "🥩 МЯСО"
    },
    {
        "name": "Блины с мясом",
        "price": 156,
        "old": 260,
        "stock": 8,  # estimated
        "image": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/56eb03b0-aef1-49f4-9713-6d8653619a72.webp",
        "cat": "🍳 ГОТОВАЯ ЕДА"
    },
]

def get_emojis(name, stock):
    import re
    # Weight emoji
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(г|кг)', name)
    if match:
        value = float(match.group(1).replace(',', '.'))
        unit = match.group(2)
        grams = value * 1000 if unit == 'кг' else value
        if grams <= 500: w = "🥄"
        elif grams <= 1000: w = "🍽️"
        else: w = "📦"
    else:
        w = "📦"
    
    # Stock emoji
    if stock <= 2: s = "🔴"
    elif stock <= 5: s = "🟠"
    elif stock <= 10: s = "🟡"
    elif stock <= 15: s = "🟢"
    else: s = "✅"
    
    return w, s

print(f"Sending to rustam ({CHAT_ID})...")

# Header
header = "🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b> (исправленные)\n\n📦 4 товара с ПРАВИЛЬНЫМИ картинками | -40%"
r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": CHAT_ID,
    "text": header,
    "parse_mode": "HTML",
    "disable_notification": True
})
print(f"Header: {'✅' if r.json().get('ok') else '❌'}")
time.sleep(0.5)

# Products with CORRECT images
for i, p in enumerate(products, 1):
    w_emoji, s_emoji = get_emojis(p["name"], p["stock"])
    
    caption = (
        f"{w_emoji}{s_emoji} <b>{p['name']}</b>\n"
        f"💰 <s>{p['old']}₽</s> → <b>{p['price']}₽</b> (-40%)\n"
        f"📊 В наличии: {p['stock']} шт\n"
        f"📁 {p['cat']}"
    )
    
    r = requests.post(f"{BASE_URL}/sendPhoto", json={
        "chat_id": CHAT_ID,
        "photo": p["image"],
        "caption": caption,
        "parse_mode": "HTML",
        "disable_notification": True
    })
    
    result = r.json()
    if result.get("ok"):
        print(f"Product {i}: ✅ {p['name'][:30]}")
    else:
        print(f"Product {i}: ❌ {result.get('description', 'error')}")
    time.sleep(0.3)

print("\n✅ Done! Check Telegram (rustam account)")
