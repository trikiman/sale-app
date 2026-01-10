"""
VkusVill Sale Monitor Configuration
"""
import os

# Telegram Bot Configuration
TELEGRAM_TOKEN = "8395628734:AAGWGAWsQN3RomSrp9UhRD0QLTsqIsX8_44"

# VkusVill URLs
VKUSVILL_BASE_URL = "https://vkusvill.ru"
VKUSVILL_GREEN_PRICES_URL = "https://vkusvill.ru/offers/zelenye-tsenniki.html"

# Polling interval in minutes
POLLING_INTERVAL_MINUTES = 5

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATABASE_PATH = os.path.join(DATA_DIR, "salebot.db")

# Cookie file path
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json") 

# Green pricing section identifier
GREEN_PRICE_SECTION_TEXT = "Зелёные ценники"

# CSS Selectors for scraping
SELECTORS = {
    # Product card selectors
    "product_card": ".ProductCard",
    "product_card_item": ".ProductCard",
    "product_link": ".ProductCard__link",
    "product_price": ".Price__value",
    "product_old_price": ".Price__old",
    
    # Data layer selectors
    "datalayer_price": ".js-datalayer-catalog-list-price",
    "datalayer_price_old": ".js-datalayer-catalog-list-price-old",
    "datalayer_category": ".js-datalayer-catalog-list-category",
    
    # Price display selectors
    "price_label": ".ProductCard__price .Price__value",
    "price_last": ".ProductCard__priceStrike",
    
    # Section selectors
    "green_section": ".js-Delivery__Order-green",
    "section_title": ".VV22_Modal_Forgot__Teasers-title",
    "section_label": ".VV22_Modal_Forgot__Teasers-label",
    
    # Stock selector (appears after adding to cart)
    "stock_count": ".js-delivery__basket--row__maxq",
}

# Category mappings for grouping
CATEGORY_GROUPS = {
    "🥩 МЯСО": ["мясо", "говядин", "свинин", "курин", "индейк", "кролик", "бедро", "филе", "фарш", "котлет", "люля", "стейк", "эскалоп", "ветчин", "колбас", "сосиск", "фрикадел"],
    "🐟 РЫБА": ["рыба", "морепродукт", "креветк", "кальмар", "лосось", "форель", "сельдь", "скумбри", "кета", "дорадо"],
    "🥛 МОЛОЧКА": ["молоч", "йогурт", "кефир", "творог", "сметан", "сыр", "масло сливоч"],
    "🥗 САЛАТЫ": ["салат", "винегрет", "оливье"],
    "🍲 СУПЫ": ["суп", "борщ", "щи", "солянк"],
    "🍳 ГОТОВАЯ ЕДА": ["готов", "курица с", "печень по", "шаурма", "сэндвич", "клаб", "онигири", "заливное", "блин"],
    "🍰 ДЕСЕРТЫ": ["торт", "пирожн", "эклер", "брауни", "десерт", "профитрол", "рулет", "желе"],
    "🥐 ВЫПЕЧКА": ["пирож", "рогалик", "блинчик", "выпечк", "батон", "хлеб"],
    "🥚 ЯЙЦА": ["яйц"],
}
