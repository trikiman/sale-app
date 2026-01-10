"""
Send green products to Telegram with images and real stock
"""
import requests
import json
import time

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = 8436144812

# Load products
with open("data/green_products.json", "r", encoding="utf-8") as f:
    products = json.load(f)

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
    else:  # шт
        if value <= 1: return "🔴"
        elif value <= 3: return "🟠"
        elif value <= 5: return "🟡"
        else: return "🟢"

print(f"Sending {len(products)} products to Telegram...")

# Header
header = f"""🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b>

📦 {len(products)} товаров | -40%
⏰ {time.strftime('%H:%M')} МСК

Реальные остатки на складе!"""

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
    unit = p.get("unit", "шт")
    emoji = get_stock_emoji(p["stock"], unit)
    
    caption = (
        f"{emoji} <b>{p['name']}</b>\n"
        f"💰 <b>{p['price']}₽</b> (-40%)\n"
        f"📊 В наличии: {p['stock']} {unit}"
    )
    
    if p.get("image"):
        r = requests.post(f"{BASE_URL}/sendPhoto", json={
            "chat_id": CHAT_ID,
            "photo": p["image"],
            "caption": caption,
            "parse_mode": "HTML",
            "disable_notification": True
        })
        result = r.json()
        if not result.get("ok"):
            # Fallback to text
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
    
    status = "✅" if result.get("ok") else "❌"
    print(f"{i}/{len(products)}: {status} {p['name'][:30]}... [{p['stock']} {unit}]")
    time.sleep(0.3)

print("\n✅ Done! Check Telegram")
