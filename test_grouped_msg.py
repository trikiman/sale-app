"""
Test the new grouped message format
"""
import asyncio
import requests

BOT_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"
CHAT_ID = 1534916944
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Products from VkusVill (simplified data from the 76 products)
products_data = [
    # Мясо
    {"name": "Бедро цыпленка бройлера, упаковка от 1.3 кг", "price": 227, "old": 379, "cat": "🥩 МЯСО"},
    {"name": "Бедро цыпленка-бройлера Халяль", "price": 261, "old": 435, "cat": "🥩 МЯСО"},
    {"name": "Ветчина куриная Аппетитная", "price": 229, "old": 382, "cat": "🥩 МЯСО"},
    {"name": "Вырезка из кролика", "price": 262, "old": 436, "cat": "🥩 МЯСО"},
    {"name": "Котлеты из кролика", "price": 289, "old": 482, "cat": "🥩 МЯСО"},
    {"name": "Котлеты из цыпленка с индейкой", "price": 223, "old": 372, "cat": "🥩 МЯСО"},
    {"name": "Стейк Денвер", "price": 580, "old": 966, "cat": "🥩 МЯСО"},
    {"name": "Фарш из говядины и свинины, 360 г", "price": 203, "old": 339, "cat": "🥩 МЯСО"},
    # Рыба  
    {"name": "Дорадо 400/600 горячего копчения, 600 г", "price": 1399, "old": 2332, "cat": "🐟 РЫБА"},
    {"name": "Кета холодного копчения ломтики, 150 г", "price": 256, "old": 427, "cat": "🐟 РЫБА"},
    {"name": "Креветки Королевские подкопченные, 200 г", "price": 277, "old": 462, "cat": "🐟 РЫБА"},
    {"name": "Сельдь тихоокеанская в масле, 230 г", "price": 100, "old": 167, "cat": "🐟 РЫБА"},
    {"name": "Форель радужная х/к ломтики, 150 г", "price": 300, "old": 500, "cat": "🐟 РЫБА"},
    # Салаты
    {"name": "Салат Винегрет, 600 г", "price": 234, "old": 390, "cat": "🥗 САЛАТЫ"},
    {"name": "Салат Оливье с красной рыбой, 500 г", "price": 541, "old": 902, "cat": "🥗 САЛАТЫ"},
    {"name": "Салат из капусты по-грузински", "price": 108, "old": 180, "cat": "🥗 САЛАТЫ"},
    # Супы
    {"name": "Борщ Украинский", "price": 132, "old": 220, "cat": "🍲 СУПЫ"},
    {"name": "Борщ с говядиной", "price": 131, "old": 218, "cat": "🍲 СУПЫ"},
    {"name": "Суп Куриный с домашней лапшой", "price": 120, "old": 200, "cat": "🍲 СУПЫ"},
    {"name": "Щи из свежей капусты постные", "price": 120, "old": 200, "cat": "🍲 СУПЫ"},
    # Готовая еда
    {"name": "Курица с картофельным хашбрауном", "price": 180, "old": 300, "cat": "🍳 ГОТОВАЯ ЕДА"},
    {"name": "Печень по-строгановски с пюре", "price": 192, "old": 320, "cat": "🍳 ГОТОВАЯ ЕДА"},
    {"name": "Шаурма с курицей, 230 г", "price": 192, "old": 320, "cat": "🍳 ГОТОВАЯ ЕДА"},
    {"name": "Онигири со вкусом Спайси", "price": 120, "old": 200, "cat": "🍳 ГОТОВАЯ ЕДА"},
    {"name": "Клаб-сэндвич с курицей и беконом", "price": 150, "old": 250, "cat": "🍳 ГОТОВАЯ ЕДА"},
    # Десерты
    {"name": "Торт Шоколадный вулкан", "price": 600, "old": 1000, "cat": "🍰 ДЕСЕРТЫ"},
    {"name": "Торт Наполеон со сгущенкой", "price": 420, "old": 700, "cat": "🍰 ДЕСЕРТЫ"},
    {"name": "Торт Морковный с пеканом постный", "price": 357, "old": 595, "cat": "🍰 ДЕСЕРТЫ"},
    {"name": "Брауни с черникой", "price": 155, "old": 258, "cat": "🍰 ДЕСЕРТЫ"},
    {"name": "Эклер Классический", "price": 254, "old": 424, "cat": "🍰 ДЕСЕРТЫ"},
    {"name": "Профитроли-мини Крембусики", "price": 136, "old": 227, "cat": "🍰 ДЕСЕРТЫ"},
]

def get_weight_emoji(name):
    """Get weight emoji based on product name"""
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

def get_stock_emoji(stock=10):
    """Get stock emoji - using placeholder for now"""
    if stock <= 2: return "🔴"
    elif stock <= 5: return "🟠"
    elif stock <= 10: return "🟡"
    elif stock <= 15: return "🟢"
    else: return "✅"

# Group products by category
groups = {}
for p in products_data:
    cat = p["cat"]
    if cat not in groups:
        groups[cat] = []
    groups[cat].append(p)

# Build message
lines = [
    f"🟢 <b>ЗЕЛЁНЫЕ ЦЕННИКИ</b>",
    f"📦 {len(products_data)} товаров (примеры) | -40%",
    ""
]

category_order = ["🥩 МЯСО", "🐟 РЫБА", "🥗 САЛАТЫ", "🍲 СУПЫ", "🍳 ГОТОВАЯ ЕДА", "🍰 ДЕСЕРТЫ"]

for cat in category_order:
    if cat in groups:
        prods = groups[cat]
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        lines.append(f"<b>{cat}</b> ({len(prods)})")
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        
        for p in prods[:5]:  # Max 5 per category
            w_emoji = get_weight_emoji(p["name"])
            s_emoji = get_stock_emoji()  # Placeholder
            lines.append(f"{w_emoji}{s_emoji} {p['name']}")
            lines.append(f"    {p['old']}₽ → <b>{p['price']}₽</b> (-40%)")
            lines.append("")
        
        if len(prods) > 5:
            lines.append(f"<i>...и ещё {len(prods) - 5}</i>")
            lines.append("")

message = "\n".join(lines)

# Send to Telegram
print(f"Sending grouped message to chat {CHAT_ID}...")
print(f"Message length: {len(message)} chars")

r = requests.post(f"{BASE_URL}/sendMessage", json={
    "chat_id": CHAT_ID,
    "text": message,
    "parse_mode": "HTML",
    "disable_notification": True  # Silent for regular updates
})

if r.json().get('ok'):
    print("✅ Message sent successfully!")
else:
    print(f"❌ Error: {r.json()}")
