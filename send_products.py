"""
Send green pricing products to Telegram
"""
import requests

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Products extracted from VkusVill
products = [
    {"name": "Ветчина из грудки индейки с паприкой, ~320 г", "price": "205.44", "old": "342.40"},
    {"name": "Буженина варено-копченая из мяса индейки, 350 г", "price": "321", "old": "535"},
    {"name": "Йогурт Братья Чебурашкины безлактозный 2,5%, 200 г", "price": "97", "old": "161"},
    {"name": "Кальмар гигантский филе горячего копчения, 150 г", "price": "234", "old": "390"},
    {"name": "Колбаса вареная Рублевский Докторская нарезка, 190 г", "price": "157", "old": "261"},
    {"name": "Колбаса вареная без яиц", "price": "156", "old": "260"},
    {"name": "Колбаса вареная из курицы и индейки, нарезка", "price": "158", "old": "264"},
    {"name": "Колбаса вареная нарезка, 150 г", "price": "126", "old": "210"},
    {"name": "Колбаса вареная со сливками категории А, нарезка", "price": "130", "old": "216"},
    {"name": "Корм сухой Grandorf для стерилизованных кошек, 2 кг", "price": "2461", "old": "4102"},
    {"name": "Сардельки свиные Ближние Горки, 580 г", "price": "292", "old": "487"},
    {"name": "Филе куриной грудки с перцем и чесноком", "price": "178", "old": "297"},
]

# Get bot info
print("Getting bot info...")
r = requests.get(f"{BASE_URL}/getMe")
print(f"Bot: {r.json()}")

# Get updates to find chat ID
print("\nGetting updates...")
r = requests.get(f"{BASE_URL}/getUpdates")
updates = r.json()
print(f"Updates: {updates}")

chat_id = None
if updates.get("ok") and updates.get("result"):
    for update in updates["result"]:
        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            print(f"\nFound chat_id: {chat_id}")
            break

if not chat_id:
    print("\n❌ No chat found! Please send /start to the bot first:")
    bot_info = requests.get(f"{BASE_URL}/getMe").json()
    if bot_info.get("ok"):
        username = bot_info["result"].get("username")
        print(f"👉 Open Telegram and message: @{username}")
    exit(1)

# Send products
print(f"\n📤 Sending {len(products)} products to chat {chat_id}...")

# Header message
header = f"🟢 <b>Зелёные ценники (-40%)</b>\n\n📦 Найдено {len(products)} товаров:\n"
r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": chat_id,
    "text": header,
    "parse_mode": "HTML"
})
print(f"Header sent: {r.json().get('ok')}")

# Send each product
for i, p in enumerate(products, 1):
    msg = f"🟢 <b>{p['name']}</b>\n💰 <s>{p['old']}₽</s> → <b>{p['price']}₽</b>\n📉 Скидка: <b>-40%</b>"
    r = requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML"
    })
    print(f"Product {i}/{len(products)}: {r.json().get('ok')}")

print("\n✅ Done!")
