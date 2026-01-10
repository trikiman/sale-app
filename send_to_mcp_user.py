"""
Send products to rustam (MCP user) for verification
"""
import requests
import time

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = 8436144812  # rustam - MCP user

products = [
    {"name": "Банановый кекс с орехом", "price": 155, "old": 258, "stock": 9, "image": "https://img.vkusvill.ru/pim/images/site_MiniWebP/be8bac69-118e-470d-80c1-d686f502024d.webp", "cat": "🍰 ДЕСЕРТЫ"},
    {"name": "Бедро цыпленка, 1.3 кг", "price": 227, "old": 379, "stock": 2, "image": "https://img.vkusvill.ru/pim/images/site_MiniWebP/90fab100-9348-4cd8-9205-78d24bcb91e5.webp", "cat": "🥩 МЯСО"},
    {"name": "Борщ Украинский", "price": 132, "old": 220, "stock": 15, "image": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/dc804839-f372-474d-a716-dd3b6432db47.webp", "cat": "🍲 СУПЫ"},
    {"name": "Форель х/к, 150 г", "price": 300, "old": 500, "stock": 5, "image": "https://img.vkusvill.ru/pim/images/site/site_MiniWebP/845ab3b6-749c-4430-b1cd-675f7276d3d7.webp", "cat": "🐟 РЫБА"},
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
        elif grams <= 3000: w = "🥡"
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
header = "🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b>\n\n📦 4 товара с картинками | -40%"
r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": CHAT_ID,
    "text": header,
    "parse_mode": "HTML",
    "disable_notification": True
})
print(f"Header: {'✅' if r.json().get('ok') else '❌'}")
time.sleep(0.5)

# Products with images
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
    
    status = "✅" if r.json().get("ok") else f"❌ {r.json().get('description', 'error')}"
    print(f"Product {i}: {status}")
    time.sleep(0.3)

print("\n✅ Done!")
